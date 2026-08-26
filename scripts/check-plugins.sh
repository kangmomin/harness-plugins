#!/usr/bin/env bash
# check-plugins.sh — 플러그인 구조 검사 (start-workflow 티어·md 리포트 작업의 구조 검증 대체).
#   1) SKILL.md ≤ 500줄  2) 오버레이 앵커 제목이 베이스에 정확히 1회 존재  3) 스크립트 사본 byte-identical
#   4) python3 -m py_compile (assets/*.py)  5) HTML 리포트 문구 잔재 0건
# 사용: bash scripts/check-plugins.sh   (exit 0 = 전부 통과)
set -u
cd "$(dirname "$0")/.."
fail=0
say() { printf '%s\n' "$*"; }
bad() { fail=1; say "FAIL: $*"; }

# 1) SKILL.md 줄 수
while IFS= read -r f; do
  n=$(wc -l < "$f")
  if [ "$n" -gt 500 ]; then bad "$f: ${n}줄 (> 500)"; fi
done < <(find . -path ./work-log -prune -o -path ./node_modules -prune -o -name SKILL.md -print)

# 2) 앵커 (docs/overlay.md — 제목 매칭)
check_anchor() { # file, pattern
  local c; c=$(grep -c -E "$2" "$1" || true)
  if [ "$c" -ne 1 ]; then bad "앵커 '$2' — $1 에 ${c}회 (1회 필요)"; fi
}
BE_SW=be-harness/skills/start-workflow/SKILL.md
check_anchor "$BE_SW" '^## Phase 1: 작업 범위 수집'
check_anchor "$BE_SW" '^## Phase 4: Plan 작성 \+ 리뷰'
check_anchor "$BE_SW" '^### Phase 8: 품질 루프'
check_anchor "$BE_SW" '^### Phase 9: API 문서 동기화'
BE_E2E=be-harness/skills/e2e-test/SKILL.md
for a in '^## Step 1: 대상 API 수집' '^## Step 2: 시나리오 구성' '^## Step 4: 서버 기동' '^## Step 5: 요청 실행' '^## Step 6: 서버 종료' '^## Step 7: 리포트'; do
  check_anchor "$BE_E2E" "$a"
done
FE_SW=fe-harness/skills/start-workflow/SKILL.md
check_anchor "$FE_SW" '^## Phase 1: 작업 범위 수집'

# 3) 사본 parity
pair() { if ! diff -q "$1" "$2" >/dev/null 2>&1; then bad "사본 불일치: $1 ↔ $2"; fi; }
for s in test_failures.py workflow_archive.py risk_facts.py; do
  pair "be-harness/skills/start-workflow/assets/$s" "fe-harness/skills/start-workflow/assets/$s"
done
pair be-harness/skills/start-workflow/assets/workflow_archive.py common/skills/start-workflow/assets/workflow_archive.py

# 4) py_compile
while IFS= read -r f; do
  if ! python3 -W error -m py_compile "$f" 2>/dev/null; then bad "py_compile 실패: $f"; fi
done < <(find . -path ./work-log -prune -o -path '*/skills/*/assets/*.py' -print)
find . -path ./work-log -prune -o -name __pycache__ -type d -print 2>/dev/null | xargs -r rm -rf

# 5) HTML 리포트 문구 잔재 (스킬·오버레이·README·PROFILE·plugin.json)
res=$(grep -rn -E 'e2e-report\.html|impl-notes\.html|리포트 HTML|HTML 렌더링|HTML 리포트|api-test-cases-prompt' \
  --include='*.md' --include='*.json' be-harness fe-harness common minmos-harness hyeondongs-harness README.md docs/overlay.md docs/skill-authoring.md 2>/dev/null \
  | grep -v 'community-feedback/' || true)
if [ -n "$res" ]; then bad "HTML 리포트 문구 잔재:"; say "$res"; fi

if [ "$fail" -eq 0 ]; then say "check-plugins: OK"; fi
exit "$fail"
