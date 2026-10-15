import assert from 'node:assert/strict';
import { fork, spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { projectVaultPath } from '../mcp/lib/config.js';

const pluginRoot = fileURLToPath(new URL('../', import.meta.url));

test('Codex manifest가 상대 MCP 경로와 환경 전달을 선언한다', () => {
  const manifest = JSON.parse(
    fs.readFileSync(path.join(pluginRoot, '.codex-plugin', 'plugin.json'), 'utf8'),
  );
  const server = manifest.mcpServers['work-log'];

  assert.deepEqual(server.args, ['./mcp/server.js']);
  assert.equal(server.cwd, '.');
  assert.deepEqual(server.env_vars, [
    'WORK_LOG_ROOT', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME',
  ]);
});

test('저장 후 인덱스 timeout은 저장 성공으로 응답하고 sync만 재시도한다', { timeout: 15000 }, async (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-partial-'));
  const root = path.join(temp, 'vault');
  fs.mkdirSync(root);
  fs.writeFileSync(path.join(root, 'doc.md'), '# Before');
  const env = { ...process.env, WORK_LOG_ROOT: root, XDG_CACHE_HOME: path.join(temp, 'cache') };
  const owner = fork(new URL('./helpers/sync-worker.mjs', import.meta.url), [], {
    env, execArgv: [], stdio: ['ignore', 'ignore', 'inherit', 'ipc'],
  });
  const child = spawn(process.execPath, [path.join(pluginRoot, 'mcp/server.js')], { env, cwd: temp });
  t.after(async () => {
    for (const process of [owner, child]) {
      if (process.exitCode === null && process.signalCode === null) {
        const exited = once(process, 'exit');
        process.kill();
        await exited;
      }
    }
    fs.rmSync(temp, { recursive: true, force: true });
  });
  let buffer = '', id = 0;
  const pending = new Map();
  child.stdout.setEncoding('utf8');
  child.stdout.on('data', (chunk) => {
    buffer += chunk;
    let at;
    while ((at = buffer.indexOf('\n')) >= 0) {
      const message = JSON.parse(buffer.slice(0, at));
      buffer = buffer.slice(at + 1);
      pending.get(message.id)?.(message);
      pending.delete(message.id);
    }
  });
  child.stderr.resume();
  const call = (name, args = {}) => new Promise((resolve) => {
    const requestId = ++id;
    pending.set(requestId, resolve);
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: requestId, method: 'tools/call', params: { name, arguments: args } })+'\n');
  });
  await once(owner, 'message');
  const held = once(owner, 'message');
  owner.send({ type: 'sync', cfg: { root } });
  assert.equal((await held)[0].type, 'before-commit');
  const response = await call('wiki_write', { path: 'doc.md', content: 'APPENDED ONCE', mode: 'append' });
  assert.notEqual(response.result.isError, true);
  const result = JSON.parse(response.result.content[0].text);
  assert.equal(result.written.path, 'doc.md');
  assert.equal(result.indexing.status, 'FAILED');
  assert.equal(result.indexing.retry, 'wiki_sync');
  const released = once(owner, 'message');
  owner.send({ type: 'release' });
  assert.equal((await released)[0].type, 'done');
  const synced = await call(result.indexing.retry);
  assert.equal(JSON.parse(synced.result.content[0].text).status, 'OK');
  assert.equal(fs.readFileSync(path.join(root, 'doc.md'), 'utf8'), '# Before\n\nAPPENDED ONCE');
  const invalid = await call('wiki_write', { path: 'bad.md', content: 'body', frontmatter: null });
  assert.equal(invalid.error.code, -32602);
});

test('공백이 있는 독립 경로에서 initialize와 tools/list가 동작한다', async (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'work log mcp '));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const copy = path.join(temp, 'plugin copy');
  const cwd = path.join(temp, 'unrelated cwd');
  fs.cpSync(pluginRoot, copy, { recursive: true });
  fs.mkdirSync(cwd);

  const child = spawn(process.execPath, [path.join(copy, 'mcp', 'server.js')], {
    cwd,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  t.after(() => child.kill());

  let stdout = '';
  let stderr = '';
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', (chunk) => { stdout += chunk; });
  child.stderr.on('data', (chunk) => { stderr += chunk; });

  child.stdin.end([
    JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'initialize',
      params: { protocolVersion: '2024-11-05' },
    }),
    JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list' }),
  ].join('\n') + '\n');

  const exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', resolve);
  });
  assert.equal(exitCode, 0, stderr);

  const messages = stdout.trim().split('\n').map((line) => JSON.parse(line));
  assert.equal(messages[0].result.serverInfo.version, '0.3.2');
  assert.deepEqual(
    messages[1].result.tools.map((tool) => tool.name),
    ['wiki_resolve', 'wiki_read', 'wiki_write', 'wiki_sync', 'wiki_status'],
  );
});

test('구조화된 전역 MCP create→resolve→read→overwrite/append→sync 흐름', (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-structured-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const root = path.join(temp, 'vault');
  fs.mkdirSync(path.join(root, '_shared/docs'), { recursive: true });
  fs.writeFileSync(path.join(root, '_shared/docs/html.html'), '<title>needle HTML</title>');
  const rel = `projects/${'한글'.normalize('NFD')}/history/note.md`;
  const requests = [
    ['wiki_write', { path: rel, content: '---\ncustom:\n  preserved: true\n---\n# needle' }],
    ['wiki_resolve', { query: 'needle', project: '한글', category: 'history' }],
    ['wiki_read', { path: rel }],
    ['wiki_write', { path: rel, content: '# needle changed', mode: 'overwrite' }],
    ['wiki_write', { path: rel, content: 'Append once', mode: 'append' }],
    ['wiki_sync'],
    ['wiki_read', { path: rel }],
    ['wiki_read', { path: '_shared/docs/html.html' }],
    ['wiki_resolve', { query: 'needle' }],
    ['wiki_status'],
    ['wiki_resolve', { query: 'needle', category: 'bad' }],
    ['wiki_resolve', { query: 'needle', project: null }],
    ['wiki_write', { content: 'Missing path' }],
  ];
  const child = spawnSync(process.execPath, [path.join(pluginRoot, 'mcp/server.js')], {
    cwd: temp, env: { ...process.env, WORK_LOG_ROOT: root, XDG_CACHE_HOME: path.join(temp, 'cache') },
    encoding: 'utf8', timeout: 15000,
    input: requests.map(([name, args], i) => JSON.stringify({ jsonrpc: '2.0', id: i + 1, method: 'tools/call', params: { name, arguments: args } })).join('\n')+'\n',
  });
  assert.equal(child.status, 0, child.error?.message || child.stderr);
  const messages = child.stdout.trim().split('\n').map(JSON.parse);
  assert.equal(messages.length, requests.length);
  const results = messages.slice(0, 10).map((message) => {
    assert.equal(message.error, undefined);
    assert.notEqual(message.result.isError, true, message.result.content[0].text);
    return JSON.parse(message.result.content[0].text);
  });
  assert.equal(results[0].written.path, rel);
  assert.equal(results[1].candidates[0].path, rel);
  assert.equal(results[1].candidates[0].project, '한글');
  assert.equal(results[2].frontmatter.project, '한글');
  assert.equal(results[2].category, 'history');
  assert.equal(results[5].status, 'OK');
  assert.match(results[6].body, /needle changed\n\nAppend once/);
  assert.equal(results[7].project, '_shared');
  assert.equal(results[7].category, 'docs');
  assert.equal(results[8].total, 2);
  assert.equal(results[9].server, '0.3.2');
  assert.equal(JSON.parse(fs.readFileSync(results[9].indexPath, 'utf8')).version, 3);
  assert.match(fs.readFileSync(path.join(root, rel), 'utf8'), /custom:\n  preserved: true\n/);
  for (const message of messages.slice(10)) assert.equal(message.error.code, -32602);
  const oldIndex = JSON.parse(fs.readFileSync(results[9].indexPath, 'utf8'));
  fs.writeFileSync(results[9].indexPath, JSON.stringify({ ...oldIndex, version: 2 }));
  const migrated = spawnSync(process.execPath, [path.join(pluginRoot, 'mcp/server.js')], {
    cwd: temp, env: { ...process.env, WORK_LOG_ROOT: root, XDG_CACHE_HOME: path.join(temp, 'cache') },
    encoding: 'utf8', timeout: 15000,
    input: [['wiki_resolve', { query: 'needle' }], ['wiki_sync', {}], ['wiki_resolve', { query: 'needle', project: '한글' }]]
      .map(([name, args], i) => JSON.stringify({ jsonrpc: '2.0', id: i + 1, method: 'tools/call', params: { name, arguments: args } })).join('\n')+'\n',
  });
  assert.equal(migrated.status, 0, migrated.error?.message || migrated.stderr);
  const migration = migrated.stdout.trim().split('\n').map(JSON.parse);
  assert.equal(migration[0].result.isError, true);
  assert.match(migration[0].result.content[0].text, /INDEX_VERSION.*wiki_sync/);
  assert.equal(JSON.parse(migration[1].result.content[0].text).root, root);
  assert.equal(JSON.parse(migration[2].result.content[0].text).candidates[0].path, rel);
});

test('중앙 프로젝트 vault는 검색·쓰기·스캔·캐시를 분리하고 기존 이력을 보존한다', (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'work-log-projects-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const baseRoot = path.join(temp, 'central');
  fs.mkdirSync(baseRoot);
  fs.writeFileSync(path.join(baseRoot, 'legacy.md'), '# sharedtoken legacy');
  const roots = ['project-a', 'project-b'].map((name) => {
    const projectDir = path.join(temp, name);
    fs.mkdirSync(projectDir);
    const selected = projectVaultPath({ baseRoot, projectDir });
    fs.mkdirSync(selected.root);
    assert.deepEqual(projectVaultPath({ baseRoot, projectDir }), selected);
    fs.writeFileSync(path.join(selected.configDir, '.work-log.json'), JSON.stringify({ scope: 'project', root: selected.root }));
    return selected;
  });
  const env = { ...process.env, WORK_LOG_ROOT: '', XDG_CACHE_HOME: path.join(temp, 'cache') };
  const call = (cwd, requests, overrides = {}) => {
    const child = spawnSync(process.execPath, [path.join(pluginRoot, 'mcp/server.js')], {
      cwd, env: { ...env, ...overrides }, encoding: 'utf8', timeout: 15000,
      input: requests.map(([name, args = {}], i) => JSON.stringify({
        jsonrpc: '2.0', id: i + 1, method: 'tools/call', params: { name, arguments: args },
      })).join('\n') + '\n',
    });
    assert.equal(child.status, 0, child.error?.message || child.stderr);
    const messages = child.stdout.trim().split('\n').map((line) => JSON.parse(line));
    assert.equal(messages.length, requests.length);
    return messages.map((message) => {
      assert.equal(message.error, undefined);
      assert.notEqual(message.result.isError, true, message.result.content[0].text);
      return JSON.parse(message.result.content[0].text);
    });
  };
  const [empty, written, resolved, aStatus] = call(roots[0].projectDir, [
    ['wiki_sync'],
    ['wiki_write', { path: 'same-note.md', content: '# sharedtoken project-a', frontmatter: { title: 'sharedtoken project-a' } }],
    ['wiki_resolve', { query: 'sharedtoken' }],
    ['wiki_status'],
  ]);
  assert.equal(empty.counts.files, 0);
  assert.equal(written.indexing.status, 'OK');
  assert.equal(resolved.total, 1);
  assert.equal(resolved.candidates[0].title, 'sharedtoken project-a');
  assert.equal(aStatus.root, roots[0].root);

  for (let i = 0; i < 12; i++) fs.writeFileSync(path.join(roots[1].root, `extra-${i}.md`), '# sharedtoken extra-b');
  const [bWritten, bResolved, bStatus] = call(pluginRoot, [
    ['wiki_write', { path: 'same-note.md', content: '# sharedtoken project-b' }],
    ['wiki_resolve', { query: 'sharedtoken' }],
    ['wiki_status'],
  ], { WORK_LOG_ROOT: roots[1].root });
  assert.equal(bWritten.indexing.status, 'OK');
  assert.equal(bResolved.total, 13);
  assert.equal(bStatus.root, roots[1].root);
  assert.notEqual(aStatus.indexPath, bStatus.indexPath);
  const bIndex = fs.readFileSync(bStatus.indexPath, 'utf8');

  const [aSynced, aRead, aResolved] = call(roots[0].projectDir, [
    ['wiki_sync'], ['wiki_read', { path: 'same-note.md' }], ['wiki_resolve', { query: 'sharedtoken' }],
  ]);
  assert.equal(aSynced.scan.filesRead, 1);
  assert.equal(aSynced.counts.files, 1);
  assert.equal(aResolved.total, 1);
  assert.equal(aRead.body, '\n# sharedtoken project-a');
  assert.equal(fs.readFileSync(bStatus.indexPath, 'utf8'), bIndex);
  assert.equal(fs.readFileSync(path.join(baseRoot, 'legacy.md'), 'utf8'), '# sharedtoken legacy');
  const [flat] = call(pluginRoot, [['wiki_sync']], { WORK_LOG_ROOT: baseRoot });
  assert.equal(flat.counts.files, 15);
});
