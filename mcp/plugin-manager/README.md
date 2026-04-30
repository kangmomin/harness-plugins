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

## Update checks

The server checks the npm registry once per hour and writes update notices to stderr only, so stdout remains reserved for MCP protocol messages.

Disable update checks with:

```bash
PLUGIN_MANAGER_DISABLE_UPDATE_CHECK=1 plugin-manager-mcp
```
