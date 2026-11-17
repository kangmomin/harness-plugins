---
target: skill:doc-gen
created: 2026-11-17
---

# Community Feedback

<!-- feedback:b1fb4681fdce136afaf1bd6386dc6f81132e673eeb1d5fbe09a9bdf55d7ca702 -->
## 2026-11-17

**대상**: skill:doc-gen
**요지**: docgen.mjs 의 main guard 가 링크(심볼릭 링크·정션) 경로에서 어긋나 아무것도 하지 않고 exit 0
**범용성**: 특정 조건
**조건**: 스킬 경로가 심볼릭 링크·정션을 거칠 때(프로필별 home 을 쓰는 실행 도구, 링크로 연결한 plugins 디렉터리 등)

### 컨텍스트
/common:merge 에서 doc-gen 으로 PR 요약을 만들 때 `node <스킬 경로>/assets/docgen.mjs <md> <docs> md` 가 출력 없이 exit 0 으로 끝나고 파일도 만들지 않았다. 스킬 경로가 다른 디렉터리를 가리키는 링크였다(Orca 같은 도구가 프로필별 home 아래의 plugins 경로를 실제 ~/.claude/plugins 로 연결한 경우). Node 는 import.meta.url 을 실제 경로(realpath)로 주지만, 진입 검사 `import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href` 는 링크 경로 그대로 비교해서 false 가 된다. 그래서 main() 이 불리지 않고, 실패 JSON 도 남기지 않는다. 실제 경로로 node 를 실행해 우회했다.

### 제안
1. 진입 검사에서 argv[1] 을 실제 경로로 바꿔 비교한다: `fs.realpathSync(process.argv[1])` 를 `pathToFileURL` 에 넘긴다(Windows 대소문자 차이도 줄어든다).
2. 또는 라이브러리 export 와 CLI 진입점을 나눠 CLI 파일(예: docgen-cli.mjs)은 조건 없이 main() 을 부른다.
3. 아무것도 하지 않고 끝나는 경우가 생기지 않게, 진입 검사가 false 인데 인자가 주어졌으면 경고를 stderr 에 남기거나 SKILL.md 에 'status JSON 이 출력되지 않으면 FAIL' 로 판정하라고 적는다.
