---
name: simplify-loop-mm
description: "수정 사항이 없을 때까지 빌트인 /simplify 반복 실행 (최대 10회)"
---

아래 절차를 따라 Claude Code **빌트인** `/simplify` 스킬을 반복 실행해:

> **주의**: 여기서 `/simplify`는 Claude Code 빌트인 스킬이다. 본 플러그인(minmos-harness)의 스킬이 아니다.
> 스킬 호출 호출 시 `$simplify (빌트인)` (빌트인)로 호출해야 하며, `skill: "minmos-harness:simplify"`로 호출하면 안 된다.

---

## 수정 금지 항목 (Exclusion Interface)

simplify 실행 시 특정 파일/경로를 수정 대상에서 제외할 수 있다.

### 제외 목록 소스 (우선순위 순)

1. **`$ARGUMENTS`의 `--exclude` 플래그**: 쉼표 구분 Glob 패턴
   - 예: `--exclude "internal/handler/auth*.go,internal/migration/**"`
2. **`.simplify-exclude.json`** (프로젝트 루트): 영구적 제외 목록
   ```json
   {
     "exclude": [
       "internal/migration/**",
       "internal/handler/auth_handler.go",
       "*.generated.go"
     ]
   }
   ```
3. 두 소스 모두 없으면 제외 없이 진행한다.

### 제외 적용 방식

1. 루프 시작 전, 제외 대상 파일을 Glob으로 확장하여 **전체 경로 목록**을 확정한다.
2. 매 iteration 전에 제외 대상 파일의 현재 내용을 **스냅샷**(메모리에 경로+내용 기록)한다.
3. `/simplify` 실행 후, 제외 대상 파일에 변경이 발생했는지 `git diff`로 확인한다.
4. **변경 발생 시**: `git checkout -- {파일}` 로 스냅샷 상태로 복원하고, 해당 복원을 로그에 기록한다.

---

## 절차

1. **제외 목록 로드**: `$ARGUMENTS`에서 `--exclude` 패턴과 `.simplify-exclude.json`을 읽어 제외 파일 목록을 확정한다.
2. 제외 대상 파일의 현재 내용을 스냅샷한다.
3. 빌트인 `/simplify` 를 실행한다 (`$simplify (빌트인)`).
4. 제외 대상 파일에 변경이 있으면 복원한다.
5. 리뷰 결과를 확인한다:
   - **코드 수정이 적용된 경우** (복원된 파일 제외) → iteration 카운트를 1 증가시키고 2번으로 돌아간다.
   - **수정할 사항이 없는 경우** (Applied Changes: 없음, 또는 모든 에이전트가 KEEP 판정) → 루프를 종료한다.
6. **최대 10회** iteration 후에는 수정 사항 유무와 관계없이 종료한다.

## 종료 시 출력

```
Simplify Loop 완료
- 총 iteration: N회
- 총 수정 횟수: M회
- 제외 파일: [목록 또는 "없음"]
- 복원 횟수: K회 (제외 파일 변경 복원)
```
