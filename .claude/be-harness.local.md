---
preset: custom
language: ko
codexMode: none
# codexModels:                                              # 기본(미변경)이면 이 주석 2줄 그대로, 변경했으면 실제 codexModels 블록으로 교체
#   review: { provider: zai, model: glm-5.3, effort: high }

buildCommand: ""
testCommand:  "bash scripts/verify.sh"
lintCommand:  "bash scripts/check-plugins.sh"
typeCheckCommand: ""
makeTestCommand: ""

runServerCommand: ""
serverUrl: ""
e2eEnabled: false
apiDocsPath: ""
frontendRepo: ""

sourceDirs: [be-harness, fe-harness, common, minmos-harness, hyeondongs-harness, harness-settings, work-log, scripts]
testDirs:   [tests, work-log/tests]

mainBranch: main
featureBranchPrefix: feat/
hotfixBranchPrefix: hotfix/

commitPrefixes: [Add, Update, Fix, Del, Refactor, Doc, Test, Chore, WIP]
commitCoAuthor: ""

projectConventions: ["CLAUDE.md"]
---

# Project Notes

(프로젝트별 메모는 아래에 자유롭게 작성)
