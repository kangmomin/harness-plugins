import path from "node:path";
import { UserFacingError } from "./errors.js";

export function normalizeRelativePath(input: string): string {
  if (path.isAbsolute(input)) {
    throw new UserFacingError(`Absolute paths are not allowed in marketplace sources: ${input}`);
  }

  const normalized = path.normalize(input);
  if (normalized === "." || normalized.startsWith("..") || path.isAbsolute(normalized)) {
    throw new UserFacingError(`Marketplace source escapes repository root: ${input}`);
  }

  return normalized;
}

export function assertInsideRoot(root: string, candidate: string): void {
  const resolvedRoot = path.resolve(root);
  const resolvedCandidate = path.resolve(candidate);
  const relative = path.relative(resolvedRoot, resolvedCandidate);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new UserFacingError(`Path escapes harness-plugins repository: ${candidate}`);
  }
}
