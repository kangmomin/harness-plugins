import { get } from "node:https";

interface UpdateCheckerOptions {
  packageName: string;
  currentVersion: string;
  intervalMs: number;
}

interface NpmRegistryResponse {
  "dist-tags"?: {
    latest?: string;
  };
}

export function startUpdateChecker(options: UpdateCheckerOptions): void {
  if (process.env.PLUGIN_MANAGER_DISABLE_UPDATE_CHECK === "1") {
    return;
  }

  const check = async (): Promise<void> => {
    try {
      const latest = await fetchLatestVersion(options.packageName);
      if (latest && compareVersions(latest, options.currentVersion) > 0) {
        process.stderr.write(
          `[plugin-manager-mcp] update available: ${options.currentVersion} -> ${latest}. Run npm install -g ${options.packageName}@latest.\n`
        );
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      process.stderr.write(`[plugin-manager-mcp] update check failed: ${message}\n`);
    }
  };

  setTimeout(() => {
    void check();
  }, 5_000).unref();

  setInterval(() => {
    void check();
  }, options.intervalMs).unref();
}

async function fetchLatestVersion(packageName: string): Promise<string | undefined> {
  const encodedName = packageName.startsWith("@") ? `@${encodeURIComponent(packageName.slice(1))}` : encodeURIComponent(packageName);
  const url = `https://registry.npmjs.org/${encodedName}`;

  return new Promise((resolve, reject) => {
    const request = get(
      url,
      {
        headers: {
          accept: "application/json",
          "user-agent": "plugin-manager-mcp"
        },
        timeout: 10_000
      },
      (response) => {
        if (response.statusCode === 404) {
          response.resume();
          resolve(undefined);
          return;
        }

        if (!response.statusCode || response.statusCode < 200 || response.statusCode >= 300) {
          response.resume();
          reject(new Error(`npm registry returned HTTP ${response.statusCode ?? "unknown"}`));
          return;
        }

        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk: string) => {
          body += chunk;
        });
        response.on("end", () => {
          try {
            const parsed = JSON.parse(body) as NpmRegistryResponse;
            resolve(parsed["dist-tags"]?.latest);
          } catch (error) {
            reject(error);
          }
        });
      }
    );

    request.on("timeout", () => {
      request.destroy(new Error("npm registry request timed out"));
    });
    request.on("error", reject);
  });
}

function compareVersions(left: string, right: string): number {
  const leftParts = parseVersion(left);
  const rightParts = parseVersion(right);

  for (let index = 0; index < Math.max(leftParts.length, rightParts.length); index += 1) {
    const leftValue = leftParts[index] ?? 0;
    const rightValue = rightParts[index] ?? 0;
    if (leftValue > rightValue) {
      return 1;
    }
    if (leftValue < rightValue) {
      return -1;
    }
  }

  return 0;
}

function parseVersion(version: string): number[] {
  const coreVersion = version.replace(/^v/, "").split("-", 1)[0] ?? "";
  return coreVersion.split(".").map((part) => {
    const parsed = Number.parseInt(part, 10);
    return Number.isFinite(parsed) ? parsed : 0;
  });
}
