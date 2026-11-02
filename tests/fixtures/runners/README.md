# Recorded runner fixtures

Captured by the 2026-09-05 audit from actual runners, retained verbatim from
`docs/harness-audit-2026-09-05-evidence.json` (`runner_files`). Only the original
scratch directory was redacted as `$AUDIT_TMP` during that audit.

- Vitest package/CLI 4.1.10: `vitest run --globals --reporter=verbose`.
  Both files use `describe("User") / it("rejects invalid input")`;
  baseline a returns 2, b returns 3; current only a changes to 4.
  Rerun invokes b alone after changing its assertion to pass.
- Jest package 30.2.0 (CLI reports 30.1.3): `jest --runInBand --verbose`.
  The same unchanged test expects 1; implementation returns 2 then 4.

- Playwright 1.64.0 (`@playwright/test`, recorded 2026-11-02, scratch dir redacted as `/repo`):
  `playwright test --reporter=list` (non-TTY) and `--reporter=json` with `PLAYWRIGHT_JSON_OUTPUT_NAME`.
  `list.log`/`report.json`: `retries: 1`, one describe `form` with pass, fail, retry-flaky, two soft errors,
  failing `test.step`, title tag `submit @new`, metadata tag `@smoke`, skip, `test.fail()` expected/unexpected,
  `throw new Error()`, and fail-then-dynamic-skip. `projects-*`: projects `chromium`/`mobile` with the same title.
  `maxfail-*`: `--max-failures=1` (did not run). `import-error-*`: a spec that throws at import.
- Vitest 3.2.7 message-less throws (`throw new Error()`, `new TypeError()`, helper frame):
  `vitest run --reporter=verbose` → `messageless-verbose.log`, `--reporter=json` → `messageless.json`.

Tests consume these logs offline. Updating a supported runner requires recording
new logs and version/command provenance; unit tests never download a runner.
