> `overlay/e2e-test.md`가 서버 시작 전, 첫 쓰기 요청 전, 정리 전에 로드하는 canonical 절차다. 단독 실행 금지.

# DB 대상 검증과 실행 소유 데이터 정리

## Step 7.1: 시작 전 게이트 — 생략 불가

`--skip-doctor`/`-sd`, smoke, REST/gRPC/PubSub 모두 이 게이트를 유지한다. 선택 환경 probe를 생략해도 데이터 변경 권한은 생기지 않는다.

1. 실제 앱의 설정 로딩·DB connection factory, migration, 시작 시 seed, background worker를 읽는다. 환경 파일을 `source`하거나 비밀 값을 출력하지 않는다. env에 적힌 호스트만으로 실제 연결을 확인했다고 하지 않는다.
2. 로컬/격리 테스트 DB라는 기존 근거와 호스트 허용 정책을 확인한다. `localhost`, loopback, Unix socket도 tunnel/proxy일 수 있다. `0.0.0.0`은 서버 listen 주소이므로 접속 대상 증거가 아니다. `host.docker.internal` 같은 별칭은 실제 연결 identity로 확인한다. 값 부재/조회 NULL은 자동 허용이 아니다.
3. `secret/.e2e-allowed-hosts`는 이미 승인된 대상의 호스트 정책만 보완한다. 앱/MCP identity 일치, 전용 테스트 대상, 소유권 검증을 대체하지 않는다. 미승인 대상은 `BLOCKED:DB_TARGET_UNAPPROVED`; 승인 근거가 없으면 임의 등록하지 않는다.
4. 시작 시 쓰기가 있으면 기존에 지원되는 설정으로 migration·seed·worker를 비활성화하고, 실제 connection factory의 읽기 전용 probe로 대상을 먼저 확인한다. 존재하지 않는 플래그를 만들지 않는다. 쓰기 없이 확인할 수 없으면 `BLOCKED:DB_STARTUP_UNVERIFIED`로 서버 시작을 보류한다.
5. `secret/.env`, 키 파일, 허용 호스트 파일은 실제 대상 경로에서 `git ls-files --error-unmatch -- <path>`가 실패하고 `git check-ignore --quiet -- <path>`가 성공하는지 확인한다. 이미 ignore됐다고 가정하지 않는다. 복사는 init의 worktree hook 계약에 따라 기존 파일·권한을 보존한다.

## Step 7.4: 실제 연결 확인과 소유 ID ledger 초기화

서버를 쓰기 없는 상태로 시작한 뒤 **첫 시드/REST/gRPC/PubSub 쓰기 전에** 실행한다. gRPC가 별도 pool을 쓰거나 앱이 여러 DB로 쓰면 모든 실제 write connection을 확인한다. 이 절차는 한 ledger당 한 DB를 지원한다. 여러 DB/미확인 외부 writer는 `BLOCKED:DB_SCOPE_UNSUPPORTED`다.

앱의 **실제 연결/pool**과 정리에 사용할 **실제 DB connection** 각각에서 다음 값을 수집한다. `.env`로 별도 접속한 클라이언트를 앱 연결 증거로 바꾸어 부르지 않는다. 앱 진단 기능/connection factory를 통한 실제 관측이 없으면 `BLOCKED:DB_IDENTITY_UNVERIFIED`다.

```sql
SELECT current_database() AS database,
       (SELECT oid::bigint FROM pg_database WHERE datname = current_database()) AS database_oid,
       (SELECT system_identifier::text FROM pg_control_system()) AS cluster_id,
       pg_postmaster_start_time() AS server_started_at,
       inet_server_addr()::text AS server_address, inet_server_port() AS server_port,
       current_user, current_schemas(false) AS search_path_schemas;
```

명시적 대상 schema 목록을 추가로 `pg_namespace`에서 확인한다. cluster ID + DB명/OID + 서버 시작 시각 + 대상 schema 이름/OID가 일치해야 한다. 연결 문자열의 host/port와 관측된 서버 address/port를 비밀 없이 함께 기록한다. 터널의 로컬 port와 서버 port가 달라도 위 실제 identity가 같다는 근거가 필요하다. `pg_control_system()` 권한 부족이나 metadata 조회 실패는 UNKNOWN/BLOCKED이며 호스트 문자열로 대신하지 않는다. 서버 재시작·failover·DB 대상 변화 시 이전 ledger로 정리하지 않는다.

`overlay/assets/db_ownership.py`는 **읽기 전용 검증/SQL 계획 helper**다. DB 연결이나 transaction을 생성하지 않으며 JSON의 `verified`는 실제 관측 receipt가 있을 때만 true로 설정한다.

- `init INPUT.json`: `{run_id, schemas, observations, tables, reviewed_triggers}` → ledger.
- `observations.app.source=app_runtime_connection`, `observations.cleanup.source=cleanup_transaction_connection`. 각 관측은 위 identity, 명시적 `schemas`, `verified:true`, `host_allowed:true`를 포함한다. 근거와 connection/session 식별은 별도 실행 evidence에 저장한다.
- `tables`: `{schema, table, schema_oid, relation_oid, pk, status_column, id_type, visibility_verified, trigger_fingerprint}` 목록. `schema_oid`/`relation_oid`는 초기화 시 실제 `pg_namespace.oid`/`pg_class.oid`를 고정하고 이후 매번 비교한다. 같은 이름/컬럼으로 DROP+CREATE된 테이블의 재사용 PK는 다른 소유권이다. 식별자는 실제 catalog allowlist에 있는 ASCII SQL identifier만, PK는 단일 int4/int8/uuid만 지원한다. partition/inheritance, 복합 키, RLS/권한으로 숨겨진 행, 미지원 status 의미는 BLOCKED다. `visibility_verified`는 모든 행 조회 권한과 RLS 비적용을 실제 확인한 결과다.
- `trigger_fingerprint`: 모든 관련 trigger 정의·활성 상태·함수 본문·호출 함수 의존성의 정렬된 snapshot SHA-256. 실행자는 소스와 부작용을 검토해 안전한 fingerprint만 `reviewed_triggers[schema.table]`로 제공한다. 방금 조회한 hash를 자동 승인하지 않는다. 기존 비소유 행을 변경할 수 있거나 외부 I/O를 수행하는 trigger/rule은 지원하지 않는다. trigger가 없어도 빈 snapshot hash를 명시한다.
- 출력 ledger는 `{E2E_RUN_DIR}`의 실행 전용 0600 파일로 저장한다. 원자적으로 교체하고 단일 오케스트레이터가 갱신한다. 다른 실행 ledger를 합치지 않는다. 미완료/UNKNOWN이면 ledger와 receipt를 보존한다.

## Step 7.5: 시드와 API 생성 소유권 기록

필요한 최소 데이터만 만든다. 기존 FK 부모는 **읽기 전용 참조**로 사용하며 ledger 소유 ID에 넣지 않는다. UPDATE/DELETE 테스트 대상은 이번 실행의 신규 데이터여야 한다.

1. schema와 table을 함께 지정하여 컬럼, NOT NULL/CHECK, FK, trigger를 확인한다. catalog의 OID로 관계를 연결하고 FK 부모부터 생성한다. identifier는 catalog allowlist에서만, 값은 driver bind parameter로 전달한다.
2. 시드는 **INSERT-only** SQL의 `RETURNING`으로 실제 신규 PK를 캡처한다. 예: `INSERT INTO "public"."publishers" ("name", "status") VALUES (%s, %s) RETURNING "id"`, parameters `["[E2E:<run_id>] Publisher", "active"]`. 여러 행 INSERT도 반환된 모든 ID를 기록한다.
3. API는 실제 create 경로가 새 행 INSERT임을 확인하고 반환 ID와 run/case 요청 receipt를 연결한다. `201`, `RETURNING`, POST라는 이름만으로 소유권을 인정하지 않는다. `ON CONFLICT DO UPDATE`, upsert, 이미 완료된 idempotency 응답, 기존 ID 재사용은 신규 소유권이 아니다.
4. `record`에 `{ledger, run_id, row:{schema,table,id,case_id,proof}}`를 전달한다. `proof={kind,created_new:true,run_id,evidence_ref}`; kind는 `insert_only_returning`, `api_insert_only`, `attributed_trigger_insert`만 허용한다. 증거를 꾸며 kind를 바꾸지 않는다. child도 실제 INSERT/검토된 trigger 생성과 해당 run token의 상관관계로 각각 증명한다. 부모 FK를 공유한다는 이유만으로 소유하지 않는다.
5. timeout/비동기 응답 유실은 run token/correlation 및 실제 신규 생성 경로로만 복구한다. 복구 불가 ID는 ledger `unresolved`와 `UNKNOWN:CREATION`으로 남긴다. MAX, ID 대소/범위, 최신 timestamp, `[E2E]` 접두사만으로 추정하지 않는다. 미확인 상태에서 쓰기 요청을 자동 재시도하지 않는다.

### 물리 DELETE 기능 테스트의 ledger lifecycle

검토된 DELETE가 소유 행을 물리 삭제했으면 실제 삭제 receipt와 같은 DB/table identity의 read-back(absent)을 기록한다. `deleted` 입력은 `{ledger,run_id,row:{schema,table,id},observations,tables,proof:{kind:verified_physical_delete,readback_absent:true,run_id,evidence_ref}}`다. 이 action은 해당 row를 `lifecycle:deleted`로 표시하고 정리 UPDATE에서 제외한다. 같은 PK가 나중에 재사용되어도 새 행을 소유하지 않는다. soft-delete는 active 소유 목록을 유지한다. 정체 불명의 absent/timeout을 삭제 완료로 바꾸지 않는다.

## Step 10: 같은 transaction 안에서 정리

HTTP DELETE는 기능 테스트로 별도 검증한다. 일반 정리의 우선 경로로 쓰지 않는다. 여러 HTTP/MCP 요청을 하나의 SQL transaction이라고 취급할 수 없다. 서비스가 같은 소유권/원자성 계약을 직접 구현한 경우에만 그 cleanup API를 별도로 사용할 수 있다.

정리는 검증된 단일 physical DB connection의 한 transaction에서 아래 전부를 실행한다. MCP가 호출마다 autocommit/connection을 바꾸거나 bind parameter/transaction 보장을 제공하지 않으면 `BLOCKED:CLEANUP_TRANSACTION_UNAVAILABLE`이다. `BEGIN` 호출 후 다른 MCP 호출들이 같은 session이라고 가정하지 않는다. 검증된 session executor 또는 기존 로컬 DB driver를 사용하며 비밀은 SQL/로그/argv에 넣지 않는다.

1. 앱/worker의 이 실행 작업 완료를 확인한다. unresolved 생성이 있으면 정리 범위를 추정하지 않는다. transaction을 시작하고 lock/statement timeout을 설정한다. 앱과 cleanup identity를 다시 확인한다.
2. 소유 테이블과 incoming FK child를 schema-qualified catalog OID로 전부 찾는다. **테스트 대상 목록 밖/schema 밖의 incoming FK도 포함**한다. 예시 catalog 조회:
   ```sql
   SELECT c.oid, pn.nspname AS parent_schema, p.relname AS parent_table,
          cn.nspname AS child_schema, ch.relname AS child_table,
          c.confkey AS parent_attnums, c.conkey AS child_attnums
   FROM pg_constraint c
   JOIN pg_class p ON p.oid = c.confrelid
   JOIN pg_namespace pn ON pn.oid = p.relnamespace
   JOIN pg_class ch ON ch.oid = c.conrelid
   JOIN pg_namespace cn ON cn.oid = ch.relnamespace
   WHERE c.contype = 'f';
   ```
   각 attnum은 해당 relation의 `pg_attribute`에 연결한다. 같은 constraint/table 이름을 schema 없이 join하지 않는다. 단일 PK를 참조하는 단일 FK만 지원하며 복합/self/cycle, 조회 권한/RLS 미확인, 범위 밖 child는 BLOCKED다.
3. 대상과 모든 child 테이블을 이름 순으로 `SHARE ROW EXCLUSIVE` 잠근 뒤 metadata/FK를 재조회한다. 범위 변화는 rollback 후 재검토한다. 소유 행도 `SELECT ... WHERE pk IN (...) FOR UPDATE`로 잠근다. 삭제 완료 lifecycle을 제외한 모든 소유 ID의 존재/상태와 원래 생성 correlation·불변 식별 증거를 대조한다. 같은 PK의 다른 생성 행인지 배제할 수 없으면 `BLOCKED:ROW_IDENTITY_UNVERIFIED`다. FK 추가 및 동시 일반 INSERT/UPDATE와 충돌하는 잠금을 정리 완료까지 유지한다. migration/함수 교체도 정리 동안 중지되어야 한다. 테이블 잠금만으로 `CREATE OR REPLACE FUNCTION`까지 배제했다고 하지 않는다.
4. 모든 incoming FK에서 소유 부모를 참조하는 **실제 child ID**를 조회한다. removed 행도 생략하지 않는다. 각각 소유 ledger ID와 대조한다. 하나라도 비소유이면 `BLOCKED:UNOWNED_DEPENDENTS`; 그 child를 정리 범위에 추가하지 않는다. trigger/rule과 함수 snapshot도 재검증한다. 미검토 또는 변화 시 rollback한다.
5. `plan` 입력: `{ledger,run_id,observations,tables,transaction_verified:true,incoming_checked:true,foreign_keys,dependents}`. `foreign_keys` 원소는 `{parent:{schema,table},child:{schema,table},parent_columns:[pk],child_columns:[fk]}`, `dependents` 원소는 `{parent:{schema,table,id},child:{schema,table,id}}`. 완전한 catalog/실제 row 조회 receipt가 있어야 checked=true다.
6. helper가 READY를 반환하면 child→parent 순서의 `statements`를 **같은 connection에서** 실행한다. `sql`과 `params`를 driver에 별도로 전달한다. 이 SQL은 psycopg `%s` parameter 문법이며 문자열 치환/다른 MCP 문법으로 그대로 실행하지 않는다. 각 UPDATE의 `RETURNING` ID 집합이 `expected_ids`와 정확히 같아야 한다. PK 전체 범위/부모 FK 기반 일괄 변경은 금지다.
7. 같은 transaction에서 소유 ID의 status와 검토된 trigger 부작용을 확인한다. RETURNING/count만으로 trigger가 다른 행을 건드리지 않았다고 단정하지 않는다. 검증 실패는 전부 rollback; 통과 후에만 commit한다. commit 응답 유실은 `UNKNOWN:CLEANUP_COMMIT`으로 보고하고 같은 identity에서 read-back한다. 새 transaction에서 무조건 재실행하지 않는다.
8. 실행별 DB identity, 테이블별 소유 ID/정리 반환 ID, 참조 전용 ID, 미정리 ID와 사유를 최종 리포트에 기록한다. 새 audit 행처럼 보존이 필요한 trigger 결과는 별도 명시한다. BLOCKED/UNKNOWN을 정리 완료로 표시하지 않는다. DB 정리에 실패해도 이번 실행의 서버/세션 정리는 수행한다.

PostgreSQL의 [잠금 규칙](https://www.postgresql.org/docs/17/explicit-locking.html), [FK catalog](https://www.postgresql.org/docs/17/catalog-pg-constraint.html), [trigger catalog](https://www.postgresql.org/docs/17/catalog-pg-trigger.html)를 기준으로 한다. helper는 receipt를 검증하는 계획 도구이며 DB 권한 통제나 임의 trigger의 안전성을 자동 증명하지 않는다.
