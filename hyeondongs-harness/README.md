# hyeondong's harness

hyeondongs 프로젝트용 **fe-harness 오버레이 플러그인**.

프론트엔드 워크플로우 절차 자체는 갖지 않는다. `fe-harness` 의 절차 위에 hyeondongs 환경 델타(`.hyeondong-config.json` profile 폴백, 풀스택 전환 시 minmos 백엔드 연계)만 얹고, 환경 세팅/진단을 제공한다.

> **v3.0.0 breaking change** — 풀스택 워크플로우(`start-workflow-fs`)가 `common` 으로 이관되고, `-hd` 접미사가 제거되었다. 이관 표는 아래 [마이그레이션](#마이그레이션-v2x--v3) 참조.
> **v2.0.0** — 프론트엔드 개발 스킬 10종이 `fe-harness` 로 통합되었다.

## 의존 플러그인

- **`fe-harness` (필수)** — 프론트엔드 워크플로우·컴포넌트·테스트·린트·컨벤션 절차의 베이스. 없으면 동작하지 않는다.
- `common` (권장) — 풀스택 진입점(`start-workflow --fs`), 커밋/PR 워크플로우, `doc-gen`.
- `minmos-harness` (권장) — 풀스택 작업 시 백엔드 오버레이.

## 설치

```
/plugin marketplace add kangmomin/harness-plugins
/plugin install common@harness-plugins
/plugin install fe-harness@harness-plugins
/plugin install minmos-harness@harness-plugins   # 풀스택 작업 시
/plugin install hyeondongs-harness@harness-plugins
```

## 초기 세팅

```bash
/hyeondongs-harness:init      # .hyeondong-config.json 세팅
/hyeondongs-harness:doctor    # 전체 환경 진단
```

`.hyeondong-config.json` 은 fe-harness 스킬이 **2순위 profile** 로 읽는다(읽기 전용). `.claude/fe-harness.local.md` 가 있으면 그쪽이 우선한다.
새 프로젝트라면 `/fe-harness:init` 이 더 완전하다 — 빌드/검증 명령, 서버, Git·커밋 컨벤션, 리포트 경로까지 담는다. 필드 매핑 표는 fe-harness 루트 `PROFILE.md`.

## 오버레이 구조

규약: [`docs/overlay.md`](../docs/overlay.md).

| 오버레이 | 얹는 내용 |
|---------|----------|
| `overlay/common.md` | `.hyeondong-config.json` 2순위 profile 폴백 (읽기 전용) |
| `overlay/start-workflow.md` | 풀스택 전환 시 백엔드 도메인을 minmos 오버레이로 지정 |

## 스킬 목록

| 스킬 | 호출 | 설명 |
|------|------|------|
| **start-workflow** | `/hyeondongs-harness:start-workflow` | `fe-harness:start-workflow` + hyeondongs 오버레이. 절차는 fe-harness 가 정의 |
| **init** | `/hyeondongs-harness:init` | 프론트엔드 환경 한 번에 세팅 (프레임워크, UI lib, 상태관리, 테스트 도구) → `.hyeondong-config.json` |
| **doctor** | `/hyeondongs-harness:doctor` | 모든 의존성 한 번에 진단 (필수/선택 분류) |

`/common:start-workflow` 로 진입하면 도메인 판정 후 이 플러그인의 `start-workflow` 가 자동 선택된다 (오버레이 감지).

프론트엔드 단일 도메인 작업의 개별 스킬은 모두 `fe-harness` 를 쓴다: `/fe-harness:request`, `/fe-harness:component`, `/fe-harness:unit-test`, `/fe-harness:e2e-test`, `/fe-harness:test-loop`, `/fe-harness:lint-check`, `/fe-harness:convention-check`, `/fe-harness:simplify-loop`, `/fe-harness:default-conventions`.

### 에이전트

hyeondongs-harness 자체 에이전트는 없다. 사용되는 에이전트는 모두 [`fe-harness`](../fe-harness/README.md) 의 것을 그대로 호출한다: `scope-reviewer`, `a11y-reviewer`, `component-reviewer`, `workflow-implementer`, `workflow-pr`, `workflow-reflection`.

## 풀스택 작업

화면과 API가 함께 바뀌면 `/common:start-workflow --fs` 를 쓴다.

```
Phase 1 : 기능 정의 + Feature Matrix (Plan 모드 진입)
Phase 2 : 통신 계약 정의
Phase 3 : 계약 리뷰 (읽기 전용 advisor 교차 리뷰)
Phase 4 : BE/FE/공용 Plan 분리 + Codex 검증 루프
Phase 5 : 브랜치 + 상태 파일 + 도메인별 baseline
Phase 6 : 계약 기반 TDD (Red 배리어 → 병렬 Green)
Phase 7 : 도메인별 품질 루프 (최대 3회)
Phase 8 : 통합 검증 (계약 격리 Read-back → 3방향 대조)
Phase 9 : 단일 PR
Phase 10: 회고 + 정리
```

프론트엔드는 fe-harness + hyeondongs 오버레이가, 백엔드는 be-harness + minmos 오버레이가 담당한다.

## 마이그레이션 (v2.x → v3)

| 이전 (v2.x) | 현재 (v3) |
|------------|----------|
| `/hyeondongs-harness:start-workflow-fs` | `/common:start-workflow --fs` |
| `/hyeondongs-harness:hyeondong-init-hd` | `/hyeondongs-harness:init` |
| `/hyeondongs-harness:hyeondong-doctor-hd` | `/hyeondongs-harness:doctor` |
| (없음) | `/hyeondongs-harness:start-workflow` — fe 위임 + 오버레이 |

**해야 할 일**: `fe-harness` 와 `common` 을 설치한다. `.hyeondong-config.json` 은 그대로 계속 쓸 수 있다.
