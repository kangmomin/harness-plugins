#!/usr/bin/env python3
"""Local Apidog schema/receipt boundary. Never connects to Apidog or reads tokens.

normalize/tools/decision are pure JSON; freeze creates one private run directory;
request verifies the original receipt and returns the exact buffered request bytes.
"""
import argparse
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

METHODS = {'get', 'put', 'post', 'delete', 'patch', 'head', 'options', 'trace'}
MODES = {'OVERWRITE_EXISTING', 'KEEP_EXISTING', 'AUTO_MERGE', 'CREATE_NEW'}
NAMED_MAPS = {'headers', 'content', 'responses', 'callbacks', 'links', 'encoding'}
STATUSES = {'designing', 'pending', 'developing', 'integrating', 'testing', 'tested',
            'released', 'deprecated', 'exception', 'obsolete'}


class Blocked(ValueError):
    pass


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def schema(value, dialect):
    if not isinstance(value, dict):
        if dialect == '3.1' and type(value) is bool:
            return value
        raise Blocked('SCHEMA_UNSUPPORTED')
    result = deepcopy(value)
    typ = result.get('type')
    if dialect == '3.0':
        if isinstance(typ, list):
            if len(typ) != 2 or len(set(typ)) != 2 or 'null' not in typ:
                raise Blocked('TYPE_UNION_UNSUPPORTED')
            result['type'] = next(t for t in typ if t != 'null')
            result['nullable'] = True
        elif typ == 'null':
            # Null-only, not an invented nullable string domain.
            if 'enum' in result and None not in result['enum']:
                raise Blocked('EMPTY_NULL_DOMAIN')
            result.update(type='string', nullable=True, enum=[None])
    elif dialect == '3.1' and 'nullable' in result:
        nullable = result.pop('nullable')
        if type(nullable) is not bool or not isinstance(typ, str) or typ == 'null':
            raise Blocked('NULLABLE_CONVERSION_UNSUPPORTED')
        if nullable:
            result['type'] = [typ, 'null']
    for exclusive, bound in [('exclusiveMinimum', 'minimum'), ('exclusiveMaximum', 'maximum')]:
        if exclusive not in result:
            continue
        value = result[exclusive]
        if dialect == '3.1' and type(value) is bool:
            if value:
                if type(result.get(bound)) not in (int, float):
                    raise Blocked('EXCLUSIVE_BOUND_UNSUPPORTED')
                result[exclusive] = result.pop(bound)
            else:
                del result[exclusive]
        elif dialect == '3.0' and type(value) is not bool:
            raise Blocked('EXCLUSIVE_BOUND_UNSUPPORTED')
    for key in ('properties', 'patternProperties', '$defs', 'dependentSchemas'):
        if key in result:
            result[key] = {name: schema(child, dialect) for name, child in result[key].items()}
    for key in ('items', 'additionalProperties', 'not', 'contains', 'if', 'then', 'else', 'unevaluatedProperties'):
        if key in result and isinstance(result[key], (dict, bool)):
            if key == 'additionalProperties' and type(result[key]) is bool:
                continue
            result[key] = schema(result[key], dialect)
    for key in ('oneOf', 'anyOf', 'allOf', 'prefixItems'):
        if key in result:
            result[key] = [schema(child, dialect) for child in result[key]]
    return result


def normalize(data):
    dialect = data['dialect']
    if dialect not in ('3.0', '3.1'):
        raise Blocked('DIALECT_UNSUPPORTED')
    doc = deepcopy(data['document'])
    def walk(value):
        if isinstance(value, list):
            return [walk(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for k, v in value.items():
            if k == 'schema':
                result[k] = schema(v, dialect)
            elif k in ('example', 'examples', 'default') or k.startswith('x-'):
                result[k] = deepcopy(v)
            elif k in NAMED_MAPS:
                result[k] = {name: walk(child) for name, child in v.items()}
            else:
                result[k] = walk(v)
        return result
    components = doc.pop('components', {})
    doc = walk(doc)
    if components:
        doc['components'] = {k: ({n: schema(s, dialect) for n, s in v.items()} if k == 'schemas' else deepcopy(v) if k == 'examples' else {n: walk(item) for n, item in v.items()}) for k, v in components.items()}
    doc['openapi'] = '3.0.3' if dialect == '3.0' else '3.1.0'
    return doc


def references(value, kind='oas'):
    """Only structural OAS/Schema references, excluding literal example/vendor data."""
    if isinstance(value, list):
        for child in value:
            yield from references(child, kind)
        return
    if not isinstance(value, dict):
        return
    if '$ref' in value:
        yield value['$ref']
    if kind == 'schema':
        if any(k in value for k in ('$id', '$anchor', '$dynamicRef', '$dynamicAnchor', '$recursiveRef')):
            raise Blocked('SCHEMA_SCOPE_UNSUPPORTED')
        for k in ('properties', 'patternProperties', '$defs', 'dependentSchemas'):
            for child in value.get(k, {}).values():
                yield from references(child, 'schema')
        for k in ('items', 'additionalProperties', 'not', 'contains', 'if', 'then', 'else', 'unevaluatedProperties',
                  'oneOf', 'anyOf', 'allOf', 'prefixItems'):
            if k in value:
                yield from references(value[k], 'schema')
        for mapped in value.get('discriminator', {}).get('mapping', {}).values():
            yield mapped if mapped.startswith('#/') or '/' in mapped else '#/components/schemas/' + mapped
        return
    for k, child in value.items():
        if k in ('example', 'default', 'enum', 'const') or k.startswith('x-') or (kind == 'example' and k == 'value'):
            continue
        if k == 'schema':
            yield from references(child, 'schema')
        elif k == 'components':
            for group, entries in child.items():
                for item in entries.values():
                    yield from references(item, 'schema' if group == 'schemas' else 'example' if group == 'examples' else 'oas')
        elif k == 'examples':
            if isinstance(child, dict):
                for example in child.values():
                    yield from references(example, 'example')
        elif k == 'security':
            for requirement in child:
                for name in requirement:
                    yield '#/components/securitySchemes/' + name.replace('~', '~0').replace('/', '~1')
        elif k in NAMED_MAPS:
            for item in child.values():
                yield from references(item, 'oas')
        elif k == 'operationRef':
            yield child
        else:
            yield from references(child, 'oas')


def pointer(doc, ref):
    if not isinstance(ref, str) or not ref.startswith('#/'):
        raise Blocked('EXTERNAL_REF_UNRESOLVED')
    parts = [p.replace('~1', '/').replace('~0', '~') for p in ref[2:].split('/')]
    target = doc
    try:
        for part in parts:
            target = target[int(part)] if isinstance(target, list) else target[part]
    except (KeyError, TypeError, ValueError, IndexError):
        raise Blocked('LOCAL_REF_MISSING') from None
    return parts, target


def local_references(doc):
    for ref in references(doc):
        pointer(doc, ref)


def select_endpoint(data):
    source, path, method = data['document'], data['path'], data['method']
    if method not in METHODS or method not in source['paths'][path]:
        raise Blocked('ENDPOINT_UNRESOLVED')
    doc = {k: deepcopy(v) for k, v in source.items() if k not in ('paths', 'components', 'webhooks')}
    doc['paths'] = {path: {k: deepcopy(v) for k, v in source['paths'][path].items() if k not in METHODS or k == method}}
    queue = list(references(doc))
    copied = set()
    while queue:
        ref = queue.pop()
        parts, _ = pointer(source, ref)
        if len(parts) < 3 or parts[0] != 'components':
            # A cross-operation reference cannot silently lose its target when scoping.
            pointer(doc, ref)
            continue
        group, name = parts[1:3]
        if (group, name) in copied:
            continue
        copied.add((group, name))
        component = deepcopy(source['components'][group][name])
        doc.setdefault('components', {}).setdefault(group, {})[name] = component
        queue.extend(references(component, 'schema' if group == 'schemas' else 'example' if group == 'examples' else 'oas'))
    local_references(doc)
    return doc


def schema_roots(value):
    if isinstance(value, list):
        for child in value:
            yield from schema_roots(child)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in ('example', 'examples', 'default') or key.startswith('x-'):
                continue
            if key == 'schema':
                yield child
            elif key == 'components':
                for group, entries in child.items():
                    if group == 'schemas':
                        yield from entries.values()
                    elif group != 'examples':
                        for item in entries.values():
                            yield from schema_roots(item)
            elif key in NAMED_MAPS:
                for item in child.values():
                    yield from schema_roots(item)
            else:
                yield from schema_roots(child)


def validate(doc):
    if not isinstance(doc, dict) or not re.fullmatch(r'3\.(?:0\.[0-4]|1\.[0-2])', str(doc.get('openapi', ''))):
        raise Blocked('DIALECT_UNSUPPORTED')
    local_references(doc)
    try:
        from openapi_spec_validator import validate as validate_openapi
    except ImportError:
        raise Blocked('OPENAPI_VALIDATOR_MISSING: install the project-pinned validator in an isolated environment') from None
    try:
        validate_openapi(doc)
        from openapi_schema_validator import OAS30Validator, OAS31Validator
        validator = OAS30Validator if doc['openapi'].startswith('3.0.') else OAS31Validator
        for node in schema_roots(doc):
            validator.check_schema(node)
    except Exception as exc:
        raise Blocked('OPENAPI_INVALID: ' + type(exc).__name__) from None


def number(value):
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch('[1-9][0-9]*', value):
        return int(value)
    raise Blocked('TARGET_ID')


def target(value):
    expected = {'project_id', 'branch_id', 'method', 'path', 'folder_id', 'mode', 'schema_mode'}
    if set(value) != expected:
        raise Blocked('TARGET_FIELDS')
    result = deepcopy(value)
    result['project_id'] = number(value['project_id'])
    result['branch_id'] = number(value['branch_id'])  # resolve main to an actual ID before freeze
    if value['folder_id'] is not None:
        result['folder_id'] = number(value['folder_id'])
    if value['method'] not in METHODS or not isinstance(value['path'], str) or not value['path'].startswith('/'):
        raise Blocked('TARGET_ENDPOINT')
    if value['mode'] not in MODES or value['schema_mode'] not in MODES:
        raise Blocked('TARGET_MODE')
    return result


def make_request(doc, dest):
    operations = [(p, m) for p, item in doc['paths'].items() if not p.startswith('x-') for m in item if m in METHODS]
    if operations != [(dest['path'], dest['method'])]:
        raise Blocked('SINGLE_TARGET_OPERATION_REQUIRED')
    operation = doc['paths'][dest['path']][dest['method']]
    if operation.get('x-apidog-status') not in STATUSES:
        raise Blocked('ENDPOINT_STATUS')
    if operation['x-apidog-status'] == 'deprecated' and (operation.get('deprecated') is not True or dest['mode'] != 'OVERWRITE_EXISTING'):
        raise Blocked('DEPRECATED_CONTRACT')
    options = dict(endpointOverwriteBehavior=dest['mode'], schemaOverwriteBehavior=dest['schema_mode'],
                   targetBranchId=dest['branch_id'], updateFolderOfChangedEndpoint=False, prependBasePath=False)
    if dest['folder_id'] is not None:
        options['targetFolderId'] = dest['folder_id']
    return dict(input=encoded(doc).decode(), options=options)


def freeze(data):
    dest, doc = target(data['target']), data['document']
    if not isinstance(data['run_id'], str) or not data['run_id']:
        raise Blocked('RUN_ID')
    validate(doc)
    payload = encoded(doc)
    request = encoded(make_request(doc, dest))
    directory = Path(tempfile.mkdtemp(prefix='apidog-run-', dir=data.get('directory')))
    # mkdtemp is exclusive/0700. Artifacts are created 0600, no endpoint-slug reuse.
    created = []
    try:
        for name, content in [('openapi.json', payload), ('request.json', request)]:
            path = directory / name
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
                created.append(path)
                stream.write(content)
        receipt = dict(schema_version=1, run_id=data['run_id'], directory=str(directory.resolve()), target=dest,
                       payload_sha256=digest(payload), request_sha256=digest(request))
        with os.fdopen(os.open(directory / 'receipt.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            created.append(directory / 'receipt.json')
            stream.write(encoded(receipt))
        return receipt
    except BaseException:
        for path in created:
            path.unlink()
        directory.rmdir()
        raise


def read_private(path):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600:
            raise Blocked('ARTIFACT_PERMISSIONS')
        return stream.read()


def request_bytes(data):
    # Receipt is the original in-memory/orchestrator state receipt, never reloaded from this directory.
    receipt = data['receipt']
    dest = target(data['target'])
    if receipt.get('schema_version') != 1 or data['run_id'] != receipt['run_id'] or dest != receipt['target']:
        raise Blocked('FROZEN_TARGET_MISMATCH')
    directory = Path(receipt['directory'])
    st = directory.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
        raise Blocked('ARTIFACT_DIRECTORY')
    payload = read_private(directory / 'openapi.json')
    content = read_private(directory / 'request.json')
    if digest(payload) != receipt['payload_sha256'] or digest(content) != receipt['request_sha256']:
        raise Blocked('PAYLOAD_CHANGED')
    if encoded(make_request(json.loads(payload), dest)) != content:
        raise Blocked('REQUEST_TARGET_MISMATCH')
    return dict(url='https://api.apidog.com/v1/projects/' + str(dest['project_id']) + '/import-openapi',
                request_base64=base64.b64encode(content).decode(), request_sha256=digest(content), target=dest)


def project_args(args):
    values = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('--project', '--project-id'):
            i += 1
            if i == len(args):
                raise Blocked('PROJECT_ARG_MISSING')
            values.append(number(args[i]))
        elif arg.startswith(('--project=', '--project-id=')):
            values.append(number(arg.split('=', 1)[1]))
        i += 1
    if not values or len(set(values)) != 1:
        raise Blocked('PROJECT_ARG_AMBIGUOUS')
    return values[0]


def discover(data):
    project, branch = number(data['project_id']), number(data['branch_id'])
    if 'mcp_args' in data and project_args(data['mcp_args']) != project:
        raise Blocked('MCP_PROJECT_MISMATCH')
    result = {}
    for operation in ('read', 'refs', 'refresh'):
        matches = [t['name'] for t in data['tools'] if t.get('operation') == operation and t.get('verified') is True
                   and t.get('project_id') == project and t.get('branch_id') == branch]
        if len(matches) != 1 or not isinstance(matches[0], str) or not matches[0]:
            raise Blocked('CALLABLE_' + operation.upper() + '_UNRESOLVED')
        result[operation] = matches[0]
    return dict(project_id=project, branch_id=branch, callables=result)


def proto_helper(data):
    matches = [s for s in data['skills'] if s.get('name', '').split(':')[-1] == 'go-codegen']
    if len(matches) != 1:
        raise Blocked('PROTO_PROVIDER_UNRESOLVED')
    provider = matches[0]
    main = Path(provider['path']).resolve(strict=True)
    # Read the actual provider skill before supplying its declared script-relative path.
    if provider.get('contract_read') is not True or provider.get('script_relative') != 'scripts/find-proto.sh':
        raise Blocked('PROTO_CONTRACT_UNVERIFIED')
    script = (main.parent / provider['script_relative']).resolve(strict=True)
    if not script.is_file() or main.parent not in script.parents:
        raise Blocked('PROTO_HELPER_UNAVAILABLE')
    return dict(skill=provider['name'], main_resource=str(main), script=str(script))


def outcome(data):
    if data.get('transmission_started') is False and data.get('no_write_verified') is True:
        return dict(state='NOT_SENT')
    body = data.get('body')
    if not isinstance(body, dict):
        return dict(state='UNKNOWN')
    info = body.get('data') or {}
    counts = info.get('counters') or {}
    changed = sum(v.get(k, 0) for v in counts.values() for k in ('created', 'updated'))
    failed = sum(v.get('failed', 0) for v in counts.values())
    errors = info.get('errors') or body.get('errors') or []
    code = data.get('http_status')
    success = type(code) is int and 200 <= code < 300 and code != 202 and body.get('success') is True
    if failed or errors or (changed and not success):
        return dict(state='PARTIAL' if changed else 'UNKNOWN')
    if success and counts:
        return dict(state='ACKNOWLEDGED')  # not final until complete read-back
    if not changed and data.get('no_write_verified') is True and type(code) is int and 400 <= code < 500:
        return dict(state='REJECTED_NO_WRITE')
    return dict(state='UNKNOWN')


def decision(data):
    receipt = data['receipt']
    if data['run_id'] != receipt['run_id'] or target(data['target']) != receipt['target']:
        raise Blocked('FROZEN_TARGET_MISMATCH')
    # Credential sources must prove the same project/branch; credentials never appear in this input/output.
    if data.get('credential_target') is not None and target(data['credential_target']) != receipt['target']:
        raise Blocked('CREDENTIAL_TARGET_MISMATCH')
    state = data['state']
    if state in ('NOT_SENT', 'REJECTED_NO_WRITE'):
        retry = data.get('attempts') == 1 and data.get('no_write_verified') is True
        return dict(status='RETRY_SAME_REQUEST' if retry else 'BLOCKED:RETRY_UNPROVEN', may_retry=retry)
    if state not in ('UNKNOWN', 'ACKNOWLEDGED', 'PARTIAL'):
        raise Blocked('IMPORT_STATE')
    observed = data.get('readback', {})
    if observed and target(observed['target']) != receipt['target']:
        raise Blocked('READBACK_TARGET_MISMATCH')
    matched = (observed.get('fresh') is True and observed.get('after_attempt') is True
               and observed.get('complete') is True and observed.get('matches_expected') is True
               and observed.get('request_sha256') == receipt['request_sha256'])
    if matched and receipt['target']['mode'] != 'CREATE_NEW':
        return dict(status='OBSERVED_MATCH', may_retry=False, attribution='unproven')
    if matched and state == 'ACKNOWLEDGED':
        created = data.get('creation', {})
        before, after, matching = (created.get(k) for k in ('before_ids', 'after_ids', 'new_matching_ids'))
        valid_ids = lambda v: isinstance(v, list) and all(type(x) is int and x > 0 for x in v) and len(set(v)) == len(v)
        if (created.get('before_verified') is True and created.get('acknowledged_created_count') == 1
                and all(valid_ids(v) for v in (before, after, matching)) and len(matching) == 1
                and set(before) <= set(after) and set(after) - set(before) == set(matching)):
            return dict(status='OBSERVED_NEW_MATCH', may_retry=False, attribution='unproven', created_ids=matching)
    # Absence may precede a delayed import, so even fresh absence never authorizes an UNKNOWN retry.
    return dict(status='UNKNOWN:IMPORT', may_retry=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['select', 'normalize', 'freeze', 'request', 'tools', 'proto', 'outcome', 'decision'])
    parser.add_argument('input', help='JSON file or -; no access tokens')
    args = parser.parse_args()
    try:
        data = json.loads(sys.stdin.read() if args.input == '-' else Path(args.input).read_text())
        result = {'select': select_endpoint, 'normalize': normalize, 'freeze': freeze, 'request': request_bytes, 'tools': discover, 'proto': proto_helper, 'outcome': outcome, 'decision': decision}[args.action](data)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
        print('BLOCKED:APIDOG: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
