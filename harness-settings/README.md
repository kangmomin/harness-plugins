# harness-settings

harness 공통 설정 파일 `.claude/harness.config.json` 을 편집하는 Claude Code mod (hooks 모듈).

## 사용

1. `/plugin install harness-settings@harness-plugins`
2. `/harness-settings` → pane 이 열린다.
3. 버튼으로 켜고 끈다. 변경은 즉시 파일에 저장된다. status line 에 현재 값이 표시된다.

| 항목 | 키 | 기본값 |
|------|----|--------|
| 타 모델 리뷰 (전체) | `review.enabled` | on |
| Plan 리뷰 / 품질 리뷰 | `review.points.plan` / `review.points.quality` | on |
| 리뷰 엔진 | `review.engine` (`auto` = 키 삭제 → `codexMode` 따름) | auto |
| Gemini 모델 | `review.gemini.model` (빈 값 = CLI 기본) | 빈 값 |
| OCR / E2E / simplify-loop / 성찰 | `steps.ocr` / `steps.e2e` / `steps.simplifyLoop` / `steps.reflect` | on / on / on / off |

- 리뷰 off = 건너뛰지 않음. Claude 패널이 리뷰한다.
- 파일에 있는 다른 키는 보존한다. JSON 파싱이 실패한 파일은 덮어쓰지 않는다.
- 파일을 직접 고쳐도 된다. 하네스는 다음 워크플로우 Pre-flight 에서 읽는다 (실행 중인 워크플로우는 상태 파일 값을 유지).

계약: `be-harness/skills/start-workflow/references/review-config.md`.

## 개발

```bash
claude plugin validate harness-settings
claude plugin test harness-settings
claude --plugin-dir harness-settings   # hot reload 로 직접 확인
```
