"""No Apidog network calls; optional pinned OAS validator + local HTTP byte capture."""
import base64
from copy import deepcopy
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'minmos-harness/skills/apidog-schema-gen/assets/apidog_contract.py'
spec = importlib.util.spec_from_file_location('apidog_contract', MODULE)
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
HAS_VALIDATOR = importlib.util.find_spec('openapi_spec_validator') is not None
if os.environ.get('HARNESS_REQUIRE_OPENAPI') == '1' and not HAS_VALIDATOR:
    raise RuntimeError('Required openapi-spec-validator unavailable')


def target(project=101, **changes):
    result = dict(project_id=project, branch_id=201, method='post', path='/things/{id}',
                  folder_id=301, mode='OVERWRITE_EXISTING', schema_mode='KEEP_EXISTING')
    result.update(changes)
    return result


def document():
    return dict(openapi='3.1.0', info=dict(title='Fixture', version='1'),
        security=[{'Bearer': []}],
        paths={'/things/{id}': {
            'parameters': [dict(name='id', **{'in': 'path'}, required=True, schema={'type': 'integer'})],
            'post': {'x-apidog-status': 'tested', 'parameters': [
                dict(name='search', **{'in': 'query'}, schema={'type': 'string'}),
                dict(name='X-Correlation', **{'in': 'header'}, schema={'type': 'string'}),
                dict(name='session', **{'in': 'cookie'}, schema={'type': 'string'})],
                'requestBody': {'required': True, 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Node'}}}},
                'responses': {'201': {'description': 'Created', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Node'}}}},
                              '202': {'description': 'Accepted'}, '204': {'description': 'No body'},
                              '400': {'description': 'Invalid', 'headers': {'X-Reason': {'schema': {'type': 'string'}}}}}},
            'get': {'responses': {'200': {'description': 'Other method'}}}},
            '/unrelated': {'get': {'responses': {'200': {'description': 'Other path'}}}}},
        components={'schemas': {
            'Node': {'type': 'object', 'properties': {
                'label': {'type': ['string', 'null']},
                'nullableList': {'type': ['array', 'null'], 'items': {'type': 'integer'}},
                'nullableObject': {'type': ['object', 'null'], 'properties': {'id': {'type': 'integer'}}},
                'choice': {'oneOf': [{'type': 'null'}, {'type': 'string', 'enum': ['A']}]},
                'next': {'$ref': '#/components/schemas/Node'}},
                'example': {'type': ['literal', 'null'], '$ref': 'literal-example'}},
            'Unrelated': {'type': 'string'}},
            'securitySchemes': {'Bearer': {'type': 'http', 'scheme': 'bearer'}}})


def selected(dialect='3.0'):
    doc = contract.select_endpoint(dict(document=document(), path='/things/{id}', method='post'))
    return contract.normalize(dict(document=doc, dialect=dialect))


class ApidogContractTests(unittest.TestCase):
    def test_select_preserves_all_statuses_parameters_bodies_and_reachable_recursive_refs(self):
        source = document()
        got = contract.select_endpoint(dict(document=source, path='/things/{id}', method='post'))
        self.assertEqual(got['paths']['/things/{id}']['post'], source['paths']['/things/{id}']['post'])
        self.assertEqual(got['paths']['/things/{id}']['parameters'], source['paths']['/things/{id}']['parameters'])
        self.assertEqual(set(got['components']['schemas']), {'Node'})
        self.assertEqual(got['components']['securitySchemes'], source['components']['securitySchemes'])
        self.assertEqual(got['components']['schemas']['Node']['properties']['next'], {'$ref': '#/components/schemas/Node'})
        self.assertEqual(len(got['paths']), 1)
        self.assertNotIn('get', got['paths']['/things/{id}'])
        normalized = selected()
        operation = normalized['paths']['/things/{id}']['post']
        self.assertEqual(set(operation['responses']), {'201', '202', '204', '400'})
        self.assertNotIn('content', operation['responses']['204'])
        self.assertEqual([p['in'] for p in operation['parameters']], ['query', 'header', 'cookie'])
        self.assertEqual(normalized['components']['schemas']['Node']['example'], source['components']['schemas']['Node']['example'])

    def test_delete_body_and_get_body_are_preserved_by_actual_contract(self):
        for method in ['delete', 'get']:
            source = document()
            source['paths']['/things/{id}'][method] = source['paths']['/things/{id}'].pop('post')
            got = contract.select_endpoint(dict(document=source, path='/things/{id}', method=method))
            self.assertIn('requestBody', got['paths']['/things/{id}'][method])
            self.assertIn('201', got['paths']['/things/{id}'][method]['responses'])

    def test_discriminator_and_security_name_closure_excludes_literal_refs(self):
        source = document()
        node = source['components']['schemas']['Node']
        node['discriminator'] = {'propertyName': 'kind', 'mapping': {'leaf': '#/components/schemas/Leaf'}}
        source['components']['schemas']['Leaf'] = {'type': 'object', 'properties': {'kind': {'type': 'string'}}}
        source['components']['examples'] = {'Sample': {'value': {'schema': {'type': ['literal', 'null']}, '$ref': 'literal'}}}
        media = source['paths']['/things/{id}']['post']['responses']['201']['content']['application/json']
        media['examples'] = {'sample': {'$ref': '#/components/examples/Sample'}}
        media['x-custom'] = {'$ref': 'vendor-literal'}
        got = contract.select_endpoint(dict(document=source, path='/things/{id}', method='post'))
        self.assertEqual(set(got['components']['schemas']), {'Node', 'Leaf'})
        self.assertEqual(got['components']['examples'], source['components']['examples'])
        normalized = contract.normalize(dict(document=got, dialect='3.0'))
        self.assertEqual(normalized['components']['examples'], got['components']['examples'])
        contract.local_references(normalized)
        media['examples']['sample']['$ref'] = 'https://example.invalid/unresolved'
        with self.assertRaisesRegex(contract.Blocked, 'EXTERNAL_REF'):
            contract.select_endpoint(dict(document=source, path='/things/{id}', method='post'))

    def test_dynamic_tool_names_and_both_project_arg_formats(self):
        for args in [['--project=101'], ['--project-id=101'], ['--project', '101'], ['--project-id', '101']]:
            for suffix in ['alpha', 'new_project_suffix']:
                tools = [dict(name='actual_host_read_' + suffix, operation='read', project_id=101, branch_id=201, verified=True),
                         dict(name='actual_host_refs_' + suffix, operation='refs', project_id=101, branch_id=201, verified=True),
                         dict(name='actual_host_refresh_' + suffix, operation='refresh', project_id=101, branch_id=201, verified=True)]
                result = contract.discover(dict(project_id=101, branch_id=201, tools=tools, mcp_args=args))
                calls = []
                runtime = {t['name']: lambda name=t['name']: calls.append(name) for t in tools}
                for name in result['callables'].values():
                    runtime[name]()
                self.assertEqual(set(calls), {t['name'] for t in tools})
        with self.assertRaisesRegex(contract.Blocked, 'AMBIGUOUS'):
            contract.project_args(['--project=101', '--project-id=102'])
        with self.assertRaisesRegex(contract.Blocked, 'MCP_PROJECT_MISMATCH'):
            contract.discover(dict(project_id=101, branch_id=201, tools=tools, mcp_args=['--project=102']))

    def test_proto_provider_resolves_moved_install_and_actual_script_argument(self):
        import subprocess
        with tempfile.TemporaryDirectory(prefix='proto 한글 ') as tmp:
            for version in ['2.0.1', 'new version']:
                root = Path(tmp) / version / 'skills/go-codegen'
                (root / 'scripts').mkdir(parents=True)
                main = root / 'SKILL.md'
                main.write_text('Scripts: scripts/find-proto.sh')
                script = root / 'scripts/find-proto.sh'
                script.write_text('#!/bin/bash\nprintf "%s" "$1"\n')
                data = dict(skills=[dict(name='renamed-stack:go-codegen', path=str(main), contract_read=True,
                                        script_relative='scripts/find-proto.sh')])
                got = contract.proto_helper(data)
                self.assertEqual(subprocess.check_output(['bash', got['script'], 'pms'], text=True), 'pms')
                script.unlink()
                with self.assertRaises(OSError):
                    contract.proto_helper(data)

    def test_partial_and_pending_responses_never_become_safe_retry(self):
        for status, success, changed, failed, expected in [(200, True, 1, 1, 'PARTIAL'), (400, False, 1, 0, 'PARTIAL'),
                (202, True, 0, 0, 'UNKNOWN'), (200, True, 1, 0, 'ACKNOWLEDGED'), (401, False, 0, 0, 'REJECTED_NO_WRITE')]:
            response = dict(http_status=status, no_write_verified=True,
                body=dict(success=success, data=dict(counters=dict(endpoint=dict(created=changed, failed=failed)), errors=[])))
            self.assertEqual(contract.outcome(response)['state'], expected)
        self.assertEqual(contract.outcome(dict(http_status=302))['state'], 'UNKNOWN')
        self.assertEqual(contract.outcome(dict(http_status=200, body={} ))['state'], 'UNKNOWN')


@unittest.skipUnless(HAS_VALIDATOR, 'openapi-spec-validator (required in CI)')
class ApidogValidatedTests(unittest.TestCase):
    def test_declared_dialect_validation_and_nullable_enum_semantics(self):
        from openapi_schema_validator import OAS30Validator, OAS31Validator
        for dialect, validator in [('3.0', OAS30Validator), ('3.1', OAS31Validator)]:
            doc = selected(dialect)
            contract.validate(doc)
            props = doc['components']['schemas']['Node']['properties']
            for name, accepted in [('label', [None, 'x']), ('nullableList', [None, [1]]),
                                   ('nullableObject', [None, {'id': 1}]), ('choice', [None, 'A'])]:
                checker = validator(props[name])
                for value in accepted:
                    self.assertTrue(checker.is_valid(value), (dialect, name, value, list(checker.iter_errors(value))))
            self.assertFalse(validator(props['choice']).is_valid('B'))
            self.assertFalse(validator(props['label']).is_valid(12))
        invalid = selected()
        invalid['components']['schemas']['Node']['properties']['label'] = {'type': ['string', 'null']}
        with self.assertRaisesRegex(contract.Blocked, 'OPENAPI_INVALID'):
            contract.validate(invalid)

    def test_component_and_header_named_schema_are_maps_not_schema_objects(self):
        source = document()
        source['components']['responses'] = {'schema': {'description': 'named schema', 'content': {
            'application/json': {'schema': {'type': ['string', 'null']}}},
            'headers': {'schema': {'schema': {'type': ['string', 'null']}}}}}
        source['paths']['/things/{id}']['post']['responses']['201'] = {'$ref': '#/components/responses/schema'}
        doc = contract.normalize(dict(document=contract.select_endpoint(dict(document=source, path='/things/{id}', method='post')), dialect='3.0'))
        contract.validate(doc)
        response = doc['components']['responses']['schema']
        self.assertEqual(response['content']['application/json']['schema'], {'type': 'string', 'nullable': True})
        self.assertEqual(response['headers']['schema']['schema'], {'type': 'string', 'nullable': True})

    def test_exclusive_bound_conversion_keeps_boundary_values_and_bad_schema_blocks(self):
        from openapi_schema_validator import OAS30Validator, OAS31Validator
        for keyword, bound in [('exclusiveMinimum', 'minimum'), ('exclusiveMaximum', 'maximum')]:
            original = dict(type='number', **{bound: 5, keyword: True})
            changed = contract.schema(original, '3.1')
            self.assertEqual(changed, dict(type='number', **{keyword: 5}))
            for value in [4, 5, 6]:
                self.assertEqual(OAS30Validator(original).is_valid(value), OAS31Validator(changed).is_valid(value))
            doc = selected('3.1')
            doc['components']['schemas']['Bad'] = original
            with self.assertRaisesRegex(contract.Blocked, 'OPENAPI_INVALID'):
                contract.validate(doc)
            with self.assertRaisesRegex(contract.Blocked, 'EXCLUSIVE_BOUND_UNSUPPORTED'):
                contract.schema(changed, '3.0')

    def freeze(self, folder, project=101, **changes):
        return contract.freeze(dict(document=selected(), target=target(project, **changes), run_id='run-' + str(project), directory=folder))

    def test_interleaved_same_slug_projects_transmit_original_bytes_to_correct_local_path(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path, self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.end_headers()
            def log_message(self, *args):
                pass
        with tempfile.TemporaryDirectory() as tmp:
            a = self.freeze(tmp, 101)
            b = self.freeze(tmp, 102)
            self.assertNotEqual(a['directory'], b['directory'])
            for receipt in [a, b]:
                root = Path(receipt['directory'])
                self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
                self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in root.iterdir()))
            with HTTPServer(('127.0.0.1', 0), Handler) as server:
                worker = threading.Thread(target=server.serve_forever)
                worker.start()
                try:
                    for receipt in [b, a]:
                        result = contract.request_bytes(dict(receipt=receipt, target=receipt['target'], run_id=receipt['run_id']))
                        payload = base64.b64decode(result['request_base64'])
                        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                        try:
                            conn.request('POST', '/v1/projects/' + str(receipt['target']['project_id']) + '/import-openapi', body=payload)
                            self.assertEqual(conn.getresponse().status, 200)
                        finally:
                            conn.close()
                        self.assertEqual(contract.digest(received[-1][1]), receipt['request_sha256'])
                        self.assertEqual(json.loads(payload)['options']['targetBranchId'], 201)
                    self.assertIn('/102/', received[0][0])
                    self.assertIn('/101/', received[1][0])
                finally:
                    server.shutdown()
                    worker.join(timeout=5)

    def test_deprecated_preserves_original_dialect_and_only_changes_two_fields(self):
        doc = selected()
        doc['openapi'] = '3.0.0'
        before = deepcopy(doc)
        operation = doc['paths']['/things/{id}']['post']
        operation.update({'x-apidog-status': 'deprecated', 'deprecated': True})
        with tempfile.TemporaryDirectory() as tmp:
            receipt = contract.freeze(dict(document=doc, target=target(), run_id='deprecated', directory=tmp))
            sent = json.loads((Path(receipt['directory']) / 'openapi.json').read_bytes())
            sent['paths']['/things/{id}']['post']['x-apidog-status'] = before['paths']['/things/{id}']['post']['x-apidog-status']
            del sent['paths']['/things/{id}']['post']['deprecated']
            self.assertEqual(sent, before)

    def test_local_server_accepts_body_but_loses_response_then_readback_no_resend(self):
        stored = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                stored.append(self.rfile.read(int(self.headers['Content-Length'])))
                self.close_connection = True  # accepted state; deliberately no HTTP response
            def log_message(self, *args):
                pass
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self.freeze(tmp)
            data = dict(receipt=receipt, target=receipt['target'], run_id=receipt['run_id'])
            payload = base64.b64decode(contract.request_bytes(data)['request_base64'])
            with HTTPServer(('127.0.0.1', 0), Handler) as server:
                thread = threading.Thread(target=server.handle_request)
                thread.start()
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                try:
                    conn.request('POST', '/v1/projects/101/import-openapi', body=payload)
                    with self.assertRaises(http.client.RemoteDisconnected):
                        conn.getresponse()
                finally:
                    conn.close()
                    thread.join(timeout=5)
            state = contract.outcome(dict(transmission_started=True))['state']
            self.assertEqual(state, 'UNKNOWN')
            self.assertFalse(contract.decision(dict(data, state=state, attempts=1))['may_retry'])
            observed = dict(target=receipt['target'], request_sha256=contract.digest(stored[0]), fresh=True,
                            after_attempt=True, complete=True, matches_expected=stored[0] == payload)
            self.assertEqual(contract.decision(dict(data, state=state, attempts=1, readback=observed))['status'], 'OBSERVED_MATCH')
            self.assertEqual(len(stored), 1)

    def test_modified_payload_and_cross_target_credentials_block_before_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self.freeze(tmp)
            data = dict(receipt=receipt, target=receipt['target'], run_id=receipt['run_id'])
            with self.assertRaisesRegex(contract.Blocked, 'FROZEN_TARGET_MISMATCH'):
                contract.request_bytes(dict(data, target=target(102)))
            with self.assertRaisesRegex(contract.Blocked, 'CREDENTIAL_TARGET_MISMATCH'):
                contract.decision(dict(data, credential_target=target(102), state='REJECTED_NO_WRITE', no_write_verified=True, attempts=1))
            (Path(receipt['directory']) / 'request.json').write_text('{"input":"other run"}')
            with self.assertRaisesRegex(contract.Blocked, 'PAYLOAD_CHANGED'):
                contract.request_bytes(data)

    def test_timeout_requires_matching_fresh_full_readback_and_never_blind_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = self.freeze(tmp)
            data = dict(receipt=receipt, target=receipt['target'], run_id=receipt['run_id'], state='UNKNOWN', attempts=1)
            self.assertFalse(contract.decision(data)['may_retry'])
            observed = dict(target=receipt['target'], request_sha256=receipt['request_sha256'], fresh=True,
                            after_attempt=True, complete=True, matches_expected=True)
            self.assertEqual(contract.decision(dict(data, readback=observed))['status'], 'OBSERVED_MATCH')
            for key, bad in [('request_sha256', 'stale-hash'), ('fresh', False), ('complete', False), ('matches_expected', False)]:
                result = contract.decision(dict(data, readback=dict(observed, **{key:bad})))
                self.assertEqual(result['status'], 'UNKNOWN:IMPORT')
                self.assertFalse(result['may_retry'])
            with self.assertRaisesRegex(contract.Blocked, 'READBACK_TARGET_MISMATCH'):
                contract.decision(dict(data, readback=dict(observed, target=target(102))))
            self.assertTrue(contract.decision(dict(data, state='NOT_SENT', no_write_verified=True))['may_retry'])
            self.assertFalse(contract.decision(dict(data, state='NOT_SENT', no_write_verified=True, attempts=2))['may_retry'])
            new = self.freeze(tmp, mode='CREATE_NEW')
            result = contract.decision(dict(data, receipt=new, target=new['target'], readback=dict(observed, target=new['target'], request_sha256=new['request_sha256'])))
            self.assertEqual(result['status'], 'UNKNOWN:IMPORT')
            observed_new = dict(observed, target=new['target'], request_sha256=new['request_sha256'])
            created = dict(before_verified=True, acknowledged_created_count=1, before_ids=[8], after_ids=[8, 9], new_matching_ids=[9])
            completed = contract.decision(dict(data, receipt=new, target=new['target'], state='ACKNOWLEDGED', readback=observed_new, creation=created))
            self.assertEqual(completed['status'], 'OBSERVED_NEW_MATCH')
            self.assertEqual(completed['created_ids'], [9])
            # The same snapshots never authorize or resolve an UNKNOWN create attempt.
            self.assertEqual(contract.decision(dict(data, receipt=new, target=new['target'], readback=observed_new, creation=created))['status'], 'UNKNOWN:IMPORT')


if __name__ == '__main__':
    unittest.main()
