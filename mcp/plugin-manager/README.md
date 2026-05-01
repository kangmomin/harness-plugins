# plugin-manager-mcp

MCP server for deterministic harness plugin management inside the `harness-plugins` repository.

## Install

```bash
npm install -g plugin-manager-mcp
```

## Run

```bash
HARNESS_PLUGINS_ROOT=/path/to/harness-plugins plugin-manager-mcp
```

For a direct readiness check:

```bash
HARNESS_PLUGINS_ROOT=/path/to/harness-plugins plugin-manager-mcp --health
```

The server uses stdio transport and exposes these MCP tools:

- `list_plugins`
- `show_status`
- `update_repo`
- `install_plugin`
- `sync_plugin`
- `sync_all`
- `sync_to_claude`
- `sync_to_opencode`
- `sync_to_codex`

## OpenCode layout

`sync_to_opencode` writes repo-local plugins to:

```text
<harness-plugins>/.opencode/
├── commands/<skill-name>.md
├── skills/<skill-name>/SKILL.md
└── plugins/<plugin-name>/
    ├── agents/
    ├── commands/
    ├── instructions/
    ├── profiles/
    ├── skills/
    └── opencode-plugin.json
```

The sync keeps the harness source as the authority and maps:

- `skills/` to `skills/`
- `agents/` to `agents/`
- `README.md` and other top-level markdown files to `instructions/`
- `PROFILE.md` to `profiles/default.md`
- `OVERRIDES.md` to `profiles/overrides.md`

OpenCode slash commands are thin wrappers that say `Use the <skill-name> skill.` so the original `SKILL.md` remains the source of truth.

Generated OpenCode skill and command names are namespaced as `<plugin-name>__<skill-name>` to avoid collisions across harnesses.

Example:

```text
/minmos-harness__commit-mm
```

## Update checks

The server checks the npm registry once per hour and writes update notices to stderr only, so stdout remains reserved for MCP protocol messages.

Disable update checks with:

```bash
PLUGIN_MANAGER_DISABLE_UPDATE_CHECK=1 plugin-manager-mcp
```
