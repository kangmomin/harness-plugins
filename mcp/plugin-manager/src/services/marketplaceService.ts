import path from "node:path";
import { z } from "zod";
import type { FileSystem } from "../utils/fileSystem.js";
import { assertInsideRoot, normalizeRelativePath } from "../utils/pathSafety.js";
import { UserFacingError } from "../utils/errors.js";
import type { MarketplaceLoadResult, NormalizedPlugin, Target } from "./types.js";

const claudeMarketplaceSchema = z.object({
  name: z.string(),
  owner: z.unknown().optional(),
  plugins: z.array(
    z.object({
      name: z.string(),
      description: z.string().optional(),
      source: z.string()
    })
  )
});

const codexMarketplaceSchema = z.object({
  name: z.string(),
  interface: z.unknown().optional(),
  plugins: z.array(
    z.object({
      name: z.string(),
      source: z.object({
        source: z.literal("local"),
        path: z.string()
      }),
      policy: z.unknown().optional(),
      category: z.string().optional()
    })
  )
});

export class MarketplaceService {
  private readonly claudeMarketplacePath: string;
  private readonly codexMarketplacePath: string;

  constructor(
    private readonly fs: FileSystem,
    private readonly repoRoot: string
  ) {
    this.claudeMarketplacePath = path.join(repoRoot, ".claude-plugin", "marketplace.json");
    this.codexMarketplacePath = path.join(repoRoot, ".agents", "plugins", "marketplace.json");
  }

  async loadAll(): Promise<MarketplaceLoadResult> {
    const [claude, codex] = await Promise.all([
      this.fs.readJson(this.claudeMarketplacePath, claudeMarketplaceSchema),
      this.fs.readJson(this.codexMarketplacePath, codexMarketplaceSchema)
    ]);

    const byName = new Map<string, NormalizedPlugin>();

    for (const plugin of claude.plugins) {
      const source = this.resolveMarketplaceSource(plugin.source);
      byName.set(plugin.name, {
        name: plugin.name,
        description: plugin.description,
        availableTargets: ["claude", "opencode"],
        sources: { claude: source }
      });
    }

    for (const plugin of codex.plugins) {
      const source = this.resolveMarketplaceSource(plugin.source.path);
      const existing = byName.get(plugin.name);
      if (existing) {
        existing.sources.codex = source;
        existing.availableTargets = uniqueTargets([...existing.availableTargets, "codex"]);
      } else {
        byName.set(plugin.name, {
          name: plugin.name,
          availableTargets: ["codex"],
          sources: { codex: source }
        });
      }
    }

    const plugins = [...byName.values()].sort((left, right) => left.name.localeCompare(right.name));

    return {
      plugins,
      summary: {
        claude: {
          path: this.claudeMarketplacePath,
          name: claude.name,
          pluginCount: claude.plugins.length
        },
        codex: {
          path: this.codexMarketplacePath,
          name: codex.name,
          pluginCount: codex.plugins.length
        }
      }
    };
  }

  requirePlugin(marketplaces: MarketplaceLoadResult, name: string, target: Target): NormalizedPlugin {
    const plugin = marketplaces.plugins.find((entry) => entry.name === name);
    if (!plugin) {
      throw new UserFacingError(`Plugin "${name}" is not allowlisted in marketplace.json.`);
    }
    if (!plugin.availableTargets.includes(target)) {
      throw new UserFacingError(`Plugin "${name}" is not allowlisted for target "${target}".`);
    }
    return plugin;
  }

  private resolveMarketplaceSource(source: string): string {
    const relativePath = normalizeRelativePath(source);
    const absolutePath = path.resolve(this.repoRoot, relativePath);
    assertInsideRoot(this.repoRoot, absolutePath);
    return absolutePath;
  }
}

function uniqueTargets(targets: Target[]): Target[] {
  return targets.filter((target, index) => targets.indexOf(target) === index);
}
