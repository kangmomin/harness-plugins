export const targets = ["claude", "opencode", "codex"] as const;
export type Target = (typeof targets)[number];

export interface MutationOptions {
  dryRun?: boolean;
  overwrite?: boolean;
}

export interface RepoUpdateOptions {
  force?: boolean;
  dryRun?: boolean;
}

export interface SyncRequest extends MutationOptions {
  name: string;
  target: Target;
}

export interface PluginSourceMap {
  claude?: string;
  codex?: string;
}

export interface NormalizedPlugin {
  name: string;
  description?: string;
  availableTargets: Target[];
  sources: PluginSourceMap;
}

export interface MarketplaceSummary {
  claude: {
    path: string;
    name: string;
    pluginCount: number;
  };
  codex: {
    path: string;
    name: string;
    pluginCount: number;
  };
}

export interface MarketplaceLoadResult {
  plugins: NormalizedPlugin[];
  summary: MarketplaceSummary;
}

export interface PluginListResult {
  repoRoot: string;
  plugins: Array<{
    name: string;
    description?: string;
    availableTargets: Target[];
    sources: PluginSourceMap;
  }>;
  marketplaces: MarketplaceSummary;
}

export interface FileChange {
  action: "copy" | "mkdir" | "write" | "skip" | "delete";
  from?: string;
  to: string;
  reason?: string;
  hash?: string;
}

export interface SyncResult {
  plugin: string;
  target: Target;
  dryRun: boolean;
  changed: boolean;
  destination: string;
  changes: FileChange[];
}

export interface PluginStatus {
  name: string;
  targets: Partial<Record<Target, {
    source: string;
    destination: string;
    installed: boolean;
    sourceHash?: string;
    destinationHash?: string;
    inSync: boolean;
  }>>;
}
