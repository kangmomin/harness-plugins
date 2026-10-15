import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { buildIndex } from '../mcp/lib/vault.js';
import { extractSection, rank } from '../mcp/lib/search.js';

test('구조화된 전역 vault의 exact 필터·NFD 원본 경로·HTML twin·flat nullable 분류', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-classification-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const korean = '한글'.normalize('NFD');
  const files = {
    [`projects/${korean}/docs/guide.md`]: '---\nproject: wrong\ncategory: data\n---\n# needle',
    [`projects/${korean}/docs/guide.html`]: '<title>needle twin</title>',
    'projects/other/history/guide.md': '# needle',
    '_shared/docs/guide.html': '<title>needle shared</title>',
    '_unclassified/data/guide.md': '# needle',
    'flat.md': '---\nproject: flat\ncategory: history\n---\n# needle',
    'complex.md': '---\nproject: {owner: flat}\ncategory: [docs]\n---\n# needle',
    'plain.md': '# needle',
  };
  for (const [rel, body] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
    fs.writeFileSync(path.join(root, rel), body);
  }
  const index = buildIndex({ root, scope: 'global' });
  assert.equal(index.status, 'OK');
  assert.equal(index.counts.companions, 1);
  assert.equal(rank(index, { query: 'needle' }).total, 7);
  const found = rank(index, { query: 'needle', project: korean, category: 'docs' });
  assert.equal(found.total, 1);
  assert.equal(found.candidates[0].path, `projects/${korean}/docs/guide.md`);
  assert.equal(found.candidates[0].project, '한글');
  assert.ok(found.candidates[0].tags.includes('한글'));
  assert.ok(!found.candidates[0].tags.includes('projects'));
  assert.deepEqual(found.candidates[0].companions, [`projects/${korean}/docs/guide.html`]);
  for (const [project, category] of [['_shared', 'docs'], ['_unclassified', 'data'], ['flat', 'history']]) {
    const match = rank(index, { query: 'needle', project, category });
    assert.equal(match.total, 1);
    assert.equal(match.candidates[0].category, category);
  }
  assert.equal(rank(index, { query: 'needle', project: 'Flat' }).emptyResult, true);
  assert.equal(rank(index, { query: 'needle', project: '' }).emptyResult, true);
  assert.equal(rank(index, { query: 'needle', category: 'history' }).total, 2);
  assert.deepEqual(index.docs.filter((d) => d.project === null).map((d) => d.path).sort(), ['complex.md', 'plain.md']);
});

test('코드 펜스 밖의 제목만 섹션 경계와 인덱스에 사용한다', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-headings-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const [open, close] of [['```sh', '```'], ['~~~~sh', '~~~~~'], ['   ````sh', '   ````']]) {
    const section = ['## Deployment', 'before', open, '# code heading', '[[missing/code]]',
      '```', 'still code', close, '### Details', 'after'].join('\r\n');
    // The nested triple-backtick is code when the outer fence has four markers or uses tildes.
    const expected = open.trim().startsWith('```sh')
      ? ['## Deployment', 'before', open, '# code heading', '[[missing/code]]', close, '### Details', 'after'].join('\r\n')
      : section;
    const body = '# Real\r\n'+expected+'\r\n## Next\r\nnext';
    fs.writeFileSync(path.join(root, 'doc.md'), body);
    const found = extractSection(body, 'Deployment');
    assert.equal(found.text, expected+'\r');
    assert.equal(extractSection(body, 'code heading').sectionNotFound, true);
    const index = buildIndex({ root });
    assert.deepEqual(index.docs[0].headings, ['Real', 'Deployment', 'Details', 'Next']);
    assert.deepEqual(index.brokenLinks, []);
  }
});

test('명시한 경로는 basename fallback하지 않고 동명 후보는 모호함으로 보고한다', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-links-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const dir of ['real', 'other', 'notes']) fs.mkdirSync(path.join(root, dir));
  fs.writeFileSync(path.join(root, 'real/guide.md'), '# Guide');
  fs.writeFileSync(path.join(root, 'other/guide.md'), '# Other');
  fs.writeFileSync(path.join(root, 'notes/index.md'), '# Index\n[[missing/guide]]\n[[guide]]\n[[real/guide]]');
  fs.writeFileSync(path.join(root, 'real/index.md'), '# Local\n[[guide]]');
  const index = buildIndex({ root });
  assert.deepEqual(index.brokenLinks, [{ from: 'notes/index.md', to: 'missing/guide' }]);
  assert.deepEqual(index.ambiguousLinks, [{ from: 'notes/index.md', to: 'guide', candidates: ['other/guide.md', 'real/guide.md'] }]);
  assert.deepEqual(index.backlinks['real/guide.md'], ['notes/index.md', 'real/index.md']);
  fs.unlinkSync(path.join(root, 'other/guide.md'));
  assert.deepEqual(buildIndex({ root }).ambiguousLinks, []);
});
