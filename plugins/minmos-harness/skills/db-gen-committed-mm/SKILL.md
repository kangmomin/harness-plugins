---
name: db-gen-committed-mm
description: "db-gen으로 migration 파일을 생성하고 자동으로 committed 상태로 변환"
---

## Prerequisites

### 필요 환경
- **db-tools 플러그인**: `/db-tools:db-gen` 스킬 제공

### `--init` (초기 세팅)

`$ARGUMENTS`가 `--init`이면 아래 절차를 실행하고 종료한다:

1. **db-tools 플러그인 확인**: `db-tools:db-gen` 스킬이 사용 가능한지 확인한다.
   - 없으면 안내:
     > "db-tools 플러그인이 설치되어 있지 않습니다. 아래 명령으로 설치하세요:"
     > ```bash
     > claude plugin add postmath-plugins/db-tools
     > ```
2. 결과를 보고한다.

### `--doctor` (상태 진단)

`$ARGUMENTS`가 `--doctor`이면 아래 항목을 점검하고 결과를 보고한 뒤 종료한다:

```markdown
## DB Gen Committed — Doctor

| 항목 | 상태 | 비고 |
|------|------|------|
| db-tools 플러그인 | OK / MISSING | 스킬 호출 가능 여부 |
| migrations 디렉토리 | OK / MISSING | infra/flyway/migrations/ 존재 여부 |
```

---

/db-tools:db-gen 을 실행해서 migration 파일을 생성해.

생성이 완료되면, 생성된 파일의 changeset 라인에서 다음 변환을 자동으로 적용해:
1. `context:draft` → `context:committed` 로 변경
2. `runOnChange:true` 제거
3. comment 에 `[DRAFT]` 접두사가 있으면 제거

즉, 처음부터 committed 상태로 migration 파일을 만들어줘.
