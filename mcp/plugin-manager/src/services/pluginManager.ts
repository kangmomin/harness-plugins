import path from "node:path";
import { FileSystem } from "../utils/fileSystem.js";
import { GitService } from "./gitService.js";
import { MarketplaceService } from "./marketplaceService.js";
import { SyncService } from "./syncService.js";
import { OperationLogger } from "../utils/logger.js";
import type {
  MarketplaceSummary,
  MutationOptions,
  PluginListResult,
  PluginStatus,
  RepoUpdateOptions,
  SyncRequest,
  SyncResult,
  Target
} from "./types.js";
import { assertTarget } from "../utils/validation.js";

export class PluginManager {
  constructor(
    private readonly repoRoot: string,
    private readonly marketplace: MarketplaceService,
    private readonly git: GitService,
    private readonly sync: SyncService,
    private readonly logger: OperationLogger
  ) {}

  async listPlugins(): Promise<PluginListResult> {
    const marketplaces = await this.marketplace.loadAll();
    return {
      repoRoot: this.repoRoot,
      plugins: marketplaces.plugins.map((plugin) => ({
        name: plugin.name,
        description: plugin.description,
        availableTargets: plugin.availableTargets,
        sources: plugin.sources
      })),
      marketplaces: marketplaces.summary
    };
  }

  async showStatus(): Promise<{
    repoRoot: string;
    git: Awaited<ReturnType<GitService["status"]>>;
    marketplaces: MarketplaceSummary;
    plugins: PluginStatus[];
  }> {
    const marketplaces = await this.marketplace.loadAll();
    return {
      repoRoot: this.repoRoot,
      git: await this.git.status(),
      marketplaces: marketplaces.summary,
      plugins: await this.sync.statusForPlugins(marketplaces.plugins)
    };
  }

  async updateRepo(options: RepoUpdateOptions): Promise<Awaited<ReturnType<GitService["pull"]>>> {
    await this.logger.record("update_repo", { force: options.force, dryRun: options.dryRun });
    return this.git.pull(options);
  }

  async installPlugin(request: SyncRequest): Promise<SyncResult> {
    return this.syncPlugin(request);
  }

  async syncPlugin(request: SyncRequest): Promise<SyncResult> {
    const target = assertTarget(request.target);
    const marketplaces = await this.marketplace.loadAll();
    const plugin = this.marketplace.requirePlugin(marketplaces, request.name, target);
    await this.logger.record("sync_plugin", {
      name: plugin.name,
      target,
      dryRun: request.dryRun,
      overwrite: request.overwrite
    });
    return this.sync.syncPlugin(plugin, target, request);
  }

  async syncAll(options: MutationOptions & { target: Target }): Promise<{ target: Target; results: SyncResult[] }> {
    const target = assertTarget(options.target);
    const marketplaces = await this.marketplace.loadAll();
    const plugins = marketplaces.plugins.filter((plugin) => plugin.availableTargets.includes(target));
    await this.logger.record("sync_all", {
      target,
      count: plugins.length,
      dryRun: options.dryRun,
      overwrite: options.overwrite
    });

    const results: SyncResult[] = [];
    for (const plugin of plugins) {
      results.push(await this.sync.syncPlugin(plugin, target, options));
    }
    return { target, results };
  }
}

export async function createPluginManager(configuredRoot?: string): Promise<PluginManager> {
  const fs = new FileSystem();
  const repoRoot = await discoverRepoRoot(fs, configuredRoot);
  const logger = new OperationLogger(fs, path.join(repoRoot, ".plugin-manager-mcp", "operations.log"));
  const marketplace = new MarketplaceService(fs, repoRoot);
  const git = new GitService(repoRoot);
  const sync = new SyncService(fs, repoRoot, logger);
  return new PluginManager(repoRoot, marketplace, git, sync, logger);
}

async function discoverRepoRoot(fs: FileSystem, configuredRoot?: string): Promise<string> {
  const start = configuredRoot ? path.resolve(configuredRoot) : process.cwd();
  let current = start;

  for (;;) {
    const claudeMarketplace = path.join(current, ".claude-plugin", "marketplace.json");
    const codexMarketplace = path.join(current, ".agents", "plugins", "marketplace.json");
    if ((await fs.exists(claudeMarketplace)) && (await fs.exists(codexMarketplace))) {
      return current;
    }

    const parent = path.dirname(current);
    if (parent === current) {
      throw new Error(
        `Unable to locate harness-plugins root from ${start}. Set HARNESS_PLUGINS_ROOT to the repository root.`
      );
    }
    current = parent;
  }
}
