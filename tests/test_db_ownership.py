"""Ownership contract: pure validation plus an optional, private real PostgreSQL cluster.

HARNESS_REQUIRE_POSTGRES=1 makes missing PG/psycopg an error for CI. No external DSN.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'minmos-harness/overlay/assets/db_ownership.py'
spec = importlib.util.spec_from_file_location('db_ownership', HELPER)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def observations(**changes):
    common = dict(cluster_id='12345', database='fixture', database_oid=123,
                  server_started_at='2026-01-01T00:00:00+00:00', schemas=['a', 'b'],
                  verified=True, host_allowed=True)
    return dict(app=dict(common, source='app_runtime_connection'),
                cleanup=dict(common, source='cleanup_transaction_connection', **changes))


def metadata(schema='a', table='parent', **changes):
    return dict(schema=schema, table=table, schema_oid=100 if schema == 'a' else 101,
                relation_oid=200 + (1 if table == 'child' else 0) + (10 if schema == 'b' else 0), pk='id', status_column='status', id_type='int8',
                visibility_verified=True, trigger_fingerprint=hashlib.sha256(b'[]').hexdigest(), **changes)


def make_ledger(catalog=None, observed=None):
    catalog = catalog or [metadata(), metadata(table='child'), metadata('b')]
    return guard.initialize(dict(run_id='run1', schemas=['a', 'b'], observations=observed or observations(),
                                 tables=catalog, reviewed_triggers={guard.key(x): x['trigger_fingerprint'] for x in catalog}))


def own(ledger, table, row_id, schema='a', kind='insert_only_returning'):
    return guard.record(dict(ledger=ledger, run_id='run1', row=dict(schema=schema, table=table, id=row_id,
        case_id='CASE-01', proof=dict(kind=kind, created_new=True, run_id='run1', evidence_ref='actual-insert-receipt'))))


def plan_input(ledger, **changes):
    return dict(ledger=ledger, run_id='run1', observations=observations(), tables=list(ledger['tables'].values()),
                transaction_verified=True, incoming_checked=True, foreign_keys=[], dependents=[], **changes)


class DbOwnershipTests(unittest.TestCase):
    def test_exact_ids_and_schema_collisions_preserve_input_and_bind_values(self):
        ledger = own(own(own(make_ledger(), 'parent', 8), 'parent', 2), 'parent', 2, schema='b')
        before = deepcopy(ledger)
        result = guard.plan(plan_input(ledger))
        self.assertEqual(ledger, before)
        self.assertEqual([s['expected_ids'] for s in result['statements']], [[2, 8], [2]])
        self.assertIn('UPDATE "a"."parent"', result['statements'][0]['sql'])
        self.assertEqual(result['statements'][0]['params'], ['removed', 2, 8])
        self.assertNotIn('> ', result['statements'][0]['sql'])
        with self.assertRaisesRegex(guard.Blocked, 'ROW_ID'):
            own(ledger, 'parent', '2); UPDATE outside SET status=1;--')

    def test_target_identity_and_schema_mismatch_fail_closed(self):
        base = make_ledger()
        for key, bad in [('cluster_id', '999'), ('database', 'other'), ('database_oid', 456),
                         ('server_started_at', '2026-01-02T00:00:00Z'), ('schemas', ['b']),
                         ('verified', False), ('host_allowed', False), ('source', 'env_constructed_connection')]:
            observed = observations()
            observed['cleanup'][key] = bad
            data = plan_input(base)
            data['observations'] = observed
            with self.subTest(key=key), self.assertRaises(guard.Blocked):
                guard.plan(data)

    def test_ownership_proof_rejects_existing_upsert_and_unresolved_creation(self):
        ledger = make_ledger()
        for kind in ['upsert_returning', 'http_201', 'existing_reference', 'max_id_range']:
            with self.subTest(kind=kind), self.assertRaisesRegex(guard.Blocked, 'OWNERSHIP_UNPROVEN'):
                own(ledger, 'parent', 1, kind=kind)
        ledger = own(ledger, 'parent', 1)
        ledger['rows'][0]['proof']['created_new'] = False
        with self.assertRaisesRegex(guard.Blocked, 'OWNERSHIP_UNPROVEN'):
            guard.plan(plan_input(ledger))
        ledger = make_ledger()
        ledger['unresolved'] = [{'case_id': 'timeout', 'correlation': 'run1/create2'}]
        with self.assertRaisesRegex(guard.Blocked, 'CLEANUP_EVIDENCE_INCOMPLETE'):
            guard.plan(plan_input(ledger))

    def test_unowned_child_outside_schema_hidden_rows_and_cycle_block(self):
        ledger = own(make_ledger(), 'parent', 1)
        fk = dict(parent=dict(schema='a', table='parent'), child=dict(schema='a', table='child'),
                  parent_columns=['id'], child_columns=['parent_id'])
        dependent = dict(parent=dict(schema='a', table='parent', id=1), child=dict(schema='a', table='child', id=9))
        data = plan_input(ledger)
        data.update(foreign_keys=[fk], dependents=[dependent])
        with self.assertRaisesRegex(guard.Blocked, 'UNOWNED_DEPENDENTS'):
            guard.plan(data)
        ledger = own(ledger, 'child', 9, kind='attributed_trigger_insert')
        data.update(ledger=ledger)
        self.assertEqual([s['table'] for s in guard.plan(data)['statements']], ['a.child', 'a.parent'])
        for change, reason in [(dict(child=dict(schema='outside', table='child')), 'UNSCOPED'),
                               (dict(parent_columns=['id', 'other']), 'FK_UNSUPPORTED')]:
            with self.subTest(reason=reason), self.assertRaisesRegex(guard.Blocked, reason):
                guard.plan(dict(data, foreign_keys=[dict(fk, **change)]))
        reverse = dict(parent=fk['child'], child=fk['parent'], parent_columns=['id'], child_columns=['child_id'])
        with self.assertRaisesRegex(guard.Blocked, 'FK_CYCLE'):
            guard.plan(dict(data, foreign_keys=[fk, reverse]))
        hidden = deepcopy(data)
        hidden['tables'][0]['visibility_verified'] = False
        with self.assertRaisesRegex(guard.Blocked, 'HIDDEN'):
            guard.plan(hidden)

    def test_metadata_trigger_drift_and_false_transaction_block(self):
        ledger = own(make_ledger(), 'parent', 1)
        for field in ['incoming_checked', 'transaction_verified']:
            data = plan_input(ledger)
            data[field] = False
            with self.assertRaisesRegex(guard.Blocked, 'CLEANUP_EVIDENCE_INCOMPLETE'):
                guard.plan(data)
        data = plan_input(ledger)
        data['tables'] = deepcopy(data['tables'])
        data['tables'][0]['trigger_fingerprint'] = 'f' * 64
        with self.assertRaisesRegex(guard.Blocked, 'DB_METADATA_DRIFT'):
            guard.plan(data)
        with self.assertRaisesRegex(guard.Blocked, 'UNREVIEWED_TRIGGERS'):
            guard.initialize(dict(run_id='run1', schemas=['a', 'b'], observations=observations(), tables=[metadata()]))

    def test_invalid_cli_nested_shapes_return_blocked_without_traceback(self):
        for action, value in [('init', []), ('init', {'run_id':'x', 'observations':{'app':[]}, 'schemas':['a']}),
                              ('record', {'ledger':None}), ('plan', {'ledger':[]})]:
            result = subprocess.run([sys.executable, '-B', str(HELPER), action, '-'], input=json.dumps(value),
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('BLOCKED:DB_OWNERSHIP', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(result.stdout, '')


class PostgreSqlOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
            cls.psycopg = psycopg
            configured = shutil.which('pg_config')
            binary = Path(subprocess.check_output([configured, '--bindir'], text=True).strip()) if configured else None
            if binary is None or not (binary / 'initdb').is_file() or os.geteuid() == 0:
                raise RuntimeError('unprivileged initdb/pg_ctl required')
        except (ImportError, OSError, RuntimeError) as exc:
            if os.environ.get('HARNESS_REQUIRE_POSTGRES') == '1':
                raise RuntimeError('Required local PostgreSQL fixture unavailable') from exc
            raise unittest.SkipTest(str(exc))
        cls.temp = tempfile.TemporaryDirectory(prefix='harness-pg-owned-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.binary = binary
        cls.data = cls.base / 'data'
        cls.sock = cls.base / 'socket'
        cls.sock.mkdir(mode=0o700)
        subprocess.run([str(binary / 'initdb'), '-D', str(cls.data), '--no-locale', '--encoding=UTF8',
                        '--auth=trust', '--username=fixture'], check=True, capture_output=True)
        (cls.data / 'postgresql.conf').write_text("listen_addresses = ''\nunix_socket_directories = '" + str(cls.sock) + "'\n")
        subprocess.run([str(binary / 'pg_ctl'), '-D', str(cls.data), '-l', str(cls.base / 'server.log'), '-w', 'start'],
                       check=True, capture_output=True)
        cls.addClassCleanup(cls.stop_server)
        cls.app = cls.connect()
        cls.cleanup = cls.connect()
        cls.other = cls.connect()
        for conn in [cls.app, cls.cleanup, cls.other]:
            cls.addClassCleanup(conn.close)

    @classmethod
    def stop_server(cls):
        subprocess.run([str(cls.binary / 'pg_ctl'), '-D', str(cls.data), '-m', 'immediate', '-w', 'stop'],
                       check=True, capture_output=True)

    @classmethod
    def connect(cls):
        return cls.psycopg.connect(host=str(cls.sock), port=5432, user='fixture', dbname='postgres', autocommit=True)

    def setUp(self):
        self.app.execute('DROP SCHEMA IF EXISTS a CASCADE; DROP SCHEMA IF EXISTS b CASCADE; CREATE SCHEMA a; CREATE SCHEMA b')
        self.app.execute('''CREATE TABLE a.parent(id bigint PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
            token text UNIQUE, status text NOT NULL DEFAULT 'active', touched boolean NOT NULL DEFAULT false);
            CREATE TABLE a.child(id bigint PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY, parent_id bigint REFERENCES a.parent(id),
            token text, status text NOT NULL DEFAULT 'active');
            CREATE TABLE b.parent(LIKE a.parent INCLUDING ALL);
            CREATE FUNCTION a.touch() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN NEW.touched := true; RETURN NEW; END $$;
            CREATE TRIGGER touch BEFORE UPDATE ON a.parent FOR EACH ROW EXECUTE FUNCTION a.touch()''')
        self.catalog = self.read_catalog()
        self.ledger = make_ledger(self.catalog, self.actual_observations())

    def actual_observations(self):
        result = {}
        for role, conn in [('app', self.app), ('cleanup', self.cleanup)]:
            row = conn.execute('''SELECT (SELECT system_identifier::text FROM pg_control_system()), current_database(),
                (SELECT oid::bigint FROM pg_database WHERE datname=current_database()), pg_postmaster_start_time()''').fetchone()
            schemas = [r[0] for r in conn.execute("SELECT nspname FROM pg_namespace WHERE nspname IN ('a','b') ORDER BY nspname")]
            result[role] = dict(cluster_id=row[0], database=row[1], database_oid=row[2], server_started_at=row[3].isoformat(),
                schemas=schemas, verified=True, host_allowed=True,
                source='app_runtime_connection' if role == 'app' else 'cleanup_transaction_connection')
        return result

    def read_catalog(self):
        items = []
        for schema, table in [('a', 'parent'), ('a', 'child'), ('b', 'parent')]:
            relation = schema + '.' + table
            triggers = self.cleanup.execute('''SELECT pg_get_triggerdef(t.oid), t.tgenabled, pg_get_functiondef(t.tgfoid)
                FROM pg_trigger t WHERE t.tgrelid=%s::regclass ORDER BY t.tgname''', (relation,)).fetchall()
            row = self.cleanup.execute('''SELECT c.relkind, c.relrowsecurity, has_table_privilege(c.oid, 'SELECT'),
                (SELECT count(*) FROM pg_inherits WHERE inhrelid=c.oid OR inhparent=c.oid)
                FROM pg_class c WHERE c.oid=%s::regclass''', (relation,)).fetchone()
            self.assertEqual(row, ('r', False, True, 0))
            item = metadata(schema, table)
            item['schema_oid'], item['relation_oid'] = self.cleanup.execute(
                'SELECT relnamespace::bigint, oid::bigint FROM pg_class WHERE oid=%s::regclass', (relation,)).fetchone()
            item['trigger_fingerprint'] = hashlib.sha256(json.dumps(triggers, sort_keys=True).encode()).hexdigest()
            items.append(item)
        return items

    def incoming(self):
        result = []
        rows = self.cleanup.execute('''SELECT pn.nspname, p.relname, cn.nspname, ch.relname,
            ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY k(num,ord)
                  JOIN pg_attribute a ON a.attrelid=p.oid AND a.attnum=k.num ORDER BY k.ord),
            ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(num,ord)
                  JOIN pg_attribute a ON a.attrelid=ch.oid AND a.attnum=k.num ORDER BY k.ord)
            FROM pg_constraint c JOIN pg_class p ON p.oid=c.confrelid JOIN pg_namespace pn ON pn.oid=p.relnamespace
            JOIN pg_class ch ON ch.oid=c.conrelid JOIN pg_namespace cn ON cn.oid=ch.relnamespace WHERE c.contype='f' ''')
        for ps, pt, cs, ct, pc, cc in rows:
            result.append(dict(parent=dict(schema=ps, table=pt), child=dict(schema=cs, table=ct), parent_columns=pc, child_columns=cc))
        return result

    def cleanup_owned(self, ledger, reject_after_update=False):
        # One physical psycopg connection; this fixture's app holds no async jobs/DDL.
        with self.cleanup.transaction():
            self.cleanup.execute("SET LOCAL lock_timeout='1s'; SET LOCAL statement_timeout='3s'")
            self.cleanup.execute('LOCK TABLE a.child, a.parent, b.parent IN SHARE ROW EXCLUSIVE MODE')
            fks = self.incoming()  # entire database, including other schema
            deps = []
            for fk in fks:
                parent_name = guard.key(fk['parent'])
                child_name = guard.key(fk['child'])
                parent_ids = [r['id'] for r in ledger['rows'] if guard.key(r) == parent_name and r.get('lifecycle') != 'deleted']
                if not parent_ids or child_name not in ledger['tables']:
                    continue  # helper blocks incoming metadata outside the ledger
                child = ledger['tables'][child_name]
                sql = 'SELECT ' + guard.ident(child['pk']) + ', ' + guard.ident(fk['child_columns'][0])
                sql += ' FROM ' + guard.ident(child['schema']) + '.' + guard.ident(child['table'])
                sql += ' WHERE ' + guard.ident(fk['child_columns'][0]) + ' = ANY(%s) FOR UPDATE'
                for cid, pid in self.cleanup.execute(sql, (parent_ids,)):
                    deps.append(dict(parent=dict(fk['parent'], id=pid), child=dict(fk['child'], id=cid)))
            data = dict(ledger=ledger, run_id='run1', observations=self.actual_observations(), tables=self.read_catalog(),
                        transaction_verified=True, incoming_checked=True, foreign_keys=fks, dependents=deps)
            plan = guard.plan(data)
            for statement in plan['statements']:
                got = sorted(r[0] for r in self.cleanup.execute(statement['sql'], statement['params']))
                if got != statement['expected_ids']:
                    raise guard.Blocked('RETURNING_MISMATCH')
            if reject_after_update:
                raise guard.Blocked('POST_UPDATE_CHECK')
            return plan

    def test_interleaved_writers_colliding_schema_ids_fk_and_safe_trigger(self):
        first = self.app.execute("INSERT INTO a.parent(token) VALUES ('run1/one') RETURNING id").fetchone()[0]
        other = self.other.execute("INSERT INTO a.parent(token) VALUES ('general') RETURNING id").fetchone()[0]
        last = self.app.execute("INSERT INTO a.parent(token) VALUES ('run1/two') RETURNING id").fetchone()[0]
        child = self.app.execute("INSERT INTO a.child(parent_id,token) VALUES (%s,'run1/child') RETURNING id", (first,)).fetchone()[0]
        self.other.execute("INSERT INTO b.parent(id,token) VALUES (%s,'other-schema')", (first,))
        ledger = own(own(own(self.ledger, 'parent', first), 'parent', last), 'child', child)
        self.cleanup_owned(ledger)
        self.assertEqual(self.app.execute('SELECT id,status,touched FROM a.parent ORDER BY id').fetchall(),
                         [(first, 'removed', True), (other, 'active', False), (last, 'removed', True)])
        self.assertEqual(self.app.execute('SELECT status FROM b.parent WHERE id=%s', (first,)).fetchone(), ('active',))
        self.assertEqual(self.app.execute('SELECT status FROM a.child WHERE id=%s', (child,)).fetchone(), ('removed',))

    def test_unowned_incoming_child_and_other_schema_fk_prevent_any_cleanup(self):
        parent = self.app.execute("INSERT INTO a.parent(token) VALUES ('run1') RETURNING id").fetchone()[0]
        child = self.other.execute("INSERT INTO a.child(parent_id,token) VALUES (%s,'general') RETURNING id", (parent,)).fetchone()[0]
        ledger = own(self.ledger, 'parent', parent)
        with self.assertRaisesRegex(guard.Blocked, 'UNOWNED_DEPENDENTS'):
            self.cleanup_owned(ledger)
        self.assertEqual(self.app.execute('SELECT status FROM a.parent').fetchone(), ('active',))
        self.other.execute('DELETE FROM a.child WHERE id=%s', (child,))  # fixture owner only
        self.other.execute('CREATE TABLE b.outside(id bigint PRIMARY KEY, parent_id bigint REFERENCES a.parent(id))')
        self.other.execute('INSERT INTO b.outside VALUES (1,%s)', (parent,))
        # Refresh approved FK-trigger metadata so this case reaches full incoming catalog check.
        self.catalog = self.read_catalog()
        ledger = own(make_ledger(self.catalog, self.actual_observations()), 'parent', parent)
        with self.assertRaisesRegex(guard.Blocked, 'UNSCOPED_INCOMING_FK'):
            self.cleanup_owned(ledger)
        self.assertEqual(self.app.execute('SELECT status FROM a.parent').fetchone(), ('active',))

    def test_upsert_returning_existing_row_does_not_grant_ownership(self):
        existing = self.other.execute("INSERT INTO a.parent(token) VALUES ('existing') RETURNING id").fetchone()[0]
        returned = self.app.execute("INSERT INTO a.parent(token) VALUES ('existing') ON CONFLICT(token) DO UPDATE SET token=EXCLUDED.token RETURNING id").fetchone()[0]
        self.assertEqual(returned, existing)
        with self.assertRaisesRegex(guard.Blocked, 'OWNERSHIP_UNPROVEN'):
            own(self.ledger, 'parent', returned, kind='upsert_returning')
        self.assertEqual(self.ledger['rows'], [])

    def test_trigger_can_change_unowned_row_despite_normal_returning_and_drift_blocks(self):
        first = self.app.execute("INSERT INTO a.parent(token) VALUES ('run1') RETURNING id").fetchone()[0]
        self.other.execute("INSERT INTO b.parent(id,token) VALUES (1,'sentinel')")
        ledger = own(self.ledger, 'parent', first)
        self.app.execute('''CREATE FUNCTION a.bad() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN UPDATE b.parent SET status='removed'; RETURN NEW; END $$;
            CREATE TRIGGER bad AFTER UPDATE ON a.parent FOR EACH ROW EXECUTE FUNCTION a.bad()''')
        # Show real counterexample inside a transaction that always rolls back.
        with self.assertRaisesRegex(RuntimeError, 'rollback fixture'):
            with self.app.transaction():
                self.assertEqual(self.app.execute("UPDATE a.parent SET status='removed' WHERE id=%s RETURNING id", (first,)).fetchall(), [(first,)])
                self.assertEqual(self.app.execute('SELECT status FROM b.parent').fetchone(), ('removed',))
                raise RuntimeError('rollback fixture')
        with self.assertRaisesRegex(guard.Blocked, 'DB_METADATA_DRIFT'):
            self.cleanup_owned(ledger)
        self.assertEqual(self.app.execute('SELECT status FROM b.parent').fetchone(), ('active',))
        self.assertEqual(self.app.execute('SELECT status FROM a.parent').fetchone(), ('active',))

    def test_recreated_relation_with_reused_pk_blocks_before_nonowned_row_update(self):
        row_id = self.app.execute("INSERT INTO b.parent(token) VALUES ('run1') RETURNING id").fetchone()[0]
        ledger = own(self.ledger, 'parent', row_id, schema='b')
        self.other.execute('DROP TABLE b.parent; CREATE TABLE b.parent(LIKE a.parent INCLUDING ALL)')
        self.other.execute("INSERT INTO b.parent(id,token) VALUES (%s,'general')", (row_id,))
        with self.assertRaisesRegex(guard.Blocked, 'DB_METADATA_DRIFT'):
            self.cleanup_owned(ledger)
        self.assertEqual(self.app.execute('SELECT status FROM b.parent').fetchone(), ('active',))

    def test_verified_physical_delete_lifecycle_allows_remaining_cleanup(self):
        gone = self.app.execute("INSERT INTO b.parent(token) VALUES ('run1/delete') RETURNING id").fetchone()[0]
        remains = self.app.execute("INSERT INTO b.parent(token) VALUES ('run1/remains') RETURNING id").fetchone()[0]
        ledger = own(own(self.ledger, 'parent', gone, schema='b'), 'parent', remains, schema='b')
        self.assertEqual(self.app.execute('DELETE FROM b.parent WHERE id=%s RETURNING id', (gone,)).fetchall(), [(gone,)])
        self.assertEqual(self.app.execute('SELECT id FROM b.parent WHERE id=%s', (gone,)).fetchall(), [])
        with self.assertRaisesRegex(guard.Blocked, 'RETURNING_MISMATCH'):
            self.cleanup_owned(ledger)
        ledger = guard.deleted(dict(ledger=ledger, run_id='run1', row=dict(schema='b', table='parent', id=gone),
            proof=dict(kind='verified_physical_delete', readback_absent=True, run_id='run1', evidence_ref='actual-delete+readback'),
            observations=self.actual_observations(), tables=self.read_catalog()))
        # Even a general writer reusing the deleted PK is not claimed by this execution.
        self.other.execute("INSERT INTO b.parent(id,token) VALUES (%s,'general-reused')", (gone,))
        self.cleanup_owned(ledger)
        self.assertEqual(self.app.execute('SELECT id,status FROM b.parent ORDER BY id').fetchall(), [(gone, 'active'), (remains, 'removed')])

    def test_post_update_verification_failure_rolls_back_all_tables(self):
        parent = self.app.execute("INSERT INTO a.parent(token) VALUES ('run1') RETURNING id").fetchone()[0]
        child = self.app.execute('INSERT INTO a.child(parent_id) VALUES (%s) RETURNING id', (parent,)).fetchone()[0]
        ledger = own(own(self.ledger, 'parent', parent), 'child', child)
        with self.assertRaisesRegex(guard.Blocked, 'POST_UPDATE_CHECK'):
            self.cleanup_owned(ledger, reject_after_update=True)
        self.assertEqual(self.app.execute('SELECT status,touched FROM a.parent').fetchone(), ('active', False))
        self.assertEqual(self.app.execute('SELECT status FROM a.child').fetchone(), ('active',))


if __name__ == '__main__':
    unittest.main()
