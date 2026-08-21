/**
 * 랭킹 · 스니펫 · 섹션 추출 · 예산 캡.
 *
 * 인덱스에 저장된 필드에만 가중치를 준다 (저장하지 않는 본문에 가중치를 주지 않는다).
 */

import { nfc } from './vault.js';

/** 1 토큰 ≈ 4자. Node 내장만으로는 진짜 토크나이저를 돌릴 수 없어 근사치다. */
export const CHARS_PER_TOKEN = 4;

const WEIGHTS = { title: 5, tags: 4, headings: 2, path: 2, summary: 1, excerpt: 1 };

const norm = (s) => nfc(String(s ?? '')).toLowerCase();

function tokenize(query) {
  return norm(query).split(/\s+/).filter((t) => t.length > 0);
}

function fieldText(doc, field) {
  switch (field) {
    case 'title': return norm(doc.title);
    case 'tags': return norm((doc.tags ?? []).join(' '));
    case 'headings': return norm((doc.headings ?? []).join(' '));
    case 'path': return norm(doc.key ?? doc.path);
    case 'summary': return norm(doc.summary);
    case 'excerpt': return norm(doc.excerpt);
    default: return '';
  }
}

/**
 * 본문 없이 후보를 랭킹한다. 형태소 분석 없이 부분 문자열 포함으로 처리한다
 * (교착어인 한국어에서 어간 매칭이 자연히 걸린다).
 */
export function rank(index, { query, type, tags, limit = 5 }) {
  const terms = tokenize(query);
  if (!terms.length) return { candidates: [], emptyResult: true, reason: '쿼리가 비어 있습니다' };

  const wantTags = (tags ?? []).map(norm);
  const scored = [];

  for (const doc of index.docs) {
    if (type && doc.type !== type) continue;
    if (wantTags.length) {
      const docTags = (doc.tags ?? []).map(norm);
      if (!wantTags.every((t) => docTags.some((d) => d.includes(t)))) continue;
    }

    let score = 0;
    const matched = new Set();
    for (const [field, weight] of Object.entries(WEIGHTS)) {
      const text = fieldText(doc, field);
      if (!text) continue;
      for (const term of terms) {
        if (text.includes(term)) {
          score += weight;
          matched.add(term);
        }
      }
    }
    if (!score) continue;

    // 모든 검색어를 만족하는 문서를 우선한다
    if (matched.size === terms.length) score += 3;
    scored.push({ doc, score });
  }

  if (!scored.length) {
    const topTags = tagHistogram(index).slice(0, 15).map(([t, n]) => `${t}(${n})`);
    return {
      candidates: [],
      emptyResult: true,
      reason: '일치하는 문서가 없습니다',
      hintTags: topTags,
    };
  }

  scored.sort((a, b) => b.score - a.score || b.doc.mtime - a.doc.mtime);

  const candidates = scored.slice(0, Math.max(1, Math.min(20, limit))).map(({ doc, score }) => ({
    path: doc.path,
    title: doc.title,
    type: doc.type,
    kind: doc.kind,
    tags: doc.tags,
    created: doc.created,
    summary: doc.summary,
    snippet: snippet(doc, terms),
    companions: (doc.companions ?? []).map((c) => c.path),
    score,
  }));

  return { candidates, emptyResult: false, total: scored.length };
}

function tagHistogram(index) {
  const counts = new Map();
  for (const d of index.docs) for (const t of d.tags ?? []) counts.set(t, (counts.get(t) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

/** 첫 매칭어 주변을 잘라 보여준다. */
function snippet(doc, terms, width = 160) {
  const text = doc.excerpt || doc.summary || '';
  if (!text) return '';
  const lower = norm(text);
  let at = -1;
  for (const t of terms) {
    const i = lower.indexOf(t);
    if (i !== -1 && (at === -1 || i < at)) at = i;
  }
  if (at === -1) return text.slice(0, width);
  const start = Math.max(0, at - width / 3);
  return (start > 0 ? '…' : '') + text.slice(start, start + width) + '…';
}

/**
 * 헤딩 단위로 섹션을 잘라낸다. topic 이 헤딩에 부분 일치하면 그 헤딩부터
 * 같거나 더 높은 레벨의 다음 헤딩 직전까지를 반환한다.
 */
export function extractSection(body, topic) {
  if (!topic) return { text: body, matchedHeading: null };
  const want = norm(topic);
  const lines = body.split('\n');

  let startIdx = -1;
  let level = 0;
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^(#{1,6})\s+(.+?)\s*$/);
    if (m && norm(m[2]).includes(want)) {
      startIdx = i;
      level = m[1].length;
      break;
    }
  }
  if (startIdx === -1) return { text: body, matchedHeading: null, sectionNotFound: true };

  let endIdx = lines.length;
  for (let i = startIdx + 1; i < lines.length; i++) {
    const m = lines[i].match(/^(#{1,6})\s+/);
    if (m && m[1].length <= level) {
      endIdx = i;
      break;
    }
  }
  return {
    text: lines.slice(startIdx, endIdx).join('\n'),
    matchedHeading: lines[startIdx].replace(/^#+\s*/, ''),
  };
}

/** token_budget 을 문자 수로 환산해 자른다. 정확한 토큰 캡이라고 주장하지 않는다. */
export function applyBudget(text, tokenBudget) {
  if (!tokenBudget || tokenBudget <= 0) {
    return { text, truncated: false, approximate: true, chars: text.length };
  }
  const maxChars = tokenBudget * CHARS_PER_TOKEN;
  if (text.length <= maxChars) {
    return { text, truncated: false, approximate: true, chars: text.length };
  }
  return {
    text: text.slice(0, maxChars) + '\n\n…(예산 초과로 잘림)',
    truncated: true,
    approximate: true,
    chars: maxChars,
    originalChars: text.length,
  };
}
