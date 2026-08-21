/**
 * work-log 스코프 해석 — 단일 진실.
 *
 * MCP 서버와 스킬이 모두 이 모듈을 통해 vault 루트를 결정한다.
 * 스킬은 `node config.js` 로 CLI 실행해 같은 답을 JSON 으로 받는다.
 *
 * 우선순위 (캐시 없이 매 호출마다 재해석):
 *   1. WORK_LOG_ROOT 환경변수 (절대경로일 때만 유효)
 *   2. cwd 에서 위로 올라가며 .work-log.json 탐색 (.git 경계까지 포함해 확인 후 정지)
 *   3. ~/.claude/work-log.json
 *   4. 없음 -> needsInit
 */

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';

export const CONFIG_BASENAME = '.work-log.json';
export const GLOBAL_CONFIG = path.join(os.homedir(), '.claude', 'work-log.json');
export const DEFAULT_EXCLUDES = ['.obsidian', '.trash', '.git', 'node_modules', '.wiki'];

/** 설정이 잘못됐을 때 조용히 다음 우선순위로 내려가지 않고 던지는 오류. */
export class ConfigError extends Error {
  constructor(message, source) {
    super(message);
    this.name = 'ConfigError';
    this.source = source;
  }
}

function readJson(file) {
  let raw;
  try {
    raw = fs.readFileSync(file, 'utf8');
  } catch {
    return null; // 존재하지 않음 — 정상적인 miss
  }
  try {
    return JSON.parse(raw);
  } catch (e) {
    // fail-closed: 깨진 설정은 무시하지 않고 멈춘다
    throw new ConfigError(`설정 파일 JSON 파싱 실패: ${file} (${e.message})`, file);
  }
}

/**
 * 후보 root 가 이 플러그인 자신의 소스 디렉토리인지 검사한다.
 * harness-plugins 저장소에서 프로젝트 스코프를 켜면 <repo>/work-log/ 가
 * 플러그인 코드 자신을 가리키므로 vault 로 채택하면 안 된다.
 */
export function isPluginSource(dir) {
  return (
    fs.existsSync(path.join(dir, '.claude-plugin')) ||
    fs.existsSync(path.join(dir, 'mcp', 'server.js')) ||
    (fs.existsSync(path.join(dir, 'skills')) && fs.existsSync(path.join(dir, '.mcp.json')))
  );
}

function validateRoot(root, source) {
  let st;
  try {
    st = fs.statSync(root);
  } catch {
    throw new ConfigError(`vault 루트가 존재하지 않습니다: ${root}`, source);
  }
  if (!st.isDirectory()) {
    throw new ConfigError(`vault 루트가 디렉토리가 아닙니다: ${root}`, source);
  }
  if (isPluginSource(root)) {
    throw new ConfigError(
      `이 경로는 work-log 플러그인 소스입니다. 문서 vault 로 쓸 수 없습니다: ${root}`,
      source
    );
  }
  return root;
}

function fromConfigFile(file) {
  const cfg = readJson(file);
  if (!cfg) return null;

  const scope = cfg.scope === 'project' ? 'project' : 'global';
  if (typeof cfg.root !== 'string' || cfg.root.trim() === '') {
    throw new ConfigError(`설정에 root 가 없습니다: ${file}`, file);
  }
  if (scope === 'global' && !path.isAbsolute(cfg.root)) {
    throw new ConfigError(`scope "global" 은 root 에 절대경로가 필요합니다: ${file}`, file);
  }
  // 상대경로는 설정 파일 위치 기준
  const root = path.resolve(path.dirname(file), cfg.root);

  return {
    scope,
    root: validateRoot(root, file),
    excludes: Array.isArray(cfg.excludes) && cfg.excludes.length
      ? cfg.excludes
      : DEFAULT_EXCLUDES,
    configSource: file,
  };
}

/** cwd 에서 위로 올라가며 .work-log.json 을 찾는다. .git 을 만나면 거기까지 보고 정지. */
function walkUp(startDir) {
  let dir = path.resolve(startDir);
  for (;;) {
    const candidate = path.join(dir, CONFIG_BASENAME);
    if (fs.existsSync(candidate)) return fromConfigFile(candidate);

    // .git 은 디렉토리(일반) 또는 파일(worktree/submodule) 둘 다 가능
    if (fs.existsSync(path.join(dir, '.git'))) return null; // 저장소 경계에서 정지

    const parent = path.dirname(dir);
    if (parent === dir) return null; // 파일시스템 루트
    dir = parent;
  }
}

/**
 * vault 루트를 해석한다.
 * @returns {{scope,root,excludes,configSource,cwd}} 또는 {needsInit:true,...}
 */
export function resolveConfig({ cwd = process.cwd(), env = process.env } = {}) {
  const base = { cwd, home: os.homedir() };

  // 1. 환경변수 — 빈 문자열/공백/상대경로는 unset 취급.
  //    .mcp.json 의 ${WORK_LOG_ROOT:-} 는 unset 일 때 빈 문자열로 도착한다.
  const envRoot = (env.WORK_LOG_ROOT || '').trim();
  if (envRoot && path.isAbsolute(envRoot)) {
    return {
      ...base,
      scope: 'global',
      root: validateRoot(path.resolve(envRoot), 'env:WORK_LOG_ROOT'),
      excludes: DEFAULT_EXCLUDES,
      configSource: 'env:WORK_LOG_ROOT',
    };
  }

  // 2. cwd 에서 위로 .work-log.json 탐색
  const found = walkUp(cwd);
  if (found) return { ...base, ...found };

  // 3. 전역 설정
  const global = fromConfigFile(GLOBAL_CONFIG);
  if (global) return { ...base, ...global };

  // 4. 미설정
  return {
    ...base,
    needsInit: true,
    configSource: null,
    hint: `설정이 없습니다. /work-log:init 을 실행하거나 ${GLOBAL_CONFIG} 를 만드세요.`,
  };
}

/** vault 별 인덱스 캐시 디렉토리. vault 안에는 아무것도 쓰지 않는다. */
export function cacheDirFor(vaultRoot) {
  let real = vaultRoot;
  try {
    real = fs.realpathSync(vaultRoot);
  } catch {
    /* 아직 없으면 원본 경로로 키를 만든다 */
  }
  const key = crypto.createHash('sha1').update(real).digest('hex').slice(0, 16);
  const base = process.env.XDG_CACHE_HOME || path.join(os.homedir(), '.cache');
  return { dir: path.join(base, 'work-log', key), realRoot: real };
}

// CLI 진입점 — 스킬이 `node config.js` 로 호출한다.
if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    const cfg = resolveConfig();
    if (cfg.root) cfg.cacheDir = cacheDirFor(cfg.root).dir;
    process.stdout.write(JSON.stringify(cfg, null, 2) + '\n');
  } catch (e) {
    process.stdout.write(
      JSON.stringify({ error: e.message, source: e.source ?? null }, null, 2) + '\n'
    );
    process.exitCode = 1;
  }
}
