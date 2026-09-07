#!/usr/bin/env python3
"""Bounded harness frontmatter reader/editor. No YAML execution or shell commands."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile


class ProfileError(ValueError):
    pass


ENUMS = {
    "language": ("ko", "en"), "codexMode": ("none", "mix", "max"),
    "testRunner": ("vitest", "jest"), "e2eRunner": ("playwright", "cypress", "none"),
    "packageManager": ("pnpm", "yarn", "npm", "bun"),
    "componentPattern": ("feature-based", "atomic", "flat"),
}
STRINGS = set("buildCommand testCommand lintCommand typeCheckCommand runServerCommand serverUrl "
              "e2eLockDir reportDir mainBranch featureBranchPrefix hotfixBranchPrefix commitCoAuthor".split())
ARRAYS = set("sourceDirs testDirs commitPrefixes projectConventions".split())
SLOTS = ("review", "explore", "judge", "write")
EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max", "ultra", "tiered")
COMMON = dict(language="ko", codexMode="mix", reportDir=".claude/harness-reports",
              e2eLockDir="", projectConventions=["CLAUDE.md"])
PRESETS = {
    "go": dict(buildCommand="go build ./...", testCommand="go test ./...", lintCommand="go vet ./...",
               typeCheckCommand="", makeTestCommand="", runServerCommand="", serverUrl="http://localhost:8080",
               sourceDirs=["internal/", "cmd/", "pkg/"], testDirs=["internal/", "pkg/"]),
    "node": dict(buildCommand="npm run build", testCommand="npm test", lintCommand="npm run lint",
                 typeCheckCommand="npm run typecheck", makeTestCommand="", runServerCommand="npm run dev",
                 serverUrl="http://localhost:3000", sourceDirs=["src/"], testDirs=["src/", "tests/", "__tests__/"]),
}
ROOT = re.compile(r"^([A-Za-z0-9_-]+):(?=\s|$)")
DELIM = re.compile(r"^---[ \t]*$")


def schema(domain):
    result = {k: "string" for k in STRINGS}
    result.update({k: "array" for k in ARRAYS})
    result.update(language=ENUMS["language"], codexMode=ENUMS["codexMode"], codexModels="block")
    if domain == "be":
        result.update(preset=("go", "node", "custom"), e2eEnabled="bool", makeTestCommand="string", apiDocsPath="string")
    elif domain == "fe":
        result.update(ENUMS)
        result.update(preset=("node",), typescript="bool", storybook="bool", framework="string",
                      uiLibrary="string", stateManagement="string", e2eCommand="string")
    else:
        raise ProfileError("INVALID_DOMAIN")
    return result


def json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileError("DUPLICATE_KEY: " + key)
        result[key] = value
    return result


def split_flow(value):
    """Split a single flow level; quote-aware, no nested containers."""
    pieces, start, quote, i, node_start = [], 0, None, 0, True
    while i < len(value):
        c = value[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 1
            elif c == quote:
                if quote == "'" and i + 1 < len(value) and value[i + 1] == "'":
                    i += 1
                else:
                    quote = None
        elif c in "\"'" and node_start:
            quote = c
            node_start = False
        elif c in "[]{}":
            raise ProfileError("UNSUPPORTED_LAYOUT: nested flow")
        elif c == ",":
            pieces.append(value[start:i].strip())
            start = i + 1
            node_start = True
        elif c == ":" and i + 1 < len(value) and value[i + 1].isspace():
            node_start = True
        elif not c.isspace():
            node_start = False
        i += 1
    if quote:
        raise ProfileError("UNSUPPORTED_LAYOUT: unterminated quote")
    tail = value[start:].strip()
    if tail:
        pieces.append(tail)
    if any(not p for p in pieces):
        raise ProfileError("INVALID_VALUE: empty flow entry")
    return pieces


def scalar(value):
    if not value or value.lower() in ("null", "~"):
        return None
    if value.startswith('"'):
        try:
            result = json.loads(value)
        except ValueError as exc:
            raise ProfileError("UNSUPPORTED_LAYOUT: double-quoted scalar (JSON escapes only)") from exc
        if not isinstance(result, str):
            raise ProfileError("UNSUPPORTED_LAYOUT: scalar")
        return result
    if value.startswith("'"):
        if not re.fullmatch(r"'(?:[^']|'')*'", value):
            raise ProfileError("UNSUPPORTED_LAYOUT: single-quoted scalar")
        return value[1:-1].replace("''", "'")
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"[-+]?(?:\d[\d_]*(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", value):
        return float(value.replace("_", ""))
    if value[0] in "|>&*!%@`[{" or re.search(r":(?:\s|$)", value) or re.match(r"[-?:](?:\s|$)", value):
        raise ProfileError("UNSUPPORTED_LAYOUT: scalar")
    # YAML 1.1 booleans/dates/hex differ between consumers. Require quoting them.
    if value.lower() in ("yes", "no", "on", "off", ".nan", ".inf", "-.inf", "+.inf") or re.match(r"[-+]?0[xob]|\d{4}-\d\d-\d\d", value, re.I):
        raise ProfileError("UNSUPPORTED_LAYOUT: ambiguous YAML scalar; quote it")
    return value


def lex(line, prefix):
    """Return unchanged prefix/separator, scalar lexeme, suffix/comment, EOL."""
    eol = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    text = line[:-len(eol)] if eol else line
    rest = text[len(prefix):]
    quote, comment, i, node_start, depth = None, len(rest), 0, True, 0
    while i < len(rest):
        c = rest[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 1
            elif c == quote:
                if quote == "'" and i + 1 < len(rest) and rest[i + 1] == "'":
                    i += 1
                else:
                    quote = None
        elif c in "\"'" and node_start:
            quote = c
            node_start = False
        elif c == "#" and (i == 0 or rest[i - 1].isspace()):
            comment = i
            break
        elif c in "[{" and node_start:
            depth += 1
            node_start = True
        elif depth and c in "]}":
            depth -= 1
            node_start = False
        elif depth and (c == "," or c == ":" and i + 1 < len(rest) and rest[i + 1].isspace()):
            node_start = True
        elif not c.isspace():
            node_start = False
        i += 1
    content = rest[:comment]
    left = len(content) - len(content.lstrip(" \t"))
    value = content.strip(" \t")
    if value:
        return prefix + content[:left], value, content[left + len(value):] + rest[comment:], eol
    return prefix, "", rest, eol


def render_lex(parts, value):
    prefix, old, suffix, eol = parts
    if not old:
        # Existing whitespace belongs to the comment when inserting a value.
        return prefix + ("" if prefix.endswith((" ", "\t")) else " ") + value + suffix + eol
    return prefix + value + suffix + eol


def encode(value, old=""):
    if isinstance(value, str) and old.startswith("'"):
        return "'" + value.replace("'", "''") + "'"
    return json.dumps(value, ensure_ascii=False)


def validate_slot(slot, value):
    if slot not in SLOTS or not isinstance(value, dict) or set(value) - {"provider", "model", "effort"}:
        raise ProfileError("INVALID_SLOT: " + slot)
    for key, pattern in (("provider", r"[A-Za-z0-9_-]+"), ("model", r"[A-Za-z0-9._:/-]+")):
        v = value.get(key)
        if not isinstance(v, str) or not re.fullmatch(pattern, v) or scalar(v) != v:
            raise ProfileError("INVALID_SLOT: " + slot + "." + key)
    if "effort" in value and (value["effort"] not in EFFORTS or value["effort"] == "tiered" and slot != "review"):
        raise ProfileError("INVALID_SLOT: " + slot + ".effort")


def validate(key, value, domain, patch=False):
    kind = schema(domain).get(key)
    if kind is None:
        raise ProfileError("UNKNOWN_KEY: " + key)
    if kind == "block":
        if not isinstance(value, dict):
            raise ProfileError("INVALID_VALUE: " + key)
        for slot, record in value.items():
            if patch and record is None and slot in SLOTS:
                continue
            validate_slot(slot, record)
        return
    valid = (isinstance(value, str) if kind == "string" else type(value) is bool if kind == "bool" else
             isinstance(value, list) and all(isinstance(v, str) for v in value) if kind == "array" else
             isinstance(value, str) and value in kind)
    if not valid or isinstance(value, str) and any(ord(c) < 32 for c in value):
        raise ProfileError("INVALID_VALUE: " + key)
    if isinstance(value, list) and any(any(ord(c) < 32 for c in v) for v in value):
        raise ProfileError("INVALID_VALUE: " + key)


class Document:
    def __init__(self, data):
        self.lines = re.findall(r"[^\n]*\n|[^\n]+$", data.decode("utf-8"))
        if not self.lines or not self.lines[0].endswith("\n") or not DELIM.fullmatch(self.lines[0].rstrip("\r\n")):
            raise ProfileError("INVALID_PROFILE: opening delimiter")
        self.end = next((i for i in range(1, len(self.lines)) if DELIM.fullmatch(self.lines[i].rstrip("\r\n"))), None)
        if self.end is None:
            raise ProfileError("INVALID_PROFILE: closing delimiter")
        self.roots, self.placeholders = {}, {}
        for i in range(1, self.end):
            line = self.lines[i]
            root = ROOT.match(line)
            if root:
                if root[1] in self.roots:
                    raise ProfileError("DUPLICATE_KEY: " + root[1])
                self.roots[root[1]] = i
            elif line.startswith("# ") and ROOT.match(line[2:]):
                self.placeholders.setdefault(ROOT.match(line[2:])[1], i)
            elif line.strip() and not line.lstrip().startswith("#") and not self.roots:
                raise ProfileError("UNSUPPORTED_LAYOUT: orphan child line " + str(i + 1))
            elif line.strip() and not line.startswith((" ", "\t", "#")):
                raise ProfileError("UNSUPPORTED_LAYOUT: root line " + str(i + 1))

    def block(self, key):
        placeholder = key not in self.roots
        i = self.placeholders.get(key) if placeholder else self.roots[key]
        if i is None:
            return None
        line = self.lines[i][2:] if placeholder else self.lines[i]
        parts = lex(line, key + ":")
        children, gap = [], False
        if not placeholder:
            stop = min([v for v in self.roots.values() if v > i] + [self.end])
            for j in range(i + 1, stop):
                child = self.lines[j]
                if not child.strip() or child.lstrip().startswith("#"):
                    gap = True
                elif child.startswith((" ", "\t")):
                    if gap or child.startswith("\t"):
                        raise ProfileError("UNSUPPORTED_LAYOUT: separated children: " + key)
                    children.append(j)
                else:
                    raise ProfileError("UNSUPPORTED_LAYOUT: " + key)
        return i, parts, children, placeholder

    def value(self, key, domain):
        block = self.block(key)
        if block is None:
            return None
        _, parts, children, _ = block
        raw, kind = parts[1], schema(domain).get(key)
        if kind == "block":
            if raw:
                raise ProfileError("UNSUPPORTED_LAYOUT: codexModels must be a block")
            pairs = []
            for j in children:
                match = re.match(r"^( +)([A-Za-z0-9_-]+):(?=\s|$)", self.lines[j])
                if not match:
                    raise ProfileError("UNSUPPORTED_LAYOUT: slot child")
                flow = lex(self.lines[j], match[0])[1]
                if not (flow.startswith("{") and flow.endswith("}")):
                    raise ProfileError("UNSUPPORTED_LAYOUT: slot flow")
                fields = []
                for item in split_flow(flow[1:-1]):
                    field = re.fullmatch(r"([a-z]+):\s*(.+)", item)
                    if not field:
                        raise ProfileError("INVALID_SLOT: field")
                    fields.append((field[1], scalar(field[2])))
                pairs.append((match[2], json_object(fields)))
            return json_object(pairs)
        if kind == "array":
            if raw.startswith("[") and raw.endswith("]") and not children:
                return [scalar(item) for item in split_flow(raw[1:-1])]
            if not raw and children:
                values = []
                for j in children:
                    match = re.match(r"^ +-\s+", self.lines[j])
                    if not match:
                        raise ProfileError("UNSUPPORTED_LAYOUT: sequence")
                    values.append(scalar(lex(self.lines[j], match[0])[1]))
                return values
            raise ProfileError("UNSUPPORTED_LAYOUT: array " + key)
        if children:
            raise ProfileError("UNSUPPORTED_LAYOUT: scalar children " + key)
        return scalar(raw)

    def edit(self, changes, domain):
        if not isinstance(changes, dict):
            raise ProfileError("INVALID_VALUE: changes must be an object")
        replacements, expected = [], {}
        for key, value in changes.items():
            validate(key, value, domain, patch=True)
            kind, block = schema(domain)[key], self.block(key)
            old = self.value(key, domain) if block else None
            if kind == "block":
                if old is not None:
                    validate(key, old, domain)
                merged = dict(old or {})
                for slot, record in value.items():
                    if record is None:
                        merged.pop(slot, None)
                    else:
                        merged[slot] = record
                value = merged
            expected[key] = value
            if key in self.roots and old == value or kind == "block" and not old and not value:
                continue
            if block:
                i, parts, children, _ = block
            else:
                i, children = self.end, []
                eol = "\r\n" if self.lines[self.end].endswith("\r\n") else "\n" if self.lines[self.end].endswith("\n") else "\r\n" if self.lines[0].endswith("\r\n") else "\n"
                parts = (key + ":", "", "", eol)
            eol = parts[3]
            rendered = []
            if kind == "block" or kind == "array" and children:
                old_children = {}
                for n, j in enumerate(children):
                    match = re.match(r"^ +([A-Za-z0-9_-]+):", self.lines[j]) if kind == "block" else re.match(r"^ +-\s*", self.lines[j])
                    child_key = match[1] if kind == "block" else n
                    old_children[child_key] = lex(self.lines[j], match[0])
                items = value.items() if kind == "block" else enumerate(value)
                exemplar = next(reversed(old_children.values()))[0] if old_children else "  - "
                indent = re.match(r"^ +", exemplar)[0]
                separator = re.search(r"[ \t]*$", exemplar)[0] or " "
                for child_key, child_value in items:
                    default_prefix = indent + (str(child_key) + ":" if kind == "block" else "-") + separator
                    child_parts = old_children.pop(child_key, (default_prefix, "", "", eol))
                    previous = (old or {}).get(child_key) if kind == "block" else old[child_key] if old and child_key < len(old) else None
                    if previous == child_value and child_parts[1]:
                        rendered.append("".join(child_parts))
                        continue
                    child_raw = "{ " + ", ".join(k + ": " + child_value[k] for k in ("provider", "model", "effort") if k in child_value) + " }" if kind == "block" else encode(child_value, child_parts[1])
                    rendered.append(render_lex(child_parts, child_raw))
                if any("#" in p[2] for p in old_children.values()) or kind == "block" and not value and "#" in parts[2]:
                    raise ProfileError("UNSUPPORTED_LAYOUT: deleting a commented line: " + key)
                if value:
                    rendered.insert(0, "".join(parts) if block else key + ":" + eol)
                elif kind == "array":
                    rendered = [render_lex(parts, "[]")]
            else:
                raw = value if isinstance(kind, tuple) and not parts[1].startswith(("'", '"')) else encode(value, parts[1])
                rendered = [render_lex(parts, raw)]
            replacements.append((i, children[-1] + 1 if children else i + bool(block), rendered))
        lines = self.lines[:]
        for start, stop, rendered in sorted(replacements, key=lambda r: r[0], reverse=True):
            lines[start:stop] = rendered
        result = "".join(lines).encode("utf-8")
        parsed = Document(result)
        for key, value in expected.items():
            if parsed.value(key, domain) != value and not (key == "codexModels" and not value and key not in parsed.roots):
                raise ProfileError("INVALID_RENDER: " + key)
        return result


def resolve(cwd, domain):
    cwd = Path(cwd)
    profile = cwd / ".claude" / (domain + "-harness.local.md")
    values, sources, diagnostics = {}, {}, []
    source = "missing"
    try:
        data = profile.read_bytes()
    except FileNotFoundError:
        data = None
        if profile.is_symlink():
            raise ProfileError("INVALID_PROFILE: dangling symlink")
    if data is not None:
        doc, source = Document(data), "profile"
        for key in doc.roots:
            if key not in schema(domain):
                diagnostics.append("UNKNOWN_KEY: " + key)
                continue
            try:
                value = doc.value(key, domain)
                if key == "codexModels":
                    valid = {}
                    for slot, record in value.items():
                        try:
                            validate_slot(slot, record)
                            valid[slot] = record
                        except ProfileError as exc:
                            diagnostics.append(str(exc) + "; use this slot's codex-mode default")
                    value = valid
                else:
                    validate(key, value, domain)
            except ProfileError as exc:
                if key != "codexModels":
                    raise
                diagnostics.append(str(exc) + "; use codex-mode slot defaults")
                continue
            values[key], sources[key] = value, source
    elif domain == "fe":
        legacy_path = cwd / ".hyeondong-config.json"
        try:
            legacy = json.loads(legacy_path.read_text(), object_pairs_hook=json_object)
        except FileNotFoundError:
            legacy = None
            if legacy_path.is_symlink():
                raise ProfileError("INVALID_PROFILE: dangling legacy symlink")
        else:
            if not isinstance(legacy, dict):
                raise ProfileError("INVALID_PROFILE: legacy root")
            source = "legacy"
        if legacy is not None:
            keys = "framework uiLibrary stateManagement testRunner e2eRunner packageManager componentPattern typescript storybook".split()
            for key in keys:
                if key in legacy:
                    validate(key, legacy[key], domain)
                    values[key], sources[key] = legacy[key], "legacy"
            if "conventions" in legacy:
                conventions = legacy["conventions"]
                if not isinstance(conventions, list) or any(not isinstance(c, dict) for c in conventions):
                    raise ProfileError("INVALID_PROFILE: legacy conventions")
                paths = [c.get("path") for c in conventions if c.get("source") == "project"]
                validate("projectConventions", paths, domain)
                values["projectConventions"], sources["projectConventions"] = paths, "legacy"
    def defaults(items, origin):
        for key, value in items.items():
            if key not in values:
                values[key], sources[key] = value, origin
    defaults(COMMON, "default")
    if domain == "be":
        defaults({"e2eEnabled": True}, "default")
        if "preset" not in values:
            if (cwd / "go.mod").is_file():
                defaults({"preset": "go"}, "detected:go.mod")
            elif (cwd / "package.json").is_file():
                defaults({"preset": "node"}, "detected:package.json")
        defaults(PRESETS.get(values.get("preset"), {}), "preset:" + values.get("preset", "missing"))
    else:
        try:
            package = json.loads((cwd / "package.json").read_text(), object_pairs_hook=json_object)
        except FileNotFoundError:
            package = {}
        if not isinstance(package, dict) or not isinstance(package.get("scripts", {}), dict):
            raise ProfileError("INVALID_PROFILE: package scripts")
        if "packageManager" not in values:
            managers = {pm for name, pm in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("package-lock.json", "npm"), ("bun.lock", "bun"), ("bun.lockb", "bun")) if (cwd / name).exists()}
            if len(managers) > 1:
                raise ProfileError("AMBIGUOUS_PACKAGE_MANAGER: set packageManager")
            defaults({"packageManager": next(iter(managers), "npm")}, "lockfile" if managers else "default")
        pm = values["packageManager"]
        for key, script in dict(buildCommand="build", testCommand="test", lintCommand="lint", typeCheckCommand="typecheck", e2eCommand="e2e", runServerCommand="dev").items():
            if script in package.get("scripts", {}):
                defaults({key: pm + " run " + script}, "package.scripts." + script)
    # Keep explicit empty settings in values; runtime fallbacks are separately attributed.
    commands = {k: {"value": v, "source": sources[k]} for k, v in values.items() if k.endswith("Command")}
    if domain == "fe":
        # Execute only the project's installed runner; package-manager exec may download.
        runner_exec = lambda runner: shlex.quote(str(cwd.resolve() / "node_modules" / ".bin" / runner))
        for key, runner_key, suffix in (("testCommand", "testRunner", " run" if values.get("testRunner") == "vitest" else ""), ("e2eCommand", "e2eRunner", " test" if values.get("e2eRunner") == "playwright" else " run")):
            runner = values.get(runner_key)
            if runner == "none":
                commands[key] = {"value": "", "source": runner_key + ":none"}
            elif runner and not values.get(key):
                commands[key] = {"value": runner_exec(runner) + suffix, "source": "runner:" + runner}
        if values.get("typescript") is False:
            commands["typeCheckCommand"] = {"value": "", "source": "typescript:false"}
        if not values.get("lintCommand") and (cwd / "node_modules/.bin/eslint").is_file():
            commands["lintCommand"] = {"value": runner_exec("eslint") + " . --format=stylish", "source": "runner:eslint"}
    if source == "missing":
        diagnostics.append("NO_PROFILE: defaults/detection only; init creates the writable profile")
    return dict(values=values, sources=sources, commands=commands, diagnostics=diagnostics,
                profile_source=source, profile_path=str(profile), writable=source == "profile")


def apply(path, original, rendered, expected_sha):
    if hashlib.sha256(original).hexdigest() != expected_sha:
        raise ProfileError("STALE_PROFILE: expected hash differs")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    tmp = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = os.fstat(fd)
        current = os.stat(path, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino) or Path(path).read_bytes() != original:
            raise ProfileError("STALE_PROFILE: changed since read")
        if rendered == original:
            return False
        tmp_fd, tmp = tempfile.mkstemp(prefix=".profile-", dir=Path(path).parent)
        with os.fdopen(tmp_fd, "wb") as out:
            out.write(rendered)
            out.flush()
            os.fchown(out.fileno(), before.st_uid, before.st_gid)
            os.fchmod(out.fileno(), stat.S_IMODE(before.st_mode))
            os.fsync(out.fileno())
        current = os.stat(path, follow_symlinks=False)
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino) or Path(path).read_bytes() != original:
            raise ProfileError("STALE_PROFILE: changed before publication")
        os.replace(tmp, path)
        tmp = None
        return True
    finally:
        if tmp:
            os.unlink(tmp)
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("resolve", "edit", "schema", "run"))
    parser.add_argument("--domain", choices=("be", "fe"), required=True)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--changes", default="-", help="Typed JSON object file; - reads stdin")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--key", choices=("lintCommand", "typeCheckCommand", "buildCommand", "testCommand", "e2eCommand"))
    parser.add_argument("--fix", action="store_true", help="Only the built-in ESLint fallback supports this transformation")
    args = parser.parse_args()
    try:
        if args.action == "schema":
            result = schema(args.domain)
        elif args.action == "resolve":
            result = resolve(args.cwd, args.domain)
        elif args.action == "run":
            if not args.key:
                raise ProfileError("INVALID_VALUE: run requires --key")
            selected = resolve(args.cwd, args.domain)["commands"].get(args.key, {"value": "", "source": "missing"})
            command = selected["value"]
            if args.fix:
                if args.key != "lintCommand" or selected["source"] != "runner:eslint":
                    raise ProfileError("UNSUPPORTED_COMMAND_TRANSFORMATION: preserve the configured command")
                command += " --fix"
            if not command:
                result = dict(status="SKIPPED", key=args.key, source=selected["source"])
            else:
                # This action is explicit execution of the user's trusted project command.
                code = subprocess.run(["bash", "-c", command], cwd=args.cwd).returncode
                print(json.dumps(dict(status="PASS" if code == 0 else "FAIL", key=args.key, source=selected["source"], exit_code=code)))
                return 0 if code == 0 else 1
        else:
            path = Path(args.cwd) / ".claude" / (args.domain + "-harness.local.md")
            if path.is_symlink():
                raise ProfileError("UNSUPPORTED_LAYOUT: profile symlink is read-only")
            original = path.read_bytes()
            raw = sys.stdin.read() if args.changes == "-" else Path(args.changes).read_text()
            changes = json.loads(raw, object_pairs_hook=json_object)
            rendered = Document(original).edit(changes, args.domain)
            digest = hashlib.sha256(original).hexdigest()
            changed = apply(path, original, rendered, args.expected_sha256) if args.apply else original != rendered
            result = dict(status="DONE" if args.apply else "PREVIEW", changed=changed, sha256_before=digest,
                          sha256_after=hashlib.sha256(rendered).hexdigest())
            if not args.apply:
                result["preview"] = rendered.decode("utf-8")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps(dict(status="BLOCKED", error=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
