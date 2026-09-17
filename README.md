# harness-plugins

개발 워크플로우 자동화를 위한 Claude Code 하네스 모음.

Technical Spec 작성, Plan 리뷰, 테스트 선작성(TDD), 구현, 품질 루프, 커밋/PR까지 반복되는 개발 절차를 플러그인과 스킬로 묶어 제공한다.

`start-workflow` 는 **Spec의 추적 ID(`AC`/`EC`/`RC`)를 근거로 실패 테스트를 먼저 고정한 뒤 구현한다.** 테스트 범위는 Spec이 상한이며, 구현 직전에 수집한 회귀 baseline과 대조해 이번 변경이 깨뜨린 것과 원래 깨져 있던 것을 구분한다. TDD가 맞지 않는 상황(`--no-tdd`, 테스트 인프라 부재 등)에서는 자동으로 기존 흐름으로 되돌아간다.

Spec에는 대상·기준 문서·완료 조건·승인 범위를 짧은 작업 계약으로 남긴다. 같은 승인과 결정을 인계하고, 필수 검증 이후 추가 리뷰는 새 근거가 있을 때 수행한다. 테스트 기대값과 역할별 권한 조건은 현재 요구에서 정한다. 공통 기준은 [작업 계약과 실행 원칙](be-harness/skills/start-workflow/references/execution-policy.md)에 있으며 BE/FE/common 패키지에 동일하게 포함된다.

## 2026-09-17 단순화 반론 검증

BE 1.5.8 / FE 1.4.7. 3/4 찬성의 즉시 적용을 없애고 실제 소수 반론을 독립 Arbiter가 검토한다. 만장일치는 기존 DA를 유지하며, 모든 승인은 반론 해소 여부와 코드·테스트 근거를 요구한다. 미해소·근거 부족은 보류하고 잘못된 결과는 기존 재시도 상한을 따른다. 단일 writer·루프 상한·최종 검증 계약은 유지한다.

## 2026-09-16 리뷰 근거 보강

BE 1.5.7 / common 0.14.5 / FE 공통 자산 1.4.6 / minmos 2.5.3. 읽기 전용 scope 리뷰에 실제 diff와 검사 로그를 전달하고, 근거 미완료·staged 내용 변경·artifact 손상은 마감에서 검사한다. 최초/보완 결과와 지적의 반영·보류·범위 제외를 구분해 남긴다. FE 필수 리뷰 단계는 변경하지 않고 공통 자산만 동기화했다. 상세 계약은 [review-evidence.md](be-harness/skills/start-workflow/references/review-evidence.md)에 있다.

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

## 호스트 지원 범위

| 실행 환경 | 이 저장소에서 제공하는 경계 | 실행 전 확인 |
|---|---|---|
| Claude Code plugin | common/BE/FE/overlay 스킬과 `agents/`, work-log MCP | `.claude-plugin` 설치, 실제 scoped agent/skill 이름과 도구 목록 |
| Codex native work-log | `work-log/.codex-plugin/plugin.json`, skills와 stdio MCP | 세션의 work-log 스킬·MCP 도구 발견, Node/Python과 vault 설정 |
| Codex에 별도 설치한 harness skills | 이 저장소의 Claude agent frontmatter가 Codex 권한을 설정하지는 않음 | 세션에 제공된 실제 스킬명·도구·host adapter를 확인. 없는 실행 기능은 BLOCKED |
| Claude workflow에서 Codex CLI 위임 | `codexMode` 및 슬롯 설정을 따른 별도 프로세스 | 활성 모드에서만 CLI/provider/model 확인, writer 격리·종료 확인 계약 적용 |

Codex의 스킬/MCP 패키징은 [공식 OpenAI plugin 문서](https://learn.chatgpt.com/docs/plugins)와 [skill 문서](https://learn.chatgpt.com/docs/build-skills)를 따른다. 별도 배포판의 이름을 이 저장소 이름으로 바꿔 호출하지 않는다. 사용법은 현재 세션 metadata에서 수집한다.

Claude agent는 스킬의 `allowed-tools`와 달리 `tools`/`disallowedTools`를 사용한다. 읽기 전용 리뷰어는 Read/Glob/Grep만 허용한다. Bash를 가진 구현·PR agent는 파일 쓰기도 가능하며 읽기 전용으로 분류하지 않는다. [Claude subagent 계약](https://code.claude.com/docs/en/sub-agents#supported-frontmatter-fields)

검증한 호스트 버전, 실제 로드된 도구, 재현 절차와 한계는 [호스트 검증 계약](docs/host-contract.md)에 기록한다. doctor는 활성 framework/runner/codexMode의 의존성만 검사하며 진단 중 설치·다운로드하지 않는다. 설치가 필요한 경우 누락 상태와 별도 설치 명령을 보고한다.

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
| **common** | 진입점 | 워크플로우 단일 진입점(`start-workflow` — 도메인 판정 + 풀스택 오케스트레이션), 커밋/Push/PR(`commit`, `commit-push`, `commit-pr`, `commit-hard-push`, `merge`), base 최신화 + 버전 범프(`sync-base`), 추론 태그 해소(`resolve-assumption`), 문서 생성(`doc-gen`) |
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

공통 플래그: `--reflect`(성찰 Phase 실행 — 기본 off), `--tier standard`(검증 티어 상향 강제 — 기본은 Spec 점수로 light/standard 자동 판정), `--codex none|mix|max`(Codex 사용 모드 — profile `codexMode`에 저장, 기본 mix. `max`는 서브에이전트까지 Codex 슬롯 모델로 위임해 Claude 토큰 최소화), `--codex-models {슬롯}={provider}/{model}[@{effort}]`(슬롯 `review`·`explore`·`judge`·`write`별 위임 모델 — profile `codexModels` 저장. GLM·Kimi 등 Codex `[model_providers.<id>]`로 정의한 provider 사용 가능), `--hard`, `--no-tdd`. 워크플로우 종료 시 md Workflow Report가 profile `reportDir`에 아카이브된다.

워크플로우 외 스킬은 하네스를 직접 호출한다:

```bash
/be-harness:init          /fe-harness:init          # profile 생성 (최초 1회)
/be-harness:config        /fe-harness:config        # profile 값 조회·수정
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

## 저장소 검증

`bash scripts/verify.sh`는 구조·manifest/marketplace·agent 계약·활성 참조·Phase/override·사본 일치, Python 전체 테스트, work-log stdio/Node, 실제 Chromium 오프라인 문서, FE build/type/Vitest/Jest, loopback gRPC를 순서대로 검사한다. 필요한 의존성이 없으면 성공으로 skip하지 않는다. 준비 단계와 다운로드는 [.github/workflows/verify.yml](.github/workflows/verify.yml)의 한 `Required harness checks` job에 모았다. 검증 스크립트 자체는 설치하지 않는다.

로컬 실행 전 `tests/requirements.txt`, 두 npm lockfile, fixture Go module, PostgreSQL/Chromium runtime을 준비한다. PostgreSQL은 별도 임시 cluster/socket만 쓰며 업무 DB 설정을 읽지 않는다. 호스트 loader는 설치 버전에 따라 명시적으로 수행하는 별도 로컬 mock probe다.

구조 검사는 제품별 현재 manifest 버전을 기준으로 같은 제품의 package/Codex manifest만 대조한다. 제품 간 버전은 독립적이다. 과거 감사 문서와 community-feedback은 활성 지시 검증에서 제외하며, 두 migration 표는 이전 열만 제외하고 현재 호출 열은 검사한다. 템플릿 placeholder 링크 예외는 `scripts/check_contracts.py`에 파일과 값 단위로 명시한다. 구조 통과는 실행 fixture 통과와 함께 판단한다.

GitHub 보호 브랜치의 필수 check 설정은 별도 저장소 설정이다. 이 변경은 해당 설정을 원격 수정하지 않는다.
