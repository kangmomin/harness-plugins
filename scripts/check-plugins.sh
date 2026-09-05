#!/usr/bin/env bash
# check-plugins.sh — 플러그인 구조 검사 (start-workflow 티어·md 리포트 작업의 구조 검증 대체).
#   1) SKILL.md ≤ 500줄  2) 오버레이 앵커 제목이 베이스에 정확히 1회 존재  3) 스크립트 사본 byte-identical
#   4) python3 -m py_compile (assets/*.py)  5) HTML 리포트 문구 잔재 0건
#   6) codex-mode.md 공통 블록 parity(sync-codex-mode.py --check) · defaults 마커 구조 · 모델/effort 리터럴 범위 · codexMode/codexModels·슬롯 토큰·플래그 존재 · 구 문구 잔재 0건
#   7) config 스킬: PROFILE.md ↔ config SKILL.md 키 parity(양방향, config:keys 마커 1쌍)
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
for s in test_failures.py workflow_archive.py risk_facts.py workflow_run.py; do
  pair "be-harness/skills/start-workflow/assets/$s" "fe-harness/skills/start-workflow/assets/$s"
done
pair be-harness/skills/start-workflow/assets/workflow_archive.py common/skills/start-workflow/assets/workflow_archive.py
pair be-harness/skills/start-workflow/assets/workflow_run.py common/skills/start-workflow/assets/workflow_run.py
pair be-harness/skills/e2e-test/assets/e2e-lock.sh fe-harness/skills/e2e-test/assets/e2e-lock.sh
pair be-harness/skills/e2e-test/references/run-context.md fe-harness/skills/e2e-test/references/run-context.md
for s in run-lifecycle.md finalization.md; do
  pair "be-harness/skills/start-workflow/references/$s" "fe-harness/skills/start-workflow/references/$s"
  pair "be-harness/skills/start-workflow/references/$s" "common/skills/start-workflow/references/$s"
done

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

# 6) codex-mode: 공통 블록 parity · defaults 마커 구조 · 모델/effort 리터럴 범위 · 줄 수 · codexMode/codexModels·슬롯 토큰 존재 · 구 문구 잔재
if ! python3 scripts/sync-codex-mode.py --check >/dev/null 2>&1; then bad "codex-mode 공통 블록 불일치 — python3 scripts/sync-codex-mode.py 로 동기화"; fi
CM_FILES='be-harness/skills/start-workflow/references/codex-mode.md fe-harness/skills/start-workflow/references/codex-mode.md common/skills/start-workflow/references/codex-mode.md'
for f in $CM_FILES; do
  if [ ! -f "$f" ]; then bad "없음: $f"; continue; fi
  cb=$(grep -n 'codex-mode:common-begin' "$f" | cut -d: -f1 | head -1); ce=$(grep -n 'codex-mode:common-end' "$f" | cut -d: -f1 | head -1)
  db=$(grep -n 'codex-mode:defaults-begin' "$f" | cut -d: -f1); de=$(grep -n 'codex-mode:defaults-end' "$f" | cut -d: -f1)
  if [ "$(printf '%s\n' "$db" | grep -c .)" -ne 1 ] || [ "$(printf '%s\n' "$de" | grep -c .)" -ne 1 ]; then bad "$f: defaults 마커가 정확히 1쌍이 아님"; continue; fi
  if ! { [ -n "$cb" ] && [ -n "$ce" ] && [ "$cb" -lt "$db" ] && [ "$db" -lt "$de" ] && [ "$de" -lt "$ce" ]; }; then bad "$f: defaults 마커 순서/위치 오류 (공통 블록 내부여야 함)"; continue; fi
  inside=$(sed -n "$((db+1)),$((de-1))p" "$f")
  rows=$(printf '%s\n' "$inside" | grep -oE '^\| `(review|explore|judge|write)` \|' | sed -E 's/^\| `//; s/` \|$//' | tr '\n' ' ')
  if [ "$rows" != "review explore judge write " ]; then bad "$f: defaults 표는 review·explore·judge·write 4행이어야 함 (현재: ${rows:-없음})"; fi
  m=$(printf '%s\n' "$inside" | grep -oE 'gpt-5\.[0-9]+-[A-Za-z0-9-]+' | grep -vE '^gpt-5\.6-(sol|luna)$' | sort -u | tr '\n' ' ' || true)
  if [ -n "$m" ]; then bad "$f: defaults 표에 허용되지 않은 Codex 모델: $m"; fi
  e=$(printf '%s\n' "$inside" | grep -oE '`[a-z0-9._-]+`' | grep -vE '^`(review|explore|judge|write|openai|gpt-5\.6-sol|gpt-5\.6-luna|tiered|medium|high|xhigh|max|read-only|workspace-write)`$' | sort -u | tr '\n' ' ' || true)
  if [ -n "$e" ]; then bad "$f: defaults 표에 허용되지 않은 토큰(effort/모델/sandbox 허용 목록 밖): $e"; fi
  o=$(sed "${db},${de}d" "$f" | grep -n -E 'gpt-5\.[0-9]+-' || true)
  if [ -n "$o" ]; then bad "$f: defaults 마커 밖 OpenAI 모델 리터럴:"; say "$o"; fi
  n=$(wc -l < "$f")
  if [ "$n" -gt 180 ]; then bad "$f: ${n}줄 (> 180)"; fi
done
res=$(grep -rn -E 'gpt-5\.[0-9]+-' --include='*.md' be-harness fe-harness common minmos-harness README.md 2>/dev/null | grep -v 'community-feedback/' | grep -v 'references/codex-mode.md' || true)
if [ -n "$res" ]; then bad "codex-mode.md defaults 표 밖 OpenAI 모델 리터럴 (슬롯 기본값 표만 허용):"; say "$res"; fi
for f in be-harness/PROFILE.md fe-harness/PROFILE.md be-harness/skills/init/SKILL.md fe-harness/skills/init/SKILL.md be-harness/skills/doctor/SKILL.md fe-harness/skills/doctor/SKILL.md minmos-harness/skills/doctor/SKILL.md be-harness/skills/config/SKILL.md fe-harness/skills/config/SKILL.md; do
  for k in codexMode codexModels; do if ! grep -q "$k" "$f"; then bad "$f: $k 없음"; fi; done
done
for f in $CM_FILES be-harness/PROFILE.md fe-harness/PROFILE.md be-harness/skills/doctor/SKILL.md fe-harness/skills/doctor/SKILL.md minmos-harness/skills/doctor/SKILL.md be-harness/skills/config/SKILL.md fe-harness/skills/config/SKILL.md; do
  for s in review explore judge write; do if ! grep -q "\`$s\`" "$f"; then bad "$f: 슬롯 토큰 \`$s\` 없음"; fi; done
done
for f in be-harness/skills/start-workflow/SKILL.md fe-harness/skills/start-workflow/SKILL.md common/skills/start-workflow/SKILL.md common/skills/start-workflow/references/fullstack.md; do
  if ! grep -q -- '--codex-models' "$f"; then bad "$f: --codex-models 없음"; fi
done
for f in be-harness/skills/start-workflow/references/templates.md fe-harness/skills/start-workflow/references/templates.md common/skills/start-workflow/references/contract-templates.md be-harness/skills/start-workflow/SKILL.md fe-harness/skills/start-workflow/SKILL.md common/skills/start-workflow/references/fullstack.md; do
  if ! grep -q 'CODEX_MODELS' "$f"; then bad "$f: CODEX_MODELS 없음"; fi
done
for p in 'Model provider' 'Missing environment variable'; do
  if ! grep -q "$p" be-harness/skills/start-workflow/references/codex-mode.md; then bad "codex-mode.md 정본: §7 감지 문구 '$p' 없음"; fi
done
res=$(grep -rn -E 'Codex 계열|Plan 검증 루프 상시|재실패 시 quota 차단과 동일 취급|command not found, 도구 미존재|Codex sol\b|Codex luna\b|Codex `sol`|Codex `luna`|luna/sol|luna\(읽기\)/sol\(쓰기\)|sol/high/workspace-write|luna/xhigh/read-only|Codex\(gpt-5\.6-sol\)|Codex\(luna|fallback\((mcp_missing|quota_exhausted|auth_failed|model_unavailable)\)' \
  --include='*.md' be-harness fe-harness common minmos-harness README.md 2>/dev/null | grep -v 'community-feedback/' || true)
if [ -n "$res" ]; then bad "codex-mode 구 문구 잔재:"; say "$res"; fi

# 7) config 스킬: PROFILE.md(문서 canonical) 프론트매터 키 ↔ config SKILL.md `config:keys` 마커 안 백틱 토큰 — 양방향 parity (개수 하드코딩 없음)
for p in be-harness fe-harness; do
  pf=$p/PROFILE.md; cf=$p/skills/config/SKILL.md
  if [ ! -f "$cf" ]; then bad "없음: $cf"; continue; fi
  if [ ! -f "$pf" ]; then bad "없음: $pf"; continue; fi
  if [ "$(grep -c '^---$' "$pf")" -ne 2 ]; then bad "$pf: 프론트매터 구분선(^---$)이 정확히 2개가 아님 — parity 추출 불가"; continue; fi
  d1=$(grep -n '^---$' "$pf" | sed -n 1p | cut -d: -f1); d2=$(grep -n '^---$' "$pf" | sed -n 2p | cut -d: -f1)
  pk=$(sed -n "$((d1+1)),$((d2-1))p" "$pf" | grep -oE '^(# )?[A-Za-z0-9_-]+:' | sed -E 's/^# //; s/:$//')
  kb=$(grep -n 'config:keys-begin' "$cf" | cut -d: -f1); ke=$(grep -n 'config:keys-end' "$cf" | cut -d: -f1)
  if [ "$(printf '%s\n' "$kb" | grep -c .)" -ne 1 ] || [ "$(printf '%s\n' "$ke" | grep -c .)" -ne 1 ] || [ "$kb" -ge "$ke" ]; then bad "$cf: config:keys 마커가 정확히 1쌍(begin < end)이 아님"; continue; fi
  ck=$(sed -n "$((kb+1)),$((ke-1))p" "$cf" | grep -oE '`[^`]+`' | tr -d '`')
  dup=$(printf '%s\n' "$pk" | sort | uniq -d | tr '\n' ' '); if [ -n "$dup" ]; then bad "$pf: 프론트매터 키 중복: $dup"; fi
  dup=$(printf '%s\n' "$ck" | sort | uniq -d | tr '\n' ' '); if [ -n "$dup" ]; then bad "$cf: 마커 안 토큰 중복: $dup"; fi
  miss=$(comm -23 <(printf '%s\n' "$pk" | sort -u) <(printf '%s\n' "$ck" | sort -u) | tr '\n' ' ')
  extra=$(comm -13 <(printf '%s\n' "$pk" | sort -u) <(printf '%s\n' "$ck" | sort -u) | tr '\n' ' ')
  if [ -n "$miss" ]; then bad "$cf: PROFILE.md 키가 마커 안에 없음: $miss"; fi
  if [ -n "$extra" ]; then bad "$cf: 마커 안 토큰이 PROFILE.md 프론트매터에 없음: $extra"; fi
done

if [ "$fail" -eq 0 ]; then say "check-plugins: OK"; fi
exit "$fail"
