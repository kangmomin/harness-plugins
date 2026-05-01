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
      adapterPath?: string;
      adapterContent?: string;
      adapterSkillName?: string;
    }
  | {
      kind: "generated";
      relativePath: string;
      content: string;
      adapterPath?: string;
    };

export class SyncService {
  constructor(
    private readonly fs: FileSystem,
    private readonly repoRoot: string,
    private readonly openCodeRoot: string,
    private readonly logger: OperationLogger
  ) {}

  async syncPlugin(plugin: NormalizedPlugin, target: Target, options: MutationOptions): Promise<SyncResult> {
    const source = this.sourceForTarget(plugin, target);
    const destination = this.destinationFor(plugin.name, target);
    const dryRun = options.dryRun ?? false;
    const overwrite = options.overwrite ?? false;

    assertInsideRoot(this.repoRoot, source);
    this.assertInsideManagedRoot(destination, target);

    const syncPlan = await this.planSync(plugin.name, source, destination, target, overwrite);
    const changes = syncPlan.changes;
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
        const installed = await this.isInstalled(plugin.name, target);
        const sourceHash = await this.hashSourceForTarget(plugin, target);
        const destinationHash = installed
          ? target === "opencode"
            ? await this.hashOpenCodeDestination(destination, await this.collectSourceEntries(source, target, plugin.name))
            : await this.fs.hashTree(destination)
          : undefined;
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
      return path.join(this.openCodeRoot, "plugins", pluginName);
    }
    return path.join(this.repoRoot, ".agents", "plugins", "installed", pluginName);
  }

  private async isInstalled(pluginName: string, target: Target): Promise<boolean> {
    if (target !== "opencode") {
      return this.fs.exists(this.destinationFor(pluginName, target));
    }
    return (await this.fs.exists(path.join(this.openCodeRoot, "plugins", pluginName))) &&
      (await this.fs.exists(path.join(this.openCodeRoot, "skills"))) &&
      (await this.fs.exists(path.join(this.openCodeRoot, "commands")));
  }

  private async planSync(
    pluginName: string,
    source: string,
    destination: string,
    target: Target,
    overwrite: boolean
  ): Promise<{ changes: FileChange[]; sourceEntries: SourceEntry[] }> {
    const sourceEntries = await this.collectSourceEntries(source, target, pluginName);
    const destinationExists = await this.fs.exists(destination);

    if (destinationExists && !overwrite) {
      const sourceHash = await this.hashEntries(sourceEntries);
      const destinationHash =
        target === "opencode"
          ? await this.hashOpenCodeDestination(destination, sourceEntries)
          : await this.fs.hashTree(destination);
      if (sourceHash !== destinationHash) {
        throw new UserFacingError(`Destination already exists at ${destination}. Re-run with overwrite=true to replace it.`);
      }
    }

    const changes: FileChange[] = [{ action: "mkdir", to: destination }];

    for (const entry of sourceEntries) {
      const to = path.join(destination, entry.relativePath);
      this.assertInsideManagedRoot(to, target);
      changes.push(await this.planEntryWrite(entry, to));

      if (target === "opencode" && entry.adapterPath) {
        const adapterTo = this.openCodeAdapterDestination(entry.adapterPath);
        assertInsideRoot(this.openCodeRoot, adapterTo);
        changes.push(await this.planAdapterWrite(entry, adapterTo));
      }
    }

    return { changes, sourceEntries };
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
      const skillFiles = await this.fs.listFiles(skillsPath, "skills");
      for (const entry of skillFiles) {
        const adapterSkillName = this.openCodeSkillAdapterName(pluginName, entry.relativePath);
        entries.push({
          kind: "file",
          ...entry,
          adapterPath: adapterSkillName ? path.join(".opencode", "skills", adapterSkillName, "SKILL.md") : undefined,
          adapterContent: adapterSkillName ? await this.openCodeSkillAdapterContent(entry.absolutePath, adapterSkillName) : undefined,
          adapterSkillName
        });
      }
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

    for (const skillName of this.openCodeSkillNames(entries)) {
      entries.push({
        kind: "generated",
        relativePath: path.join("commands", `${skillName}.md`),
        adapterPath: path.join(".opencode", "commands", `${skillName}.md`),
        content: this.openCodeCommand(skillName, pluginName)
      });
    }

    entries.push({
      kind: "generated",
      relativePath: "opencode-plugin.json",
      content: `${JSON.stringify(this.openCodeManifest(pluginName, entries), null, 2)}\n`
    });

    return entries.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
  }

  private async planEntryWrite(entry: SourceEntry, to: string): Promise<FileChange> {
    const hash = await this.hashEntry(entry);
    const existingHash = (await this.fs.exists(to)) ? await this.fs.hashFile(to) : undefined;
    if (existingHash === hash) {
      return {
        action: "skip",
        from: entry.kind === "file" ? entry.absolutePath : undefined,
        to,
        reason: "unchanged",
        hash
      };
    }
    if (entry.kind === "generated") {
      return { action: "write", to, hash, content: entry.content };
    }
    return { action: "copy", from: entry.absolutePath, to, hash };
  }

  private async planAdapterWrite(entry: SourceEntry, to: string): Promise<FileChange> {
    if (entry.kind !== "file" || !entry.adapterContent) {
      return this.planEntryWrite(entry, to);
    }

    const hash = this.fs.hashText(entry.adapterContent);
    const existingHash = (await this.fs.exists(to)) ? await this.fs.hashFile(to) : undefined;
    if (existingHash === hash) {
      return {
        action: "skip",
        from: entry.kind === "file" ? entry.absolutePath : undefined,
        to,
        reason: "unchanged",
        hash
      };
    }
    return { action: "write", from: entry.absolutePath, to, hash, content: entry.adapterContent };
  }

  private openCodeSkillAdapterName(pluginName: string, relativePath: string): string | undefined {
    const parts = relativePath.split(path.sep);
    if (parts.length >= 3 && parts[0] === "skills" && parts[2] === "SKILL.md") {
      return `${pluginName}__${parts[1]}`;
    }
    return undefined;
  }

  private async openCodeSkillAdapterContent(absolutePath: string, skillName: string): Promise<string> {
    const content = (await this.fs.readFile(absolutePath)).toString("utf8");
    if (!content.startsWith("---\n")) {
      return `---\nname: ${skillName}\n---\n\n${content}`;
    }

    const endIndex = content.indexOf("\n---", 4);
    if (endIndex === -1) {
      return `---\nname: ${skillName}\n---\n\n${content}`;
    }

    const frontmatter = content.slice(4, endIndex);
    const body = content.slice(endIndex);
    const nextFrontmatter = frontmatter.match(/^name:\s*.+$/m)
      ? frontmatter.replace(/^name:\s*.+$/m, `name: ${skillName}`)
      : `name: ${skillName}\n${frontmatter}`;
    return `---\n${nextFrontmatter}${body}`;
  }

  private openCodeSkillNames(entries: SourceEntry[]): string[] {
    const names = new Set<string>();
    for (const entry of entries) {
      if (entry.kind === "file" && entry.adapterSkillName) {
        names.add(entry.adapterSkillName);
      }
    }
    return [...names].sort();
  }

  private openCodeCommand(skillName: string, pluginName: string): string {
    return `---\ndescription: Use the ${skillName} skill from ${pluginName}\n---\n\nUse the \`${skillName}\` skill.\n`;
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
        commands: "commands/",
        instructions: "instructions/",
        skills: "skills/",
        agents: "agents/",
        profiles: "profiles/",
        openCodeSkills: "../skills/",
        openCodeCommands: "../commands/"
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

  private async hashOpenCodeDestination(destination: string, entries: SourceEntry[]): Promise<string> {
    const hash = createHash("sha256");
    const destinations: Array<{ absolutePath: string; relativePath: string }> = [];

    for (const entry of entries) {
      destinations.push({
        absolutePath: path.join(destination, entry.relativePath),
        relativePath: entry.relativePath
      });
      if (entry.adapterPath) {
        destinations.push({
          absolutePath: this.openCodeAdapterDestination(entry.adapterPath),
          relativePath: entry.adapterPath
        });
      }
    }

    for (const entry of destinations.sort((left, right) => left.relativePath.localeCompare(right.relativePath))) {
      hash.update(entry.relativePath);
      hash.update("\0");
      if (await this.fs.exists(entry.absolutePath)) {
        hash.update(await this.fs.readFile(entry.absolutePath));
      }
      hash.update("\0");
    }
    return hash.digest("hex");
  }

  private async hashEntries(entries: SourceEntry[]): Promise<string> {
    const hash = createHash("sha256");
    const hashes: Array<{ relativePath: string; content: Buffer | string }> = [];
    for (const entry of entries) {
      const content = entry.kind === "generated" ? entry.content : await this.fs.readFile(entry.absolutePath);
      hashes.push({ relativePath: entry.relativePath, content });
      if (entry.adapterPath) {
        hashes.push({ relativePath: entry.adapterPath, content: entry.kind === "file" ? entry.adapterContent ?? content : content });
      }
    }

    for (const entry of hashes.sort((left, right) => left.relativePath.localeCompare(right.relativePath))) {
      hash.update(entry.relativePath);
      hash.update("\0");
      hash.update(entry.content);
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
        destinationHash:
          target === "opencode"
            ? await this.hashOpenCodeDestination(destination, await this.collectSourceEntries(source, target, pluginName))
            : await this.fs.hashTree(destination),
        syncedAt: new Date().toISOString()
      }
    };
    await this.fs.writeJson(cachePath, nextCache);
  }

  private openCodeAdapterDestination(adapterPath: string): string {
    const prefix = `.opencode${path.sep}`;
    const normalized = path.normalize(adapterPath);
    const relativePath = normalized.startsWith(prefix) ? normalized.slice(prefix.length) : normalized;
    const destination = path.join(this.openCodeRoot, relativePath);
    assertInsideRoot(this.openCodeRoot, destination);
    return destination;
  }

  private assertInsideManagedRoot(candidate: string, target: Target): void {
    assertInsideRoot(target === "opencode" ? this.openCodeRoot : this.repoRoot, candidate);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
