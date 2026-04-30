#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerPluginTools } from "./tools/pluginTools.js";
import { createPluginManager } from "./services/pluginManager.js";

async function main(): Promise<void> {
  const server = new McpServer({
    name: "plugin-manager-mcp",
    version: "0.1.0"
  });

  const manager = await createPluginManager(process.env.HARNESS_PLUGINS_ROOT);
  registerPluginTools(server, manager);

  await server.connect(new StdioServerTransport());
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.stack ?? error.message : String(error);
  process.stderr.write(`[plugin-manager-mcp] fatal: ${message}\n`);
  process.exit(1);
});
