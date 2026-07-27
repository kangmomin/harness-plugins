# hyeondong's harness

hyeondongs 프로젝트 전용 **부속** 하네스. 환경 세팅/진단과, minmos 백엔드와 짝지은 풀스택 오케스트레이션만 담당한다.

> **v2.0.0 breaking change** — 프론트엔드 개발 스킬 10종(`request-hd`, `component-hd`, `unit-test-hd`, `e2e-test-hd`, `test-loop-hd`, `lint-check-hd`, `convention-check-hd`, `simplify-loop-hd`, `default-conventions-hd`, `start-workflow-hd`)은 `fe-harness` 와 내용이 사실상 같아 **fe-harness 로 통합**되었다. 자세한 이관 방법은 아래 [마이그레이션](#마이그레이션-v1x--v2) 참조.

## 의존 플러그인

hyeondongs-harness 는 다음 세 플러그인의 스킬/에이전트를 호출한다. **반드시 함께 설치해야 한다.**

- `common` — `commit`, `commit-push`, `commit-pr`, `commit-hard-push` 등 커밋/PR 워크플로우 + 라우터 스킬 + `doc-gen`
- `fe-harness` — 프론트엔드 개발 스킬 전부와 `a11y-reviewer`, `component-reviewer`, `scope-reviewer`, `workflow-implementer`, `workflow-pr`, `workflow-reflection` 에이전트
- `minmos-harness` — `request-mm`, `simplify-loop-mm`, `convention-check-mm`, `e2e-test-loop-mm`, `e2e-apidog-schema-gen-mm` 등 백엔드 스킬 (`start-workflow-fs` 전용)

## 설치

```
/plugin marketplace add kangmomin/harness-plugins
/plugin install common@harness-plugins
/plugin install fe-harness@harness-plugins
/plugin install minmos-harness@harness-plugins
/plugin install hyeondongs-harness@harness-plugins
```

## 초기 세팅

```bash
/hyeondongs-harness:hyeondong-init-hd     # .hyeondong-config.json 세팅
/hyeondongs-harness:hyeondong-doctor-hd   # 전체 환경 진단
```

`.hyeondong-config.json` 은 fe-harness 스킬이 **2순위 profile** 로 읽는다(읽기 전용). `.claude/fe-harness.local.md` 가 있으면 그쪽이 우선한다.
새 프로젝트라면 `/fe-harness:init` 이 더 완전하다 — 빌드/검증 명령, 서버, Git·커밋 컨벤션까지 담는다. 필드 매핑 표는 fe-harness 루트 `PROFILE.md`.

## 스킬 목록

| 스킬 | 호출 | 설명 |
|------|------|------|
| **hyeondong-init** | `/hyeondongs-harness:hyeondong-init-hd` | 프론트엔드 환경 한 번에 세팅 (프레임워크, UI lib, 상태관리, 테스트 도구) → `.hyeondong-config.json` |
| **hyeondong-doctor** | `/hyeondongs-harness:hyeondong-doctor-hd` | 모든 의존성 한 번에 진단 (필수/선택 분류) |
| **start-workflow-fs** | `/hyeondongs-harness:start-workflow-fs` | **풀스택 애자일 워크플로우** — 기능 정의→통신 계약→교차 리뷰→FE/BE 병렬 구현→통합 검증→PR |

프론트엔드 단일 도메인 작업은 모두 `fe-harness` 를 쓴다: `/fe-harness:start-workflow`, `/fe-harness:request`, `/fe-harness:component`, `/fe-harness:unit-test`, `/fe-harness:e2e-test`, `/fe-harness:test-loop`, `/fe-harness:lint-check`, `/fe-harness:convention-check`, `/fe-harness:simplify-loop`, `/fe-harness:default-conventions`.
`/common:*` 라우터로 진입하면 하네스를 기억하지 않아도 된다 (`/common:start-workflow`, `/common:request`, …).

### 에이전트

hyeondongs-harness 자체 에이전트는 없다. 사용되는 에이전트는 모두 [`fe-harness`](../fe-harness/README.md) 의 것을 그대로 호출한다:

- `scope-reviewer` — Spec 기반 UI 구현/비즈니스 로직 검증
- `a11y-reviewer` — WAI-ARIA, 키보드 네비게이션, 색상 대비 등 접근성 검증
- `component-reviewer` — Props 설계, 재사용성, 렌더링 성능, 관심사 분리 검증
- `workflow-implementer`, `workflow-pr`, `workflow-reflection`

## 풀스택 워크플로우 (`/hyeondongs-harness:start-workflow-fs`)

```
Phase 1: 기능 정의 + Feature Matrix (Plan 모드 진입)
Phase 2: Codex Spec 사전 검토
Phase 3: 통신 계약 정의
Phase 4: 계약 리뷰
Phase 5: 분리 Plan 작성
Phase 6: 브랜치 + 상태 파일
Phase 7: 프론트/백엔드 병렬 구현
Phase 8: 도메인별 품질 루프 (최대 3회)
Phase 9: Codex 품질 리뷰 (항상)
Phase 10: 통합 검증
Phase 11: 커밋/PR
Phase 12: 회고 + 정리
```

FE 는 `fe-harness`, BE 는 `minmos-harness` 스킬로 위임된다. 범용 FE+BE 조합이 필요하면 `fs-harness` 를 쓴다.

## 마이그레이션 (v1.x → v2)

| v1.x 호출 | v2 대체 |
|-----------|---------|
| `/hyeondongs-harness:start-workflow-hd` | `/fe-harness:start-workflow` |
| `/hyeondongs-harness:request-hd` | `/fe-harness:request` |
| `/hyeondongs-harness:component-hd` | `/fe-harness:component` |
| `/hyeondongs-harness:unit-test-hd` | `/fe-harness:unit-test` |
| `/hyeondongs-harness:e2e-test-hd` | `/fe-harness:e2e-test` |
| `/hyeondongs-harness:test-loop-hd` | `/fe-harness:test-loop` |
| `/hyeondongs-harness:lint-check-hd` | `/fe-harness:lint-check` |
| `/hyeondongs-harness:convention-check-hd` | `/fe-harness:convention-check` |
| `/hyeondongs-harness:simplify-loop-hd` | `/fe-harness:simplify-loop` |
| `/hyeondongs-harness:default-conventions-hd` | `/fe-harness:default-conventions` |

- **설정 파일은 그대로 둬도 된다.** fe-harness 가 `.hyeondong-config.json` 을 폴백 profile 로 읽는다.
- `/common:*` 라우터의 `--hd` 는 위 스킬들에 한해 `--fe` 로 자동 처리된다 (`--hd` 가 그대로 유효한 곳: `/common:init`, `/common:doctor`, `/common:start-workflow --hd-fs`).
- hyeondongs-harness 는 프로젝트 오버라이드 레이어가 없었다. fe-harness 로 오면 `.claude/fe-harness/common.md` · `.claude/fe-harness/skills/*.md` 로 스킬 동작을 프로젝트별로 조정할 수 있다. 상세: fe-harness 루트 `OVERRIDES.md`.
