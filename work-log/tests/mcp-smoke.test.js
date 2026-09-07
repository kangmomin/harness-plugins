import assert from 'node:assert/strict';
import { fork, spawn } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

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
  assert.equal(messages[0].result.serverInfo.version, '0.3.0');
  assert.deepEqual(
    messages[1].result.tools.map((tool) => tool.name),
    ['wiki_resolve', 'wiki_read', 'wiki_write', 'wiki_sync', 'wiki_status'],
  );
});
