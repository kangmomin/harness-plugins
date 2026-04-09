# harness-plugins — Codex CLI 버전

Claude Code 하네스를 OpenAI Codex CLI용으로 변환한 버전.

## 설치 (백엔드: minmos)

```bash
# 프로젝트에서 실행
cp -r codex/minmos/skills/* .agents/skills/
cp -r codex/minmos/agents/* .codex/agents/
cp codex/minmos/AGENTS.md AGENTS.md   # 기존 AGENTS.md가 있으면 내용 병합
```

## 설치 (프론트엔드: hyeondongs)

```bash
cp -r codex/hyeondongs/skills/* .agents/skills/
cp -r codex/hyeondongs/agents/* .codex/agents/
cp codex/hyeondongs/AGENTS.md AGENTS.md
```

## 스킬 호출

```bash
# Claude Code          →  Codex CLI
# /minmos-harness:commit-mm  →  $commit-mm
# /hyeondongs-harness:commit-hd  →  $commit-hd

# 명시적 호출
$commit-mm
$request-hd
$start-workflow-mm

# 또는 /skills 로 목록 확인 후 선택
```

## 구조

```
codex/
├── minmos/                  # Go 백엔드
│   ├── skills/              # → .agents/skills/
│   ├── agents/              # → .codex/agents/
│   └── AGENTS.md            # → 프로젝트 루트
└── hyeondongs/              # React 프론트엔드
    ├── skills/
    ├── agents/
    └── AGENTS.md
```
