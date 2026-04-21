# fe-harness — Community Feedback

이 디렉토리는 fe-harness 플러그인의 **사용자 피드백 수집 영역**입니다. 플러그인 원본 스킬/에이전트는 수정되지 않고 그대로 유지됩니다.

## 구조

```
fe-harness/community-feedback/
├── README.md                  # 이 파일
├── common/
│   └── {YYYY-MM-DD}-{project}.md    # 플러그인 공통에 제안된 피드백
├── skills/
│   └── {skill-name}.md              # 각 스킬별로 누적되는 피드백
└── agents/
    └── {agent-name}.md              # 각 에이전트별로 누적되는 피드백
```

각 파일은 시간순 append 로그. PR로 들어오고, 유지보수자가 주기적으로 **큐레이션**하여 범용 규칙이 확인된 항목만 플러그인 원본 SKILL.md 에 반영합니다.

## 기여 방식

1. 프로젝트에서 `/fe-harness:start-workflow` 를 실행하고 Phase 9에서 **"로컬 저장 + PR"** 옵션을 선택
2. `/fe-harness:submit-feedback` 이 자동으로:
   - 이 레포를 fork/clone
   - 해당 스킬/에이전트/common 파일에 append
   - PR 생성
3. 유지보수자가 PR을 검토하고 머지

수동으로도 이 디렉토리에 직접 PR을 열 수 있습니다.

## 피드백 포맷 (표준)

```markdown
## {YYYY-MM-DD} — {project-name-optional}

**출처**: /fe-harness:start-workflow Phase 8 성찰
**대상**: skill:{name} / agent:{name} / common
**요지**: [한 줄 요약]

### 컨텍스트
- 어떤 작업에서 나온 피드백인지 (도메인/기술 스택 수준, 사내 이름 금지)
- 플러그인 기본 동작의 어느 부분이 아쉬웠는지

### 제안
- [구체적 변경/추가 사항]

### 범용성 검토
- [이 제안이 모든 프로젝트에 도움이 되는가, 아니면 특정 도메인/스택 한정인가]
- [특정 한정이면 어떤 조건에서만 적용해야 하는가]
```

> **사내 용어·시크릿·경로·티켓 번호는 PR 본문이나 파일에 포함 금지**. 피드백 핵심만 추출해 범용 용어로 작성.

## 유지보수 정책

| 상태 | 처리 |
|------|------|
| **신규 PR** | community-feedback 디렉토리에 append 후 머지 (원본 SKILL.md 는 건들지 않음) |
| **유사 피드백 3회 이상 누적** | 범용 규칙 후보로 검토 큐에 진입 |
| **범용 규칙 확정** | 별도 PR로 원본 SKILL.md 에 반영, 해당 피드백 항목에 `[ADOPTED]` 마크 |
| **프로젝트 한정 규칙** | `.claude/fe-harness/` 로컬 오버라이드 문서로 이전 권장, community 파일에는 `[PROJECT-SPECIFIC]` 마크 |

원본 SKILL.md 반영은 **수동 검토 후 별도 PR**. 자동 반영되지 않습니다.
