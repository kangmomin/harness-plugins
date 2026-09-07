#!/usr/bin/env python3
"""Opt-in actual Claude loader probe; all inference responses come from loopback.

No real model, account, MCP or file tools are used. Store only agent/tool metadata.
"""
import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import uuid


def probe(cli, plugin, agent):
    marker = uuid.uuid4().hex
    parent_marker, child_marker = 'PARENT_' + marker, 'CHILD_' + marker
    seen, errors = [], []
    parent_calls = 0

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            nonlocal parent_calls
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path.split('?')[0] == '/v1/messages/count_tokens':
                data = b'{"input_tokens":10}'
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
                return
            if self.path.split('?')[0] != '/v1/messages':
                errors.append('unexpected API path: ' + self.path)
                self.send_error(400); return
            user_texts = [b.get('text', '') for m in request.get('messages', []) if m['role'] == 'user'
                          for b in m['content'] if isinstance(b, dict) and b.get('type') == 'text']
            is_parent = any(parent_marker in text for text in user_texts)
            is_child = any(child_marker in text for text in user_texts) and not is_parent
            if is_child and not seen:
                seen.append(sorted(t['name'] for t in request['tools']))
                block = {'type': 'text', 'text': 'loader smoke done'}
            elif is_parent and parent_calls == 0:
                parent_calls += 1
                names = {t['name'] for t in request['tools']}
                if not {'Agent', 'Bash', 'Write', 'Edit'} <= names:
                    errors.append('parent tool pool was narrowed: ' + ','.join(sorted(names)))
                block = {'type': 'tool_use', 'id': 'toolu_loader_smoke', 'name': 'Agent',
                         'input': {'description': 'Local loader smoke', 'subagent_type': agent, 'run_in_background': False,
                                   'prompt': child_marker + ' Return loader smoke done without using any tools.'}}
            elif is_parent and parent_calls == 1:
                parent_calls += 1
                results = [b for m in request['messages'] if m['role'] == 'user'
                           for b in m['content'] if isinstance(b, dict)
                           and b.get('type') == 'tool_result' and b.get('tool_use_id') == 'toolu_loader_smoke']
                if not results or any(b.get('is_error') for b in results) or not seen:
                    errors.append('Agent did not successfully launch: ' + json.dumps(results))
                block = {'type': 'text', 'text': 'parent done'}
            else:
                errors.append('unexpected additional or unidentified model request')
                self.send_error(400); return
            reason = 'tool_use' if block['type'] == 'tool_use' else 'end_turn'
            response = {'id': 'msg_loader_smoke', 'type': 'message', 'role': 'assistant',
                        'model': request['model'], 'content': [block], 'stop_reason': reason,
                        'stop_sequence': None, 'usage': {'input_tokens': 10, 'output_tokens': 10}}
            if request.get('stream'):
                events = [('message_start', {'type': 'message_start', 'message': {**response, 'content': [], 'stop_reason': None}})]
                empty = {**block, 'input': {}} if block['type'] == 'tool_use' else {'type': 'text', 'text': ''}
                delta = {'type': 'input_json_delta', 'partial_json': json.dumps(block['input'])} if block['type'] == 'tool_use' else {'type': 'text_delta', 'text': block['text']}
                events += [('content_block_start', {'type': 'content_block_start', 'index': 0, 'content_block': empty}),
                           ('content_block_delta', {'type': 'content_block_delta', 'index': 0, 'delta': delta}),
                           ('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
                           ('message_delta', {'type': 'message_delta', 'delta': {'stop_reason': reason, 'stop_sequence': None}, 'usage': {'output_tokens': 10}}),
                           ('message_stop', {'type': 'message_stop'})]
                data = ''.join(f'event: {event}\ndata: {json.dumps(value)}\n\n' for event, value in events).encode()
                content_type = 'text/event-stream'
            else:
                data = json.dumps(response).encode(); content_type = 'application/json'
            self.send_response(200); self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='harness-host-loader-') as directory:
            env = {'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8', 'CLAUDE_CONFIG_DIR': directory,
                   'ANTHROPIC_API_KEY': 'local-fixture-only',
                   'ANTHROPIC_BASE_URL': f'http://127.0.0.1:{server.server_port}',
                   'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'DISABLE_AUTOUPDATER': '1',
                   'NO_PROXY': '127.0.0.1,localhost'}
            cmd = [cli, '--settings', '{"disableAllHooks":true}', '--plugin-dir', str(plugin), '--setting-sources', '',
                   '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                   '--no-session-persistence', '--output-format', 'json', '--max-budget-usd', '0.01',
                   '-p', parent_marker + ' Perform only the local host metadata smoke.']
            result = subprocess.run(cmd, cwd=directory, env=env, capture_output=True, text=True, timeout=45)
            if result.returncode:
                raise RuntimeError(f'Claude loader exit {result.returncode}: {result.stderr[-600:]} {result.stdout[-1800:]}')
            if errors or len(seen) != 1 or parent_calls != 2:
                raise RuntimeError(str({'errors': errors, 'subagent_requests': len(seen), 'parent_calls': parent_calls,
                                        'output': result.stdout[-700:]}))
            return {'agent': agent, 'tools': seen[0], 'delegation_verified': True}
    finally:
        server.shutdown(); server.server_close(); thread.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--agent', help='optional single plugin:name for development')
    args = parser.parse_args()
    cli = shutil.which('claude')
    if not cli:
        raise SystemExit('BLOCKED:CLAUDE_CLI_MISSING')
    version = subprocess.check_output([cli, '--version'], text=True).strip()
    output = []
    for path in sorted(args.root.glob('*/agents/*.md')):
        name = f'{path.parents[1].name}:{path.stem}'
        if args.agent and name != args.agent:
            continue
        entry = probe(cli, path.parents[1].resolve(), name)
        entry['source_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        output.append(entry)
        print(json.dumps(entry), flush=True)
    with tempfile.TemporaryDirectory(prefix='harness-host-negative-') as directory:
        plugin = Path(directory)
        (plugin / '.claude-plugin').mkdir(); (plugin / 'agents').mkdir()
        (plugin / '.claude-plugin/plugin.json').write_text('{"name":"host-negative","version":"1.0.0"}')
        (plugin / 'agents/legacy.md').write_text('---\nname: legacy\ndescription: Local negative fixture\nallowed-tools: Read, Glob, Grep\n---\nReturn a short text only.\n')
        negative = probe(cli, plugin, 'host-negative:legacy')
        if not {'Bash', 'Write', 'Edit'} <= set(negative['tools']):
            raise SystemExit('negative control did not inherit writer tools; investigate host contract')
    receipt = {'host': 'Claude Code', 'version': version, 'cli_sha256': hashlib.sha256(Path(cli).read_bytes()).hexdigest(), 'transport': 'loopback mock; no real inference',
               'agents': output, 'negative_control': negative}
    with args.output.open('x') as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2); handle.write('\n')


if __name__ == '__main__':
    main()
