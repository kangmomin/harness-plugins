import { createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { z } from "zod";

export class FileSystem {
  async exists(filePath: string): Promise<boolean> {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  async ensureDir(dirPath: string): Promise<void> {
    await fs.mkdir(dirPath, { recursive: true });
  }

  async readJson<T>(filePath: string, schema?: z.ZodType<T>): Promise<T> {
    const raw = await fs.readFile(filePath, "utf8");
    const parsed = JSON.parse(raw) as unknown;
    return schema ? schema.parse(parsed) : (parsed as T);
  }

  async writeJson(filePath: string, value: unknown): Promise<void> {
    await this.ensureDir(path.dirname(filePath));
    await fs.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  }

  async writeText(filePath: string, value: string): Promise<void> {
    await this.ensureDir(path.dirname(filePath));
    await fs.writeFile(filePath, value, "utf8");
  }

  async readFile(filePath: string): Promise<Buffer> {
    return fs.readFile(filePath);
  }

  async appendFile(filePath: string, value: string): Promise<void> {
    await this.ensureDir(path.dirname(filePath));
    await fs.appendFile(filePath, value, "utf8");
  }

  async copyFile(source: string, destination: string): Promise<void> {
    await this.ensureDir(path.dirname(destination));
    await fs.copyFile(source, destination);
  }

  async listFiles(root: string, relativePrefix = ""): Promise<Array<{ absolutePath: string; relativePath: string }>> {
    const results: Array<{ absolutePath: string; relativePath: string }> = [];
    await this.walk(root, "", relativePrefix, results);
    return results.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
  }

  async listTopLevelFiles(root: string): Promise<Array<{ absolutePath: string; relativePath: string }>> {
    const entries = await fs.readdir(root, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile())
      .map((entry) => ({
        absolutePath: path.join(root, entry.name),
        relativePath: entry.name
      }))
      .sort((left, right) => left.relativePath.localeCompare(right.relativePath));
  }

  async hashFile(filePath: string): Promise<string> {
    const buffer = await fs.readFile(filePath);
    return createHash("sha256").update(buffer).digest("hex");
  }

  hashText(value: string): string {
    return createHash("sha256").update(value).digest("hex");
  }

  async hashFiles(filePaths: string[]): Promise<string> {
    const hash = createHash("sha256");
    for (const filePath of [...filePaths].sort()) {
      hash.update(filePath);
      hash.update("\0");
      hash.update(await fs.readFile(filePath));
      hash.update("\0");
    }
    return hash.digest("hex");
  }

  async hashTree(root: string): Promise<string> {
    const files = await this.listFiles(root);
    const hash = createHash("sha256");
    for (const file of files) {
      hash.update(file.relativePath);
      hash.update("\0");
      hash.update(await fs.readFile(file.absolutePath));
      hash.update("\0");
    }
    return hash.digest("hex");
  }

  private async walk(
    root: string,
    relativeDir: string,
    relativePrefix: string,
    results: Array<{ absolutePath: string; relativePath: string }>
  ): Promise<void> {
    const currentDir = path.join(root, relativeDir);
    const entries = await fs.readdir(currentDir, { withFileTypes: true });

    for (const entry of entries) {
      if (entry.name === ".git" || entry.name === "node_modules" || entry.name === "dist") {
        continue;
      }

      const childRelative = path.join(relativeDir, entry.name);
      const absolutePath = path.join(root, childRelative);
      if (entry.isDirectory()) {
        await this.walk(root, childRelative, relativePrefix, results);
      } else if (entry.isFile()) {
        results.push({
          absolutePath,
          relativePath: path.join(relativePrefix, childRelative)
        });
      }
    }
  }
}
