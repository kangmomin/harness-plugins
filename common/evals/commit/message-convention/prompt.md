---
name: commit-message-convention
tags: [behavior]
runs: 3
max_turns: 6
allowed_tools: [Skill, Read, Glob, Grep]
---

이 프로젝트의 커밋 규칙대로 커밋 메시지 제목 한 줄만 써줘. 실제 커밋과 git 명령 실행은 하지 마.

변경 내용: 로그인 API 에 비밀번호 5회 실패 시 계정을 잠그는 기능을 새로 추가했다.
