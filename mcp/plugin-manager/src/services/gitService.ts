import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type { RepoUpdateOptions } from "./types.js";
import { UserFacingError } from "../utils/errors.js";

const execFileAsync = promisify(execFile);

export class GitService {
  constructor(private readonly repoRoot: string) {}

  async status(): Promise<{
    branch: string;
    commit: string;
    dirty: boolean;
    porcelain: string[];
  }> {
    const [branch, commit, porcelain] = await Promise.all([
      this.git(["rev-parse", "--abbrev-ref", "HEAD"]),
      this.git(["rev-parse", "HEAD"]),
      this.git(["status", "--porcelain=v1"])
    ]);

    const lines = porcelain.split("\n").filter(Boolean);
    return {
      branch: branch.trim(),
      commit: commit.trim(),
      dirty: lines.length > 0,
      porcelain: lines
    };
  }

  async pull(options: RepoUpdateOptions): Promise<{
    dryRun: boolean;
    before: Awaited<ReturnType<GitService["status"]>>;
    after?: Awaited<ReturnType<GitService["status"]>>;
    output?: string;
  }> {
    const before = await this.status();
    if (before.dirty && !options.force) {
      throw new UserFacingError("Repository is dirty. Refusing git pull without force=true.");
    }

    if (options.dryRun) {
      return { dryRun: true, before };
    }

    const output = await this.git(["pull", "--ff-only"]);
    return {
      dryRun: false,
      before,
      after: await this.status(),
      output
    };
  }

  private async git(args: string[]): Promise<string> {
    const { stdout, stderr } = await execFileAsync("git", args, {
      cwd: this.repoRoot,
      timeout: 120_000,
      maxBuffer: 1024 * 1024
    });
    return `${stdout}${stderr}`.trim();
  }
}
