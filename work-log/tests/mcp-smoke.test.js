import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
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
  assert.equal(messages[0].result.serverInfo.version, '0.2.1');
  assert.deepEqual(
    messages[1].result.tools.map((tool) => tool.name),
    ['wiki_resolve', 'wiki_read', 'wiki_write', 'wiki_sync', 'wiki_status'],
  );
});
