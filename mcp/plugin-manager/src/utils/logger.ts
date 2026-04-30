import type { FileSystem } from "./fileSystem.js";

export class OperationLogger {
  constructor(
    private readonly fs: FileSystem,
    private readonly logPath: string
  ) {}

  async record(event: string, details: Record<string, unknown>): Promise<void> {
    const line = `${JSON.stringify({ at: new Date().toISOString(), event, details })}\n`;
    await this.fs.appendFile(this.logPath, line);
  }
}
