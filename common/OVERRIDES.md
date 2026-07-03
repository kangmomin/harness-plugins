# common Project Overrides

플러그인 스킬의 **기본 동작을 그대로 두고**, 프로젝트마다 필요한 **추가 규칙/예외**를 프로젝트 내부에 레이어로 두기 위한 규약.

플러그인 원본 파일(`common/skills/{name}/SKILL.md`)은 **절대 수정하지 않는다**. 프로젝트 특화 규칙은 아래 경로의 오버라이드 파일에만 작성한다.

## 경로 구조

```
<repo-root>/.claude/common/
├── common.md                   # 플러그인 공통 오버라이드 (모든 스킬에 적용)
└── skills/
    └── doc-gen.md              # /common:doc-gen 오버라이드
```

모든 파일은 선택적이다. 없으면 해당 레이어를 건너뛴다.

## 병합 규칙

스킬 실행 시 로드 순서:

1. **플러그인 기본 동작** — `common/skills/{name}/SKILL.md`
2. **공통 오버라이드** — `.claude/common/common.md` 가 있으면 먼저 읽는다
3. **스킬별 오버라이드** — `.claude/common/skills/{name}.md` 가 있으면 읽는다

### 충돌 해결

| 상황 | 규칙 |
|------|------|
| 오버라이드가 새 규칙 추가 | 플러그인 기본 동작 + 오버라이드 규칙 모두 적용 |
| 오버라이드가 특정 단계 변경 | 해당 단계만 오버라이드 지시로 치환 |
| 오버라이드가 특정 단계 skip | 그 단계를 SKIPPED로 처리 |
| 오버라이드와 플러그인 기본 동작 충돌 | **오버라이드가 우선** |

## 선언 예시: 브랜치 모델

commit-push(브랜치 판정)와 commit-pr(base 결정·조합 검증)이 **함께** 소비하는 정책이므로, 스킬별 파일이 아닌 **공통 레이어 `.claude/common/common.md`** 에 선언한다 — 각 스킬은 `common.md`와 자기 스킬별 오버라이드만 읽기 때문에, `skills/commit-push.md`에 선언하면 commit-pr이 읽지 못한다.

```markdown
## 브랜치 모델

| prefix | 허용 base |
|--------|----------|
| feat/* | dev |
| hotfix/* | main |
```

선언 시 효과: 브랜치 판정·이름 규칙의 prefix 집합이 위 표로 대체되고, PR 생성 전 `{prefix} → {base}` 조합이 검증된다. 미선언 시 플러그인 기본 동작 그대로.

## 주의

- 오버라이드 파일은 **프로젝트 저장소에 커밋**되어야 팀 전체에 일관 적용된다.
- 프라이빗 설정은 `.claude/common/common.local.md` 처럼 `.local.md` 접미사를 쓰고 `.gitignore` 대상으로 둘 수 있다.
