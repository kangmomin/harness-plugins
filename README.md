# harness-plugins

개발 워크플로우 자동화를 위한 Claude Code 하네스 모음.

Technical Spec 작성, Plan 리뷰, 테스트 선작성(TDD), 구현, 품질 루프, 커밋/PR까지 반복되는 개발 절차를 플러그인과 스킬로 묶어 제공한다.

`start-workflow` 계열은 **Spec의 추적 ID(`AC`/`EC`/`RC`)를 근거로 실패 테스트를 먼저 고정한 뒤 구현한다.** 테스트 범위는 Spec이 상한이며, 구현 직전에 수집한 회귀 baseline과 대조해 이번 변경이 깨뜨린 것과 원래 깨져 있던 것을 구분한다. TDD가 맞지 않는 상황(`--no-tdd`, 테스트 인프라 부재 등)에서는 자동으로 기존 흐름으로 되돌아간다.

## 설치

### Claude Code

```bash
# 마켓플레이스 등록
/plugin marketplace add kangmomin/harness-plugins

# 공용 스킬 (다른 하네스보다 먼저 설치)
/plugin install common@harness-plugins

# 범용 백엔드 하네스
/plugin install be-harness@harness-plugins

# 범용 프론트엔드 하네스
/plugin install fe-harness@harness-plugins

# 풀스택 오케스트레이터
/plugin install fs-harness@harness-plugins
```

프로젝트 특화 하네스가 필요하면 아래 플러그인을 설치한다.

```bash
/plugin install minmos-harness@harness-plugins
/plugin install hyeondongs-harness@harness-plugins
```

Claude Code marketplace 정의는 `.claude-plugin/marketplace.json` 에 있다.

## 플러그인 목록

| 플러그인 | 대상 | 설명 |
|---------|------|------|
| **common** | 모든 하네스 베이스 | 여러 하네스 공용 스킬(`/common:doc-gen`, 커밋/PR 워크플로우)과 **하네스 공용 진입점 라우터**. 다른 하네스 설치 전에 먼저 설치 |
| **be-harness** | 범용 백엔드 | Go/Node 프리셋과 project profile 기반의 Spec→Plan→Red→Green→품질 루프→PR 워크플로우 |
| **fe-harness** | 범용 프론트엔드 | React/Next.js 중심의 컴포넌트 생성, lint/a11y, 단위/E2E 테스트, PR 워크플로우 |
| **fs-harness** | 풀스택 | BE/FE 하네스를 병렬로 사용해 계약 정의, 교차 리뷰, 통합 검증, 단일 PR까지 오케스트레이션 |
| **minmos-harness** | Post-Math 백엔드 | 커밋/PR, 컨벤션 검사, Feature Spec 생성, E2E 테스트(REST+gRPC+PubSub), Apidog 스키마 생성 |
| **hyeondongs-harness** | hyeondongs 부속 | 환경 세팅/진단(`.hyeondong-config.json`)과 minmos 백엔드 연계 풀스택 워크플로우. 프론트엔드 개발 스킬은 fe-harness 로 통합됨 |

## 빠른 시작

여러 하네스가 같은 이름의 스킬(`start-workflow`, `request`, `e2e-test` …)을 제공한다.
**`/common:` 진입점**을 쓰면 하네스 접두를 기억할 필요 없이 대상만 고르면 된다.

```bash
/common:how-to-use          # 설치된 스킬 전체 안내부터

/common:init                # 설치된 하네스 중에서 선택지 제시
/common:start-workflow      # 〃
```

대상을 알고 있으면 플래그로 바로 지정한다 — `--be` · `--fe` · `--fs` · `--mm` · `--hd`:

```bash
/common:init --be
/common:start-workflow --be

/common:init --fe
/common:start-workflow --fe
```

풀스택은 백엔드·프론트엔드 profile을 각각 만든 뒤 `--fs` 로 실행한다:

```bash
/common:init --be
/common:init --fe
/common:start-workflow --fs
```

`fs-harness` 는 `be-harness` 와 `fe-harness` 가 모두 설치되어 있어야 한다.

기존처럼 하네스를 직접 호출해도 동작은 동일하다 (`/be-harness:start-workflow`).
라우터 대상과 공통 규약은 [`common/ROUTING.md`](./common/ROUTING.md) 참조.

## 디렉터리 구조

```text
.
├── common/                 # 모든 하네스에서 공용으로 쓰는 범용 스킬 (먼저 설치)
├── be-harness/             # 범용 백엔드 Claude Code 플러그인
├── fe-harness/             # 범용 프론트엔드 Claude Code 플러그인
├── fs-harness/             # 풀스택 Claude Code 오케스트레이터
├── minmos-harness/         # Post-Math 백엔드 Claude Code 플러그인
├── hyeondongs-harness/     # hyeondongs 전용 세팅/진단 + 풀스택 오케스트레이터
├── docs/                   # 저장소 차원 문서 (스킬 작성 표준 등)
└── .claude-plugin/         # Claude Code marketplace 정의
```

## 참고 문서

- `docs/skill-authoring.md`: 스킬 작성 표준 (모든 플러그인 SKILL.md의 기준)
- `common/README.md`: 공용 스킬 모음 (`/common:doc-gen` 등)
- `be-harness/README.md`: 범용 백엔드 하네스
- `fe-harness/README.md`: 범용 프론트엔드 하네스
- `fs-harness/README.md`: 풀스택 오케스트레이터
- `minmos-harness/README.md`: Post-Math 백엔드 하네스
- `hyeondongs-harness/README.md`: hyeondongs 전용 부속 하네스 (세팅/진단 + 풀스택)
