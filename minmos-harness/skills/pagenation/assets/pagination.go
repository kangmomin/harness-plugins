// Package pagination is a bounded, typed keyset reference. Adapt the repository
// and cursor migration explicitly; this wire format is not CloudKit's format.
package pagination

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"regexp"
	"strconv"
	"strings"
)

type Field struct {
	Column string
	Kind   string // int64 or string; non-null, stable sort values only
}

type Term struct {
	Key       string          `json:"key"`
	Direction string          `json:"direction"`
	Value     json.RawMessage `json:"value,omitempty"`
}

type Codec interface {
	Encode([]Term) (string, error)
	Decode(string) ([]Term, error)
}

// SignedJSONCodec authenticates the raw payload before decoding typed values.
// hp1 is a new versioned wire format, never an unsigned CloudKit decode fallback.
type SignedJSONCodec struct{ Secret []byte }

type envelope struct {
	Version int    `json:"version"`
	Terms   []Term `json:"terms"`
}

func (c SignedJSONCodec) sign(payload string) (string, error) {
	if len(c.Secret) == 0 {
		return "", errors.New("cursor secret required")
	}
	mac := hmac.New(sha256.New, c.Secret)
	_, _ = mac.Write([]byte("hp1." + payload))
	return hex.EncodeToString(mac.Sum(nil)), nil
}

func (c SignedJSONCodec) Encode(terms []Term) (string, error) {
	data, err := json.Marshal(envelope{1, terms})
	if err != nil {
		return "", err
	}
	payload := base64.RawURLEncoding.EncodeToString(data)
	signature, err := c.sign(payload)
	if err != nil {
		return "", err
	}
	cursor := "hp1." + payload + "." + signature
	if len(cursor) > 16384 {
		return "", errors.New("cursor exceeds supported size")
	}
	return cursor, nil
}

func (c SignedJSONCodec) Decode(cursor string) ([]Term, error) {
	parts := strings.Split(cursor, ".")
	if len(parts) != 3 || parts[0] != "hp1" || len(cursor) > 16384 {
		return nil, errors.New("unsupported cursor; restart first page")
	}
	expected, err := c.sign(parts[1])
	if err != nil {
		return nil, err
	}
	if !hmac.Equal([]byte(expected), []byte(parts[2])) {
		return nil, errors.New("invalid cursor signature")
	}
	data, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return nil, err
	}
	var value envelope
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.DisallowUnknownFields()
	if err = decoder.Decode(&value); err != nil {
		return nil, err
	}
	if decoder.Decode(new(any)) != io.EOF || value.Version != 1 || len(value.Terms) == 0 {
		return nil, errors.New("invalid cursor shape")
	}
	// Canonical re-encoding rejects duplicate JSON keys, extra whitespace/fields,
	// null roots and ambiguous numeric spellings in the signed envelope.
	canonical, err := json.Marshal(value)
	if err != nil || string(canonical) != string(data) {
		return nil, errors.New("noncanonical cursor shape")
	}
	return value.Terms, nil
}

type Plan struct {
	Terms      []Term
	OrderSQL   string
	WhereSQL   string
	Args       []any
	Limit      int
	FetchLimit int
	FirstPage  bool
	fields     map[string]Field
}

var identifier = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

func column(name string) (string, error) {
	parts := strings.Split(name, ".")
	if len(parts) > 2 {
		return "", errors.New("unsupported column")
	}
	for i, part := range parts {
		if !identifier.MatchString(part) {
			return "", errors.New("invalid configured identifier")
		}
		parts[i] = `"` + part + `"`
	}
	return strings.Join(parts, "."), nil
}

func validateTerms(terms []Term, fields map[string]Field, requireValues bool) error {
	if len(terms) == 0 || len(terms) > len(fields) {
		return errors.New("invalid order count")
	}
	seen := map[string]bool{}
	for _, term := range terms {
		field, exists := fields[term.Key]
		if !exists || seen[term.Key] || (term.Direction != "asc" && term.Direction != "desc") {
			return errors.New("invalid order key/direction")
		}
		seen[term.Key] = true
		if _, err := column(field.Column); err != nil {
			return err
		}
		if field.Kind != "int64" && field.Kind != "string" {
			return errors.New("unsupported sort value type")
		}
		if requireValues {
			if _, err := typedValue(term.Value, field.Kind); err != nil {
				return err
			}
		}
	}
	if !seen["id"] {
		return errors.New("cursor/order missing unique id; restart first page")
	}
	return nil
}

func normalized(order string, fields map[string]Field) ([]Term, error) {
	if order == "" {
		order = "id:desc"
	}
	terms := []Term{}
	hasID := false
	for _, part := range strings.Split(order, "|") {
		pair := strings.Split(part, ":")
		if len(pair) != 2 {
			return nil, errors.New("order syntax must be key:direction|key:direction")
		}
		key, direction := strings.TrimSpace(pair[0]), strings.ToLower(strings.TrimSpace(pair[1]))
		terms = append(terms, Term{Key: key, Direction: direction})
		hasID = hasID || key == "id"
	}
	if !hasID {
		terms = append(terms, Term{Key: "id", Direction: "desc"})
	}
	return terms, validateTerms(terms, fields, false)
}

func typedValue(raw json.RawMessage, kind string) (any, error) {
	if len(raw) == 0 || string(raw) == "null" {
		return nil, errors.New("cursor value missing or null")
	}
	switch kind {
	case "int64":
		value, err := strconv.ParseInt(string(raw), 10, 64)
		return value, err
	case "string":
		var value string
		err := json.Unmarshal(raw, &value)
		return value, err
	}
	return nil, errors.New("unsupported value kind")
}

// Build validates SQL structure even after signature verification. fields is a
// code-owned API-key allowlist, never a request-provided mapping. id must be unique.
func Build(order, cursor string, limit int, fields map[string]Field, codec Codec) (Plan, error) {
	p := Plan{Limit: limit, FetchLimit: limit + 1, FirstPage: cursor == "", fields: fields}
	if limit < 1 || limit > 100 {
		return p, errors.New("limit must be 1..100")
	}
	requested, err := normalized(order, fields)
	if err != nil {
		return p, err
	}
	p.Terms = requested
	if cursor != "" {
		p.Terms, err = codec.Decode(cursor)
		if err != nil {
			return p, err
		}
		if err = validateTerms(p.Terms, fields, true); err != nil {
			return p, err
		}
		if order != "" {
			if len(requested) != len(p.Terms) {
				return p, errors.New("cursor/order mismatch")
			}
			for i := range requested {
				if requested[i].Key != p.Terms[i].Key || requested[i].Direction != p.Terms[i].Direction {
					return p, errors.New("cursor/order mismatch")
				}
			}
		}
	}
	orders, alternatives := []string{}, []string{}
	for i, term := range p.Terms {
		col, _ := column(fields[term.Key].Column)
		orders = append(orders, col+" "+strings.ToUpper(term.Direction))
		if cursor == "" {
			continue
		}
		clauses := []string{}
		for j := 0; j <= i; j++ {
			current := p.Terms[j]
			name, _ := column(fields[current.Key].Column)
			op := "="
			if j == i {
				op = ">"
				if current.Direction == "desc" {
					op = "<"
				}
			}
			clauses = append(clauses, name+" "+op+" ?")
			value, _ := typedValue(current.Value, fields[current.Key].Kind)
			p.Args = append(p.Args, value)
		}
		alternatives = append(alternatives, "("+strings.Join(clauses, " AND ")+")")
	}
	p.OrderSQL = strings.Join(orders, ", ")
	if len(alternatives) > 0 {
		p.WhereSQL = "(" + strings.Join(alternatives, " OR ") + ")"
	}
	return p, nil
}

// Finish consumes limit+1 rows, trims the sentinel, and encodes the last retained
// row using the same normalized order. Last pages have no cursor, even at limit.
func Finish[T any](p Plan, rows []T, value func(T, string) (json.RawMessage, error), codec Codec) ([]T, string, error) {
	if len(rows) <= p.Limit {
		return rows, "", nil
	}
	page := rows[:p.Limit]
	terms := append([]Term(nil), p.Terms...)
	for i := range terms {
		raw, err := value(page[len(page)-1], terms[i].Key)
		if err != nil {
			return nil, "", err
		}
		if _, err = typedValue(raw, p.fields[terms[i].Key].Kind); err != nil {
			return nil, "", fmt.Errorf("encode %s: %w", terms[i].Key, err)
		}
		terms[i].Value = raw
	}
	next, err := codec.Encode(terms)
	return page, next, err
}
