# common

여러 harness(be/fe/fs/특화 하네스)에서 공통으로 사용하는 스킬 모음.

`be-harness`, `fe-harness`, `fs-harness`, `minmos-harness`, `hyeondongs-harness` 등 어떤 하네스를 쓰더라도 **먼저 설치되어야 하는 베이스 플러그인**이다. 도메인 종속성이 없는 범용 스킬만 둔다.

## 설치

```bash
/plugin marketplace add kangmomin/mimo-s-harness

# 다른 하네스를 쓰기 전에 먼저 설치
/plugin install common@harness-plugins
```

이후 원하는 하네스를 설치한다.

```bash
/plugin install be-harness@harness-plugins
/plugin install fe-harness@harness-plugins
# ...
```

## 스킬 목록

| 스킬 | 호출 | 설명 |
|------|------|------|
| **doc-gen** | `/common:doc-gen` | 지정한 범위(파일/디렉토리/glob/PR/commit range)를 분석해 인터랙션·다이어그램이 포함된 단일 파일 문서(`-md` 또는 `-html`)로 정리 |

## 사용 예시

```bash
# 현재 작업 디렉토리에서 시작 — 단계적 질문으로 범위 확정 후 md 출력
/common:doc-gen -md

# HTML 모드, src/auth 범위
/common:doc-gen -html src/auth

# PR 범위 요약
/common:doc-gen -md PR#42
```

자세한 동작 흐름은 `skills/doc-gen/SKILL.md` 참고.

## Project Overrides

다른 하네스와 동일한 오버라이드 규약을 따른다. 자세한 내용은 `OVERRIDES.md`.

```
.claude/common/
├── common.md                   # 플러그인 공통 오버라이드
└── skills/
    └── doc-gen.md              # /common:doc-gen 오버라이드
```
