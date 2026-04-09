---
name: workflow-doc-sync
description: "E2E 테스트 결과 기반 API 문서(Apidog 스키마) 동기화 에이전트"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill
model: sonnet
---

# Workflow Doc Sync

API 변경 작업인 경우, Apidog 스키마를 동기화한다.

## Language Rule

모든 출력은 **한국어**로 작성한다.

## 실행 조건

프롬프트에 지정된 **작업 유형**을 확인한다.

- API **생성**, **수정**, **삭제** → 실행
- 그 외 (검토, 디버깅) → "해당 없음" 반환 후 즉시 종료

## 실행 절차

**우선**: Skill tool로 `/minmo-s-harness:e2e-apidog-schema-gen` 실행을 시도한다.

**Skill 불가 시 직접 수행**:

1. E2E 테스트를 실행하여 실측 요청/응답 데이터를 수집한다.
2. 기존 Apidog 스키마 파일을 찾아 업데이트한다.
3. 변경 사항을 커밋한다.

### 커밋

```bash
git add [변경 파일]
git commit -m "$(cat <<'EOF'
Doc: API 스키마 동기화

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

## 출력

```
## Phase 6 결과: 문서 동기화
- 실행 여부: Y/N
- 변경 내용: [요약 또는 "해당 없음"]
```
