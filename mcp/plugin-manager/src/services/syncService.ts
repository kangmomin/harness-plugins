import { createHash } from "node:crypto";
import path from "node:path";
import type { FileSystem } from "../utils/fileSystem.js";
import { OperationLogger } from "../utils/logger.js";
import { UserFacingError } from "../utils/errors.js";
import { assertInsideRoot } from "../utils/pathSafety.js";
import type { FileChange, MutationOptions, NormalizedPlugin, PluginStatus, SyncResult, Target } from "./types.js";

type SourceEntry =
  | {
      kind: "file";
      absolutePath: string;
      relativePath: string;
    }
  | {
      kind: "generated";
      relativePath: string;
      content: string;
    };

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

    const changes = await this.planSync(plugin.name, source, destination, target, overwrite);
    if (!dryRun) {
      for (const change of changes) {
        if (change.action === "mkdir") {
          await this.fs.ensureDir(change.to);
        } else if (change.action === "copy" && change.from) {
          await this.fs.copyFile(change.from, change.to);
        } else if (change.action === "write" && change.content !== undefined) {
          await this.fs.writeText(change.to, change.content);
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
        const sourceHash = await this.hashSourceForTarget(plugin, target);
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

  private async planSync(
    pluginName: string,
    source: string,
    destination: string,
    target: Target,
    overwrite: boolean
  ): Promise<FileChange[]> {
    const sourceEntries = await this.collectSourceEntries(source, target, pluginName);
    const destinationExists = await this.fs.exists(destination);

    if (destinationExists && !overwrite) {
      const sourceHash = await this.hashEntries(sourceEntries);
      const destinationHash = await this.fs.hashTree(destination);
      if (sourceHash !== destinationHash) {
        throw new UserFacingError(`Destination already exists at ${destination}. Re-run with overwrite=true to replace it.`);
      }
    }

    const changes: FileChange[] = [{ action: "mkdir", to: destination }];

    for (const entry of sourceEntries) {
      const to = path.join(destination, entry.relativePath);
      assertInsideRoot(this.repoRoot, to);
      const hash = await this.hashEntry(entry);
      const existingHash = (await this.fs.exists(to)) ? await this.fs.hashFile(to) : undefined;
      if (existingHash === hash) {
        changes.push({
          action: "skip",
          from: entry.kind === "file" ? entry.absolutePath : undefined,
          to,
          reason: "unchanged",
          hash
        });
      } else if (entry.kind === "generated") {
        changes.push({ action: "write", to, hash, content: entry.content });
      } else {
        changes.push({ action: "copy", from: entry.absolutePath, to, hash });
      }
    }

    return changes;
  }

  private async collectSourceEntries(source: string, target: Target, pluginName?: string): Promise<SourceEntry[]> {
    if (target === "opencode") {
      return this.collectOpenCodeEntries(source, pluginName ?? path.basename(source));
    }
    return (await this.fs.listFiles(source)).map((entry) => ({ kind: "file", ...entry }));
  }

  private async collectOpenCodeEntries(source: string, pluginName: string): Promise<SourceEntry[]> {
    const entries: SourceEntry[] = [];
    const skillsPath = path.join(source, "skills");
    if (await this.fs.exists(skillsPath)) {
      entries.push(...(await this.fs.listFiles(skillsPath, "skills")).map((entry) => ({ kind: "file" as const, ...entry })));
    }

    const agentsPath = path.join(source, "agents");
    if (await this.fs.exists(agentsPath)) {
      entries.push(...(await this.fs.listFiles(agentsPath, "agents")).map((entry) => ({ kind: "file" as const, ...entry })));
    }

    const rootFiles = await this.fs.listTopLevelFiles(source);
    for (const entry of rootFiles) {
      const fileName = path.basename(entry.relativePath);
      const extension = path.extname(fileName).toLowerCase();
      if ([".md", ".markdown"].includes(extension)) {
        entries.push({
          kind: "file",
          absolutePath: entry.absolutePath,
          relativePath: this.openCodeMarkdownDestination(fileName)
        });
      }
    }

    if (entries.length === 0) {
      throw new UserFacingError(`OpenCode sync found no skills or markdown instruction files under ${source}.`);
    }

    entries.push({
      kind: "generated",
      relativePath: "opencode-plugin.json",
      content: `${JSON.stringify(this.openCodeManifest(pluginName, entries), null, 2)}\n`
    });

    return entries.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
  }

  private openCodeMarkdownDestination(fileName: string): string {
    if (fileName === "PROFILE.md") {
      return path.join("profiles", "default.md");
    }
    if (fileName === "OVERRIDES.md") {
      return path.join("profiles", "overrides.md");
    }
    return path.join("instructions", fileName);
  }

  private openCodeManifest(pluginName: string, entries: SourceEntry[]): Record<string, unknown> {
    const relativePaths = entries.map((entry) => entry.relativePath).sort();
    return {
      name: pluginName,
      target: "opencode",
      generatedBy: "plugin-manager-mcp",
      layout: {
        instructions: "instructions/",
        skills: "skills/",
        agents: "agents/",
        profiles: "profiles/"
      },
      files: relativePaths
    };
  }

  private async hashSourceForTarget(plugin: NormalizedPlugin, target: Target): Promise<string> {
    const source = this.sourceForTarget(plugin, target);
    if (target !== "opencode") {
      return this.fs.hashTree(source);
    }
    return this.hashEntries(await this.collectSourceEntries(source, target, plugin.name));
  }

  private async hashEntries(entries: SourceEntry[]): Promise<string> {
    const hash = createHash("sha256");
    const sortedEntries = [...entries].sort((left, right) => left.relativePath.localeCompare(right.relativePath));
    for (const entry of sortedEntries) {
      hash.update(entry.relativePath);
      hash.update("\0");
      if (entry.kind === "generated") {
        hash.update(entry.content);
      } else {
        hash.update(await this.fs.readFile(entry.absolutePath));
      }
      hash.update("\0");
    }
    return hash.digest("hex");
  }

  private async hashEntry(entry: SourceEntry): Promise<string> {
    return entry.kind === "generated" ? this.fs.hashText(entry.content) : this.fs.hashFile(entry.absolutePath);
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
        sourceHash:
          target === "opencode"
            ? await this.hashEntries(await this.collectSourceEntries(source, target, pluginName))
            : await this.fs.hashTree(source),
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
