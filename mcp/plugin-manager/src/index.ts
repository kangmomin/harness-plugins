#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerPluginTools } from "./tools/pluginTools.js";
import { createPluginManager } from "./services/pluginManager.js";
import { startUpdateChecker } from "./services/updateChecker.js";
import { packageName, packageVersion } from "./version.js";

async function main(): Promise<void> {
  const cliHandled = await handleCli(process.argv.slice(2));
  if (cliHandled) {
    return;
  }

  const server = new McpServer({
    name: packageName,
    version: packageVersion
  });

  const manager = await createPluginManager(process.env.HARNESS_PLUGINS_ROOT);
  registerPluginTools(server, manager);
  startUpdateChecker({
    packageName,
    currentVersion: packageVersion,
    intervalMs: 60 * 60 * 1000
  });

  if (process.stdin.isTTY) {
    process.stderr.write(
      `[${packageName}] MCP stdio server is running. It waits for an MCP client on stdin; press Ctrl+C to stop.\n`
    );
  }

  await server.connect(new StdioServerTransport());
}

async function handleCli(args: string[]): Promise<boolean> {
  const command = args[0];

  if (command === "--version" || command === "-v") {
    process.stdout.write(`${packageName} ${packageVersion}\n`);
    return true;
  }

  if (command === "--help" || command === "-h") {
    process.stdout.write(`Usage: ${packageName} [init|--health|--version|--help]

Runs the plugin manager MCP server over stdio.

First-time setup after npm install -g:
  1. Clone the harness plugin repository:

     git clone https://github.com/kangmomin/harness-plugins.git /workspace/harness-plugins

  2. Verify the MCP server can find the repository:

     HARNESS_PLUGINS_ROOT=/workspace/harness-plugins ${packageName} --health

  3. Add this to ~/.config/opencode/opencode.json:

     {
       "$schema": "https://opencode.ai/config.json",
       "mcp": {
         "plugin-manager": {
           "type": "local",
           "command": ["${packageName}"],
           "enabled": true,
           "timeout": 20000,
           "environment": {
             "HARNESS_PLUGINS_ROOT": "/workspace/harness-plugins",
             "OPENCODE_CONFIG_ROOT": "/home/dev/.config/opencode"
           }
         }
       }
     }

Environment:
  HARNESS_PLUGINS_ROOT  Path to the harness-plugins repository.
  OPENCODE_CONFIG_ROOT  OpenCode config root. Defaults to ~/.config/opencode.
  PLUGIN_MANAGER_DISABLE_UPDATE_CHECK=1 disables hourly npm update checks.

Examples:
  HARNESS_PLUGINS_ROOT=/home/dev/mimo-s-harness ${packageName}
  HARNESS_PLUGINS_ROOT=/home/dev/mimo-s-harness ${packageName} --health
  ${packageName} init
`);
    return true;
  }

  if (command === "init" || command === "--init") {
    process.stdout.write(firstTimeSetupGuide());
    return true;
  }

  if (command === "--health") {
    const manager = await createPluginManager(process.env.HARNESS_PLUGINS_ROOT);
    const plugins = await manager.listPlugins();
    process.stdout.write(
      `${JSON.stringify(
        {
          ok: true,
          name: packageName,
          version: packageVersion,
          repoRoot: plugins.repoRoot,
          pluginCount: plugins.plugins.length,
          plugins: plugins.plugins.map((plugin) => plugin.name)
        },
        null,
        2
      )}\n`
    );
    return true;
  }

  if (command) {
    process.stderr.write(`[${packageName}] unknown option: ${command}\n`);
    process.stderr.write(`Run ${packageName} --help for usage.\n`);
    process.exitCode = 2;
    return true;
  }

  return false;
}

function firstTimeSetupGuide(): string {
  return `# plugin-manager-mcp init

This command prints the setup steps. It does not modify files automatically.

## 1. Install the MCP server

If you have not installed it yet:

  npm install -g plugin-manager-mcp

## 2. Clone the harness plugin repository

The npm package only installs the MCP server binary. It does not include the harness plugin repository.

  git clone https://github.com/kangmomin/harness-plugins.git /workspace/harness-plugins

If you already cloned it somewhere else, use that real path instead of /workspace/harness-plugins.

## 3. Health check

  HARNESS_PLUGINS_ROOT=/workspace/harness-plugins plugin-manager-mcp --health

Expected output includes:

  "ok": true
  "plugins": ["be-harness", "fe-harness", "fs-harness", "hyeondongs-harness", "minmos-harness"]

## 4. OpenCode config

Add this to ~/.config/opencode/opencode.json:

{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "plugin-manager": {
      "type": "local",
      "command": ["plugin-manager-mcp"],
      "enabled": true,
      "timeout": 20000,
      "environment": {
        "HARNESS_PLUGINS_ROOT": "/workspace/harness-plugins",
        "OPENCODE_CONFIG_ROOT": "/home/dev/.config/opencode"
      }
    }
  },
  "tools": {
    "plugin-manager_*": true
  }
}

Important:
- Do not put --health in the OpenCode MCP command.
- HARNESS_PLUGINS_ROOT must be the real path inside the same environment where OpenCode runs.
- If OpenCode runs in a container, clone harness-plugins inside that container or mount it there.

## 5. Restart OpenCode and verify

  opencode mcp list

Then ask:

  use plugin-manager_install_minmos_harness

`;
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.stack ?? error.message : String(error);
  process.stderr.write(`[plugin-manager-mcp] fatal: ${message}\n`);
  process.exit(1);
});
