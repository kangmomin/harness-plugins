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
    process.stdout.write(`Usage: ${packageName} [--health|--version|--help]

Runs the plugin manager MCP server over stdio.

Environment:
  HARNESS_PLUGINS_ROOT  Path to the harness-plugins repository.
  PLUGIN_MANAGER_DISABLE_UPDATE_CHECK=1 disables hourly npm update checks.

Examples:
  HARNESS_PLUGINS_ROOT=/home/dev/mimo-s-harness ${packageName}
  HARNESS_PLUGINS_ROOT=/home/dev/mimo-s-harness ${packageName} --health
`);
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

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.stack ?? error.message : String(error);
  process.stderr.write(`[plugin-manager-mcp] fatal: ${message}\n`);
  process.exit(1);
});
