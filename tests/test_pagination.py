"""Execute the Go reference's SQL against SQLite; no CloudKit/dependency download."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'minmos-harness/skills/pagenation/assets/pagination.go'

CLI = r'''package main
import (
 "context"
 "encoding/json"
 "fmt"
 "os"
 p "fixture/pagination"
)
type VO struct{ ID int64 }
type RepoContract interface { GetAllCursor(context.Context, string, int, string) ([]*VO, int, string, error) }
type Repo struct{}
func (*Repo) GetAllCursor(ctx context.Context, cursor string, limit int, order string) ([]*VO, int, string, error) {
 return nil, 0, "", nil
}
var _ RepoContract = (*Repo)(nil)
func main() {
 var input struct { Mode, Order, Cursor string; Limit int; Rows []map[string]json.RawMessage }
 if err := json.NewDecoder(os.Stdin).Decode(&input); err != nil { panic(err) }
 fields := map[string]p.Field{"id": {Column:"id", Kind:"int64"}, "createdAt": {Column:"created_at", Kind:"int64"}, "score": {Column:"score", Kind:"int64"}, "name": {Column:"name", Kind:"string"}}
 codec := p.SignedJSONCodec{Secret:[]byte("fixture-only-secret")}
 plan, err := p.Build(input.Order, input.Cursor, input.Limit, fields, codec)
 if err != nil { fmt.Fprintln(os.Stderr, err); os.Exit(2) }
 if input.Mode == "finish" {
  rows, cursor, err := p.Finish(plan, input.Rows, func(row map[string]json.RawMessage, key string)(json.RawMessage,error){return row[key],nil}, codec)
  if err != nil { fmt.Fprintln(os.Stderr,err); os.Exit(2) }
  json.NewEncoder(os.Stdout).Encode(map[string]any{"rows":rows,"cursor":cursor})
 } else { json.NewEncoder(os.Stdout).Encode(plan) }
}
'''


class PaginationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('go'):
            if os.environ.get('HARNESS_REQUIRE_GO') == '1':
                raise RuntimeError('Required Go compiler missing')
            raise unittest.SkipTest('Go compiler unavailable')
        cls.temp = tempfile.TemporaryDirectory(prefix='pagination-go-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        (cls.root / 'pagination').mkdir()
        shutil.copyfile(SOURCE, cls.root / 'pagination/pagination.go')
        (cls.root / 'go.mod').write_text('module fixture\n\ngo 1.23\n')
        (cls.root / 'main.go').write_text(CLI)
        cls.binary = cls.root / 'fixture'
        env = dict(os.environ, GOPROXY='off', GOTOOLCHAIN='local', GOWORK='off', GOCACHE=str(cls.root / 'cache'))
        compiled = subprocess.run(['go', 'build', '-o', str(cls.binary), '.'], cwd=cls.root, env=env, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)

    def call(self, **data):
        result = subprocess.run([str(self.binary)], input=json.dumps(data), text=True, capture_output=True)
        return result

    def plan(self, order='', cursor='', limit=2):
        result = self.call(Mode='plan', Order=order, Cursor=cursor, Limit=limit)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def finish(self, rows, order='', cursor='', limit=2):
        result = self.call(Mode='finish', Order=order, Cursor=cursor, Limit=limit, Rows=rows)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def database(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE things(id INTEGER PRIMARY KEY, created_at INTEGER NOT NULL, score INTEGER NOT NULL, name TEXT, status TEXT)')
        for row in [(1,100,5,'A','active'), (2,100,9,'B','active'), (3,100,9,'C','active'),
                    (4,99,5,'D','active'), (5,100,5,'E','removed'), (9007199254740993,99,4,'F','active')]:
            db.execute('INSERT INTO things VALUES(?,?,?,?,?)', row)
        return db

    def pages(self, db, order, limit=2):
        cursor, all_ids, pages = '', [], []
        for _ in range(12):
            plan = self.plan(order, cursor, limit)
            # The real reference predicate must remain grouped below the base filter.
            where = "status = 'active'" + (' AND ' + plan['WhereSQL'] if plan['WhereSQL'] else '')
            records = db.execute('SELECT id,created_at AS createdAt,score,name FROM things WHERE ' + where +
                ' ORDER BY ' + plan['OrderSQL'] + ' LIMIT ?', [*(plan['Args'] or []), plan['FetchLimit']]).fetchall()
            result = self.finish([dict(r) for r in records], order, cursor, limit)
            ids = [r['id'] for r in result['rows']]
            all_ids.extend(ids)
            pages.append(ids)
            cursor = result['cursor']
            if not cursor:
                return all_ids, pages
        self.fail('pagination did not terminate')

    def test_equal_sort_values_mixed_directions_no_missing_duplicate_or_removed_rows(self):
        db = self.database()
        for order, sql in [('createdAt:desc', 'created_at DESC,id DESC'),
                           ('createdAt:asc|score:desc|id:asc', 'created_at ASC,score DESC,id ASC'),
                           ('score:desc|createdAt:desc', 'score DESC,created_at DESC,id DESC'),
                           ('id:asc', 'id ASC')]:
            with self.subTest(order=order):
                actual, pages = self.pages(db, order)
                expected = [r[0] for r in db.execute("SELECT id FROM things WHERE status='active' ORDER BY " + sql)]
                self.assertEqual(actual, expected)
                self.assertEqual(len(actual), len(set(actual)))
                self.assertNotIn(5, actual)
                self.assertLessEqual(len(pages[-1]), 2)

    def test_unique_id_is_in_order_predicate_cursor_and_int64_stays_exact(self):
        plan = self.plan('createdAt:desc')
        self.assertEqual([t['key'] for t in plan['Terms']], ['createdAt', 'id'])
        self.assertTrue(plan['OrderSQL'].endswith('"id" DESC'))
        result = self.finish([{'createdAt':100,'id':9007199254740994}, {'createdAt':100,'id':9007199254740993},
                              {'createdAt':100,'id':9007199254740992}], order='createdAt:desc')
        next_plan = self.plan('createdAt:desc', result['cursor'])
        self.assertEqual(next_plan['Args'][-1], 9007199254740993)
        self.assertIn('"id" < ?', next_plan['WhereSQL'])
        self.assertEqual(next_plan['Terms'][-1]['value'], 9007199254740993)

    def test_exact_limit_final_page_empty_input_and_omitted_order_with_cursor(self):
        records = [{'id':2}, {'id':1}]
        self.assertEqual(self.finish(records)['cursor'], '')
        self.assertEqual(self.finish([])['cursor'], '')
        result = self.finish([{'id':1,'score':9}, {'id':2,'score':8}, {'id':3,'score':7}], order='score:desc|id:asc')
        self.assertEqual(self.plan('', result['cursor'])['OrderSQL'], '"score" DESC, "id" ASC')
        mismatch = self.call(Order='score:asc|id:asc', Cursor=result['cursor'], Limit=2)
        self.assertEqual(mismatch.returncode, 2)
        self.assertIn('mismatch', mismatch.stderr)

    def test_invalid_order_keys_directions_syntax_limits_reject_before_sql(self):
        for order in ['name;DROP TABLE things:asc', 'unknown:asc', 'id:asc;drop', 'id:up', 'id:asc|id:desc',
                      'createdAt:desc,id:asc', 'id', 'id:asc|', 'created_at:asc']:
            with self.subTest(order=order):
                result = self.call(Order=order, Cursor='', Limit=2)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
        for limit in [0, -1, 101]:
            self.assertEqual(self.call(Limit=limit).returncode, 2)

    def test_encoder_never_returns_cursor_that_decoder_rejects_for_size(self):
        rows = [{'id': i, 'name': 'x' * 13000} for i in [3, 2, 1]]
        result = self.call(Mode='finish', Order='name:asc', Limit=2, Rows=rows)
        self.assertEqual(result.returncode, 2)
        self.assertIn('cursor exceeds supported size', result.stderr)
        self.assertEqual(result.stdout, '')

    def signed(self, raw):
        encoded = base64.urlsafe_b64encode(raw.encode()).rstrip(b'=').decode()
        signature = hmac.new(b'fixture-only-secret', ('hp1.' + encoded).encode(), hashlib.sha256).hexdigest()
        return 'hp1.' + encoded + '.' + signature

    def test_even_valid_signature_rejects_legacy_no_id_null_duplicates_missing_values(self):
        examples = ['null', '{"version":1,"terms":[]}', '{"version":1,"terms":null}',
            '{"version":1,"terms":[{"key":"createdAt","direction":"desc","value":100}]}',
            '{"version":1,"terms":[{"key":"id","direction":"desc"}]}',
            '{"version":1,"terms":[{"key":"id","direction":"desc","value":null}]}',
            '{"version":1,"version":1,"terms":[{"key":"id","direction":"desc","value":1}]}',
            '{"version":1,"terms":[{"key":"id","direction":"desc","value":1},{"key":"id","direction":"desc","value":2}]}',
            '{"version":1,"terms":[{"key":"id","direction":"desc","value":1.5}]}']
        for value in examples:
            with self.subTest(value=value):
                result = self.call(Cursor=self.signed(value), Limit=2)
                self.assertEqual(result.returncode, 2, result.stdout)
        valid = self.finish([{'id':3},{'id':2},{'id':1}])['cursor']
        self.assertEqual(self.call(Cursor=valid[:-1] + ('a' if valid[-1] != 'a' else 'b'), Limit=2).returncode, 2)


if __name__ == '__main__':
    unittest.main()
