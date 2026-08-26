#!/usr/bin/env node
/**
 * work-log MCP 서버 — stdio JSON-RPC 2.0, 런타임 의존성 0.
 *
 * 규율:
 *   - stdout 에는 JSON-RPC 메시지만. 모든 로그는 stderr (console.log 한 줄이 세션을 깨뜨린다).
 *   - 프레이밍은 NDJSON. stdin 은 조각나서 오므로 개행 기준으로 버퍼링한다.
 *   - id 판정은 'id' in msg (속성 존재). truthy 검사는 id:0 을 notification 으로 오인한다.
 *   - 깨진 줄이나 예외 하나로 루프가 죽지 않는다.
 */

import fs from 'node:fs';
import path from 'node:path';
import { resolveConfig, ConfigError } from './lib/config.js';
import {
  syncIndex, readIndex, safeResolve, splitFrontmatter, writeDoc, indexPaths,
} from './lib/vault.js';
import { rank, extractSection, applyBudget } from './lib/search.js';

const SERVER_INFO = { name: 'work-log', version: '0.2.0' };
const SUPPORTED_PROTOCOLS = ['2025-06-18', '2025-03-26', '2024-11-05'];

const log = (...a) => process.stderr.write(`[work-log] ${a.join(' ')}\n`);
const send = (msg) => process.stdout.write(JSON.stringify(msg) + '\n');
const ok = (id, result) => send({ jsonrpc: '2.0', id, result });
const fail = (id, code, message, data) =>
  send({ jsonrpc: '2.0', id, error: data === undefined ? { code, message } : { code, message, data } });

const text = (payload) => ({
  content: [{ type: 'text', text: typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2) }],
});
const toolError = (message) => ({ content: [{ type: 'text', text: message }], isError: true });

/* ────────────────────────────── 툴 정의 ────────────────────────────── */

const TYPE_ENUM = ['plan', 'report', 'design', 'note', 'spec', 'meeting', 'decision'];

const TOOLS = [
  {
    name: 'wiki_resolve',
    description:
      'work-log 문서를 랭킹해 후보를 반환한다. 본문을 포함하지 않으므로 토큰이 거의 들지 않는다. ' +
      '항상 이 툴을 먼저 호출해 후보를 좁힌 뒤 wiki_read 로 하나만 읽어라.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['query'],
      properties: {
        query: { type: 'string', description: '검색어. 공백으로 여러 단어를 넣을 수 있다' },
        type: { type: 'string', enum: TYPE_ENUM, description: '문서 종류 필터' },
        tags: { type: 'array', items: { type: 'string' }, description: '태그 필터 (모두 만족)' },
        limit: { type: 'integer', minimum: 1, maximum: 20, default: 5 },
      },
    },
  },
  {
    name: 'wiki_read',
    description:
      'work-log 문서 하나의 본문을 읽는다. section 으로 헤딩 단위 일부만, token_budget 으로 분량을 제한할 수 있다.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['path'],
      properties: {
        path: { type: 'string', description: 'vault 상대 경로 (wiki_resolve 가 반환한 path)' },
        section: { type: 'string', description: '헤딩 이름 일부. 그 섹션만 반환한다' },
        token_budget: { type: 'integer', minimum: 1, description: '근사 토큰 상한 (1토큰≈4자)' },
      },
    },
  },
  {
    name: 'wiki_write',
    description:
      'work-log 에 문서를 만들거나 고친다. 기본은 create 이며 파일이 있으면 실패한다. ' +
      'frontmatter 가 없는 기존 문서에는 frontmatter 를 주입하지 않는다.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['path', 'content'],
      properties: {
        path: { type: 'string', description: 'vault 상대 경로 (.md 만)' },
        content: { type: 'string', description: '본문' },
        frontmatter: { type: 'object', description: '신규 문서의 frontmatter 재정의' },
        mode: { type: 'string', enum: ['create', 'overwrite', 'append'], default: 'create' },
        expected_hash: { type: 'string', description: '낙관적 잠금. 현재 파일 해시와 다르면 거부' },
      },
    },
  },
  {
    name: 'wiki_sync',
    description:
      'vault 를 전체 재스캔해 인덱스를 갱신하고 drift 리포트를 반환한다. vault 파일은 변경하지 않는다.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
  },
  {
    name: 'wiki_status',
    description: '현재 스코프·vault 루트·인덱스 신선도와 진단 정보(cwd, configSource)를 반환한다.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
  },
];

/* ────────────────────────────── 툴 구현 ────────────────────────────── */

/** 스코프는 매 호출마다 재해석한다 (init 후 서버 재시작 없이 반영되어야 한다). */
function requireConfig() {
  const cfg = resolveConfig();
  if (cfg.needsInit) {
    const e = new Error(
      'work-log 스코프가 설정되지 않았습니다. init 스킬을 실행하세요.\n' + cfg.hint
    );
    e.userFacing = true;
    throw e;
  }
  return cfg;
}

function loadIndex(cfg) {
  const idx = readIndex(cfg.root);
  if (!idx) {
    const e = new Error('인덱스가 아직 없습니다. wiki_sync 를 먼저 실행하세요.');
    e.userFacing = true;
    throw e;
  }
  return idx;
}

const HANDLERS = {
  wiki_status() {
    const cfg = resolveConfig();
    const base = { cwd: cfg.cwd, configSource: cfg.configSource, server: SERVER_INFO.version };
    if (cfg.needsInit) return text({ ...base, needsInit: true, hint: cfg.hint });

    const idx = readIndex(cfg.root);
    const { dir, file } = indexPaths(cfg.root);
    let indexAge = null;
    try {
      indexAge = Math.round((Date.now() - fs.statSync(file).mtimeMs) / 1000);
    } catch { /* 인덱스 없음 */ }

    return text({
      ...base,
      scope: cfg.scope,
      root: cfg.root,
      excludes: cfg.excludes,
      indexPath: file,
      indexDir: dir,
      indexExists: Boolean(idx),
      indexAgeSeconds: indexAge,
      generatedAt: idx?.generatedAt ?? null,
      counts: idx?.counts ?? null,
    });
  },

  async wiki_sync() {
    const cfg = requireConfig();
    const { index, drift } = await syncIndex(cfg);
    return text({
      root: cfg.root,
      scope: cfg.scope,
      generatedAt: index.generatedAt,
      counts: index.counts,
      drift,
    });
  },

  wiki_resolve(args) {
    const cfg = requireConfig();
    const idx = loadIndex(cfg);
    return text({ root: cfg.root, ...rank(idx, args) });
  },

  wiki_read(args) {
    const cfg = requireConfig();
    const { abs, rel, ext } = safeResolve(cfg.root, args.path);

    if (ext === '.html') {
      return text({
        path: rel,
        kind: 'html',
        note: 'html 문서의 본문은 인덱싱하지 않습니다. 브라우저나 Read 도구로 여세요.',
        absolutePath: abs,
      });
    }

    const raw = fs.readFileSync(abs, 'utf8');
    const { frontmatter, body } = splitFrontmatter(raw);
    const section = extractSection(body, args.section);
    const budget = applyBudget(section.text, args.token_budget);

    return text({
      path: rel,
      citation: `work-log:${rel}`,
      frontmatter,
      matchedHeading: section.matchedHeading,
      sectionNotFound: section.sectionNotFound ?? false,
      truncated: budget.truncated,
      approximateBudget: budget.approximate,
      chars: budget.chars,
      body: budget.text,
    });
  },

  async wiki_write(args) {
    const cfg = requireConfig();
    const res = await writeDoc(cfg, {
      relPath: args.path,
      content: args.content,
      frontmatter: args.frontmatter,
      mode: args.mode ?? 'create',
      expectedHash: args.expected_hash,
    });
    // 인덱스를 즉시 갱신해 방금 쓴 문서가 바로 검색된다.
    // 의도적으로 **전체 sync** 를 돈다 (엔트리 하나만 patch 하지 않는다):
    // 새 문서의 링크가 다른 문서의 backlink/brokenLinks/orphans 를 바꾸므로
    // 그래프는 어차피 전역 재계산이 필요하다. 300개 규모에서 수백 ms.
    // 지연이 실제로 관측되면 그때 증분화한다 (plan §2.3 과 동일한 판단).
    const { index } = await syncIndex(cfg);
    const entry = index.docs.find((d) => d.path === res.path) ?? null;
    return text({ written: res, indexed: entry ? { title: entry.title, type: entry.type, tags: entry.tags } : null });
  },
};

/* ────────────────────────── 인자 검증 (-32602) ────────────────────────── */

function validateArgs(tool, args) {
  const schema = tool.inputSchema;
  const props = schema.properties ?? {};

  for (const key of schema.required ?? []) {
    if (args[key] === undefined || args[key] === null || args[key] === '') {
      throw new Error(`필수 인자 누락: ${key}`);
    }
  }
  for (const [key, val] of Object.entries(args)) {
    const spec = props[key];
    if (!spec) throw new Error(`알 수 없는 인자: ${key}`);
    if (spec.type === 'string' && typeof val !== 'string') throw new Error(`${key} 는 string 이어야 합니다`);
    if (spec.type === 'integer' && !Number.isInteger(val)) throw new Error(`${key} 는 integer 여야 합니다`);
    if (spec.type === 'array' && !Array.isArray(val)) throw new Error(`${key} 는 array 여야 합니다`);
    if (spec.type === 'object' && (typeof val !== 'object' || Array.isArray(val))) {
      throw new Error(`${key} 는 object 여야 합니다`);
    }
    if (spec.enum && !spec.enum.includes(val)) {
      throw new Error(`${key} 는 다음 중 하나여야 합니다: ${spec.enum.join(', ')}`);
    }
  }
}

/* ────────────────────────────── 디스패치 ────────────────────────────── */

async function handleMessage(msg) {
  const hasId = msg !== null && typeof msg === 'object' && 'id' in msg;
  const id = hasId ? msg.id : null;

  if (typeof msg !== 'object' || msg === null || Array.isArray(msg) || typeof msg.method !== 'string') {
    return fail(null, -32600, 'Invalid Request');
  }

  switch (msg.method) {
    case 'initialize': {
      const requested = msg.params?.protocolVersion;
      const protocolVersion = SUPPORTED_PROTOCOLS.includes(requested)
        ? requested
        : SUPPORTED_PROTOCOLS[0];
      return ok(id, { protocolVersion, capabilities: { tools: {} }, serverInfo: SERVER_INFO });
    }

    case 'notifications/initialized':
    case 'notifications/cancelled':
      return; // notification — 응답하지 않는다

    case 'ping':
      return hasId ? ok(id, {}) : undefined;

    case 'tools/list':
      return ok(id, { tools: TOOLS });

    case 'tools/call': {
      const name = msg.params?.name;
      const tool = TOOLS.find((t) => t.name === name);
      if (!tool) return fail(id, -32602, `알 수 없는 툴: ${name}`);

      const args = msg.params?.arguments ?? {};
      try {
        validateArgs(tool, args);
      } catch (e) {
        return fail(id, -32602, `Invalid params: ${e.message}`);
      }

      try {
        return ok(id, await HANDLERS[name](args));
      } catch (e) {
        // 툴 실행 실패는 JSON-RPC error 가 아니라 isError 결과다
        if (!(e instanceof ConfigError) && !e.userFacing) log('tool error', name, e.stack ?? e.message);
        return ok(id, toolError(e.message));
      }
    }

    default:
      return hasId ? fail(id, -32601, `Method not found: ${msg.method}`) : undefined;
  }
}

/* ────────────────────────── NDJSON 입력 루프 ────────────────────────── */

let buffer = '';
const queue = [];
let draining = false;
let inputEnded = false;

async function drain() {
  if (draining) return;
  draining = true;
  while (queue.length) {
    const line = queue.shift();
    try {
      await handleMessage(JSON.parse(line));
    } catch (e) {
      if (e instanceof SyntaxError) fail(null, -32700, 'Parse error');
      else log('unhandled', e.stack ?? e.message); // 루프는 계속 산다
    }
  }
  draining = false;

  // stdin 이 이미 끝났다면 여기가 마지막 지점이다. process.exit() 로 강제 종료하면
  // 진행 중이던 async 툴의 응답이 stdout 에 쓰이기 전에 잘린다 — exitCode 만 세우고
  // 이벤트 루프가 자연히 비어 종료되게 둔다.
  if (inputEnded && !queue.length) process.exitCode = 0;
}

process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  buffer += chunk;
  let nl;
  while ((nl = buffer.indexOf('\n')) !== -1) {
    const line = buffer.slice(0, nl).trim();
    buffer = buffer.slice(nl + 1);
    if (line) queue.push(line);
  }
  drain();
});
process.stdin.on('end', () => {
  inputEnded = true;
  const tail = buffer.trim();       // 개행 없이 끝난 마지막 줄도 처리한다
  buffer = '';
  if (tail) queue.push(tail);
  drain();
});
process.on('uncaughtException', (e) => log('uncaught', e.stack ?? e.message));
process.on('unhandledRejection', (e) => log('unhandledRejection', e?.stack ?? String(e)));

log(`started (node ${process.version})`);
