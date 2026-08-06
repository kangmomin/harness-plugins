# harness-plugins

개발 워크플로우 자동화를 위한 Claude Code 하네스 모음.

Technical Spec 작성, Plan 리뷰, 테스트 선작성(TDD), 구현, 품질 루프, 커밋/PR까지 반복되는 개발 절차를 플러그인과 스킬로 묶어 제공한다.

`start-workflow` 는 **Spec의 추적 ID(`AC`/`EC`/`RC`)를 근거로 실패 테스트를 먼저 고정한 뒤 구현한다.** 테스트 범위는 Spec이 상한이며, 구현 직전에 수집한 회귀 baseline과 대조해 이번 변경이 깨뜨린 것과 원래 깨져 있던 것을 구분한다. TDD가 맞지 않는 상황(`--no-tdd`, 테스트 인프라 부재 등)에서는 자동으로 기존 흐름으로 되돌아간다.

## 구조

**베이스 2개 + 오버레이 N개**의 2층 구조다.

```
            /common:start-workflow          ← 유일한 진입점 (도메인 판정)
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    be-harness   fe-harness    풀스택 (common 이 직접 오케스트레이션)
        ▲            ▲
        │ overlay    │ overlay
   minmos-harness  hyeondongs-harness
```

- **절차는 베이스(be/fe)에만 있다.** 특화 하네스는 절차를 복제하지 않고 델타만 얹는다.
- 오버레이는 베이스의 Phase **번호가 아니라 제목(앵커)** 으로 위치를 지정하므로, 베이스가 Phase를 추가해도 깨지지 않는다. 규약: [`docs/overlay.md`](./docs/overlay.md).

## 설치

```bash
# 마켓플레이스 등록
/plugin marketplace add kangmomin/harness-plugins

# 공용 진입점 (다른 하네스보다 먼저 설치)
/plugin install common@harness-plugins

# 베이스 하네스 — 필요한 도메인만
/plugin install be-harness@harness-plugins
/plugin install fe-harness@harness-plugins
```

프로젝트 특화 오버레이가 필요하면 **베이스를 먼저 설치한 뒤** 추가한다.

```bash
/plugin install minmos-harness@harness-plugins      # be-harness 필요
/plugin install hyeondongs-harness@harness-plugins  # fe-harness 필요
```

Claude Code marketplace 정의는 `.claude-plugin/marketplace.json` 에 있다.

## 플러그인 목록

| 플러그인 | 유형 | 설명 |
|---------|------|------|
| **common** | 진입점 | 워크플로우 단일 진입점(`start-workflow` — 도메인 판정 + 풀스택 오케스트레이션), 커밋/Push/PR(`commit`, `commit-push`, `commit-pr`, `commit-hard-push`, `merge`), 문서 생성(`doc-gen`) |
| **be-harness** | 베이스 | 범용 백엔드. Go/Node 프리셋과 project profile 기반의 Spec→Plan→Red→Green→품질 루프→PR |
| **fe-harness** | 베이스 | 범용 프론트엔드. React/Next.js 중심 컴포넌트 생성, lint/a11y, 단위/E2E 테스트, PR |
| **minmos-harness** | be 오버레이 | Post-Math 백엔드 — Apidog 문서 동기화, gRPC/PubSub E2E, PostgreSQL MCP DB 안전 규칙, Post-Math 컨벤션 |
| **hyeondongs-harness** | fe 오버레이 | hyeondongs 환경 세팅/진단(`.hyeondong-config.json`), 풀스택 전환 시 minmos 백엔드 연계 |

## 빠른 시작

워크플로우는 **`/common:start-workflow` 하나로 시작한다.** 요청 내용과 프로젝트 신호(`go.mod`, `package.json`, profile 파일)로 도메인을 판정하고, 확인을 거쳐 실행한다.

```bash
/common:how-to-use                          # 설치된 스킬 전체 안내부터

/common:start-workflow "주문 취소 기능 추가"   # 도메인 자동 판정 → 확인 → 실행
```

도메인을 미리 알면 플래그로 고정한다:

```bash
/common:start-workflow --be "정산 배치 API 추가"   # 백엔드
/common:start-workflow --fe "쿠폰 목록 화면"       # 프론트엔드
/common:start-workflow --fs "쿠폰 등록 화면과 API" # 풀스택 (be+fe 모두 설치 필요)
/common:start-workflow --mm "..."                 # 백엔드 + minmos 오버레이
/common:start-workflow --hd "..."                 # 프론트엔드 + hyeondongs 오버레이
```

오버레이 플러그인이 설치되어 있으면 플래그 없이도 자동 감지된다.

워크플로우 외 스킬은 하네스를 직접 호출한다:

```bash
/be-harness:init          /fe-harness:init          # profile 생성 (최초 1회)
/be-harness:request       /fe-harness:component
/be-harness:e2e-test-loop /fe-harness:test-loop
/minmos-harness:doctor    /hyeondongs-harness:doctor
```

## 디렉터리 구조

```text
.
├── common/                 # 워크플로우 진입점 + 커밋/PR/문서 (먼저 설치)
│   └── skills/start-workflow/references/   # 풀스택 오케스트레이션 절차
├── be-harness/             # 범용 백엔드 베이스
├── fe-harness/             # 범용 프론트엔드 베이스
├── minmos-harness/         # be-harness 오버레이 (Post-Math)
│   └── overlay/            # 앵커 기반 델타 + Post-Math 특화 references
├── hyeondongs-harness/     # fe-harness 오버레이 (hyeondongs)
│   └── overlay/
├── docs/                   # 저장소 차원 문서
└── .claude-plugin/         # Claude Code marketplace 정의
```

## 참고 문서

- `docs/skill-authoring.md`: 스킬 작성 표준 (모든 플러그인 SKILL.md의 기준)
- `docs/overlay.md`: 오버레이 규약 (앵커 기반 Phase 삽입, 두 적용 경로, 승격 기준)
- `common/README.md`: 진입점 + 공용 스킬
- `be-harness/README.md`: 범용 백엔드 베이스
- `fe-harness/README.md`: 범용 프론트엔드 베이스
- `minmos-harness/README.md`: Post-Math 오버레이 (v1.x 마이그레이션 표 포함)
- `hyeondongs-harness/README.md`: hyeondongs 오버레이 (v2.x 마이그레이션 표 포함)
