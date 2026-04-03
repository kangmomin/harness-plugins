---
name: commit-pr
description: "커밋, 브랜치 생성, PR 오픈까지 전체 워크플로우 수행"
user-invocable: true
---

0. 이미 생성된 PR 이 있다면 /mimo-s-harness:commit-push 만 진행해
1. VERSION 파일이 있다면 patch VERSION 을 올려.
2. diff 를 바탕으로 branch 를 작업 현황에 맞는 이름으로 컨벤션에 맞게 하나 새로 생성해. *브랜치는 feat 으로 시작하는 prefix 를 지녀야해* 만약 이미 branch 가 있다면 넘어가.
3. /mimo-s-harness:commit-push 를 진행해
4. 작업을 분석하여 브랜치 바로 상위 브랜치로 draft PR 을 열어.
