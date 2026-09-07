#!/usr/bin/env python3
"""Validate a run-owned row ledger and plan exact-ID PostgreSQL soft deletion.

No connections or writes. Runtime/catalog/creation receipts must come from actual
observations; this helper does not manufacture their evidence or transactions.
SQL uses psycopg positional parameters, never interpolated row values.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid


class Blocked(ValueError):
    pass


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise Blocked('IDENTIFIER_UNSUPPORTED')
    return '"' + value + '"'


def key(table):
    ident(table['schema'])
    ident(table['table'])
    return table['schema'] + '.' + table['table']


def identity(observations, schemas):
    if not isinstance(schemas, list) or not schemas or len(set(schemas)) != len(schemas):
        raise Blocked('DB_SCOPE')
    for schema in schemas:
        ident(schema)
    normalized = []
    for role, expected_source in [('app', 'app_runtime_connection'), ('cleanup', 'cleanup_transaction_connection')]:
        item = observations[role]
        if item.get('source') != expected_source or item.get('verified') is not True or item.get('host_allowed') is not True:
            raise Blocked('DB_IDENTITY_UNVERIFIED')
        if not set(schemas) <= set(item.get('schemas', [])):
            raise Blocked('DB_SCHEMA_MISMATCH')
        cluster = item['cluster_id']
        if not isinstance(cluster, str) or not re.fullmatch(r'[0-9]+', cluster):
            raise Blocked('DB_CLUSTER_ID')
        if type(item['database_oid']) is not int or item['database_oid'] < 1 or not isinstance(item['database'], str) or not item['database']:
            raise Blocked('DB_DATABASE_ID')
        stamp = datetime.fromisoformat(item['server_started_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise Blocked('DB_SERVER_ID')
        normalized.append(dict(cluster_id=str(int(cluster)), database=item['database'], database_oid=item['database_oid'],
                               server_started_at=stamp.astimezone(timezone.utc).isoformat(), schemas=sorted(schemas)))
    if normalized[0] != normalized[1]:
        raise Blocked('DB_IDENTITY_MISMATCH')
    return normalized[0]


def tables(items, schemas):
    result = {}
    for item in items:
        name = key(item)
        if name in result or item['schema'] not in schemas:
            raise Blocked('DB_TABLE_SCOPE')
        if any(type(item.get(field)) is not int or not 0 < item[field] < 2 ** 32 for field in ('schema_oid', 'relation_oid')):
            raise Blocked('DB_RELATION_IDENTITY')
        ident(item['pk'])
        ident(item['status_column'])
        if item.get('id_type') not in ('int8', 'int4', 'uuid') or item.get('visibility_verified') is not True:
            raise Blocked('DB_TABLE_UNSUPPORTED_OR_HIDDEN')
        if not re.fullmatch(r'[a-f0-9]{64}', item.get('trigger_fingerprint', '')):
            raise Blocked('TRIGGER_METADATA_MISSING')
        result[name] = deepcopy(item)
    if not result:
        raise Blocked('DB_TABLE_METADATA_MISSING')
    return result


def row_id(value, table):
    if table['id_type'] == 'uuid':
        if not isinstance(value, str):
            raise Blocked('ROW_ID')
        return str(uuid.UUID(value))
    if isinstance(value, str) and re.fullmatch(r'-?[0-9]+', value):
        value = int(value)
    limit = 2 ** (31 if table['id_type'] == 'int4' else 63)
    if type(value) is not int or not -limit <= value < limit:
        raise Blocked('ROW_ID')
    return value


def initialize(data):
    run_id = data['run_id']
    if not isinstance(run_id, str) or not run_id:
        raise Blocked('RUN_ID')
    db = identity(data['observations'], data['schemas'])
    catalog = tables(data['tables'], db['schemas'])
    approved = data.get('reviewed_triggers', {})
    if any(approved.get(name) != table['trigger_fingerprint'] for name, table in catalog.items()):
        raise Blocked('UNREVIEWED_TRIGGERS')
    return dict(schema_version=1, run_id=run_id, identity=db, tables=catalog, rows=[], unresolved=[])


def record(data):
    ledger = deepcopy(data['ledger'])
    if ledger.get('schema_version') != 1 or ledger.get('run_id') != data.get('run_id'):
        raise Blocked('RUN_MISMATCH')
    row = data['row']
    name = key(row)
    if name not in ledger['tables']:
        raise Blocked('ROW_TABLE')
    proof = row.get('proof', {})
    # RETURNING or HTTP201 alone is insufficient: upsert/existing idempotency is not new ownership.
    if proof.get('kind') not in ('insert_only_returning', 'api_insert_only', 'attributed_trigger_insert') or proof.get('created_new') is not True or proof.get('run_id') != ledger['run_id']:
        raise Blocked('OWNERSHIP_UNPROVEN')
    if not isinstance(proof.get('evidence_ref'), str) or not proof['evidence_ref'] or not isinstance(row.get('case_id'), str) or not row['case_id']:
        raise Blocked('OWNERSHIP_EVIDENCE_MISSING')
    normalized = dict(schema=row['schema'], table=row['table'], id=row_id(row['id'], ledger['tables'][name]),
                      case_id=row['case_id'], proof=deepcopy(proof))
    old = next((x for x in ledger['rows'] if key(x) == name and x['id'] == normalized['id']), None)
    if old is not None and old.get('lifecycle') == 'deleted':
        raise Blocked('ROW_ALREADY_DELETED')
    if old is None:
        ledger['rows'].append(normalized)
    return ledger


def deleted(data):
    ledger = deepcopy(data['ledger'])
    if ledger.get('schema_version') != 1 or ledger.get('run_id') != data.get('run_id'):
        raise Blocked('RUN_MISMATCH')
    if identity(data['observations'], ledger['identity']['schemas']) != ledger['identity']:
        raise Blocked('DB_IDENTITY_DRIFT')
    if tables(data['tables'], ledger['identity']['schemas']) != ledger['tables']:
        raise Blocked('DB_METADATA_DRIFT')
    name = key(data['row'])
    value = row_id(data['row']['id'], ledger['tables'][name])
    row = next((r for r in ledger['rows'] if key(r) == name and r['id'] == value), None)
    proof = data['proof']
    if row is None or proof.get('kind') != 'verified_physical_delete' or proof.get('readback_absent') is not True or proof.get('run_id') != ledger['run_id']:
        raise Blocked('DELETE_UNPROVEN')
    if not isinstance(proof.get('evidence_ref'), str) or not proof['evidence_ref']:
        raise Blocked('DELETE_EVIDENCE_MISSING')
    row['lifecycle'] = 'deleted'
    row['deletion'] = dict(proof, identity=ledger['identity'], relation_oid=ledger['tables'][name]['relation_oid'])
    return ledger


def plan(data):
    ledger = data['ledger']
    if ledger.get('schema_version') != 1 or ledger.get('run_id') != data.get('run_id'):
        raise Blocked('RUN_MISMATCH')
    if ledger.get('unresolved') or data.get('transaction_verified') is not True or data.get('incoming_checked') is not True:
        raise Blocked('CLEANUP_EVIDENCE_INCOMPLETE')
    if identity(data['observations'], ledger['identity']['schemas']) != ledger['identity']:
        raise Blocked('DB_IDENTITY_DRIFT')
    current = tables(data['tables'], ledger['identity']['schemas'])
    if current != ledger['tables']:
        raise Blocked('DB_METADATA_DRIFT')
    owned = {}
    # Revalidate stored receipts too: a file edit cannot silently convert a reference ID into ownership.
    empty = dict(ledger, rows=[])
    for row in ledger['rows']:
        record(dict(ledger=empty, run_id=ledger['run_id'], row=row))
        name = key(row)
        if row.get('lifecycle') == 'deleted':
            proof = row.get('deletion', {})
            if (proof.get('kind') != 'verified_physical_delete' or proof.get('readback_absent') is not True
                    or proof.get('run_id') != ledger['run_id'] or not proof.get('evidence_ref')
                    or proof.get('identity') != ledger['identity'] or proof.get('relation_oid') != current[name]['relation_oid']):
                raise Blocked('DELETE_UNPROVEN')
            continue
        if row.get('lifecycle', 'active') != 'active':
            raise Blocked('ROW_LIFECYCLE')
        owned.setdefault(name, set()).add(row_id(row['id'], current[name]))
    children = {name: set() for name in owned}
    for fk in data['foreign_keys']:
        parent, child = key(fk['parent']), key(fk['child'])
        if parent not in owned:
            continue
        if parent not in current or child not in current:
            raise Blocked('UNSCOPED_INCOMING_FK')
        if fk.get('parent_columns') != [current[parent]['pk']] or len(fk.get('child_columns', [])) != 1:
            raise Blocked('FK_UNSUPPORTED')
        ident(fk['child_columns'][0])
        if child in owned:
            children[parent].add(child)
    for link in data['dependents']:
        parent, child = key(link['parent']), key(link['child'])
        if parent not in owned or child not in current:
            raise Blocked('DEPENDENT_METADATA')
        if row_id(link['parent']['id'], current[parent]) not in owned[parent]:
            raise Blocked('DEPENDENT_PARENT')
        if row_id(link['child']['id'], current[child]) not in owned.get(child, set()):
            raise Blocked('UNOWNED_DEPENDENTS')
    ordered, visiting = [], set()
    def visit(name):
        if name in visiting:
            raise Blocked('FK_CYCLE')
        if name in ordered:
            return
        visiting.add(name)
        for child in sorted(children[name]):
            visit(child)
        visiting.remove(name)
        ordered.append(name)
    for name in sorted(owned):
        visit(name)
    statements = []
    for name in ordered:
        table, ids = current[name], sorted(owned[name])
        qualified = ident(table['schema']) + '.' + ident(table['table'])
        pk = ident(table['pk'])
        slots = ', '.join(['%s'] * len(ids))
        statements.append(dict(table=name, expected_ids=ids,
                               sql='UPDATE ' + qualified + ' SET ' + ident(table['status_column']) + ' = %s WHERE ' + pk + ' IN (' + slots + ') RETURNING ' + pk,
                               params=['removed', *ids]))
    return dict(status='READY', run_id=ledger['run_id'], identity=ledger['identity'], parameter_style='psycopg', statements=statements)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'record', 'deleted', 'plan'])
    parser.add_argument('input', help='JSON path or -')
    args = parser.parse_args()
    try:
        data = json.loads(sys.stdin.read() if args.input == '-' else Path(args.input).read_text())
        if not isinstance(data, dict):
            raise Blocked('INPUT')
        print(json.dumps({'init': initialize, 'record': record, 'deleted': deleted, 'plan': plan}[args.action](data), ensure_ascii=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
        print('BLOCKED:DB_OWNERSHIP: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
