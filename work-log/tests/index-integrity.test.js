import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { buildIndex, indexPaths, readIndex, syncIndex, writeDoc } from '../mcp/lib/vault.js';

function fixture(t) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-index-'));
  const root = path.join(temp, 'vault');
  fs.mkdirSync(root);
  const before = process.env.XDG_CACHE_HOME;
  process.env.XDG_CACHE_HOME = path.join(temp, 'cache');
  t.after(() => {
    if (before === undefined) delete process.env.XDG_CACHE_HOME;
    else process.env.XDG_CACHE_HOME = before;
    fs.rmSync(temp, { recursive: true, force: true });
  });
  return { root };
}

test('잘못된 frontmatter 타입은 파일 생성 전에 거부한다', async (t) => {
  const cfg = fixture(t);
  for (const title of [[], {}, 4, true, null]) {
    await assert.rejects(writeDoc(cfg, { relPath: 'bad.md', content: 'body', frontmatter: { title } }), /frontmatter.*title/);
    assert.equal(fs.existsSync(path.join(cfg.root, 'bad.md')), false);
  }
  for (const raw of ['title: [bad]', 'title: {bad: value}', 'title: 123', 'title:\n  nested: value', 'tags: [valid, 1]']) {
    await assert.rejects(writeDoc(cfg, { relPath: 'bad.md', content: `---\n${raw}\n---\nbody` }), /frontmatter/);
    assert.equal(fs.existsSync(path.join(cfg.root, 'bad.md')), false);
  }
});

test('외부 손상 문서를 경로별로 보고하고 정상 문서는 검색할 수 있게 저장한다', async (t) => {
  const cfg = fixture(t);
  fs.writeFileSync(path.join(cfg.root, 'good.md'), '# Good');
  fs.writeFileSync(path.join(cfg.root, 'bad.md'), '---\ntitle: [bad]\n---\nBody');
  const { index } = await syncIndex(cfg);
  assert.equal(index.status, 'DEGRADED');
  assert.equal(index.errors[0].path, 'bad.md');
  assert.equal(index.errors[0].operation, 'parse');
  assert.deepEqual(readIndex(cfg.root).docs.map(d => d.path), ['good.md']);
  assert.ok(index.scan.bytesRead > 0);
  assert.ok(index.scan.durationMs >= 0);
});

test('읽기 오류의 문서와 디렉터리 subtree는 삭제 drift에서 제외하고 링크도 보존한다', async (t) => {
  const cfg = fixture(t);
  fs.mkdirSync(path.join(cfg.root, 'private'));
  fs.writeFileSync(path.join(cfg.root, 'private/child.md'), '# Child\n[[public]]');
  fs.writeFileSync(path.join(cfg.root, 'public.md'), '# Public');
  await syncIndex(cfg);
  for (const [method, target] of [['readFileSync', 'private/child.md'], ['readdirSync', 'private']]) {
    const original = fs[method];
    const mock = t.mock.method(fs, method, (...args) => {
      if (args[0] === path.join(cfg.root, target)) throw Object.assign(new Error('permission denied'), { code: 'EACCES' });
      return original(...args);
    });
    const { index, drift } = await syncIndex(cfg);
    mock.mock.restore();
    assert.equal(index.status, 'DEGRADED');
    assert.deepEqual(drift.removed, []);
    assert.equal(index.docs.find(d => d.path === 'private/child.md').stale, true);
    assert.deepEqual(index.backlinks['public.md'], ['private/child.md']);
  }
  fs.unlinkSync(path.join(cfg.root, 'private/child.md'));
  const recovered = await syncIndex(cfg);
  assert.equal(recovered.index.status, 'OK');
  assert.deepEqual(recovered.drift.removed, ['private/child.md']);
});

test('다른 root·버전·손상 schema의 캐시는 로드하지 않고 재생성한다', async (t) => {
  const cfg = fixture(t);
  fs.writeFileSync(path.join(cfg.root, 'doc.md'), '# Document');
  const valid = buildIndex(cfg);
  const { dir, file } = indexPaths(cfg.root);
  fs.mkdirSync(dir, { recursive: true });
  for (const invalid of [{ ...valid, version: 999 }, { ...valid, root: path.dirname(cfg.root) }, { ...valid, docs: [null] }, null]) {
    fs.writeFileSync(file, JSON.stringify(invalid));
    assert.equal(readIndex(cfg.root), null);
    await syncIndex(cfg);
    assert.equal(readIndex(cfg.root).docs[0].title, 'Document');
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
    assert.equal(fs.statSync(dir).mode & 0o777, 0o700);
  }
});
