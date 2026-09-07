#!/usr/bin/env python3
"""Read-only, offline checks of the effective profile's active capabilities."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location('harness_profile', Path(__file__).with_name('profile.py'))
_profile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_profile)
ProfileError, resolve = _profile.ProfileError, _profile.resolve


def diagnose(cwd, domain, host, tools=None):
    root = Path(cwd).resolve()
    resolved = resolve(root, domain)
    values, commands, checks = resolved["values"], resolved["commands"], []

    def row(key, status, detail, required=False):
        checks.append(dict(key=key, status=status, detail=detail, required=required))

    def binary(name, required=True):
        found = shutil.which(name)
        row(name, "OK" if found else "MISSING", found or "not installed; no download attempted", required)

    def package(name):
        present = root / "node_modules" / name / "package.json"
        if present.is_file():
            row("package:" + name, "OK", "installed locally", True)
        elif (root / ".pnp.cjs").exists():
            row("package:" + name, "UNKNOWN", "PnP: verify with the project's existing offline resolver", True)
        else:
            row("package:" + name, "MISSING", "local package absent; no install attempted", True)

    row("profile", "OK" if resolved["profile_source"] == "profile" else "LEGACY" if resolved["profile_source"] == "legacy" else "WARN",
        resolved["profile_source"] + "; modern and legacy files are alternatives")
    row("python", "OK", sys.version.split()[0])
    node_project = domain == "fe" or values.get("preset") == "node"
    if node_project:
        binary("node")
        if shutil.which("node"):
            version = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
            match = re.fullmatch(r"v(\d+)\.\d+\.\d+\S*\s*", version.stdout)
            row("node-version", "OK" if version.returncode == 0 and match and int(match[1]) >= 18 else "UNKNOWN" if not match else "OUTDATED", version.stdout.strip() or "version probe failed", True)
        binary(values.get("packageManager", "npm"))
        row("package.json", "OK" if (root / "package.json").is_file() else "MISSING", "project manifest", True)
    elif values.get("preset") == "go":
        binary("go")

    for key in ("buildCommand", "testCommand", "lintCommand", "typeCheckCommand", "e2eCommand", "runServerCommand"):
        command = commands.get(key, {"value": "", "source": "missing"})
        text = command["value"]
        if not text:
            row(key, "SKIP", command["source"])
            continue
        try:
            tokens = shlex.split(text)
        except ValueError:
            row(key, "INVALID", "shell quoting is incomplete", True)
            continue
        # Do not execute project scripts or shell substitutions during diagnosis.
        if re.search(r"[|&;<>`$()\n]", text) or not tokens or "=" in tokens[0]:
            row(key, "UNVERIFIED", "custom shell command; syntax/execution needs the requested validation step", True)
            continue
        executable = root / tokens[0] if "/" in tokens[0] else shutil.which(tokens[0])
        exists = executable is not None and os.access(executable, os.X_OK)
        row(key, "AVAILABLE" if exists else "MISSING", command["source"] + "; executable presence only, not a successful validation", True)

    if domain == "fe":
        framework = values.get("framework")
        deps = {"nextjs": ("next", "react"), "vite": ("vite", "react"), "cra": ("react-scripts", "react"), "nuxt": ("nuxt", "vue")}
        if framework in deps:
            for name in deps[framework]:
                package(name)
        else:
            row("framework", "UNKNOWN", "inspect existing framework before generating files", True)
        if values.get("typescript") is False:
            row("typescript", "SKIP", "typescript:false")
        elif values.get("typescript") is True:
            package("typescript")
            row("tsconfig", "OK" if (root / "tsconfig.json").is_file() else "MISSING", "selected TypeScript project", True)
        else:
            row("typescript", "UNKNOWN", "language setting not resolved", True)
        unit = values.get("testRunner")
        if unit:
            package(unit)
        else:
            row("testRunner", "UNKNOWN", "choose/resolve the existing unit runner", True)
        e2e = values.get("e2eRunner")
        if e2e == "none":
            row("e2eRunner", "SKIP", "e2eRunner:none")
        elif e2e == "cypress":
            package("cypress")
            row("cypress-binary", "UNVERIFIED", "package presence does not prove the Cypress binary is installed")
        elif e2e == "playwright":
            package("@playwright/test")
            row("playwright-browsers", "UNVERIFIED", "probe browser executable paths with the installed package API; do not run install")
        else:
            row("e2eRunner", "UNKNOWN", "runner not resolved")
        if values.get("storybook"):
            row("storybook", "OK" if (root / ".storybook").is_dir() else "UNVERIFIED", "selected Storybook configuration")
        else:
            row("storybook", "SKIP", "not selected")

    if values.get("codexMode") == "none":
        row("codex", "SKIP", "codexMode:none; no provider or delegation checks")
    elif host == "codex":
        row("codex", "NATIVE", "current host; delegation MCP is not required for native collaboration")
    elif host == "claude":
        # The orchestrator supplies names from current session tool metadata, never a cached suffix.
        available = [t for t in tools or [] if isinstance(t, dict) and t.get("capability") == "codex-delegation" and isinstance(t.get("name"), str) and t["name"]]
        row("codex", "DISCOVERED" if available else "WARN", ", ".join(t["name"] for t in available) if available else "delegation capability not discovered; use the documented host fallback")
    else:
        row("host", "UNKNOWN", "pass the actual current host; do not infer a successful tool load")
    failures = {"MISSING", "INVALID", "OUTDATED", "UNKNOWN"}
    status = "ISSUES_FOUND" if any(c["required"] and c["status"] in failures for c in checks) else "CHECKS_INCOMPLETE" if any(c["status"] in {"UNKNOWN", "UNVERIFIED", "WARN"} for c in checks) else "AVAILABLE"
    return dict(status=status, host=host, downloads="none", validation_executed=False, profile=resolved, checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--domain", choices=("be", "fe"), required=True)
    parser.add_argument("--host", choices=("claude", "codex", "unknown"), required=True)
    parser.add_argument("--tools-file", help="JSON metadata list from current session, capability + actual tool name")
    args = parser.parse_args()
    try:
        tools = json.loads(Path(args.tools_file).read_text()) if args.tools_file else []
        if not isinstance(tools, list):
            raise ProfileError("INVALID_TOOLS_METADATA")
        print(json.dumps(diagnose(args.cwd, args.domain, args.host, tools), ensure_ascii=False))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps(dict(status="BLOCKED", error=str(exc))), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
