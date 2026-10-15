import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fork } from 'node:child_process';
import { once } from 'node:events';
import { buildIndex, documentClassification, sha1, splitFrontmatter, writeDoc } from '../mcp/lib/vault.js';
import { rank } from '../mcp/lib/search.js';

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-vault-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return { root, excludes: [] };
}

test('구조 경로 우선 분류와 raw YAML 문자열만의 flat 분류', () => {
  assert.deepEqual(documentClassification('projects/한글/docs/file.md', 'project: other\ncategory: data\n'), { project: '한글', category: 'docs' });
  for (const owner of ['_shared', '_unclassified']) {
    assert.deepEqual(documentClassification(`${owner}/data/file.html`), { project: owner, category: 'data' });
    assert.deepEqual(documentClassification(`${owner}/data`), { project: null, category: null });
  }
  assert.deepEqual(documentClassification('projects/owner/docs'), { project: null, category: null });
  assert.deepEqual(documentClassification('projects/owner/docs/'), { project: null, category: null });
  assert.deepEqual(documentClassification('projects/90_personal/frame/history/x.md'), { project: 'frame', category: 'history' });
  assert.deepEqual(documentClassification('projects/99_no-more-use/fitlog/history/x.md', 'project: other\n'), { project: 'fitlog', category: 'history' });
  assert.deepEqual(documentClassification('projects/90_personal/x.md', 'project: owner\n'), { project: 'owner', category: null });
  assert.deepEqual(documentClassification('projects/90_personal/frame/history/'), { project: null, category: null });
  assert.deepEqual(documentClassification('projects/personal/frame/history/x.md'), { project: null, category: null });
  assert.deepEqual(documentClassification('projects/내신인강/docs/내신인강/x.md'), { project: '내신인강', category: 'docs' });
  for (const value of ['123', 'true', 'null', '{a: b}', '[a]', '\n  nested: yes', '\n- list', '0o12', '-0x1f', '+0b10', '1:20', '&anchor owner', '*alias']) {
    assert.deepEqual(documentClassification('flat.md', `project: ${value}\ncategory: docs\n`), { project: null, category: 'docs' }, value);
  }
  assert.deepEqual(documentClassification('flat.md', 'project: "123"\ncategory: "docs" # comment\n'), { project: '123', category: 'docs' });
  assert.deepEqual(documentClassification('flat.md', 'project: owner\ncategory: other\n'), { project: 'owner', category: null });
});

test('YAML quoted 문자열 escape를 분류하고 inline create와 exact 검색에 사용한다', async (t) => {
  const cfg = fixture(t);
  for (const [value, expected] of [
    [String.raw`"own\x65r"`, 'owner'],
    [String.raw`"한글"`, '한글'],
    [String.raw`"\U00020000"`, '𠀀'],
    [String.raw`"own\\x65r"`, String.raw`own\x65r`],
    [String.raw`"a\ b\_c\Nd\Le\Pf"`, 'a b\xa0c\x85d e f'],
    [String.raw`"a\0\a\v\e"`, 'a\0\x07\v\x1b'],
    [String.raw`"bad\q"`, null],
    [String.raw`"bad\x0"`, null],
    [String.raw`"bad\UFFFFFFFF"`, null],
  ]) {
    assert.equal(documentClassification('flat.md', `project: ${value}\n`).project, expected, value);
  }
  const raw = String.raw`project: "own\x65r"` + '\n' + String.raw`category: "d\x6fcs"` + '\n';
  assert.deepEqual(documentClassification('flat.md', raw), { project: 'owner', category: 'docs' });
  fs.writeFileSync(path.join(cfg.root, 'flat.md'), `---\n${raw}---\n# needle`);
  assert.equal(rank(buildIndex(cfg), { query: 'needle', project: 'owner', category: 'docs' }).candidates[0].path, 'flat.md');
  const relPath = 'projects/owner/docs/new.md';
  await writeDoc(cfg, { relPath, content: `---\n${raw}---\n# needle` });
  assert.ok(fs.readFileSync(path.join(cfg.root, relPath), 'utf8').includes(raw));
});

test('신규 structured Properties는 정규화 경로를 사용하고 양쪽 명시 충돌을 거부한다', async (t) => {
  const cfg = fixture(t);
  const relPath = 'projects/owner/history/../docs/new.md';
  const result = await writeDoc(cfg, { relPath, content: '# New' });
  assert.equal(result.path, 'projects/owner/docs/new.md');
  assert.deepEqual(documentClassification('flat.md', splitFrontmatter(fs.readFileSync(path.join(cfg.root, result.path), 'utf8')).raw), { project: 'owner', category: 'docs' });
  for (const [i, args] of [
    { frontmatter: { project: 'wrong' }, content: '# Body' },
    { frontmatter: { category: 'data' }, content: '# Body' },
    { frontmatter: { project: 'owner' }, content: '---\nproject: wrong\n---\nBody' },
    { frontmatter: { project: 'wrong' }, content: '---\nproject: owner\n---\nBody' },
    { content: '---\nproject: {owner: yes}\n---\nBody' },
    { content: '---\ncategory: true\n---\nBody' },
  ].entries()) {
    const target = `projects/owner/docs/bad-${i}.md`;
    await assert.rejects(writeDoc(cfg, { relPath: target, ...args }), /저장 경로/);
    assert.equal(fs.existsSync(path.join(cfg.root, target)), false);
  }
  await assert.rejects(writeDoc(cfg, { relPath: '../escape.md', content: '# Nope' }), /vault 밖/);
  for (const owner of ['_shared', '_unclassified']) {
    await writeDoc(cfg, { relPath: `${owner}/data/new.md`, content: '# Data' });
    const fm = splitFrontmatter(fs.readFileSync(path.join(cfg.root, `${owner}/data/new.md`), 'utf8')).frontmatter;
    assert.equal(fm.project, owner);
    assert.equal(fm.category, 'data');
  }
});

test('inline 신규 raw 키 및 기존 복합 Properties와 noFM overwrite/append를 보존한다', async (t) => {
  const cfg = fixture(t);
  const relPath = 'projects/owner/docs/doc.md';
  const custom = 'custom:\n  nested: [one, two]\nblock: |\n  first\n  second\n';
  await writeDoc(cfg, { relPath, content: `---\nproject: owner\n${custom}---\nBody`, frontmatter: { title: 'Explicit' } });
  let text = fs.readFileSync(path.join(cfg.root, relPath), 'utf8');
  assert.ok(text.includes(custom));
  assert.equal(splitFrontmatter(text).frontmatter.category, 'docs');
  assert.equal(splitFrontmatter(text).frontmatter.title, 'Explicit');
  const complex = 'project:\n  owner: original\ncategory: [custom, other]\n'+custom;
  fs.writeFileSync(path.join(cfg.root, relPath), `---\n${complex}---\nOld`);
  await writeDoc(cfg, { relPath, content: 'New', mode: 'overwrite' });
  text = fs.readFileSync(path.join(cfg.root, relPath), 'utf8');
  assert.ok(text.includes(complex));
  const metadata = splitFrontmatter(text).raw;
  await writeDoc(cfg, { relPath, content: 'Append', mode: 'append', expectedHash: sha1(Buffer.from(text)) });
  assert.equal(splitFrontmatter(fs.readFileSync(path.join(cfg.root, relPath), 'utf8')).raw, metadata);
  assert.equal(buildIndex(cfg).status, 'OK');
  fs.writeFileSync(path.join(cfg.root, relPath), '# Plain');
  await writeDoc(cfg, { relPath, content: 'Replaced', mode: 'overwrite' });
  await writeDoc(cfg, { relPath, content: 'Appended', mode: 'append' });
  assert.equal(fs.readFileSync(path.join(cfg.root, relPath), 'utf8'), 'Replaced\n\nAppended');
});

async function writers(t, cfg, count = 2) {
  const children = Array.from({ length: count }, (_, i) => fork(new URL('./helpers/write-worker.mjs', import.meta.url), [], {
    execArgv: [], stdio: ['ignore', 'ignore', 'inherit', 'ipc'],
    env: { ...process.env, XDG_CACHE_HOME: path.join(cfg.root, `cache-${i}`) },
  }));
  t.after(async () => {
    await Promise.all(children.map(async (child) => {
      if (child.exitCode === null && child.signalCode === null) {
        const closed = once(child, 'exit');
        child.kill();
        await closed;
      }
    }));
  });
  await Promise.all(children.map((child) => once(child, 'message')));
  return async (args) => {
    const replies = children.map((child) => once(child, 'message'));
    children.forEach((child, i) => child.send({ cfg, args: args[i] }));
    return (await Promise.all(replies)).map(([value]) => value);
  };
}

test('별도 프로세스·cache·경로 별칭의 같은 hash 수정은 한 번만 성공한다', { timeout: 10000 }, async (t) => {
  const cfg = fixture(t);
  const original = '# Original\n' + 'content\n'.repeat(20000);
  fs.symlinkSync('doc.md', path.join(cfg.root, 'alias.md'));
  const write = await writers(t, cfg);
  for (const mode of ['append', 'overwrite']) {
    fs.writeFileSync(path.join(cfg.root, 'doc.md'), original);
    const results = await write(['doc.md', 'alias.md'].map((relPath, i) => ({
      relPath, mode, content: `Changed ${i}`, expectedHash: sha1(Buffer.from(original)),
    })));
    assert.equal(results.filter((r) => r.ok).length, 1);
    assert.match(results.find((r) => !r.ok).error, /그 사이 변경/);
    const winner = results.find((r) => r.ok).result;
    assert.equal(sha1(fs.readFileSync(path.join(cfg.root, 'doc.md'))), winner.hash);
    assert.deepEqual(fs.readdirSync(cfg.root), ['alias.md', 'doc.md']);
  }
});

test('hash 없는 동시 append는 모든 프로세스의 내용을 보존한다', { timeout: 10000 }, async (t) => {
  const cfg = fixture(t);
  fs.writeFileSync(path.join(cfg.root, 'doc.md'), '# Original');
  const write = await writers(t, cfg, 4);
  const values = ['From A', 'From B', 'From C', 'From D'];
  const results = await write(values.map((content) => ({ relPath: 'doc.md', mode: 'append', content })));
  assert.ok(results.every((r) => r.ok), JSON.stringify(results));
  const final = fs.readFileSync(path.join(cfg.root, 'doc.md'), 'utf8');
  for (const value of values) assert.ok(final.includes(value), value);
});

test('쓰기 거부 뒤 잠금을 해제하여 다음 수정이 가능하다', async (t) => {
  const cfg = fixture(t);
  fs.writeFileSync(path.join(cfg.root, 'doc.md'), '# Original');
  await assert.rejects(writeDoc(cfg, { relPath: 'doc.md', mode: 'append', content: 'stale', expectedHash: 'wrong' }));
  await writeDoc(cfg, { relPath: 'doc.md', mode: 'append', content: 'next' });
  assert.equal(fs.readFileSync(path.join(cfg.root, 'doc.md'), 'utf8'), '# Original\n\nnext');
  assert.deepEqual(fs.readdirSync(cfg.root), ['doc.md']);
});

test('보유된 문서 락을 회수하지 않고 다른 문서는 독립적으로 쓴다', { timeout: 10000 }, async (t) => {
  const cfg = fixture(t);
  fs.writeFileSync(path.join(cfg.root, 'doc.md'), '# Original');
  const held = path.join(cfg.root, '.doc.md.write-lock');
  fs.mkdirSync(held);
  const pending = writeDoc(cfg, { relPath: 'doc.md', mode: 'append', content: 'blocked' });
  const rejected = assert.rejects(pending, /문서 쓰기 잠금 대기 시간 초과:.*소유자 정보 없음/);
  await writeDoc(cfg, { relPath: 'independent.md', content: 'independent' });
  assert.ok(fs.existsSync(path.join(cfg.root, 'independent.md')));
  await rejected;
  assert.ok(fs.existsSync(held));
  assert.equal(fs.readFileSync(path.join(cfg.root, 'doc.md'), 'utf8'), '# Original');
});

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
