---
name: stt-fix
description: "회의록 STT 전사(.txt)의 오인식을 단어장 기준으로 보정해 보정본(.md)과 정리본(.txt)을 만들고, 애매한 항목을 모아 사용자에게 확인한 뒤 결과를 단어장에 반영한다. '회의록 보정해줘', 'STT 오인식 해소', '전사 정리해줘', '회의록 단어장 만들어줘' 요청 시 사용."
user-invocable: true
allowed-tools: Bash, Read, Write, Grep, AskUserQuestion
argument-hint: <원본 .txt 경로|파일명> [--dict <단어장 경로>] [--new-dict [<경로>]] [--project <키>] [--shared-dict <경로>]... [--no-ask] [--no-txt]
---

# 회의록 STT 보정

음성인식(STT) 전사의 오인식을 단어장과 문맥으로 보정한다. 타임스탬프·화자·턴 수는 그대로 두고 **의미가 바뀌는 오인식만** 고치며,
확신이 없는 항목은 마커로 남겨 사용자에게 모아서 묻고, 그 답을 단어장에 쌓아 다음 보정의 정확도를 올린다.

## Language Rule

유저와의 모든 대화는 **한국어**로 진행한다.

Claude Code에서는 `/work-log:stt-fix`, Codex에서는 `$work-log:stt-fix` 로 명시 호출할 수 있다.
MCP 툴의 전체 이름은 클라이언트마다 다르므로 `wiki_` 로 시작하는 기본 이름을 기준으로 찾는다.

## 플레이스홀더

- `{HELPER}` = `<plugin-root>/skills/stt-fix/assets/stt_fix.py` (`<plugin-root>` 는 이 SKILL.md 의 `../..`). 항상 `python3 -I -B {HELPER} apply …` 로 실행한다
- `{SCRATCH}` = 호스트가 제공하는 세션 scratchpad 디렉터리. 없으면 `mktemp -d`. 규칙·결정 JSON, 중간 본문, 조각 파일, 로그를 둔다. **`Write` 도구는 `{SCRATCH}` 전용**이며 vault에는 쓰지 않는다
- `{ROOT}` = `wiki_status.root` 의 **canonical 절대경로**(`realpath` 로 확인 — `/work-log:edit` Step 0 의 비교 기준과 같다. 헬퍼는 root 를 다시 해석하지 않고 경로의 모든 구성 요소를 심볼릭 링크를 따라가지 않고 열므로, 링크가 섞인 경로를 넘기면 `outside_root` 로 거부된다) · `{LAYOUT}` = `{ROOT}/projects/` 가 있는 분류형 여부
- `{SRC}` = 원본 전사의 **`{ROOT}` 상대 경로**(Step 1 에서 절대경로를 확정한 뒤 `{ROOT}/` 를 떼어 만든다. 헬퍼에는 항상 `{ROOT}/{SRC}` 로 넘긴다) · `{SRC_SHA}` = `probe.json.source_sha256` 앞 12자리 · `{SRC_STEM}` = 원본 파일명(확장자 제외)
- `{PROJECT_DIR}` = 분류형에서 원본을 소유한 프로젝트 폴더의 `{ROOT}` 상대 경로 — `{SRC}` 의 상위 중 분류 폴더(`meeting`·`history`·`docs`·`data`) 바로 위(예: `projects/IB-Maker`, `projects/90_personal/frame`) · `{PROJECT}` = 그 폴더 이름(비분류형은 선택) · `{DATE6}` = 원본 파일명 선두 `YYMMDD`(없으면 오늘)
- `{DICT_MODE}` = `existing | new | none` · `{DICT}` = 단어장 `{ROOT}` 상대 경로. 기본 신설 경로 = `{PROJECT_DIR}/docs/<{PROJECT} 소문자>-stt-단어사전-note.md`
- `{OUT_MD}` = 프로젝트에 기존 `*-보정.md` 가 있으면 그 폴더, 없으면 `{PROJECT_DIR}/history/` 아래 `{DATE6}-<kebab 회의명>-보정.md`
- `{OUT_TXT}` = 원본과 같은 폴더의 `{SRC_STEM} 보정.txt`
- `{BODY_SHA}` = `final.json.body_sha256` 앞 8자리 (최종 보정 본문의 해시 — 같은 원본에 다른 답을 하면 달라진다)
- `{DICT_SECTION_ID}` = `{DATE6}-{SRC_SHA}-{BODY_SHA}` (단어장 증분 섹션 제목에 포함. 같은 원본·같은 결정의 재시도는 생략하고, 답이 달라진 재보정은 새 섹션으로 쌓는 멱등 키)
- `{MAX_RULE_RETRY}` = 3 (Step 4 규칙·Step 7 결정 JSON 재실행 상한) · `{MAX_QA_ROUNDS}` = 20 · `{QA_BATCH}` = 4 (AskUserQuestion 1회 최대 질문 수) · `{MAX_WRITE_RETRY}` = 2 (`wiki_sync` 재시도·단어장 append 해시 충돌·산출물 파일명 충돌·단어장 create 충돌 재시도 상한)

모든 명령의 경로 인자는 공백·한글을 포함할 수 있으므로 **항상 큰따옴표로 감싼다**(`--assemble` 의 두 경로도 하나의 따옴표 인자로).

## Flags

| 플래그 | 동작 |
|--------|------|
| `--dict <경로>` | `{DICT_MODE}=existing`. 경로가 없으면 `BLOCKED:DICT_NOT_FOUND` → ① 그 경로에 신설(`new`) ② 다른 경로 입력 ③ 사전 없이 진행(`none`) |
| `--new-dict [<경로>]` | `{DICT_MODE}=new`. 경로 생략 시 기본 신설 경로. Step 2의 중복 검색을 거친다. 대상이 이미 있으면 `BLOCKED:DICT_EXISTS` → ① 기존 사용(`existing`) ② 다른 경로에 신설 ③ 중단 |
| `--dict` + `--new-dict` | `BLOCKED:DICT_CONFLICT` → ① `--dict` 유지 ② `--new-dict` 유지 ③ 중단 |
| `--project <키>` | `{PROJECT}` 명시. 원본 경로에서 추론되지 않을 때 |
| `--shared-dict <경로>` (반복 가능) | 인명·서비스 코드·도구명 재사용용 타 프로젝트 사전. 미지정이면 Step 2에서 후보를 찾아 사용 여부를 묻는다 |
| `--no-ask` | Step 6 생략, 마커 전부 유지 → 질문 단계 `SKIPPED:NO_ASK` |
| `--no-txt` | 정리본 `.txt` 생략 → `SKIPPED:NO_TXT` |

## 전제 조건

- **work-log MCP**: `wiki_status` 가 응답하고 `safeIO.available:true`. 쓰기 전에 **`/work-log:edit` 의 root·서버 버전 확인 절차(Step 0)를 그대로 수행**한다(복붙하지 않고 위임). 미연결 → `BLOCKED:MCP_UNAVAILABLE` → ① `/work-log:doctor` 실행 후 재시도 ② 중단
- **레이아웃 판정은 입력 탐색보다 먼저** 한다. 비분류형(flat·독립 root)이면 Step 1의 파일명 검색 범위는 `{ROOT}` 전체, `{PROJECT}` 는 선택이며 `{DICT}`·`{OUT_MD}` 기본값을 쓰지 않고 ① 원본과 같은 폴더 ② 직접 입력 ③ 중단 으로 묻는다
- **Python 3.9+**: `python3 --version` 실패 → `BLOCKED:PYTHON_UNAVAILABLE` → ① 설치 후 재시도 ② 중단
- 원본 `.txt` 와 단어장은 **Read 도구**(`{ROOT}/…` 절대경로)로 읽는다. `.txt` 는 인덱스 대상이 아니고, 단어장은 `wiki_read` 의 `truncated` 로는 같은 섹션의 잔여를 이어 읽을 수 없어 최신 append(사용자 확인·반례)를 놓칠 수 있다
- **AskUserQuestion 이 없는 클라이언트**(Codex 등): ① 세션 도구 목록에 없음을 감지하면 → ② 같은 선택지를 번호 목록 텍스트로 묻고 텍스트 답을 받는다 → ③ "선택형 UI가 없어 번호로 답해 주세요"를 고지한다

## Step 1: 입력 확정

1. 인자가 경로면 절대경로로 해석한다(상대 경로는 현재 작업 디렉터리 기준). 파일명 조각이면 Bash `find` 로 찾는다 — 분류형은 `find "{ROOT}/projects" -path '*/meeting/*' -name '*<인자>*.txt'`(`projects/90_personal/<키>/meeting` 같은 버킷 하위 포함), 비분류형은 `{ROOT}` 전체. `보정.txt` 와 `backup/` 은 제외.
   0건 → `BLOCKED:SRC_NOT_FOUND` → ① 경로 직접 입력 ② 중단. 2건 이상 → 번호 선택지로 하나를 고른다.
   확정한 절대경로가 `{ROOT}` 밖이면 `BLOCKED:SRC_NOT_FOUND` → ① vault 안 경로 다시 입력 ② 중단. 안이면 `{ROOT}/` 를 떼어 `{SRC}` 로 쓰고(`{ROOT}/{SRC}` 가 다시 원본 절대경로가 되어야 한다), 분류형이면 `{SRC}` 에서 `{PROJECT_DIR}`·`{PROJECT}` 를 정한다. 분류 폴더가 없는 경로(예: `projects/<키>/x.txt`)는 `--project` 또는 ① 프로젝트 폴더 직접 입력 ② 중단 으로 묻는다.
2. 빈 규칙으로 헬퍼를 1회 실행해 구조를 읽는다:
   ```bash
   python3 -I -B "{HELPER}" apply --root "{ROOT}" --src "{ROOT}/{SRC}" --log "{SCRATCH}/probe.json"
   ```
   `probe.json` 의 `turns`·`header_format`(`mm:ss`/`h:mm:ss`/`mixed`/`format_unknown`)·`duplicate_times`·`preamble`·`source_sha256` 을 기록한다.
   - `preamble` 이 `[보정본]` 로 시작 → 이미 보정된 파일이다. `BLOCKED:SRC_ALREADY_CORRECTED` → ① 같은 폴더 `backup/{SRC_STEM}.txt.bak` 을 원본으로 ② 그대로 진행 ③ 중단
   - `format_unknown`(타임스탬프 헤더 없음) → ① 전체를 1턴으로 보정(화자 추정 불가 경고를 보정본에 기록) ② 중단
   - `duplicate_times` 가 있으면 보정본 메모에 적고, Step 4의 턴 지정은 반드시 **턴 서수**로 한다
3. **기존 보정본 중복 검색**: `wiki_resolve "{SRC_STEM}"` 과 `wiki_resolve "{DATE6} 보정"` 결과의 후보 중 `wiki_read token_budget:400` 으로 머리만 읽어 같은 `{SRC}` 또는 `{SRC_SHA}` 가 적힌 문서가 있으면 → ① 기존 보정본 유지(중단) ② 새 버전 파일명(`…-보정-v2.md`)으로 진행 ③ 중단.
   `INDEX_*` 오류는 `/work-log:sync` 또는 `/work-log:doctor` 안내 후 재검색한다. 검색 실패를 중복 없음으로 간주하지 않는다.

## Step 2: 단어장 결정

우선순위: `--dict` > `--new-dict` > 자동 탐색 > 사용자 선택.

1. 자동 탐색: `wiki_resolve "{PROJECT} stt 단어사전" type:note`. 후보 중 **`path` 가 `{PROJECT_DIR}/` 로 시작하는 것만** 본 프로젝트 사전 후보다(검색은 단어 하나만 맞아도 다른 프로젝트 사전을 돌려준다). 비분류형은 `{ROOT}` 직속 후보만. 소유 후보가 1건이면 `existing` 으로 확정, 2건 이상이면 번호 선택지(+ "해당 없음"). 다른 프로젝트 사전은 5의 공유 사전 절차로만 쓴다.
2. 후보가 없으면 → ① 기본 신설 경로에 신설(권장, `new`) ② 경로 직접 입력(`new`) ③ 사전 없이 진행(`none`).
3. `--new-dict` 도 1의 중복 검색을 먼저 거친다. 같은 프로젝트 사전이 있으면 → ① 기존 사용(`existing`) ② 그래도 다른 경로에 신설 ③ 중단.
4. `existing` 이면 `{ROOT}/{DICT}` 를 **Read 로 전체** 읽는다(2000줄 초과 시 `offset` 분할). §인명·§서비스명·§판별 규칙·보정 금지·**가장 뒤의 증분 섹션**을 빠뜨리지 않는다.
5. 공유 사전: `--shared-dict` 가 없으면 `wiki_resolve "stt 단어사전"` 에서 다른 프로젝트 사전 후보를 보여 주고 → ① 사용 ② 사용 안 함. 사용 시 인명·서비스 코드·도구명 절만 Read 한다.

결과를 `{DICT_MODE}`·`{DICT}`·공유 사전 목록으로 고정하고 이후 바꾸지 않는다.

## Step 3: 맥락 수집

1. 같은 프로젝트의 직전 회의록 1건: `wiki_resolve "{PROJECT} 회의록"` 최신 후보를 `wiki_read token_budget:2000` 으로 **헤더·참석자·인물 표만** 읽는다. 없으면 생략.
2. 원본 전사를 Read 로 전체 읽는다(2000줄 초과 시 `offset` 분할). 화자 라벨 종류(`참석자 N` / 실명 / 빈 라벨)와 회의 주제·등장 용어를 메모한다.

## Step 4: 치환 규칙 작성 → 1차 적용

> Step 4 진입 시 MUST: 같은 폴더의 `references/correction-rules.md` 를 Read 하고 §1~§7 을 따른다.

1. 단어장 규칙을 §3 우선순위(✅ > (문맥) > (?), 뒤 섹션 우선, 반례가 지목한 규칙 제외)로 모으고, 전사를 읽으며 문맥 근거가 있는 보정을 추가한다. 고위험(§4) 항목은 ✅ 패턴이 아니면 `(?)` 를 붙인다.
2. `{SCRATCH}/rules.json` 을 Write 한다 — `global`(전체 적용) 과 `turns`(**턴 서수** 키, 그 턴에서 정확히 1회).
3. 실행:
   ```bash
   python3 -I -B "{HELPER}" apply --root "{ROOT}" --src "{ROOT}/{SRC}" --rules "{SCRATCH}/rules.json" \
     --out-body "{SCRATCH}/body1.txt" --log "{SCRATCH}/initial.json"
   ```
4. `status: FAIL` 이면 `failures[]` 를 §7 '실패 코드 처리'대로 고쳐 재실행한다. 재실행 상한 `{MAX_RULE_RETRY}`.

| 종료 조건 | 결과 |
|-----------|------|
| `status: OK` | Step 5 진행 |
| `{MAX_RULE_RETRY}` 회 뒤에도 FAIL | `BLOCKED:RULE_MISMATCH` — 실패 규칙 목록 제시 → ① 실패 규칙을 빼고 진행 ② 중단 |

`unused_rules` 는 경고로만 기록한다(공유 사전 규칙이 이번 전사에 없는 것은 정상).

## Step 5: 보정본 조각 작성

> Step 5 진입 시 MUST: 같은 폴더의 `references/templates.md` §1·§2 를 Read 한다.

1. `{SCRATCH}/header.md` — frontmatter(분류형이면 `project`·`category` 를 저장 경로와 같은 값으로)·메타(`{SRC}`·`{SRC_SHA}`·턴 수·`header_format`·`duplicate_times`)·참석자 추정·언급 인물·보정 원칙·**용어 통일표는 `initial.json.rules_table_md` 를 그대로 붙인다**.
2. `{SCRATCH}/memo.md` — 보정 근거(확정·추정)·판독 불가·보정 금지·직전 회의록 대조. '확인 결과' 절은 Step 7 에서 채운다.
3. 아직 vault 에 쓰지 않는다. `--no-ask` 면 Step 6 을 `SKIPPED:NO_ASK` 로 기록하고 Step 7 로 간다.

## Step 6: 애매한 항목 질문

> `references/templates.md` §5 의 문구와 `references/correction-rules.md` §8 을 따른다.

1. `initial.json.markers` 를 위험도로 나눈다 — 고위험: 인명·호칭, 서비스/도구/채널명, 일정·금액·수치 / 저위험: 일반 어휘.
2. **전체 목록을 한 번 제시**하고 범위를 묻는다 → ① 고위험만 하나씩(권장) ② 전체 하나씩 ③ 목록 번호로 일괄 답변 ④ 생략(전부 보류).
3. `{QA_BATCH}` 건씩 AskUserQuestion 으로 묻는다. 항목 선택지:
   - `(?)` → ① 승인(마커 제거) ② 보류 ③ 질문 종료 · Other = 수정 문구(표시한 `phrase` 전체를 대체)
   - `[불명확: …]` → ① 원문 복원 ② 보류 ③ 질문 종료 · Other = 수정 문구
   한 질문이 여러 마커를 묶으면 대상 `marker_id` 를 모두 적는다. 같은 배치에서 '질문 종료' 앞의 답은 반영하고 뒤는 보류한다.
4. 답을 `{SCRATCH}/decisions.json` 에 누적한다: `[{"marker_id": "...", "action": "approve|restore|fix|hold", "text": "..."}]`. 묻지 않은 항목은 `hold` 로 넣지 않아도 된다(미기재 = 유지).

| 종료 조건 | 결과 |
|-----------|------|
| 범위 안 항목을 모두 처리 | Step 7 진행 |
| 사용자가 '질문 종료' 선택 | 남은 항목 보류, Step 7 진행 |
| `{MAX_QA_ROUNDS}` 라운드 도달 | `BLOCKED:MAX_ITERATIONS` → ① 남은 항목을 보류로 마감 ② 라운드 `{MAX_QA_ROUNDS}` 연장 ③ 중단 |

## Step 7: 결정 반영 → 산출물 생성

1. 결정 적용(질문을 했을 때만):
   ```bash
   python3 -I -B "{HELPER}" apply --root "{ROOT}" --src "{SCRATCH}/body1.txt" --decisions "{SCRATCH}/decisions.json" \
     --out-body "{SCRATCH}/body2.txt" --log "{SCRATCH}/decisions-applied.json"
   ```
   `--no-ask` 또는 질문 생략(범위 ④)이면 `decisions.json` 에 빈 배열 `[]` 을 쓰고 **같은 명령을 그대로 실행**한다(마커 수·로그 형식이 동일하게 나온다). FAIL 이면 `failures[].kind`(`unknown_marker`·`phrase_mismatch`·`invalid_action`·`overlapping_markers`…)대로 결정 JSON 을 고쳐 재실행한다.

   | 종료 조건 | 결과 |
   |-----------|------|
   | `status: OK` | 7.2 진행 |
   | `{MAX_RULE_RETRY}` 회 뒤에도 FAIL | `BLOCKED:DECISION_MISMATCH` — 실패 항목 제시 → ① 실패 항목을 `hold` 로 바꿔 진행 ② 중단 |
2. `memo.md` 의 '확인 결과' 표(원문·1차 보정·확정·결정)를 `decisions-applied.json` 으로 채우고, `header.md` 의 해소 이력·보정 원칙 카운트를 `decisions-applied.json.marker_counts` 로 갱신한다.
3. 조립·생성(빈 규칙, 파일별 배타적 신규 생성):
   ```bash
   python3 -I -B "{HELPER}" apply --root "{ROOT}" --src "{SCRATCH}/body2.txt" \
     --assemble "{SCRATCH}/header.md,{SCRATCH}/memo.md" --write-md "{ROOT}/{OUT_MD}" \
     --write-txt "{ROOT}/{OUT_TXT}" --expect-turns <probe.json.turns> --log "{SCRATCH}/final.json"
   ```
   `--no-txt` 면 `--write-txt` 를 뺀다. 헬퍼는 `{ROOT}` 밖·심볼릭 링크 경로·원본과 같은 파일에는 쓰지 않으며 **기존 파일을 덮어쓰지 않는다**.
4. `final.json.outputs[]` 를 파일별로 본다. `status: exists` 인 파일만 → ① 다른 이름(`-v2`, `-v3`…)으로 그 파일만 다시 생성(`--write-md` 또는 `--write-txt` 하나만 지정) ② 그 파일 생략. `created` 된 파일은 재생성하지 않는다(부분 성공 보존).

   | 종료 조건 | 결과 |
   |-----------|------|
   | 모든 출력이 `created` 또는 사용자가 생략 | 7.5 진행 |
   | 다른 이름 재시도 `{MAX_WRITE_RETRY}` 회 뒤에도 `exists` | `BLOCKED:WRITE_RETRY` → ① 그 파일 생략 ② 경로를 직접 지정해 1회 더 ③ 중단 |
5. `wiki_sync` 를 실행하고 `wiki_resolve "<보정본 제목>"` 으로 `{OUT_MD}` 가 색인됐는지 확인한다(`drift.added` 는 참고 정보). 색인이 확인되지 않으면 `wiki_sync` 만 최대 `{MAX_WRITE_RETRY}` 회 재시도하고, 그래도 안 되면 `BLOCKED:WRITE_RETRY` → ① 파일은 저장됐으므로 색인 미확인으로 보고하고 Step 8 진행 ② `/work-log:doctor` 후 재시도 ③ 중단. `final.json.body_sha256` 앞 8자리를 `{BODY_SHA}` 로 기록한다.

## Step 8: 단어장 업데이트

> Step 8 진입 시 MUST: 같은 폴더의 `references/templates.md` §3·§4 를 Read 한다.

| `{DICT_MODE}` | 처리 |
|---------------|------|
| `none` | 단어장 단계 `SKIPPED:NO_DICT`. 보고서의 단어장 경로를 비운다 |
| `existing` | §4 증분 템플릿으로 `## {DATE6} <회의명> 보정에서 추가된 패턴 — {DICT_SECTION_ID}` 섹션을 작성 → 단어장을 **한 번 스냅샷**해 같은 바이트에서 존재 여부와 해시를 함께 구한다: `cp "{ROOT}/{DICT}" "{SCRATCH}/dict-snapshot.md"` → Grep 으로 스냅샷에 `{DICT_SECTION_ID}` 가 **없음**을 확인 → `python3 -c 'import hashlib,sys;print(hashlib.sha1(open(sys.argv[1],"rb").read()).hexdigest()[:12])' "{SCRATCH}/dict-snapshot.md"` 로 해시 → `wiki_write` `mode:"append"` + `expected_hash:<해시>`, `frontmatter` 인자 없이 본문만. 스냅샷에 이미 있으면 append 하지 않고 "이미 반영됨"으로 보고. 해시 불일치로 거부되면(다른 실행이 먼저 썼다) 스냅샷부터 다시 하되 최대 `{MAX_WRITE_RETRY}` 회, 초과 시 `BLOCKED:WRITE_RETRY` → ① 증분 본문을 보고서에 실어 사용자가 직접 붙임 ② 중단 |
| `new` | §3 신설 템플릿으로 본문을 작성 → `wiki_write` `mode:"create"` `path:{DICT}` + `frontmatter {title, type:"note", tags}`. 이미 있으면(create 실패) `BLOCKED:DICT_EXISTS` 선택지로 돌아간다 — 최대 `{MAX_WRITE_RETRY}` 회, 초과 시 `BLOCKED:WRITE_RETRY` → ① 단어장 단계 생략(`SKIPPED:NO_DICT`, 신설 본문은 보고서에 첨부) ② 중단 |

증분 섹션에는 ✅ 사용자 확인(원문·확정·적용 범위·**대체하는 이전 결정**·확인 근거), (문맥) 확정, 추정 잔존, 판독 불가, 신규 인명·용어, 보정 금지, **반례 기록**(폐기된 1차 보정)을 넣는다. 머리말의 규모·갱신 이력은 고치지 않는다.

`write_state: unknown` 이면 Grep 으로 `{DICT_SECTION_ID}`(또는 신설 파일) 저장 여부를 확인하고 **미저장일 때만** 재시도한다. `written` 뒤 `indexing.status` 가 OK 가 아니면 `wiki_sync` 만 최대 `{MAX_WRITE_RETRY}` 회 재시도하고, 초과 시 `BLOCKED:WRITE_RETRY`(위 선택지와 동일 — 문서는 이미 저장됨).

## Step 9: 보고

아래 `## 출력 형식` 으로 보고한다. 이 스킬은 git 커밋·push 를 하지 않는다.

## 출력 형식

```markdown
## STT 보정 결과: <회의명>

| 산출물 | 경로 | 상태 |
|--------|------|------|
| 보정본 | {OUT_MD} | DONE / FAIL(<사유>) |
| 정리본 | {OUT_TXT} | DONE / SKIPPED:NO_TXT / FAIL(<사유>) |
| 단어장 | {DICT} | DONE(append {DICT_SECTION_ID}) / DONE(create) / SKIPPED:NO_DICT |

- 원본: `{SRC}` (sha256 `{SRC_SHA}`) · 턴 수 원본 <N> / 보정본 <N> · 헤더 <header_format> · 중복 시각 <duplicate_times 또는 없음>
- 치환: 무표기 <R>건(규칙 <V>개, 미사용 <u>개) · 잔존 `(?)` <a>건 · `[불명확]` <b>건
- 질문: 범위 <고위험만/전체/일괄/생략> · 대상 <k>건 — 승인 <x> · 수정 <y> · 복원 <r> · 보류 <z> · 미처리 <w> (또는 SKIPPED:NO_ASK)
- 색인: wiki_sync <OK/재시도 n회> · wiki_resolve 확인 <OK/미확인>
- 상태: DONE | BLOCKED:<사유> | FAIL
```

## 상태 코드

| 코드 | 의미 |
|------|------|
| `DONE` | 보정본 생성 + (정리본·단어장 중 생략되지 않은 것) 완료 |
| `SKIPPED:NO_ASK` | `--no-ask` 로 질문 단계 생략 |
| `SKIPPED:NO_TXT` | `--no-txt` 또는 충돌 시 사용자가 정리본 생략 선택 |
| `SKIPPED:NO_DICT` | `{DICT_MODE}=none` 으로 단어장 단계 생략 |
| `BLOCKED:MCP_UNAVAILABLE` / `BLOCKED:PYTHON_UNAVAILABLE` | 전제 조건 미충족 |
| `BLOCKED:SRC_NOT_FOUND` / `BLOCKED:SRC_ALREADY_CORRECTED` | 원본 미발견 / 이미 보정된 파일 |
| `BLOCKED:DICT_NOT_FOUND` / `BLOCKED:DICT_EXISTS` / `BLOCKED:DICT_CONFLICT` | 단어장 경로·플래그 문제 |
| `BLOCKED:RULE_MISMATCH` | 규칙 재실행 상한 도달 |
| `BLOCKED:MAX_ITERATIONS` | 질문 라운드 상한 도달 |
| `BLOCKED:DECISION_MISMATCH` | 결정 JSON 재실행 상한 도달 |
| `BLOCKED:WRITE_RETRY` | `wiki_sync` 재시도·단어장 append 해시 충돌·산출물 파일명 충돌·단어장 create 충돌 재시도 상한 도달 |
| `FAIL` | 헬퍼 쓰기 실패(`io_error`·`outside_root`), 또는 `wiki_write` `write_state: unknown` 뒤 미저장 확인 |

헬퍼의 `header_format`·`failures[].kind`(`scoped_mismatch`·`exists` 등)는 진단 분류(데이터)이며 결과 표 셀 안에서만 쓴다.

## References

- `references/correction-rules.md` — 표기 3단·보존 규칙·규칙 수집 우선순위·위험도·인명 판별·규칙 JSON 작성법·실패 코드 처리·질문 설계 (Step 4·6 에서 MUST Read)
- `references/templates.md` — 보정본 header/memo 템플릿·단어장 신설/증분 템플릿·질문 문구 (Step 5·6·7·8 에서 MUST Read)
- `assets/stt_fix.py` — 헬퍼. `apply --root --src [--rules|--decisions] --log [--out-body] [--assemble a,b --write-md] [--write-txt] [--expect-turns]`. `--out-body`·`--log` 는 스크래치 산출물(덮어씀), `--write-md`·`--write-txt` 는 vault 산출물(root 안 새 파일만, 배타적 생성)
