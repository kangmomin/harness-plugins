---
name: commit-push
description: "커밋 후 원격 저장소에 push"
user-invocable: true
---

1. `/donghyeons-harness:commit` 을 먼저 실행해서 변경사항을 커밋해.
2. 현재 브랜치를 확인해.
3. 보호 브랜치 확인: `main`, `master`, `dev`, `develop`, `rc-*` 브랜치이면 **push를 중단**하고 유저에게 경고해.
4. `git push origin {현재 브랜치}` 실행.
5. push 실패 시 원인을 분석하고 유저에게 안내해.

## 보호 브랜치 경고 메시지

> "현재 브랜치가 `{브랜치명}`입니다. 보호 브랜치에 직접 push하는 것은 권장되지 않습니다.
> 계속하시겠습니까? (Y/N)"

유저가 Y를 입력하면 push를 진행한다.
