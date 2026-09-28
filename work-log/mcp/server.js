#!/usr/bin/env node
/**
 * work-log MCP 서버 — Node stdio JSON-RPC; write/sync use the Python POSIX helper.
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
  syncIndex, readIndexState, safeResolve, splitFrontmatter, writeDoc, indexPaths,
} from './lib/vault.js';
import { rank, extractSection, applyBudget } from './lib/search.js';
import { ioCapability } from './lib/io.js';

const SERVER_INFO = { name: 'work-log', version: '0.3.1' };
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
      'work-log 인덱스에서 문서 후보를 점수순으로 반환한다. 본문은 주지 않고 후보마다 path, title, type, kind(md/html), tags, created, ' +
      'summary(본문 앞 200자), snippet, companions(같은 폴더·같은 이름의 .html 경로), score 를, total 에 일치 문서 수를 준다. ' +
      'query 를 공백으로 나눈 단어마다 title·tags·headings·경로·본문 앞부분(코드 블록 제외)에서 대소문자를 무시한 부분 문자열로 찾아 ' +
      '가중 합산하고, 모든 단어가 맞는 문서에 가산점을 준다(형태소 분석 없음, 동점은 최근 수정순). ' +
      '일치가 없으면 candidates: [], emptyResult: true 와 vault 상위 태그 hintTags 를 반환한다. ' +
      '인덱스는 마지막 wiki_sync·wiki_write 시점 기준이라 그 뒤 vault 에 직접 추가·수정한 문서는 wiki_sync 전까지 보이지 않고, ' +
      '인덱스가 없거나 현재 서버와 호환되지 않으면 wiki_sync 를 요구하는 오류를 반환한다. 본문은 반환된 path 로 wiki_read 를 호출해 읽는다.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['query'],
      properties: {
        query: { type: 'string', description: '검색어. 공백으로 나눈 단어를 각각 찾는다(모든 단어가 맞는 문서에 가산점)' },
        type: { type: 'string', enum: TYPE_ENUM, description: '문서 종류 필터. frontmatter type, 없으면 파일명 접미사(-plan 등)나 최상위 폴더로 추론한 종류와 정확히 같아야 한다' },
        tags: { type: 'array', items: { type: 'string' }, description: '태그 필터. 넘긴 태그마다 문서 태그 하나에 부분 문자열로 포함돼야 한다(모두 만족, 대소문자 무시)' },
        limit: { type: 'integer', minimum: 1, maximum: 20, default: 5, description: '반환할 후보 수 (기본 5, 최대 20)' },
      },
    },
  },
  {
    name: 'wiki_read',
    description:
      'work-log 문서 하나를 인덱스 없이 파일에서 직접 읽는다. .md 는 { path, citation, frontmatter(없으면 null), body(frontmatter 제외), ' +
      'matchedHeading, sectionNotFound, truncated, approximateBudget, chars } 를 반환한다. .html 은 본문 없이 ' +
      '{ path, kind: "html", note, absolutePath } 만 반환하므로 absolutePath 를 파일 읽기 도구로 연다. 파일 hash 는 반환하지 않는다.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['path'],
      properties: {
        path: { type: 'string', description: 'vault 상대 경로 (wiki_resolve 가 반환한 path, .md 또는 .html). 절대 경로·vault 밖·제외 폴더는 거부된다' },
        section: { type: 'string', description: '헤딩 텍스트 일부(대소문자 무시). 처음 일치한 헤딩부터 같거나 더 높은 수준의 다음 헤딩 직전까지 반환한다. 일치하는 헤딩이 없으면 본문 전체와 sectionNotFound: true 를 반환한다' },
        token_budget: { type: 'integer', minimum: 1, description: '근사 토큰 상한 (1토큰≈4자). 넘으면 잘라 내고 truncated: true 를 붙이며, chars 는 잘린 뒤 글자 수다' },
      },
    },
  },
  {
    name: 'wiki_write',
    description:
      'work-log vault 에 .md 문서 하나를 쓴다(삭제 기능은 없다). mode 로 새로 만들기(create)·본문 교체(overwrite)·끝에 덧붙이기(append)를 고른다. ' +
      'frontmatter 가 없는 기존 문서에 frontmatter 인자를 넘기면 거부된다(frontmatter 를 새로 주입하지 않는다). ' +
      '쓰기 뒤 인덱스를 다시 만들고 { written: {path, bytes, hash, mode, ...}, indexed, indexing: {status, errors, retry} } 를 반환한다. ' +
      'written 이 있으면 저장은 끝났으므로 indexing.status 가 OK 가 아니어도 같은 쓰기를 다시 보내지 말고 wiki_sync 만 호출한다. ' +
      '문서·인덱스 잠금을 5초 안에 얻지 못하면 실패한다.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['path', 'content'],
      properties: {
        path: { type: 'string', description: 'vault 상대 경로 (.md 만)' },
        content: { type: 'string', description: '본문' },
        frontmatter: { type: 'object', description: 'frontmatter 키 재정의. create: 자동 부여값을 덮고 키를 더한다. overwrite: 기존 frontmatter 에 병합한다(모르는 키 보존, updated 갱신). append: 반영되지 않는다' },
        mode: { type: 'string', enum: ['create', 'overwrite', 'append'], default: 'create', description: 'create(기본): 새 파일만 만든다 — 이미 있으면 실패. overwrite: 기존 본문을 content 로 교체. append: 기존 파일 끝에 덧붙인다. overwrite·append 는 파일이 없으면 실패한다' },
        expected_hash: { type: 'string', description: '낙관적 잠금. 현재 파일 전체 바이트의 SHA-1 hex 앞 12자이며 다르면 거부한다. 직전 wiki_write 응답의 written.hash 또는 불일치 오류의 actual 값이 이 형식이다(wiki_read 는 hash 를 주지 않는다)' },
      },
    },
  },
  {
    name: 'wiki_sync',
    description:
      'vault 의 .md/.html 을 모두 다시 읽어 인덱스를 재생성하고 drift 리포트를 반환한다. vault 파일은 변경하지 않는다. ' +
      'vault 에 직접 추가·수정한 문서를 검색에 반영하거나 인덱스 없음·호환 불가 오류를 해결할 때 호출한다(wiki_write 는 쓰기 뒤 자동으로 재생성한다). ' +
      '반환의 status 가 DEGRADED 이면 읽기·파싱에 실패한 항목이 errors 에 있다. 다른 sync·쓰기가 인덱스 잠금을 5초 넘게 쥐고 있으면 실패한다.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
  },
  {
    name: 'wiki_status',
    description:
      '읽기 전용 진단 툴이다. 스코프가 설정되지 않아도 오류 없이 { needsInit: true, hint, cwd, configSource, server, safeIO } 를 반환하므로 ' +
      '다른 wiki_ 툴보다 먼저 호출해도 된다. 설정돼 있으면 scope, root, indexPath, indexExists, indexAgeSeconds, generatedAt, counts, ' +
      'indexState(OK·DEGRADED 또는 INDEX_MISSING 등 재생성 사유), errors, scan 을 함께 반환한다. safeIO.available 이 false 이면 wiki_write·wiki_sync 가 동작하지 않는다.',
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
  const { index: idx, reason } = readIndexState(cfg.root);
  if (!idx) {
    const e = new Error(`인덱스를 다시 생성해야 합니다 (${reason}). wiki_sync 를 실행하세요.`);
    e.userFacing = true;
    throw e;
  }
  return idx;
}

const HANDLERS = {
  wiki_status() {
    const cfg = resolveConfig();
    const base = { cwd: cfg.cwd, configSource: cfg.configSource, server: SERVER_INFO.version, safeIO: ioCapability() };
    if (cfg.needsInit) return text({ ...base, needsInit: true, hint: cfg.hint });

    const { index: idx, reason } = readIndexState(cfg.root);
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
      indexState: reason ?? idx.status,
      errors: idx?.errors ?? [],
      scan: idx?.scan ?? null,
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
      status: index.status,
      errors: index.errors,
      scan: index.scan,
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
    // 그래프는 전역 재계산이 필요하다. scan 계측에서 지연이 확인되면 증분화를 검토한다.
    try {
      const { index } = await syncIndex(cfg);
      const entry = index.docs.find((d) => d.path === res.path) ?? null;
      return text({
        written: res,
        indexed: entry ? { title: entry.title, type: entry.type, tags: entry.tags } : null,
        indexing: { status: index.status, errors: index.errors, retry: index.status === 'OK' ? null : 'wiki_sync' },
      });
    } catch (error) {
      // Document storage already committed. Retrying the append would duplicate content.
      return text({ written: res, indexed: null, indexing: { status: 'FAILED', error: error.message, retry: 'wiki_sync' } });
    }
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
    if (spec.type === 'object' && (val === null || typeof val !== 'object' || Array.isArray(val))) {
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
        return ok(id, toolError(e.writeState ? JSON.stringify({ message: e.message, write_state: e.writeState,
          retry: e.writeState === 'unknown' ? 'wiki_read before deciding whether to retry' : null }) : e.message));
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
