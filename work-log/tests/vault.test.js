import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { buildIndex, splitFrontmatter, writeDoc } from '../mcp/lib/vault.js';
import { rank } from '../mcp/lib/search.js';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-vault-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return { root, excludes: [] };
}

test('본문 overwrite가 블록 배열·중첩 객체·따옴표·모르는 키를 보존한다', async (t) => {
  const cfg = fixture(t);
  const raw = 'title: "Example: API #1"\ntags:\n  - project\n  - backend\n' +
    'plugin_state:\n  share_link: https://example.test/doc\n  enabled: true\n' +
    'custom: |\n  first line\n  second line\n';
  fs.writeFileSync(path.join(cfg.root, 'doc.md'), `---\n${raw}---\n\nOld body\n`);
  await writeDoc(cfg, { relPath: 'doc.md', content: 'New body\n', mode: 'overwrite' });
  const result = fs.readFileSync(path.join(cfg.root, 'doc.md'), 'utf8');
  assert.ok(result.startsWith(`---\n${raw}"updated": `));
  assert.equal(splitFrontmatter(result).body.trim(), 'New body');
  assert.deepEqual(buildIndex(cfg).docs[0].tags, ['project', 'backend']);
});

test('명시한 메타데이터만 덮어쓰고 incoming raw 블록을 보존한다', async (t) => {
  const cfg = fixture(t);
  fs.writeFileSync(path.join(cfg.root, 'doc.md'), '---\ntitle: Old\ncustom:\n  keep: true\n---\nOld');
  await writeDoc(cfg, {
    relPath: 'doc.md', mode: 'overwrite',
    content: '---\ntitle: Incoming\nsettings:\n  nested: [one, two]\n---\nNew',
    frontmatter: { title: 'Explicit: title #1' },
  });
  const result = fs.readFileSync(path.join(cfg.root, 'doc.md'), 'utf8');
  assert.match(result, /custom:\n  keep: true\n/);
  assert.match(result, /settings:\n  nested: \[one, two\]\n/);
  assert.equal(splitFrontmatter(result).frontmatter.title, 'Explicit: title #1');
});

test('scalar·flow 배열·block 배열 tags 문서가 함께 인덱싱되고 검색된다', (t) => {
  const cfg = fixture(t);
  for (const [name, tags] of Object.entries({ scalar: 'backend', flow: '[backend, api]', block: '\n  - backend\n  - api' })) {
    fs.writeFileSync(path.join(cfg.root, `${name}.md`), `---\ntitle: ${name}\ntags: ${tags}\n---\nAPI body`);
  }
  const index = buildIndex(cfg);
  assert.equal(index.docs.length, 3);
  assert.equal(rank(index, { query: 'API', tags: ['backend'] }).total, 3);
});

test('신규 메타데이터의 콜론·쉼표·따옴표가 다시 읽혀도 유지된다', async (t) => {
  const cfg = fixture(t);
  await writeDoc(cfg, { relPath: 'doc.md', content: 'Body', frontmatter: { title: 'A: "B" #C', tags: ['a,b', 'backend'] } });
  const doc = buildIndex(cfg).docs[0];
  assert.equal(doc.title, 'A: "B" #C');
  assert.deepEqual(doc.tags, ['a,b', 'backend']);
});

test('CRLF YAML 블록을 유지하고 frontmatter 없는 문서에는 주입하지 않는다', async (t) => {
  const cfg = fixture(t);
  fs.writeFileSync(path.join(cfg.root, 'crlf.md'), '---\r\ntitle: Old\r\ncustom:\r\n  value: yes\r\n---\r\nBody');
  await writeDoc(cfg, { relPath: 'crlf.md', content: 'New', mode: 'overwrite' });
  assert.match(fs.readFileSync(path.join(cfg.root, 'crlf.md'), 'utf8'), /custom:\r\n  value: yes\r\n/);
  fs.writeFileSync(path.join(cfg.root, 'plain.md'), '# Plain');
  await assert.rejects(writeDoc(cfg, { relPath: 'plain.md', content: 'Body', mode: 'overwrite', frontmatter: { tags: ['api'] } }));
  assert.equal(fs.readFileSync(path.join(cfg.root, 'plain.md'), 'utf8'), '# Plain');
});

test('updated 뒤의 따옴표 키·한글 키도 별도 블록으로 보존한다', async (t) => {
  const cfg = fixture(t);
  const custom = '"external.meta":\n  keep: true\n메타정보:\n  공유: yes\n';
  fs.writeFileSync(path.join(cfg.root, 'doc.md'), `---\nupdated: 2026-01-01\n${custom}---\nBody`);
  await writeDoc(cfg, { relPath: 'doc.md', mode: 'overwrite', content: 'New' });
  assert.ok(fs.readFileSync(path.join(cfg.root, 'doc.md'), 'utf8').includes(custom));
});

test('공백 있는 flow tags와 들여쓰기 없는 block tags를 읽는다', () => {
  assert.deepEqual(splitFrontmatter('---\ntags: [ "a,b", "backend" ]\n---\n').frontmatter.tags, ['a,b', 'backend']);
  assert.deepEqual(splitFrontmatter('---\ntags:\n- backend\n- api\n---\n').frontmatter.tags, ['backend', 'api']);
});

test('tags의 인라인 주석은 제외하고 인용 문자열 안의 #은 보존한다', (t) => {
  const cfg = fixture(t);
  for (const [name, tags] of Object.entries({
    flow: '[backend, "API #1"] # labels',
    block: '# labels\n  - backend\n  - "API #1" # item',
  })) {
    fs.writeFileSync(path.join(cfg.root, `${name}.md`), `---\ntags: ${tags}\n---\nAPI body`);
  }
  const index = buildIndex(cfg);
  for (const doc of index.docs) assert.deepEqual(doc.tags, ['backend', 'API #1']);
  assert.equal(rank(index, { query: 'API', tags: ['backend'] }).total, 2);
});

test('미지원 루트 YAML을 overwrite할 때 원본을 변경하지 않는다', async (t) => {
  const cfg = fixture(t);
  for (const raw of ['  title: Example\n  custom:\n    keep: true\n', '{title: Example, custom: true}\n']) {
    const original = `---\n${raw}---\nOld body`;
    fs.writeFileSync(path.join(cfg.root, 'doc.md'), original);
    await assert.rejects(writeDoc(cfg, { relPath: 'doc.md', content: 'New body', mode: 'overwrite' }), /YAML/);
    assert.equal(fs.readFileSync(path.join(cfg.root, 'doc.md'), 'utf8'), original);
  }
});
