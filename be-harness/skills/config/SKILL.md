---
name: config
description: "be-harness project profile(.claude/be-harness.local.md)의 설정 값을 조회하고 키 단위로 수정한다. '프로필 설정 확인해줘', '설정 값 바꿔줘', '{키} 값 뭐야', '{키}를 {값}으로 바꿔줘' 요청 시, init 재실행 없이 값 하나만 보거나 고칠 때 사용. 파일 생성·환경 진단은 하지 않는다 (init·doctor 담당)."
allowed-tools: Read, Bash, AskUserQuestion
user-invocable: true
argument-hint: "[{키} | {키}={값} …]"
---

> **Project Overrides**: 실행 전 `.claude/be-harness/common.md`와 `.claude/be-harness/skills/config.md`를 Read.
> 존재하면 추가 규칙/예외로 흡수하고 충돌 시 오버라이드가 우선한다. 상세 규약: 플러그인 루트 `OVERRIDES.md`.



# be-harness Config

설정 조회·배치 수정을 `assets/profile.py`로 수행한다. Python 3.9+와 POSIX가 필요하다. 파일 생성은 init, 환경 진단은 doctor가 담당한다.

- `{PLUGIN_ROOT}`는 **현재 실행 중인 설치 플러그인**의 루트, `{CWD}`는 대상 프로젝트 루트다. 다른 캐시 버전을 추정하지 않는다.
- `.claude/be-harness.local.md`만 수정한다. 본문·오버라이드·레거시 JSON·워크플로우 상태·Codex 인증 파일은 수정하지 않는다.
- 모델 기본값·슬롯 규약은 `../start-workflow/references/codex-mode.md` §1·§2.1을 읽는다. `review`·`explore`·`judge`·`write` 생략 슬롯은 그 표의 기본값이다. 모델 리터럴을 helper나 다른 문서에 복제하지 않는다.
- 사용자가 설정 변경을 요청했으면 아래 preview 검증 뒤 바로 apply한다. 추가 승인을 반복해서 요청하지 않는다. 인자 없는 조회는 조회만 완료한다.

## 키

`PROFILE.md`의 키·허용값이 사용자 계약이고 helper `schema --domain be`이 실행 검증을 담당한다. 두 집합은 CI에서 일치 여부를 검사한다.

<!-- config:keys-begin — scripts/check-plugins.sh §7 parity 대상 -->
| 타입 | 키 | 값 규칙 |
|------|----|--------|
| enum | `preset` (go \| node \| custom) · `language` (ko \| en) · `codexMode` (none \| mix \| max) | trim 후 exact — 빈 값 무효 |
| bool | `e2eEnabled` | true \| false exact |
| string | `buildCommand` `testCommand` `lintCommand` `typeCheckCommand` `makeTestCommand` `runServerCommand` `serverUrl` `apiDocsPath` `e2eLockDir` `reportDir` `mainBranch` `featureBranchPrefix` `hotfixBranchPrefix` `commitCoAuthor` | 자유 문자열 — 빈 문자열 유효 |
| array | `sourceDirs` `testDirs` `commitPrefixes` `projectConventions` | JSON 문자열 배열 (원소 안의 쉼표 허용) — 빈 배열 유효 |
| block | `codexModels` | codex-mode.md §2.1 compact — 슬롯별 레코드 |
<!-- config:keys-end -->

## 조회

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/config/assets/profile.py" resolve --domain be --cwd "{CWD}"
```

결과의 `values`(설정 값)·`sources`(profile/legacy/preset/default/감지 출처)·`commands`(실행 시 fallback을 포함한 명령)·`diagnostics`를 사용해 `키 | 값 | 출처 | 비고` 표를 출력한다. 명시적 빈 값은 부재와 다르므로 숨기지 않는다. BE는 명령의 명시적 빈 값을 SKIP으로 유지한다. FE는 선택 runner의 fallback을 `commands`에 별도로 표시하며 `typescript:false` 타입 검사와 `e2eRunner:none` E2E는 SKIP이다.

FE는 primary profile이 있으면 레거시 파일을 읽지 않는다. primary가 없을 때만 `.hyeondong-config.json`을 읽으며 레거시는 읽기 전용이다. 잘못된 상위 profile은 하위 파일로 fallback하지 않는다. 쓰기 대상이 없으면 `BLOCKED:NO_PROFILE`과 실제 설치된 init 호출명을 안내한다.

## 배치 수정

1. 사용자 요청을 **타입이 있는 JSON 객체**로 변환한다. 명령 문자열은 쉘 코드로 보간하지 않는다. 알 수 없는 키·동일 키 중복·타입 오류는 전체 배치를 거부한다. 자연어에서 값이 결정되지 않는 경우에만 짧게 확인한다.
2. JSON을 **따옴표로 감싼 heredoc delimiter**로 stdin에 전달해 `edit` preview를 실행한다. delimiter가 입력 본문에 단독 줄로 나오지 않는지 확인한다. 전달할 수 없으면 실행별 0600 임시 JSON 파일을 만들고 `--changes`로 지정한 뒤 자기 파일만 정리한다.
3. helper 결과가 `PREVIEW`이고 의도한 키의 값만 바뀌었는지 확인한다. `sha256_before`와 **동일 JSON**으로 `--apply --expected-sha256`을 호출한다. preview는 사용자 확인을 위한 새 승인 단계가 아니다.
4. `STALE_PROFILE`이면 최신 파일을 다시 읽고 preview를 새로 만든다. 오류를 수동 전체 덮어쓰기로 우회하지 않는다.

예시(BE/FE 공통 키):

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/config/assets/profile.py" edit --domain be --cwd "{CWD}" <<'HARNESS_PROFILE_JSON'
{"language":"en","testCommand":"npm test","sourceDirs":["src/","path,with,commas/"]}
HARNESS_PROFILE_JSON
```

apply는 같은 명령에 `--apply --expected-sha256 "{PREVIEW_SHA256}"`만 추가한다. 결과 `changed:false`이면 파일을 쓰지 않는다.

`codexModels` 변경은 슬롯 객체를 통째로 병합한다. 예: `{"codexModels":{"review":{"provider":"custom","model":"vendor/model","effort":"high"},"write":null}}`. `null`은 해당 슬롯 삭제(기본값 사용)이며 다른 슬롯의 필드를 상속하지 않는다. `tiered`는 review에만 허용한다. provider·model 패턴과 effort 허용값은 codex-mode 계약을 따른다. CLI compact 입력은 먼저 이 JSON 형태로 변환한다.

## 보존 범위와 실패

- frontmatter의 root key, 한 줄 scalar(bare/단일·이중 따옴표), 한 줄 flow 배열, 연속 block 배열, 연속 compact 모델 슬롯만 지원한다. 이중 따옴표는 JSON escape 범위다. YAML anchor/tag·여러 줄 flow·block scalar·중간 주석으로 끊긴 자식 목록은 대상 키 수정 시 거부한다. 따옴표 root key와 root 중복은 전체 수정을 차단한다.
- 변경 없는 값·다른 키·본문은 바이트 그대로 보존한다. 혼합 LF/CRLF, 줄별 EOL, 기존 따옴표 형태, 구분 공백, 꼬리 주석을 보존한다. 배열 원소의 쉼표는 문자열로 지원한다.
- 기존 root가 없을 때 첫 `# key:`만 활성화한다. 뒤의 예시 주석은 보존한다. 삭제할 자식/슬롯/root에 주석이 있으면 전체 배치를 거부한다.
- 여러 키를 메모리에서 전부 검증한 뒤 같은 디렉터리 임시 파일을 atomic replace한다. 파일 mode/소유자를 보존한다. 동일 helper의 동시 쓰기는 inode lock·hash로 충돌을 보고한다. 이 로컬 편집기는 임의의 비협조적 동일 사용자 파일 교체를 방어하는 보안 경계가 아니다. symlink profile은 조회만 지원한다.
- exit 2의 `BLOCKED` 오류는 입력·구조·I/O 사유와 함께 보고한다. helper는 파일을 생성하지 않고, 지원하지 않는 YAML을 임의 재직렬화하지 않는다.

## 보고

`키 | 이전 | 이후 | 상태` 표와 변경 수를 출력한다. 부분 성공으로 보고하지 않는다. `codexMode`/`codexModels` 변경 시 “진행 중·재개 워크플로우는 저장된 상태 값을 유지하며 새 값은 다음 실행부터 적용”을 알린다. 필요 시 세션 메타데이터에서 찾은 실제 doctor 호출명을 안내한다.
