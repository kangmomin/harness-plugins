---
name: doctor
description: "fe-harness 플러그인의 모든 의존성 상태를 한 번에 진단한다. 워크플로우가 SKIP을 내거나 설정이 의심될 때, '환경 진단해줘' 요청 시 사용."
allowed-tools: Read, Glob, Grep, Bash
user-invocable: true
---

> **Project Overrides**: 실행 전 `.claude/fe-harness/common.md`와 `.claude/fe-harness/skills/doctor.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.
> **Profile**: `.claude/fe-harness.local.md` 가 없으면 `.hyeondong-config.json` 을 profile로 사용한다 (레거시 호환, 읽기 전용). 탐색 순서·필드 매핑: 플러그인 루트 `PROFILE.md`.



# fe-harness Doctor

실효 profile과 **활성 기능**에 필요한 의존성을 확인한다. 진단은 다운로드·빌드·테스트·설치 명령을 실행하지 않는다. 실제 검증 PASS와 실행 파일의 존재를 구분한다.

## 실행

1. 세션의 실제 호스트(Claude Code / Codex)를 확인한다. 설치 디렉터리 이름으로 호스트를 추정하지 않는다.
2. 아래 helper를 실행한다. `{PLUGIN_ROOT}`는 현재 설치된 fe-harness 루트다.

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/config/assets/doctor.py" --domain fe --cwd "{CWD}" --host "{claude|codex|unknown}"
```

3. `profile.values`·`profile.sources`·`profile.commands`와 `checks`를 표로 출력한다. primary가 없으면 유효 legacy/프리셋 감지를 표시하며 파일 부재 하나로 진단을 종료하지 않는다. invalid priority profile은 `BLOCKED`로 보고하고 다른 설정으로 넘어가지 않는다.
4. 나머지 Git·컨벤션·오버라이드 항목을 읽기 전용으로 확인하고 helper 결과에 추가한다. Git 저장소와 설정된 mainBranch의 실제 ref를 확인한다. 경로는 인자로 전달하고 shell 코드로 보간하지 않는다. projectConventions의 누락 파일은 선택 WARN, 비어 있는 설정은 그대로 표시한다.

## 활성 검사 표

| 조건 | 검사 | 비활성/불명 |
|------|------|------------|
| Go preset | Go 실행 파일·실효 명령 | Node 도구를 필수로 만들지 않음 |
| Node/FE | Node 버전·선택 packageManager·package.json | package manager는 존재만 검사(corepack bootstrap도 실행하지 않음) |
| framework nextjs/vite/cra/nuxt | 선택 프레임워크의 로컬 의존성 | 알 수 없는 조합 UNKNOWN, 생성 전 확인 |
| typescript true | TypeScript·tsconfig | false는 SKIP, 미설정은 UNKNOWN |
| testRunner jest/vitest | 선택한 한 러너 | 다른 러너 설정·패키지 미존재는 실패 아님 |
| e2eRunner cypress/playwright | 선택한 한 러너 | none은 전부 SKIP; Cypress에 Playwright 검사 금지 |
| storybook true | Storybook 설정 | false/미설정은 SKIP |
| custom lintCommand | 원문 명령의 정적 실행 가능성 | ESLint를 필수로 가정하지 않음 |
| codexMode none | Codex·provider 검사 SKIP | 모델·MCP 호출 없음 |
| Codex 호스트 mix/max | 현재 native collaboration 기능 | 외부 Codex MCP는 native 실행의 필수 조건 아님 |
| Claude 호스트 mix/max | 세션에서 실제 발견한 delegation 도구 | 없으면 WARN과 문서화된 host fallback |

`AVAILABLE`은 실행 파일이 있다는 뜻이다. 복합 shell 명령은 `UNVERIFIED`로 남긴다. 실제 빌드·타입·lint·unit 결과는 해당 검증 단계가 기록한다. doctor는 `npx`, `npm exec`, `pnpm dlx`, 브라우저 install 등을 실행하지 않는다. 보고서에 **downloads: none / validation_executed: false**를 포함한다.

PnP 설치는 node_modules 부재를 단정하지 않고 UNKNOWN으로 표시한다. 실제 설치된 package API/프로젝트 offline resolver로 후속 확인한다. Playwright는 설치된 package의 `browserType.executablePath()`가 가리키는 파일의 존재만 검사하고, Cypress binary는 설치된 러너의 읽기 전용 경로 조회가 가능할 때 확인한다. 브라우저 실행까지 확인하지 않았다면 `UNVERIFIED`를 유지한다. 의존성 설치 요청은 진단과 분리해 제시한다.

## 호스트·provider

도구 이름은 고정 MCP suffix로 추정하지 않는다. 현재 세션 메타데이터에서 설명·인자 계약이 맞는 Codex delegation 도구를 찾아 실제 이름을 보존한다. 발견 목록을 helper에 전달하려면 실행별 임시 JSON 배열 `[{"capability":"codex-delegation","name":"실제 도구 이름"}]`를 `--tools-file`로 지정한다. 이 표시는 **DISCOVERED**이며 host 로드/호출 성공의 증거는 아니다. 자기 임시 파일만 정리한다.

`codexMode`가 none이 아니고 `codexModels`의 `review`·`explore`·`judge`·`write`에 외부 provider가 있을 때만 codex-mode.md §2.1·§7 계약을 점검한다. 무효 슬롯은 `INVALID_SLOT`로 표시하고 유효 형제 슬롯은 유지한다. provider 테이블·인증·wire_api는 호스트가 지원하는 TOML parser로 읽고 키·URL·헤더 값은 출력하지 않는다. 값 없이 `NO_TABLE`·`ENV_UNSET`·`BEARER_TOKEN`·`WIRE_API`·`PROJECT_ONLY`만 보고한다. provider config를 읽을 기능이 없으면 UNKNOWN으로 남긴다. 정규식 grep을 TOML 파싱 성공으로 취급하지 않는다.

## 보고

`항목 | 상태 | 근거/출처 | 필수 여부` 표, 해결할 항목, 실제 검증 여부를 출력한다. `OK/AVAILABLE`, `LEGACY`, `SKIP`, `WARN/UNVERIFIED`, `MISSING/INVALID/UNKNOWN`을 합치지 않는다. 안내 호출명은 세션에 실제 설치된 init/config/doctor 스킬 메타데이터에서 찾는다. 레거시는 읽기 전용이며 새 primary profile 생성은 init이 담당한다.
