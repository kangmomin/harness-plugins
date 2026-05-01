import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { PluginManager } from "../services/pluginManager.js";
import { McpError, UserFacingError } from "../utils/errors.js";

const targetSchema = z.enum(["claude", "opencode", "codex"]);

const pluginNameSchema = z
  .string()
  .min(1)
  .max(120)
  .describe("Plugin name or alias, for example minmos-harness, minmos harness, minmo, or hyeondongs harness.");

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

function normalizePluginName(name: string): string {
  const normalized = name
    .trim()
    .toLowerCase()
    .replace(/['’]/g, "")
    .replace(/[_\s]+/g, "-");

  const aliases: Record<string, string> = {
    minmo: "minmos-harness",
    minmos: "minmos-harness",
    "minmo-harness": "minmos-harness",
    "minmos-harness": "minmos-harness",
    "minmo-s-harness": "minmos-harness",
    "mimos-harness": "minmos-harness",
    "mimo-s-harness": "minmos-harness",
    "민모": "minmos-harness",
    "민모스": "minmos-harness",
    hyeondong: "hyeondongs-harness",
    hyeondongs: "hyeondongs-harness",
    "hyeondong-harness": "hyeondongs-harness",
    "hyeondongs-harness": "hyeondongs-harness",
    "현동": "hyeondongs-harness"
  };

  return aliases[normalized] ?? normalized;
}

function exposeError(error: unknown): never {
  if (error instanceof UserFacingError) {
    throw new McpError(error.message);
  }
  throw error;
}

export function registerPluginTools(server: McpServer, manager: PluginManager): void {
  server.registerResource(
    "harness-plugin-manager-guide",
    "harness://plugin-manager/guide",
    {
      title: "Harness Plugin Manager Guide",
      description: "How to discover and install harness plugins such as minmos-harness and hyeondongs-harness.",
      mimeType: "text/markdown"
    },
    async (uri) => ({
      contents: [
        {
          uri: uri.href,
          mimeType: "text/markdown",
          text: [
            "# Harness Plugin Manager",
            "",
            "Use this MCP server when the user asks to list, find, install, or sync harness plugins.",
            "",
            "Common requests and tools:",
            "- \"minmos harness plugin install\" or \"minmos harness 플러그인을 설치해줘\": call `install_minmos_harness`.",
            "- \"hyeondongs harness plugin install\" or \"hyeondongs harness 플러그인을 설치해줘\": call `install_hyeondongs_harness`.",
            "- \"install a harness plugin into OpenCode\": call `install_opencode_plugin` with the plugin name or alias.",
            "- \"install a harness plugin into Codex\": call `install_codex_plugin` with the plugin name or alias.",
            "- \"what harness plugins are available?\": call `list_plugins`.",
            "- \"show harness plugin status\": call `show_status`.",
            "",
            "Allowlisted plugin names include `minmos-harness`, `hyeondongs-harness`, `be-harness`, `fe-harness`, and `fs-harness`."
          ].join("\n")
        }
      ]
    })
  );

  server.registerPrompt(
    "install-minmos-harness",
    {
      title: "Install Minmos Harness",
      description: "Install minmos-harness into OpenCode through the plugin manager MCP."
    },
    () => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text: "Install the minmos-harness plugin into OpenCode using the plugin-manager MCP. Use install_minmos_harness."
          }
        }
      ]
    })
  );

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
        return jsonResult(await manager.installPlugin({ name: normalizePluginName(name), target, dryRun, overwrite }));
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
        return jsonResult(await manager.syncPlugin({ name: normalizePluginName(name), target, dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "install_codex_plugin",
    "Install a harness plugin into Codex CLI. Use this when the user asks to install minmos harness, hyeondongs harness, or a harness plugin without naming a target.",
    {
      name: pluginNameSchema,
      ...mutationOptionsSchema
    },
    async ({ name, dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.installPlugin({ name: normalizePluginName(name), target: "codex", dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "install_opencode_plugin",
    "Install a harness plugin into the global OpenCode config. Use this when the user asks in OpenCode to install minmos harness, hyeondongs harness, or a harness plugin without naming a target.",
    {
      name: pluginNameSchema,
      ...mutationOptionsSchema
    },
    async ({ name, dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.installPlugin({ name: normalizePluginName(name), target: "opencode", dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "install_minmos_harness",
    "Install the minmos-harness plugin into the global OpenCode config. Use this for Korean or English OpenCode requests like 'minmos harness 플러그인을 설치해줘'.",
    mutationOptionsSchema,
    async ({ dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.installPlugin({ name: "minmos-harness", target: "opencode", dryRun, overwrite }));
      } catch (error) {
        exposeError(error);
      }
    }
  );

  server.tool(
    "install_hyeondongs_harness",
    "Install the hyeondongs-harness plugin into the global OpenCode config. Use this for Korean or English OpenCode requests like 'hyeondongs harness 플러그인을 설치해줘'.",
    mutationOptionsSchema,
    async ({ dryRun, overwrite }) => {
      try {
        return jsonResult(await manager.installPlugin({ name: "hyeondongs-harness", target: "opencode", dryRun, overwrite }));
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
    "Synchronize all allowlisted plugins into the global OpenCode config root.",
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
