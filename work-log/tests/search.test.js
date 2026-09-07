import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { buildIndex } from '../mcp/lib/vault.js';
import { extractSection } from '../mcp/lib/search.js';

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
