/**
 * vault 스캔 · 파싱 · 경로 가드 · 안전 쓰기 · 인덱스 I/O.
 *
 * 원칙: sync 는 vault 에 0 바이트를 쓴다. 인덱스는 XDG cache(기본 ~/.cache)에 둔다.
 * vault 쓰기가 일어나는 유일한 경로는 writeDoc() 이다.
 */

import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { cacheDirFor, DEFAULT_EXCLUDES } from './config.js';

const MD = '.md';

// [[...]] 대상이 이 확장자면 문서 링크가 아니라 첨부 임베드다 (![[Pasted image.png]]).
// 링크 그래프에 넣으면 brokenLinks 가 전부 첨부로 채워져 진짜 깨진 링크가 묻힌다.
const ATTACHMENT_EXT = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.avif',
  '.pdf', '.mp4', '.mov', '.webm', '.mp3', '.wav', '.m4a', '.ogg',
  '.zip', '.xlsx', '.pptx', '.docx',
]);
const HTML = '.html';
export const INDEX_VERSION = 1;

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

/** frontmatter 를 분리한다. 값은 문자열/배열만 다루는 최소 YAML 처리. */
export function splitFrontmatter(text) {
  if (!text.startsWith('---')) return { frontmatter: null, body: text, raw: '' };
  const end = text.indexOf('\n---', 3);
  if (end === -1) return { frontmatter: null, body: text, raw: '' };

  const raw = text.slice(text.indexOf('\n') + 1, end + 1);
  const rest = text.slice(end + 4).replace(/^\r?\n/, '');
  const fm = {};
  for (const line of raw.split('\n')) {
    const m = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/);
    if (!m) continue;
    const [, key, valRaw] = m;
    const val = valRaw.trim();
    if (val.startsWith('[') && val.endsWith(']')) {
      fm[key] = val.slice(1, -1).split(',').map((s) => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
    } else {
      fm[key] = val.replace(/^["']|["']$/g, '');
    }
  }
  return { frontmatter: fm, body: rest, raw };
}

/** frontmatter 객체를 YAML 블록으로 직렬화한다. */
export function renderFrontmatter(fm) {
  const lines = Object.entries(fm).map(([k, v]) =>
    Array.isArray(v) ? `${k}: [${v.join(', ')}]` : `${k}: ${v}`
  );
  return `---\n${lines.join('\n')}\n---\n\n`;
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
  const { frontmatter, body } = splitFrontmatter(text);

  const headings = [];
  let h1 = null;
  for (const line of body.split('\n')) {
    const m = line.match(/^(#{1,6})\s+(.+?)\s*$/);
    if (!m) continue;
    const title = m[2].replace(/[*_`]/g, '').trim();
    if (m[1].length === 1 && h1 === null) h1 = title;
    headings.push(nfc(title));
    if (headings.length >= 60) break;
  }

  // 본문 앞부분 — summary(200자) 와 랭킹용 excerpt(1500자)
  const plain = body
    .replace(/^#{1,6}\s+.*$/gm, ' ')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  // 링크는 코드를 걷어낸 본문에서만 뽑는다. Obsidian 도 코드 안의 [[...]] 는 링크로 만들지
  // 않는다 — bash 의 [[ "$f" == x* ]] 조건문과 문서화 예시가 그대로 오탐이 된다.
  const linkable = body
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`\n]*`/g, ' ');

  const links = [];
  for (const m of linkable.matchAll(/\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]/g)) {
    const target = nfc(m[1].trim());
    if (ATTACHMENT_EXT.has(path.extname(target).toLowerCase())) continue;
    links.push(target);
  }

  const title = nfc(frontmatter?.title || h1 || stemToTitle(rel));

  return {
    title,
    type: inferType(rel, frontmatter),
    tags: frontmatter?.tags?.length ? frontmatter.tags.map(nfc) : inferTags(rel),
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

function walk(dir, vaultRoot, excludes, out = []) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const e of entries) {
    if (excludes.includes(e.name)) continue;
    const abs = path.join(dir, e.name);
    if (e.isDirectory()) {
      walk(abs, vaultRoot, excludes, out);
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
export function buildIndex(cfg) {
  const { root, excludes = DEFAULT_EXCLUDES } = cfg;
  const files = walk(root, root, excludes);

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
    } catch {
      continue; // 스캔 중 사라진 파일
    }
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
      const parsed = parseMarkdown(rel, buf.toString('utf8'), stat);
      const doc = { ...common, kind: 'md', ...parsed, companions: [] };
      docs.push(doc);
      mdByStem.set(path.join(path.dirname(rel), path.basename(rel, MD)), doc);
    } else {
      htmlPending.push({ ...common, ext, text: buf.toString('utf8'), stat });
    }
  }

  // twin 병합: 같은 디렉토리·같은 stem 의 html 은 md 의 companion 으로 접는다.
  let htmlOnly = 0;
  let companions = 0;
  for (const h of htmlPending) {
    const stem = path.join(path.dirname(h.path), path.basename(h.path, HTML));
    const canonical = mdByStem.get(stem);
    if (canonical) {
      canonical.companions.push({
        path: h.path, mtime: h.mtime, size: h.size, hash: h.hash,
      });
      companions++;
    } else {
      htmlOnly++;
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

  // 링크 그래프는 문서 하나만 바뀌어도 전역 재계산이 필요하다.
  const byKey = new Map(docs.map((d) => [d.key, d]));
  const backlinks = {};
  const brokenLinks = [];
  const linked = new Set();

  for (const d of docs) {
    for (const raw of d.links) {
      const target = resolveLink(raw, d.path, byKey);
      if (!target) {
        brokenLinks.push({ from: d.path, to: raw });
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
    scope: cfg.scope ?? 'global',   // 마지막 sync 시점 스냅샷 — 권위 없음
    root,
    generatedAt: new Date().toISOString(),
    counts: { canonical: docs.filter((d) => d.kind === 'md').length, htmlOnly, companions, files: files.length },
    docs,
    backlinks,
    brokenLinks,
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
  for (const c of candidates) if (byKey.has(c)) return c;

  // 파일명만 적은 경우 — 전체에서 basename 일치 탐색
  const base = nfc(path.basename(withExt));
  for (const [k] of byKey) if (path.basename(k) === base) return k;
  return null;
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
  const { file } = indexPaths(vaultRoot);
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

const LOCK_STALE_MS = 5 * 60 * 1000;

/** 스캔–커밋 전체를 감싸는 크로스 프로세스 락. 동시 sync 가 인덱스를 덮어쓰지 않게 한다. */
async function withLock(vaultRoot, fn) {
  const { dir, lock, marker } = indexPaths(vaultRoot);
  await fsp.mkdir(dir, { recursive: true });
  await fsp.writeFile(marker, vaultRoot + '\n', 'utf8');

  for (let attempt = 0; ; attempt++) {
    try {
      const fh = await fsp.open(lock, 'wx');
      await fh.writeFile(String(process.pid));
      await fh.close();
      break;
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      let age = Infinity;
      try {
        age = Date.now() - (await fsp.stat(lock)).mtimeMs;
      } catch { /* 그 사이 풀렸다 */ }
      if (age > LOCK_STALE_MS) {
        await fsp.rm(lock, { force: true });   // 오래된 락 회수
        continue;
      }
      if (attempt >= 50) throw new Error('인덱스 락 획득 실패 (다른 sync 가 진행 중입니다)');
      await new Promise((r) => setTimeout(r, 100));
    }
  }

  try {
    return await fn();
  } finally {
    await fsp.rm(lock, { force: true });
  }
}

/** 전체 스캔 후 인덱스를 원자적으로 커밋하고 drift 리포트를 돌려준다. */
export async function syncIndex(cfg) {
  return withLock(cfg.root, async () => {
    const before = readIndex(cfg.root);
    const index = buildIndex(cfg);
    const { dir, file } = indexPaths(cfg.root);

    const tmp = path.join(dir, `.index.${process.pid}.${Date.now()}.tmp`);
    await fsp.writeFile(tmp, JSON.stringify(index), 'utf8');
    await fsp.rename(tmp, file);

    return { index, drift: diffIndex(before, index) };
  });
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
 * create 는 wx 로 원자 생성하고, overwrite/append 는 expectedHash 로 낙관적 잠금을 건다.
 */
export async function writeDoc(cfg, { relPath, content, frontmatter, mode = 'create', expectedHash }) {
  const { abs, rel } = safeResolve(cfg.root, relPath, { forWrite: true });

  let existing = null;
  try {
    existing = await fsp.readFile(abs, 'utf8');
  } catch { /* 신규 */ }

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
      const merged = {
        ...existingFm,                                  // share_link 등 모르는 키 보존
        ...(splitFrontmatter(content).frontmatter ?? {}),
        ...(frontmatter ?? {}),
        updated: new Date().toISOString().slice(0, 10),
      };
      final = renderFrontmatter(merged) + bodyOnly.replace(/^\s+/, '');
    } else {
      final = bodyOnly;
    }
  }

  await fsp.mkdir(path.dirname(abs), { recursive: true });

  if (mode === 'create') {
    // 존재 확인 후 rename 은 그 사이 생긴 파일을 덮어쓴다. wx 로 원자 생성한다.
    const fh = await fsp.open(abs, 'wx');
    try {
      await fh.writeFile(final, 'utf8');
    } finally {
      await fh.close();
    }
  } else {
    const tmp = path.join(path.dirname(abs), `.${path.basename(abs)}.${process.pid}.${Date.now()}.tmp`);
    await fsp.writeFile(tmp, final, 'utf8');
    await fsp.rename(tmp, abs);
  }

  return { path: rel, bytes: Buffer.byteLength(final), hash: sha1(Buffer.from(final, 'utf8')), mode };
}

export { nfc, sha1 };
