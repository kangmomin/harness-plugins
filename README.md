# harness-plugins

개발 워크플로우 자동화를 위한 Claude Code 하네스 모음.

Technical Spec 작성, Plan 리뷰, 구현, 품질 루프, 커밋/PR까지 반복되는 개발 절차를 플러그인과 스킬로 묶어 제공한다.

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
| **common** | 모든 하네스 베이스 | 여러 하네스 공용 스킬. `/common:doc-gen` 등 도메인 독립 스킬. 다른 하네스 설치 전에 먼저 설치 |
| **be-harness** | 범용 백엔드 | Go/Node 프리셋과 project profile 기반의 Spec→Plan→구현→품질 루프→PR 워크플로우 |
| **fe-harness** | 범용 프론트엔드 | React/Next.js 중심의 컴포넌트 생성, lint/a11y, 단위/E2E 테스트, PR 워크플로우 |
| **fs-harness** | 풀스택 | BE/FE 하네스를 병렬로 사용해 계약 정의, 교차 리뷰, 통합 검증, 단일 PR까지 오케스트레이션 |
| **minmos-harness** | Post-Math 백엔드 | 커밋/PR, 컨벤션 검사, Feature Spec 생성, E2E 테스트(REST+gRPC+PubSub), Apidog 스키마 생성 |
| **hyeondongs-harness** | React 프론트엔드 | 컴포넌트 생성, 커밋/PR, 단위/E2E 테스트, 코드 품질 검사(ESLint, a11y) |

## 빠른 시작

### 백엔드 프로젝트

```bash
/be-harness:init
/be-harness:start-workflow
```

### 프론트엔드 프로젝트

```bash
/fe-harness:init
/fe-harness:start-workflow
```

### 풀스택 프로젝트

```bash
/be-harness:init
/fe-harness:init
/fs-harness:start-workflow
```

`fs-harness` 는 `be-harness` 와 `fe-harness` 가 모두 설치되어 있어야 한다.

## 디렉터리 구조

```text
.
├── common/                 # 모든 하네스에서 공용으로 쓰는 범용 스킬 (먼저 설치)
├── be-harness/             # 범용 백엔드 Claude Code 플러그인
├── fe-harness/             # 범용 프론트엔드 Claude Code 플러그인
├── fs-harness/             # 풀스택 Claude Code 오케스트레이터
├── minmos-harness/         # Post-Math 백엔드 Claude Code 플러그인
├── hyeondongs-harness/     # 프로젝트 특화 프론트엔드 Claude Code 플러그인
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
- `hyeondongs-harness/README.md`: 프로젝트 특화 프론트엔드 하네스
