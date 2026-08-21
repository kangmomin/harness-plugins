#!/usr/bin/env node
/**
 * 계측 전용 최소 MCP 서버 — plan §1a.
 *
 * 플러그인 MCP 서버의 process.cwd() 가 실제로 무엇인지 확인한다.
 * 이 값에 따라 프로젝트 스코프 자동 탐지(.work-log.json walk-up)의 채택 여부가 갈린다.
 *
 * 사용법: .mcp.json 의 args 를 이 파일로 바꾸고 Claude Code 재시작 후
 *        서로 다른 두 프로젝트에서 probe 툴을 호출해 값을 비교한다.
 */
import process from 'node:process';

const send = (m) => process.stdout.write(JSON.stringify(m) + '\n');
const TOOL = {
  name: 'probe',
  description: 'MCP 서버 프로세스의 실행 환경을 그대로 보고한다 (계측 전용).',
  inputSchema: { type: 'object', additionalProperties: false, properties: {} },
};

let buf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => {
  buf += c;
  let nl;
  while ((nl = buf.indexOf('\n')) !== -1) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { continue; }
    if (!('id' in msg)) continue;

    if (msg.method === 'initialize') {
      send({ jsonrpc: '2.0', id: msg.id, result: {
        protocolVersion: msg.params?.protocolVersion ?? '2024-11-05',
        capabilities: { tools: {} },
        serverInfo: { name: 'work-log-probe', version: '0.0.1' },
      }});
    } else if (msg.method === 'tools/list') {
      send({ jsonrpc: '2.0', id: msg.id, result: { tools: [TOOL] } });
    } else if (msg.method === 'tools/call') {
      const payload = {
        cwd: process.cwd(),
        env_PWD: process.env.PWD ?? null,
        CLAUDE_PLUGIN_ROOT: process.env.CLAUDE_PLUGIN_ROOT ?? null,
        WORK_LOG_ROOT_raw: JSON.stringify(process.env.WORK_LOG_ROOT ?? null),
        argv: process.argv,
      };
      send({ jsonrpc: '2.0', id: msg.id, result: {
        content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }],
      }});
    } else {
      send({ jsonrpc: '2.0', id: msg.id, error: { code: -32601, message: 'Method not found' } });
    }
  }
});
