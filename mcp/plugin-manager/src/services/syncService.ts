import path from "node:path";
import type { FileSystem } from "../utils/fileSystem.js";
import { OperationLogger } from "../utils/logger.js";
import { UserFacingError } from "../utils/errors.js";
import { assertInsideRoot } from "../utils/pathSafety.js";
import type { FileChange, MutationOptions, NormalizedPlugin, PluginStatus, SyncResult, Target } from "./types.js";

export class SyncService {
  constructor(
    private readonly fs: FileSystem,
    private readonly repoRoot: string,
    private readonly logger: OperationLogger
  ) {}

  async syncPlugin(plugin: NormalizedPlugin, target: Target, options: MutationOptions): Promise<SyncResult> {
    const source = this.sourceForTarget(plugin, target);
    const destination = this.destinationFor(plugin.name, target);
    const dryRun = options.dryRun ?? false;
    const overwrite = options.overwrite ?? false;

    assertInsideRoot(this.repoRoot, source);
    assertInsideRoot(this.repoRoot, destination);

    const changes = await this.planSync(source, destination, target, overwrite);
    if (!dryRun) {
      for (const change of changes) {
        if (change.action === "mkdir") {
          await this.fs.ensureDir(change.to);
        } else if (change.action === "copy" && change.from) {
          await this.fs.copyFile(change.from, change.to);
        } else if (change.action === "write" && change.from) {
          await this.fs.copyFile(change.from, change.to);
        }
      }
      await this.writeCache(plugin.name, target, source, destination);
      await this.logger.record("sync_complete", { plugin: plugin.name, target, changes: changes.length });
    }

    return {
      plugin: plugin.name,
      target,
      dryRun,
      changed: changes.some((change) => change.action !== "skip"),
      destination,
      changes
    };
  }

  async statusForPlugins(plugins: NormalizedPlugin[]): Promise<PluginStatus[]> {
    const statuses: PluginStatus[] = [];
    for (const plugin of plugins) {
      const targets: PluginStatus["targets"] = {};
      for (const target of plugin.availableTargets) {
        const source = this.sourceForTarget(plugin, target);
        const destination = this.destinationFor(plugin.name, target);
        const installed = await this.fs.exists(destination);
        const sourceHash = await this.fs.hashTree(source);
        const destinationHash = installed ? await this.fs.hashTree(destination) : undefined;
        targets[target] = {
          source,
          destination,
          installed,
          sourceHash,
          destinationHash,
          inSync: installed && sourceHash === destinationHash
        };
      }
      statuses.push({ name: plugin.name, targets });
    }
    return statuses;
  }

  private sourceForTarget(plugin: NormalizedPlugin, target: Target): string {
    if (target === "codex") {
      if (!plugin.sources.codex) {
        throw new UserFacingError(`Plugin "${plugin.name}" has no Codex source.`);
      }
      return plugin.sources.codex;
    }
    if (!plugin.sources.claude) {
      throw new UserFacingError(`Plugin "${plugin.name}" has no Claude/OpenCode source.`);
    }
    return plugin.sources.claude;
  }

  private destinationFor(pluginName: string, target: Target): string {
    if (target === "claude") {
      return path.join(this.repoRoot, ".claude-plugin", "plugins", pluginName);
    }
    if (target === "opencode") {
      return path.join(this.repoRoot, ".opencode", "plugins", pluginName);
    }
    return path.join(this.repoRoot, ".agents", "plugins", "installed", pluginName);
  }

  private async planSync(source: string, destination: string, target: Target, overwrite: boolean): Promise<FileChange[]> {
    const sourceEntries = await this.collectSourceEntries(source, target);
    const destinationExists = await this.fs.exists(destination);

    if (destinationExists && !overwrite) {
      const sourceHash = await this.fs.hashFiles(sourceEntries.map((entry) => entry.absolutePath));
      const destinationHash = await this.fs.hashTree(destination);
      if (sourceHash !== destinationHash) {
        throw new UserFacingError(`Destination already exists at ${destination}. Re-run with overwrite=true to replace it.`);
      }
    }

    const changes: FileChange[] = [{ action: "mkdir", to: destination }];

    for (const entry of sourceEntries) {
      const to = path.join(destination, entry.relativePath);
      assertInsideRoot(this.repoRoot, to);
      const hash = await this.fs.hashFile(entry.absolutePath);
      const existingHash = (await this.fs.exists(to)) ? await this.fs.hashFile(to) : undefined;
      if (existingHash === hash) {
        changes.push({ action: "skip", from: entry.absolutePath, to, reason: "unchanged", hash });
      } else {
        changes.push({ action: "copy", from: entry.absolutePath, to, hash });
      }
    }

    return changes;
  }

  private async collectSourceEntries(source: string, target: Target): Promise<Array<{ absolutePath: string; relativePath: string }>> {
    if (target === "opencode") {
      return this.collectOpenCodeEntries(source);
    }
    return this.fs.listFiles(source);
  }

  private async collectOpenCodeEntries(source: string): Promise<Array<{ absolutePath: string; relativePath: string }>> {
    const entries: Array<{ absolutePath: string; relativePath: string }> = [];
    const skillsPath = path.join(source, "skills");
    if (await this.fs.exists(skillsPath)) {
      entries.push(...(await this.fs.listFiles(skillsPath, "skills")));
    }

    const rootFiles = await this.fs.listTopLevelFiles(source);
    for (const entry of rootFiles) {
      const extension = path.extname(entry.relativePath).toLowerCase();
      if ([".md", ".markdown"].includes(extension)) {
        entries.push(entry);
      }
    }

    if (entries.length === 0) {
      throw new UserFacingError(`OpenCode sync found no skills or markdown instruction files under ${source}.`);
    }

    return entries.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
  }

  private async writeCache(pluginName: string, target: Target, source: string, destination: string): Promise<void> {
    const cachePath = path.join(this.repoRoot, ".plugin-manager-mcp", "status-cache.json");
    const parsedCache = (await this.fs.exists(cachePath)) ? await this.fs.readJson(cachePath) : {};
    const cache = isRecord(parsedCache) ? parsedCache : {};
    const nextCache = {
      ...cache,
      [`${target}:${pluginName}`]: {
        pluginName,
        target,
        source,
        destination,
        sourceHash: await this.fs.hashTree(source),
        destinationHash: await this.fs.hashTree(destination),
        syncedAt: new Date().toISOString()
      }
    };
    await this.fs.writeJson(cachePath, nextCache);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
