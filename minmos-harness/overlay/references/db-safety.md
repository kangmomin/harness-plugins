> 이 문서는 `e2e-test` 스킬의 Step 7(테스트 환경 준비)에서 로드된다. 단독 실행 금지.
> 로컬 DB 전용 원칙의 요약은 SKILL.md 본문에 있으며, 이 문서가 검증 절차의 canonical이다.

# DB 안전 검증 + 테스트 데이터 준비 상세

## Step 7.1: DB 호스트 안전 검증 (Gate — 통과 필수)

테스트 환경을 준비하기 **전에** 반드시 DB 호스트가 로컬인지 검증한다. 이 게이트를 통과하지 못하면 이후 모든 단계를 실행하지 않는다.

```bash
# 1. secret/.env에서 DB_HOST 추출
DB_HOST=$(grep -E '^DB_HOST=' secret/.env | head -1 | cut -d'=' -f2 | tr -d '[:space:]"'"'"'')

# 2. PostgreSQL MCP 실제 연결에서도 호스트 확인 (이중 검증)
# PostgreSQL MCP tool로 실행:
# SELECT inet_server_addr()::text AS host, inet_server_port() AS port;
# 결과 host를 MCP_DB_HOST로 기록한다. Unix socket/로컬 연결로 NULL이면 빈 값으로 둔다.
MCP_DB_HOST="<postgresql-mcp-inet-server-addr-result>"

# 3. 사용자 승인 화이트리스트 로드
ALLOWED_HOSTS="localhost 127.0.0.1 0.0.0.0 host.docker.internal"
if [ -f secret/.e2e-allowed-hosts ]; then
  EXTRA_HOSTS=$(grep -v '^\s*#' secret/.e2e-allowed-hosts | grep -v '^\s*$' | tr '\n' ' ')
  ALLOWED_HOSTS="$ALLOWED_HOSTS $EXTRA_HOSTS"
fi

echo "DB_HOST from .env: ${DB_HOST}"
echo "DB_HOST from MCP:  ${MCP_DB_HOST}"
echo "Allowed hosts:     ${ALLOWED_HOSTS}"
```

**검증 조건 (두 값 모두 통과해야 함):**

| 값 | 허용 | 차단 |
|----|------|------|
| `DB_HOST` | 기본 허용 목록 + `secret/.e2e-allowed-hosts` + 빈 값(기본=localhost) | 그 외 모든 값 |
| `MCP_DB_HOST` | 위와 동일 + 빈 값(Unix socket/로컬 연결) | 그 외 모든 값 |

- 하나라도 허용 목록에 없으면 **즉시 중단**하고 아래 "위반 시 처리" 절차를 실행한다.
- PostgreSQL MCP에 연결할 수 없으면 테스트 데이터 생성/정리를 할 수 없으므로 `SKIPPED:POSTGRES_MCP_UNAVAILABLE`로 종료한다.
- MCP host 쿼리가 지원되지 않아 호스트를 확인할 수 없으면 `UNKNOWN`으로 보고하고, 사용자 승인을 받아 `secret/.e2e-allowed-hosts`에 기록하기 전까지 쓰기 SQL을 실행하지 않는다.
- **이 게이트를 우회하는 어떤 논리("읽기만 하겠다", "테스트 데이터만 건드리겠다" 등)도 허용하지 않는다.**

## 위반 시 처리 (차단 → 승인 요청 → 화이트리스트 등록)

DB 호스트가 허용 목록(기본 + 화이트리스트)에 없으면:

1. **즉시 테스트를 중단**한다.
2. 사용자에게 경고와 함께 **승인 여부를 질문**한다:
   > ⚠️ **E2E 테스트 차단**: DB 호스트 `{호스트}`는 허용 목록에 없습니다.
   > 이 DB에서 E2E 테스트를 실행하면 테스트 데이터가 생성/수정/삭제됩니다.
   >
   > 이 DB를 E2E 테스트 대상으로 허용하시겠습니까?
   > 1. 허용 — `secret/.e2e-allowed-hosts`에 등록하고 게이트 재검증 후 진행
   > 2. 거부 — 어떤 SQL도 실행하지 않고 `SKIPPED:REMOTE_DB_BLOCKED`로 종료
3. Claude가 사용자 승인 없이 화이트리스트에 호스트를 추가하는 것은 금지다.

## 화이트리스트 파일 형식

프로젝트 루트의 `secret/.e2e-allowed-hosts`에 호스트를 한 줄에 하나씩 등록한다 (주석·빈 줄 무시):

```
# secret/.e2e-allowed-hosts 예시
dev-db.internal.example.com
10.0.1.50
```

`secret/` 디렉토리는 이미 gitignore 처리되어 있으므로 별도 등록은 불필요하다.

## Step 7.4: 테스트 데이터 추적 준비

테스트 시작 전, 관련 테이블의 현재 최대 ID를 기록한다:

```sql
SELECT COALESCE(MAX(id), 0) FROM {table_name};
```

이 ID를 `BASELINE_ID`로 저장하여, 테스트 종료 시 이후 생성된 데이터를 식별한다.

## Step 7.5: 테스트 전제 데이터 준비 (시드)

테스트 실행 **전에**, 모든 테스트 시나리오에 필요한 전제 데이터가 DB에 존재하는지 분석하고, 부족하면 PostgreSQL MCP를 통해 자동 생성한다.

### 분석 대상 (Step 4 엣지 케이스 분석 결과 기반)

| 테스트 시나리오 | 필요한 전제 데이터 | 예시 |
|----------------|------------------|------|
| 생성(Create) 테스트 | FK로 참조할 부모 데이터 | grade_id, publisher_id 등 FK 필드에 넣을 유효한 ID |
| 수정(Update) 테스트 | 수정 대상 데이터 | 테스트 중 Create API로 직접 생성 (시드 불필요) |
| 삭제(Delete) 테스트 | 삭제 대상 데이터 | 테스트 중 Create API로 직접 생성 (시드 불필요) |
| 필터/검색 테스트 | 필터 값별 대조 데이터 | 서로 다른 grade_id를 가진 데이터 2건 이상 |
| 상태 전이 테스트 | 특정 상태의 데이터 | status='active'인 데이터 (전이 출발점) |
| FK 참조 에러 테스트 | (불필요) | 존재하지 않는 ID 999999 사용 |
| 권한 테스트 | 다른 사용자의 데이터 | company_id가 다른 데이터 |

> 수정/삭제 대상 데이터는 Step 8에서 **Create API를 호출하여 직접 생성**한다 (시드가 아닌 API 생성 → ID 캡처 → 수정/삭제 흐름). 여기서는 그 Create API가 성공하기 위한 **전제 조건**만 준비한다.

### 판단 절차

1. **테스트 대상 API의 request 스키마에서 FK 필드를 추출**한다.
   - handler의 request DTO에서 `*_id`, `*_ids` 패턴의 필드를 찾는다.
   - 해당 필드가 참조하는 테이블을 DB FK constraint 또는 코드 로직에서 확인한다.
2. **각 FK 참조 테이블에 유효한 데이터가 존재하는지 확인**한다.
   ```sql
   SELECT COUNT(*) FROM {referenced_table} WHERE status != 'removed';
   ```
   - 0건이면 → 해당 테이블에 시드 데이터 필요
   - 1건 이상이면 → 기존 데이터의 ID를 **읽기 전용으로 참조** (수정/삭제하지 않음)
3. **필터/검색 테스트용 데이터 존재 여부 확인**한다.
   ```sql
   SELECT DISTINCT {filter_column} FROM {table_name} WHERE status != 'removed' LIMIT 5;
   ```
   - 필터 값이 1종류 이하면 → 대조 테스트를 위해 2종 이상의 값을 가진 시드 데이터 필요
4. **상태 전이 테스트용 특정 상태 데이터 확인**한다. 없으면 시드로 생성하거나 Step 8에서 Create API로 생성 후 진행.

### 생성 절차

1. **스키마 분석**: 대상 테이블의 컬럼, 타입, NOT NULL, FK, CHECK constraint를 확인한다.
   ```sql
   SELECT column_name, data_type, is_nullable, column_default
   FROM information_schema.columns
   WHERE table_name = '{table_name}' ORDER BY ordinal_position;
   ```
   ```sql
   SELECT conname, pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conrelid = '{table_name}'::regclass AND contype = 'c';
   ```
2. **FK 의존 순서 해결 (위상 정렬)**: FK가 참조하는 부모 테이블부터 순서대로 생성한다.
   ```sql
   SELECT
     tc.table_name AS child_table,
     ccu.table_name AS parent_table,
     kcu.column_name AS fk_column
   FROM information_schema.table_constraints tc
   JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
   JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
   WHERE tc.constraint_type = 'FOREIGN KEY'
     AND tc.table_name IN ({테스트 관련 테이블 목록});
   ```
   예: textbooks가 publishers, grades를 FK 참조 → 생성 순서: publishers → grades → textbooks
3. **시드 INSERT**: PostgreSQL MCP로 필요한 최소한의 테스트 데이터를 삽입한다.
   - **FK 참조용 부모 데이터** (Create/Update API 성공을 위한 최소 1건):
     ```sql
     INSERT INTO publishers (name, status) VALUES ('[E2E] Publisher A', 'active') RETURNING id;
     INSERT INTO grades (name, status) VALUES ('[E2E] Grade A', 'active') RETURNING id;
     ```
   - **필터/검색 대조 데이터** (필터별로 최소 2종 이상의 다른 값):
     ```sql
     INSERT INTO grades (name, status) VALUES ('[E2E] Grade A', 'active'), ('[E2E] Grade B', 'active');
     INSERT INTO textbooks (title, grade_id, status) VALUES
       ('[E2E] Book 1', {grade_a_id}, 'active'),
       ('[E2E] Book 2', {grade_b_id}, 'active');
     ```
   - **상태 전이 테스트용 데이터** (출발 상태로 직접 INSERT):
     ```sql
     INSERT INTO tasks (title, status) VALUES ('[E2E] Task for transition', 'active') RETURNING id;
     ```
   - **권한 테스트용 데이터** (테스트 토큰과 다른 company_id/member_id):
     ```sql
     INSERT INTO resources (title, company_id, status) VALUES ('[E2E] Other company resource', 999, 'active') RETURNING id;
     ```
4. **시드 BASELINE 기록**: 시드로 생성한 데이터도 `BASELINE_ID` 이후이므로, 테스트 종료 시 함께 정리된다.
5. **시드 결과 요약**: 생성된 시드 데이터를 기록하여 Step 8에서 참조할 수 있도록 한다.
   ```
   시드 데이터 요약:
   - publishers: id={id} ('[E2E] Publisher A')
   - grades: id={id_a} ('[E2E] Grade A'), id={id_b} ('[E2E] Grade B')
   - textbooks: id={id_1} (grade_id={id_a}), id={id_2} (grade_id={id_b})
   ```

### 원칙

- 시드 데이터는 **테스트에 필요한 최소 수량**만 생성한다.
- 유니크 제약이 있는 컬럼은 `[E2E]` 접두사 등으로 기존 데이터와 구분한다.
- `RETURNING id`로 생성된 ID를 즉시 캡처한다.
- 시드 생성 실패 시 (권한 부족, constraint 위반 등) 에러를 보고하고 해당 테스트를 **SKIP** 처리한다.
- **기존 데이터는 읽기 전용 참조만 허용** (FK 참조용 ID 조회). 수정/삭제하지 않는다.
