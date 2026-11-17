---
target: common:python-helpers
created: 2026-11-17
---

# Community Feedback

<!-- feedback:4f3194482984e10889faf68c34dcec296eaf322475346b711c21b747bf179013 -->
## 2026-11-17

**대상**: common:python-helpers
**요지**: Python helper 가 인코딩 없이 파일을 읽고 써서 Windows 비-UTF-8 로캘에서 UnicodeDecodeError
**범용성**: 특정 조건
**조건**: Windows 에서 시스템 로캘이 UTF-8 이 아닐 때(예: 한국어 cp949). 한글이 든 PR 제목·요약·피드백을 다루면 거의 항상 발생

### 컨텍스트
Windows(한국어 로캘, 기본 인코딩 cp949)에서 /common:merge 를 실행했다. merge_state.py snapshot 이 gh pr view JSON(한글 PR 제목 포함)을 읽다가 `'cp949' codec can't decode byte 0xec` 로 BLOCKED:MERGE_STATE 가 되었다. 스킬은 `python3 -I -B` 로 실행하므로 PYTHONUTF8 환경 변수도 무시된다. `python -X utf8 -I -B ...` 로 실행해 우회했다.

같은 패턴(인코딩 없는 Path.read_text()/write_text()/open())이 다른 helper 에도 있다: merge/assets/merge_state.py(입력 JSON), submit-feedback/assets/feedback.py(입력 JSON, checkout 의 기존 피드백 파일 읽기·쓰기), how-to-use/assets/skill_catalog.py, start-workflow/assets/workflow_policy.py·workflow_results.py·workflow_scope.py·writer_guard.py, sync-base/assets/sync_state.py. 한글 PR 제목·요약·피드백 본문을 다루므로 Windows 사용자에게는 거의 항상 발생한다.

### 제안
1. 모든 helper 의 텍스트 파일 입출력에 `encoding='utf-8'` 을 명시한다(Path.read_text/write_text, open). stdin 은 `sys.stdin.reconfigure(encoding='utf-8')` 또는 `json.load(sys.stdin.buffer)` 를 쓴다. stdout 의 json.dumps(ensure_ascii=False) 출력도 `sys.stdout.reconfigure(encoding='utf-8')` 로 고정한다.
2. 또는 SKILL.md 의 실행 예시를 `python3 -X utf8 -I -B ...` 로 바꾼다(-I 와 함께 동작한다). 1번이 근본 해결이다.
3. 한글 내용을 담은 JSON 으로 helper 를 실행하는 테스트를 `PYTHONIOENCODING`/로캘을 바꾼 환경(또는 `-X utf8` 없는 cp949 시뮬레이션: `locale.getpreferredencoding` 패치)에서 추가한다.
