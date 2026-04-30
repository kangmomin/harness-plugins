import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { PluginManager } from "../services/pluginManager.js";
import { McpError, UserFacingError } from "../utils/errors.js";

const targetSchema = z.enum(["claude", "opencode", "codex"]);

const pluginNameSchema = z
  .string()
  .min(1)
  .max(120)
  .regex(/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/, "Plugin names may contain letters, numbers, dots, underscores, and hyphens.");

const mutationOptionsSchema = {
  dryRun: z.boolean().optional().default(false),
  overwrite: z.boolean().optional().default(false)
};

function jsonResult(value: unknown) {
  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(value, null, 2)
      }
    ]
  };
}

function exposeError(error: unknown): never {
  if (error instanceof UserFacingError) {
    throw new McpError(error.message);
  }
  throw error;
}

export function registerPluginTools(server: McpServer, manager: PluginManager): void {
  server.tool("list_plugins", "List allowlisted plugins from Claude and Codex marketplaces.", {}, async () => {
    try {
      return jsonResult(await manager.listPlugins());
    } catch (error) {
      exposeError(error);
    }
  });

  server.tool("show_status", "Show repository, marketplace, cache, and plugin sync status.", {}, async () => {
    try {
      return jsonResult(await manager.showStatus());
    } catch (error) {
      exposeError(error);
    }
  });

  server.tool(
    "update_repo",
    "Run a safe git pull in the harness-plugins repository. Rejects dirty worktrees unless force is true.",
    {
      force: z.boolean().optional().default(false),
      dryRun: z.boolean().optional().default(false)
    },
    async ({ force, dryRun }) => {
      try {
        return jsonResult(await manager.updateRepo({ force, dryRun }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "install_plugin",
    "Install an allowlisted plugin into a target integration. Existing files require overwrite=true.",
    {
      name: pluginNameSchema,
      target: targetSchema,
      ...mutationOptionsSchema
    },
    async ({ name, target, dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.installPlugin({ name, target, dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "sync_plugin",
    "Synchronize one allowlisted plugin into a target integration.",
    {
      name: pluginNameSchema,
      target: targetSchema,
      ...mutationOptionsSchema
    },
    async ({ name, target, dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.syncPlugin({ name, target, dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "sync_all",
    "Synchronize all allowlisted plugins into a target integration.",
    {
      target: targetSchema,
      ...mutationOptionsSchema
    },
    async ({ target, dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.syncAll({ target, dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "sync_to_claude",
    "Synchronize all Claude marketplace plugins and maintain the .claude-plugin marketplace.",
    mutationOptionsSchema,
    async ({ dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.syncAll({ target: "claude", dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "sync_to_opencode",
    "Synchronize all allowlisted plugins into the repo-local OpenCode plugin config.",
    mutationOptionsSchema,
    async ({ dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.syncAll({ target: "opencode", dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "sync_to_codex",
    "Synchronize all Codex marketplace plugins and maintain the .agents/plugins marketplace.",
    mutationOptionsSchema,
    async ({ dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.syncAll({ target: "codex", dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );
}
