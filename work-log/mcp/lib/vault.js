/**
 * vault 스캔 · 파싱 · 경로 가드 · 안전 쓰기 · 인덱스 I/O.
 *
 * 원칙: sync 는 vault 에 0 바이트를 쓴다. 인덱스는 XDG cache(기본 ~/.cache)에 둔다.
 * vault 쓰기가 일어나는 유일한 경로는 writeDoc() 이다.
 */

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { cacheDirFor, DEFAULT_EXCLUDES } from './config.js';
import { markdownLines } from './markdown.js';
import { ioTransaction } from './io.js';

const MD = '.md';

// [[...]] 대상이 이 확장자면 문서 링크가 아니라 첨부 임베드다 (![[Pasted image.png]]).
// 링크 그래프에 넣으면 brokenLinks 가 전부 첨부로 채워져 진짜 깨진 링크가 묻힌다.
const ATTACHMENT_EXT = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.avif',
  '.pdf', '.mp4', '.mov', '.webm', '.mp3', '.wav', '.m4a', '.ogg',
  '.zip', '.xlsx', '.pptx', '.docx',
]);
const HTML = '.html';
export const INDEX_VERSION = 2;

const TYPE_SUFFIXES = ['plan', 'report', 'design', 'note', 'spec', 'meeting', 'decision'];
const FOLDER_TYPE = {
  '회의': 'meeting',
  '의사 결정': 'decision',
  '보고용': 'report',
  '정리된 문서': 'spec',
  'todo': 'note',
  'claude': 'note',
  'codex': 'note',
};

const nfc = (s) => s.normalize('NFC');
const sha1 = (buf) => crypto.createHash('sha1').update(buf).digest('hex').slice(0, 12);

/* ────────────────────────────── 경로 가드 ────────────────────────────── */

/** 존재하는 가장 가까운 조상을 realpath 로 풀고 나머지 세그먼트를 이어붙인다. */
function realpathAllowingMissing(target) {
  let head = path.resolve(target);
  const tail = [];
  for (;;) {
    try {
      return path.join(fs.realpathSync(head), ...tail);
    } catch {
      const parent = path.dirname(head);
      if (parent === head) return path.resolve(target); // 루트까지 실패
      tail.unshift(path.basename(head));
      head = parent;
    }
  }
}

/**
 * vault 상대 경로를 검증해 절대 경로로 바꾼다.
 * 문자열 접두사 비교를 쓰지 않는다 ( /vault 와 /vault-other 를 혼동한다 ).
 * @throws {Error} 탈출·제외폴더·확장자 위반
 */
export function safeResolve(vaultRoot, relPath, { forWrite = false } = {}) {
  if (typeof relPath !== 'string' || relPath.trim() === '') {
    throw new Error('경로가 비어 있습니다');
  }
  if (path.isAbsolute(relPath)) {
    throw new Error(`vault 상대 경로만 허용합니다: ${relPath}`);
  }

  const rootReal = fs.realpathSync(vaultRoot);
  const target = realpathAllowingMissing(path.resolve(rootReal, relPath));
  const rel = path.relative(rootReal, target);

  if (rel === '' || rel.startsWith('..') || path.isAbsolute(rel)) {
    throw new Error(`vault 밖의 경로입니다: ${relPath}`);
  }
  const segments = rel.split(path.sep);
  const hit = segments.find((s) => DEFAULT_EXCLUDES.includes(s));
  if (hit) throw new Error(`제외된 폴더입니다 (${hit}): ${relPath}`);

  const ext = path.extname(target).toLowerCase();
  if (forWrite && ext !== MD) throw new Error(`쓰기는 .md 만 허용합니다: ${relPath}`);
  if (!forWrite && ext !== MD && ext !== HTML) {
    throw new Error(`읽기는 .md/.html 만 허용합니다: ${relPath}`);
  }
  return { abs: target, rel, ext };
}

/* ────────────────────────────── 파싱 ────────────────────────────── */

/** 변경하지 않은 YAML 블록은 파싱/재직렬화하지 않고 그대로 보존한다. */
function frontmatterBlocks(raw, strict = false) {
  const blocks = [];
  for (const line of raw.match(/[^\n]*\n|[^\n]+$/g) ?? []) {
    if (strict && !blocks.some((b) => b.key !== undefined) &&
        (/^[ \t]+\S/.test(line) && !/^\s*#/.test(line) || /^[{[]/.test(line))) {
      throw new Error('지원하지 않는 YAML 루트 구조는 수정하지 않습니다');
    }
    const match = line.match(/^("(?:\\.|[^"\\])*"|'(?:''|[^'])*'|[^\s#?:][^:\r\n]*):(?=[ \t\r\n]|$)/);
    const key = match ? yamlString(match[1]) : undefined;
    if (strict && !match && /^\S/.test(line) && !/^(?:#|-(?:\s|$))/.test(line)) {
      throw new Error('지원하지 않는 YAML 구조는 수정하지 않습니다');
    }
    if (match || !blocks.length) blocks.push({ key, value: match ? line.slice(match[0].length).trim() : '', raw: line });
    else blocks[blocks.length - 1].raw += line;
  }
  return blocks;
}

function yamlString(value) {
  const v = value.trim();
  const quoted = v.match(/^("(?:\\.|[^"\\])*")(?:\s+#.*)?$/);
  if (quoted) {
    try { return JSON.parse(quoted[1]); } catch { return v; }
  }
  const single = v.match(/^'((?:''|[^'])*)'(?:\s+#.*)?$/);
  if (single) return single[1].replace(/''/g, "'");
  return v.replace(/\s+#.*$/, '');
}

/** 인덱싱에 필요한 문자열/배열만 읽고, 나머지 YAML 은 raw 에 보존한다. */
export function splitFrontmatter(text) {
  const match = text.match(/^---\r?\n([\s\S]*?)^---[ \t]*\r?$(?:\n)?/m);
  if (!match || match.index !== 0) return { frontmatter: null, body: text, raw: '' };
  const raw = match[1];
  const fm = {};
  for (const { key, value, raw: block } of frontmatterBlocks(raw)) {
    if (!key) continue;
    const val = value.replace(/("(?:\\.|[^"\\])*"|'(?:''|[^'])*')|(?:^|\s+)#.*$/g, '$1').trim();
    if (val.startsWith('[') && val.endsWith(']')) {
      fm[key] = [...val.slice(1, -1).matchAll(/(?:^|,)\s*("(?:\\.|[^"\\])*"|'(?:''|[^'])*'|[^,]*)(?=\s*(?:,|$))/g)]
        .map((m) => yamlString(m[1])).filter(Boolean);
    } else if (!val && /^\s*-\s+/m.test(block)) {
      fm[key] = [...block.matchAll(/^\s*-\s+(.+)$/gm)].map((m) => yamlString(m[1]));
    } else {
      fm[key] = yamlString(val);
    }
  }
  return { frontmatter: fm, body: text.slice(match[0].length), raw };
}

/** frontmatter 객체를 YAML 블록으로 직렬화한다. */
export function renderFrontmatter(fm) {
  const lines = Object.entries(fm).map(([k, v]) =>
    `${/^[A-Za-z_][\w-]*$/.test(k) ? k : JSON.stringify(k)}: ${JSON.stringify(v)}`
  );
  return `---\n${lines.join('\n')}\n---\n\n`;
}

const INDEX_SCALARS = ['title', 'type', 'status', 'created', 'updated'];
const yamlValue = (value) => value.replace(/("(?:\\.|[^"\\])*"|'(?:''|[^'])*')|(?:^|\s+)#.*$/g, '$1').trim();
const nonStringYaml = (value) => /^[{[]/.test(value) ||
  /^(?:null|~|true|false|[-+]?(?:\d[\d_]*(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?|0x[0-9a-f]+|[-+]?\.(?:inf|nan))$/i.test(value);

/** Indexing fields have known types; unknown Obsidian metadata remains untouched. */
export function validateFrontmatter(fm, raw = '') {
  if (fm === undefined || fm === null) return;
  if (typeof fm !== 'object' || Array.isArray(fm)) throw new Error('frontmatter 는 객체여야 합니다');
  for (const key of INDEX_SCALARS) {
    if (Object.hasOwn(fm, key) && typeof fm[key] !== 'string') {
      throw new Error(`frontmatter.${key} 는 문자열이어야 합니다`);
    }
  }
  if (Object.hasOwn(fm, 'tags') && typeof fm.tags !== 'string' &&
      !(Array.isArray(fm.tags) && fm.tags.every((tag) => typeof tag === 'string'))) {
    throw new Error('frontmatter.tags 는 문자열 또는 문자열 배열이어야 합니다');
  }
  for (const { key, value, raw: block } of frontmatterBlocks(raw)) {
    const val = yamlValue(value);
    if (INDEX_SCALARS.includes(key) && (nonStringYaml(val) ||
        (!val && /^[ \t]+[^\s#][^\n]*:\s/m.test(block)))) {
      throw new Error(`frontmatter.${key} 는 YAML 문자열이어야 합니다`);
    }
    if (key === 'tags') {
      const values = val.startsWith('[')
        ? [...val.slice(1, -1).matchAll(/(?:^|,)\s*("(?:\\.|[^"\\])*"|'(?:''|[^'])*'|[^,]*)(?=\s*(?:,|$))/g)].map((m) => m[1].trim())
        : !val ? [...block.matchAll(/^\s*-\s+(.+)$/gm)].map((m) => yamlValue(m[1])) : [val];
      if (values.some(nonStringYaml)) throw new Error('frontmatter.tags 는 YAML 문자열 목록이어야 합니다');
    }
  }
}

function mergeFrontmatter(existingRaw, incomingRaw, overrides) {
  const blocks = frontmatterBlocks(existingRaw, true);
  const updates = [...frontmatterBlocks(incomingRaw, true),
    ...Object.entries(overrides).map(([key, value]) => ({ key, raw: `${JSON.stringify(key)}: ${JSON.stringify(value)}\n` }))];
  for (const update of updates) {
    if (!update.key) continue;
    const matches = blocks.filter((b) => b.key === update.key);
    if (matches.length > 1) throw new Error(`중복 frontmatter 키는 안전하게 수정할 수 없습니다: ${update.key}`);
    const i = blocks.findIndex((b) => b.key === update.key);
    if (i === -1) blocks.push(update);
    else blocks[i] = update;
  }
  return `---\n${blocks.map((b) => b.raw).join('')}---\n\n`;
}

/** 파일명에서 YYYYMMDD- 접두사와 -type 접미사를 떼어 사람이 읽을 제목을 만든다. */
function stemToTitle(rel) {
  const ext = path.extname(rel);
  let stem = path.basename(rel, ext).replace(/^\d{8}-/, '');
  const suffix = stem.split('-').pop();
  if (TYPE_SUFFIXES.includes(suffix) && stem.includes('-')) {
    stem = stem.slice(0, -(suffix.length + 1));
  }
  return stem;
}

function inferType(rel, fm) {
  if (fm?.type && TYPE_SUFFIXES.includes(fm.type)) return fm.type;
  const stem = path.basename(rel, path.extname(rel));
  const suffix = stem.split('-').pop();
  if (TYPE_SUFFIXES.includes(suffix)) return suffix;
  const top = rel.split(path.sep)[0];
  return FOLDER_TYPE[top] ?? 'note';
}

function inferTags(rel) {
  const segs = rel.split(path.sep);
  const tags = new Set();
  if (segs.length > 1) tags.add(nfc(segs[0]));
  const stem = path.basename(rel, path.extname(rel)).replace(/^\d{8}-/, '');
  // 하이픈·언더스코어·공백을 모두 토큰 경계로 본다 ("02_기능정의서" -> "기능정의서")
  for (const tok of stem.split(/[-_\s]+/)) {
    const t = tok.replace(/^\d+$/, '');
    if (t.length >= 2) tags.add(nfc(t.toLowerCase()));
  }
  for (const t of TYPE_SUFFIXES) tags.delete(t);   // type 은 별도 필드다 — 태그로 중복시키지 않는다
  return [...tags].slice(0, 12);
}

function inferCreated(rel, mtimeMs) {
  const m = path.basename(rel).match(/^(\d{4})(\d{2})(\d{2})-/);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;
  return new Date(mtimeMs).toISOString().slice(0, 10);
}

/** md 본문에서 인덱스 필드를 뽑는다. */
function parseMarkdown(rel, text, stat) {
  const { frontmatter, body, raw } = splitFrontmatter(text);
  validateFrontmatter(frontmatter, raw);

  const headings = [];
  let h1 = null;
  const lines = markdownLines(body);
  for (const { heading } of lines) {
    if (!heading) continue;
    const title = heading.title.replace(/[*_`]/g, '').trim();
    if (heading.level === 1 && h1 === null) h1 = title;
    headings.push(nfc(title));
    if (headings.length >= 60) break;
  }

  // 본문 앞부분 — summary(200자) 와 랭킹용 excerpt(1500자)
  const prose = lines.filter(({ code }) => !code).map(({ text }) => text).join('\n');
  const plain = prose
    .replace(/^#{1,6}\s+.*$/gm, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  // 링크는 코드를 걷어낸 본문에서만 뽑는다. Obsidian 도 코드 안의 [[...]] 는 링크로 만들지
  // 않는다 — bash 의 [[ "$f" == x* ]] 조건문과 문서화 예시가 그대로 오탐이 된다.
  const linkable = prose.replace(/`[^`\n]*`/g, ' ');

  const links = [];
  for (const m of linkable.matchAll(/\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]/g)) {
    const target = nfc(m[1].trim());
    if (ATTACHMENT_EXT.has(path.extname(target).toLowerCase())) continue;
    links.push(target);
  }

  const title = nfc(frontmatter?.title || h1 || stemToTitle(rel));
  const tags = (Array.isArray(frontmatter?.tags) ? frontmatter.tags : [frontmatter?.tags])
    .filter((tag) => typeof tag === 'string' && tag.trim()).map(nfc);

  return {
    title,
    type: inferType(rel, frontmatter),
    tags: tags.length ? tags : inferTags(rel),
    status: frontmatter?.status || 'active',
    summary: plain.slice(0, 200),
    excerpt: plain.slice(0, 1500),
    headings: headings.slice(0, 30),
    links: [...new Set(links)],
    created: frontmatter?.created || inferCreated(rel, stat.mtimeMs),
    hasFrontmatter: Boolean(frontmatter),
  };
}

/** html 은 제목만 뽑는다. 렌더링 마크업 본문은 인덱싱하지 않는다. */
function parseHtmlTitle(rel, text) {
  const t = text.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1]
    ?? text.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i)?.[1];
  const cleaned = t ? t.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim() : '';
  return nfc(cleaned || stemToTitle(rel));
}

/* ────────────────────────────── 스캔 ────────────────────────────── */

function scanError(errors, root, abs, operation, error) {
  if (error.code !== 'ENOENT') errors.push({
    path: path.relative(root, abs), operation, code: error.code ?? 'INVALID_METADATA', message: error.message,
  });
}

function walk(dir, vaultRoot, excludes, errors, out = []) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch (error) {
    scanError(errors, vaultRoot, dir, 'readdir', error);
    return out;
  }
  for (const e of entries) {
    if (excludes.includes(e.name)) continue;
    const abs = path.join(dir, e.name);
    if (e.isDirectory()) {
      walk(abs, vaultRoot, excludes, errors, out);
    } else if (e.isFile()) {
      const ext = path.extname(e.name).toLowerCase();
      if (ext === MD || ext === HTML) out.push(path.relative(vaultRoot, abs));
    }
  }
  return out;
}

/**
 * vault 전체를 스캔해 인덱스를 만든다. v0.1 은 항상 전체 스캔 + 전체 해시다
 * (mtime+size 증분은 같은 크기의 내용 교체를 놓치고 삭제 감지도 어차피 전체 열거가 필요하다).
 */
export function buildIndex(cfg, { previous = null } = {}) {
  const started = performance.now();
  const { root, excludes = DEFAULT_EXCLUDES } = cfg;
  const errors = [];
  const files = walk(root, root, excludes, errors);
  let bytesRead = 0, filesRead = 0;

  const mdByStem = new Map();  // "dir/stem" -> doc
  const docs = [];
  const htmlPending = [];
  const keyCollisions = [];
  const seenKeys = new Map();

  for (const rel of files) {
    const abs = path.join(root, rel);
    let stat, buf;
    try {
      stat = fs.statSync(abs);
      buf = fs.readFileSync(abs);
    } catch (error) {
      scanError(errors, root, abs, 'read', error);
      continue; // 스캔 중 사라진 파일
    }
    bytesRead += buf.length;
    filesRead++;
    const ext = path.extname(rel).toLowerCase();
    const key = nfc(rel);

    const prev = seenKeys.get(key);
    if (prev && prev !== rel) keyCollisions.push({ a: prev, b: rel, key });
    seenKeys.set(key, rel);

    const common = {
      path: rel,                 // 원본 바이트 — I/O 전용
      key,                       // NFC — 매칭 전용
      mtime: Math.floor(stat.mtimeMs),
      size: stat.size,
      hash: sha1(buf),
    };

    if (ext === MD) {
      let parsed;
      try {
        parsed = parseMarkdown(rel, buf.toString('utf8'), stat);
      } catch (error) {
        scanError(errors, root, abs, 'parse', error);
        continue;
      }
      const doc = { ...common, kind: 'md', ...parsed, companions: [] };
      docs.push(doc);
      mdByStem.set(path.join(path.dirname(rel), path.basename(rel, MD)), doc);
    } else {
      htmlPending.push({ ...common, ext, text: buf.toString('utf8'), stat });
    }
  }

  // Keep last known entries for failed files/subtrees before recomputing twins and links.
  const affected = (rel) => errors.some((e) => rel === e.path ||
    (e.operation === 'readdir' && (!e.path || rel.startsWith(e.path + path.sep))));
  for (const old of previous?.docs ?? []) {
    if (affected(old.path) && !docs.some((d) => d.key === old.key)) {
      const kept = { ...old, stale: true, companions: [] };
      docs.push(kept);
      if (kept.kind === 'md') mdByStem.set(path.join(path.dirname(kept.path), path.basename(kept.path, MD)), kept);
    }
  }

  // twin 병합: 같은 디렉토리·같은 stem 의 html 은 md 의 companion 으로 접는다.
  for (const h of htmlPending) {
    const stem = path.join(path.dirname(h.path), path.basename(h.path, HTML));
    const canonical = mdByStem.get(stem);
    if (canonical) {
      canonical.companions.push({
        path: h.path, mtime: h.mtime, size: h.size, hash: h.hash,
      });
    } else {
      docs.push({
        path: h.path, key: h.key, kind: 'html',
        title: parseHtmlTitle(h.path, h.text),
        type: inferType(h.path, null),
        tags: inferTags(h.path),
        status: 'active',
        summary: '', excerpt: '', headings: [], links: [],
        created: inferCreated(h.path, h.stat.mtimeMs),
        hasFrontmatter: false, companions: [],
        mtime: h.mtime, size: h.size, hash: h.hash,
      });
    }
  }
  for (const old of previous?.docs ?? []) {
    const canonical = docs.find((d) => d.key === old.key);
    for (const companion of old.companions ?? []) {
      if (canonical && affected(companion.path) && !canonical.companions.some((c) => c.path === companion.path)) {
        canonical.companions.push({ ...companion, stale: true });
      }
    }
  }

  // 링크 그래프는 문서 하나만 바뀌어도 전역 재계산이 필요하다.
  const byKey = new Map(docs.map((d) => [d.key, d]));
  const backlinks = {};
  const brokenLinks = [];
  const ambiguousLinks = [];
  const linked = new Set();

  for (const d of docs) {
    for (const raw of d.links) {
      const { target, candidates } = resolveLink(raw, d.path, byKey);
      if (!target) {
        if (candidates.length > 1) ambiguousLinks.push({ from: d.path, to: raw, candidates });
        else brokenLinks.push({ from: d.path, to: raw });
        continue;
      }
      (backlinks[target] ??= []).push(d.path);
      linked.add(target);
    }
  }
  const orphans = docs
    .filter((d) => !linked.has(d.key) && d.kind === 'md')
    .map((d) => d.path);

  return {
    version: INDEX_VERSION,
    status: errors.length ? 'DEGRADED' : 'OK',
    errors,
    scope: cfg.scope ?? 'global',   // 마지막 sync 시점 스냅샷 — 권위 없음
    root,
    generatedAt: new Date().toISOString(),
    counts: {
      canonical: docs.filter((d) => d.kind === 'md').length,
      htmlOnly: docs.filter((d) => d.kind === 'html').length,
      companions: docs.reduce((n, d) => n + d.companions.length, 0),
      files: new Set([...files, ...docs.flatMap((d) => [d.path, ...d.companions.map((c) => c.path)])]).size,
    },
    scan: { filesDiscovered: files.length, filesRead, bytesRead, errors: errors.length, durationMs: Math.round(performance.now() - started) },
    docs,
    backlinks,
    brokenLinks,
    ambiguousLinks,
    orphans,
    keyCollisions,
  };
}

/** [[링크]] 를 인덱스 키로 해석한다. 확장자 생략·상대경로·파일명만 쓰기를 모두 지원. */
function resolveLink(raw, fromPath, byKey) {
  const candidates = [];
  const withExt = raw.endsWith(MD) ? raw : `${raw}${MD}`;
  candidates.push(nfc(path.normalize(path.join(path.dirname(fromPath), withExt))));
  candidates.push(nfc(path.normalize(withExt)));
  for (const c of candidates) if (byKey.has(c)) return { target: c, candidates: [] };

  // 파일명만 적은 경우 — 전체에서 basename 일치 탐색
  const base = nfc(path.basename(withExt));
  const matches = raw.includes('/') || raw.includes('\\') ? []
    : [...byKey.keys()].filter((k) => path.basename(k) === base).sort();
  return { target: matches.length === 1 ? matches[0] : null, candidates: matches };
}

/* ────────────────────────── 인덱스 I/O (vault 밖) ────────────────────────── */

export function indexPaths(vaultRoot) {
  const { dir } = cacheDirFor(vaultRoot);
  return {
    dir,
    file: path.join(dir, 'index.json'),
    lock: path.join(dir, 'index.lock'),
    marker: path.join(dir, 'vault-path.txt'),
  };
}

export function readIndex(vaultRoot) {
  return readIndexState(vaultRoot).index;
}

export function readIndexState(vaultRoot) {
  const { file } = indexPaths(vaultRoot);
  try {
    return parseIndexState(vaultRoot, fs.readFileSync(file, 'utf8'));
  } catch (error) {
    return { index: null, reason: error.code === 'ENOENT' ? 'INDEX_MISSING' : 'INDEX_INVALID' };
  }
}

function parseIndexState(vaultRoot, raw) {
  try {
    if (raw === null) return { index: null, reason: 'INDEX_MISSING' };
    const index = JSON.parse(raw);
    const strings = (v) => Array.isArray(v) && v.every((s) => typeof s === 'string');
    const numbers = (v, keys) => v && keys.every((k) => Number.isFinite(v[k]) && v[k] >= 0);
    if (!index || index.version !== INDEX_VERSION) return { index: null, reason: 'INDEX_VERSION' };
    if (typeof index.root !== 'string' || fs.realpathSync(index.root) !== fs.realpathSync(vaultRoot)) {
      return { index: null, reason: 'INDEX_ROOT' };
    }
    if (!['OK', 'DEGRADED'].includes(index.status) || !Number.isFinite(Date.parse(index.generatedAt)) ||
        !Array.isArray(index.errors) || !index.errors.every((e) => e &&
          ['path', 'operation', 'code', 'message'].every((k) => typeof e[k] === 'string')) ||
        !numbers(index.scan, ['filesDiscovered', 'filesRead', 'bytesRead', 'errors', 'durationMs']) ||
        !numbers(index.counts, ['canonical', 'htmlOnly', 'companions', 'files']) ||
        !index.backlinks || typeof index.backlinks !== 'object' || !Object.values(index.backlinks).every(strings) ||
        !strings(index.orphans) || !Array.isArray(index.brokenLinks) || !Array.isArray(index.ambiguousLinks) ||
        !Array.isArray(index.keyCollisions) || !Array.isArray(index.docs) || !index.docs.every((d) => d &&
        ['path', 'key', 'title', 'type', 'hash', 'summary', 'excerpt', 'created', 'status'].every((k) => typeof d[k] === 'string') &&
        d.path && !path.isAbsolute(d.path) && !d.path.split(path.sep).includes('..') && d.key === nfc(d.path) &&
        ['md', 'html'].includes(d.kind) && numbers(d, ['mtime', 'size']) &&
        ['tags', 'headings', 'links'].every((k) => strings(d[k])) &&
        Array.isArray(d.companions) && d.companions.every((c) => c && typeof c.path === 'string' && typeof c.hash === 'string'))) {
      return { index: null, reason: 'INDEX_SCHEMA' };
    }
    return { index, reason: null };
  } catch (error) {
    return { index: null, reason: error.code === 'ENOENT' ? 'INDEX_MISSING' : 'INDEX_INVALID' };
  }
}

/** The helper holds the cache lock throughout scan and atomic publication. */
export async function syncIndex(cfg) {
  const { dir } = indexPaths(cfg.root);
  const { value } = await ioTransaction({ operation: 'index', root: dir, relPath: 'index.json', vaultRoot: cfg.root }, (raw) => {
    const before = parseIndexState(cfg.root, raw).index;
    const index = buildIndex(cfg, { previous: before });
    return { content: JSON.stringify(index), value: { index, drift: diffIndex(before, index) } };
  });
  return value;
}

function diffIndex(before, after) {
  const prev = new Map((before?.docs ?? []).map((d) => [d.key, d]));
  const next = new Map(after.docs.map((d) => [d.key, d]));

  const added = [];
  const changed = [];
  for (const [k, d] of next) {
    const p = prev.get(k);
    if (!p) added.push(d.path);
    else if (p.hash !== d.hash || companionSig(p) !== companionSig(d)) changed.push(d.path);
  }
  const removed = [...prev.keys()].filter((k) => !next.has(k)).map((k) => prev.get(k).path);

  // orphan 은 링크 그래프가 성숙해야 의미가 있다. 실측상 [[링크]] 보유 문서가 4% 뿐이라
  // 거의 모든 문서가 orphan 으로 잡힌다 — 목록을 그대로 쏟으면 리포트가 노이즈가 된다.
  // 링크가 실제로 존재하는 문서 비율이 낮으면 개수만 보고한다.
  const linkedRatio = after.docs.length
    ? after.docs.filter((d) => d.links.length).length / after.docs.length
    : 0;

  return {
    firstRun: !before,
    added, changed, removed,
    brokenLinks: after.brokenLinks,
    ambiguousLinks: after.ambiguousLinks,
    orphanCount: after.orphans.length,
    orphans: linkedRatio >= 0.3 ? after.orphans : [],
    orphansSuppressed: linkedRatio < 0.3,
    linkedRatio: Number(linkedRatio.toFixed(3)),
    keyCollisions: after.keyCollisions,
    noFrontmatter: after.docs.filter((d) => d.kind === 'md' && !d.hasFrontmatter).length,
  };
}

const companionSig = (d) => (d.companions ?? []).map((c) => `${c.path}:${c.hash}`).sort().join('|');

/* ────────────────────────────── 안전 쓰기 ────────────────────────────── */

/**
 * vault 에 문서를 쓴다. 이것이 vault 를 변경하는 유일한 경로다.
 * 읽기·hash 확인·쓰기를 문서별 프로세스 간 잠금으로 보호한다. create 는 완성된 파일의 exclusive link 로 원자 생성한다.
 */
export async function writeDoc(cfg, args) {
  if (args.frontmatter === null) throw new Error('frontmatter 는 객체여야 합니다');
  validateFrontmatter(args.frontmatter);
  const incoming = splitFrontmatter(args.content);
  if ((args.mode ?? 'create') !== 'append') validateFrontmatter(incoming.frontmatter, incoming.raw);
  safeResolve(cfg.root, args.relPath, { forWrite: true });
  const { value, durability, cleanupWarnings } = await ioTransaction({
    operation: 'write', root: cfg.root, relPath: args.relPath, mode: args.mode ?? 'create', excludes: DEFAULT_EXCLUDES,
  }, (existing, rel) => {
    const final = renderDocument(existing, rel, args);
    return { content: final, value: { path: rel, bytes: Buffer.byteLength(final), hash: sha1(Buffer.from(final)), mode: args.mode ?? 'create' } };
  });
  return { ...value, durability, cleanupWarnings };
}

function renderDocument(existing, rel, { content, frontmatter, mode = 'create', expectedHash }) {
  if (mode === 'create' && existing !== null) {
    throw new Error(`파일이 이미 있습니다. 덮어쓰려면 mode:"overwrite" 를 명시하세요: ${rel}`);
  }
  if (mode !== 'create' && existing === null) {
    throw new Error(`대상 파일이 없습니다: ${rel}`);
  }
  if (existing !== null && expectedHash) {
    const now = sha1(Buffer.from(existing, 'utf8'));
    if (now !== expectedHash) {
      throw new Error(`파일이 그 사이 변경되었습니다 (expected ${expectedHash}, actual ${now}). 다시 읽고 시도하세요.`);
    }
  }

  const existingFm = existing !== null ? splitFrontmatter(existing).frontmatter : null;

  // 비파괴 규칙: frontmatter 가 없는 기존 문서에는 어떤 경로로도 주입하지 않는다.
  const contentStartsFm = content.trimStart().startsWith('---');
  // append 는 내용을 파일 끝에 붙이므로 선두 "---" 는 markdown 수평선이지 frontmatter 가
  // 될 수 없다 (frontmatter 는 파일 맨 앞에서만 성립). frontmatter 인자 차단은 전 모드 유지.
  const injectsFm = Boolean(frontmatter) || (mode !== 'append' && contentStartsFm);
  if (existing !== null && !existingFm && injectsFm) {
    throw new Error(
      `frontmatter 가 없는 기존 문서에는 frontmatter 를 주입하지 않습니다: ${rel} ` +
      `(content 가 "---" 로 시작하거나 frontmatter 인자가 전달되었습니다)`
    );
  }

  let final;
  if (mode === 'append') {
    final = existing.replace(/\s*$/, '') + '\n\n' + content.replace(/^\s+/, '');
  } else if (existing === null) {
    // 신규 문서 — frontmatter 를 부여한다
    const today = new Date().toISOString().slice(0, 10);
    const fm = contentStartsFm
      ? null
      : {
          title: frontmatter?.title || stemToTitle(rel),
          type: frontmatter?.type || inferType(rel, null),
          tags: frontmatter?.tags || inferTags(rel),
          status: frontmatter?.status || 'draft',
          created: frontmatter?.created || today,
          updated: today,
          ...Object.fromEntries(
            Object.entries(frontmatter ?? {}).filter(
              ([k]) => !['title', 'type', 'tags', 'status', 'created', 'updated'].includes(k)
            )
          ),
        };
    final = fm ? renderFrontmatter(fm) + content.replace(/^\s+/, '') : content;
  } else {
    // overwrite — 기존 frontmatter 가 있으면 모르는 키를 보존하고 병합
    const bodyOnly = splitFrontmatter(content).frontmatter
      ? splitFrontmatter(content).body
      : content;
    if (existingFm) {
      final = mergeFrontmatter(splitFrontmatter(existing).raw, splitFrontmatter(content).raw, {
        ...(frontmatter ?? {}), updated: new Date().toISOString().slice(0, 10),
      }) + bodyOnly.replace(/^\s+/, '');
    } else {
      final = bodyOnly;
    }
  }

  const parsedFinal = splitFrontmatter(final);
  validateFrontmatter(parsedFinal.frontmatter, parsedFinal.raw);
  return final;
}

export { nfc, sha1 };
