import { z } from "zod";
import type { Target } from "../services/types.js";

const targetSchema = z.enum(["claude", "opencode", "codex"]);

export function assertTarget(value: unknown): Target {
  return targetSchema.parse(value);
}
