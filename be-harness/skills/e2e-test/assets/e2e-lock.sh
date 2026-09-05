#!/usr/bin/env bash
# e2e-lock.sh — E2E 테스트 실행 뮤텍스 (여러 에이전트의 순번 대기)
#
# canonical: be-harness/skills/e2e-test/assets/e2e-lock.sh
# version:   1.1.0
#
# fe-harness/skills/e2e-test/assets/e2e-lock.sh 는 이 파일의 동일 사본이다.
# 크로스 플러그인 파일 경로 참조가 금지되어 있어(docs/overlay.md §9) 공유하지 않고 복제한다.
# canonical 을 고치면 사본도 같은 버전으로 맞춘다.
#
# 사용법:
#   e2e-lock.sh acquire <key> --token RUN_TOKEN [--timeout SEC] [--ttl SEC] [--label TEXT] [--poll SEC]
#   e2e-lock.sh beat    <key> --token RUN_TOKEN
#   e2e-lock.sh release <key> --token RUN_TOKEN
#   e2e-lock.sh status  [key]
#
# 종료 코드: 0 성공 / 2 대기 타임아웃 / 1 그 외 실패(락 디렉토리 생성 불가 포함)
#
# 의존성: bash, mkdir, mv, stat, sed, date 만 사용한다 (node·jq·flock 불필요).
# flock 을 쓰지 않는 이유: 락이 보유 프로세스와 함께 죽는데, E2E 1회 실행은
# 여러 Bash 툴 호출에 걸쳐 있어 프로세스 수명으로 락을 유지할 수 없다.

set -uo pipefail

VERSION="1.1.0"

DEFAULT_TIMEOUT=540   # 대기 상한(초). Bash 툴 timeout(최대 600s)보다 짧게 둔다
DEFAULT_TTL=900       # heartbeat 가 이 시간 이상 끊기면 죽은 락으로 보고 회수
DEFAULT_POLL=5        # 폴링 간격(초)

TIMEOUT="$DEFAULT_TIMEOUT"
TTL="$DEFAULT_TTL"
POLL="$DEFAULT_POLL"
LABEL=""
TOKEN=""
GUARD_HELD=0

now() { date +%s; }

die() { printf 'ERROR %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

# --- 락 루트 해석 -------------------------------------------------------------
# ① $HARNESS_E2E_LOCK_DIR  ② $WORK_LOG_ROOT  ③ ~/.claude/work-log.json 의 root
# ④ fallback /tmp/harness-e2e-locks
#
# ③ 은 **전역 설정만** 파싱한다. 전역 scope 는 root 에 절대경로가 강제되므로
# (work-log/mcp/lib/config.js:validateRoot) sed 한 줄로 안전하게 읽을 수 있다.
# project 스코프(<repo>/.work-log.json)는 상대경로가 허용되므로 여기서 다루지
# 않는다 — 그런 환경에서는 $WORK_LOG_ROOT 를 절대경로로 주입할 것.
resolve_lock_root() {
  local vault=""

  if [ -n "${HARNESS_E2E_LOCK_DIR:-}" ]; then
    printf '%s' "$HARNESS_E2E_LOCK_DIR"
    return
  fi

  if [ -n "${WORK_LOG_ROOT:-}" ]; then
    vault="$WORK_LOG_ROOT"
  else
    local cfg="$HOME/.claude/work-log.json"
    if [ -f "$cfg" ]; then
      vault=$(sed -n 's/.*"root"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$cfg" | head -1)
    fi
  fi

  case "$vault" in
    /*)
      if [ -d "$vault" ]; then
        printf '%s' "$vault/.wiki/e2e-locks"
        return
      fi
      ;;
  esac

  printf '%s' "/tmp/harness-e2e-locks"
}

# serverUrl 이든 host:port 든 파일명으로 안전한 키로 정규화한다.
#   http://localhost:8080/api -> localhost-8080
normalize_key() {
  local k
  k=$(printf '%s' "${1:-}" \
    | sed -e 's#^[A-Za-z][A-Za-z0-9+.-]*://##' \
          -e 's#[/?#].*$##' \
          -e 's#[^A-Za-z0-9._-]#-#g' \
          -e 's#^-*##' -e 's#-*$##')
  [ -n "$k" ] || k="default"
  printf '%s' "$k"
}

# 호출자가 실행별 토큰을 보관해 매 호출 전달한다. uid/포트 공유 토큰은 없다.
# 소유권 확인과 변경 사이에 다른 acquire/reap/release가 끼어들지 않도록
# 짧은 파일 조작만 직렬화한다. E2E 실행/대기 동안에는 guard를 보유하지 않는다.
drop_guard() {
  if [ "$GUARD_HELD" = 1 ]; then
    rm -f "$GUARD/pid"
    rmdir "$GUARD" 2>/dev/null || true
    GUARD_HELD=0
  fi
}

take_guard() {
  local attempt
  for ((attempt=0; attempt<50; attempt++)); do
    if mkdir "$GUARD" 2>/dev/null; then
      GUARD_HELD=1
      printf '%s\n' "$$" > "$GUARD/pid" || die "guard 기록 실패: $GUARD"
      return 0
    fi
    sleep 0.1
  done
  die "락 메타데이터 잠금 실패: $GUARD (pid 확인 후 종료된 호출의 guard만 정리)"
}

trap drop_guard EXIT
trap 'exit 1' HUP INT TERM

read_field() {
  [ -f "$OWNER" ] || return 1
  sed -n "s/^$1=//p" "$OWNER" 2>/dev/null | head -1
}

mtime_of() {
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null
}

# owner 파일 기준 경과 시간. owner 가 아직 없으면(mkdir 직후 죽은 경우 포함)
# 락 디렉토리 mtime 으로 대체한다.
owner_age() {
  local target="$OWNER"
  [ -f "$target" ] || target="$LOCK"
  [ -e "$target" ] || return 1
  local m
  m=$(mtime_of "$target") || return 1
  [ -n "$m" ] || return 1
  printf '%s' $(( $(now) - m ))
}

write_owner() {
  {
    printf 'token=%s\n' "$1"
    printf 'pid=%s\n' "$$"
    printf 'host=%s\n' "$(hostname 2>/dev/null || echo unknown)"
    printf 'started=%s\n' "$(now)"
    printf 'label=%s\n' "$LABEL"
  } > "$OWNER"
}

# 락 디렉토리는 owner 파일을 품고 있어 rm -rf 가 2단계다. 지우는 도중 다른
# 에이전트가 정상 획득하면 그 락을 지워버리므로, 원자적 rename 으로 먼저
# 소유권을 확보한 뒤 삭제한다. 두 회수자가 경쟁해도 mv 는 한쪽만 성공한다.
reap() {
  local tmp="$LOCK.reap.$$.${RANDOM}"
  if mv "$LOCK" "$tmp" 2>/dev/null; then
    rm -rf "$tmp"
    return 0
  fi
  return 1
}

# 회수 도중 중단돼 남은 잔여물 정리 (TTL 을 넘긴 것만).
cleanup_reaps() {
  local d age m
  for d in "$ROOT"/*.reap.*; do
    [ -d "$d" ] || continue
    m=$(mtime_of "$d") || continue
    age=$(( $(now) - m ))
    [ "$age" -gt "$TTL" ] && rm -rf "$d"
  done
  return 0
}

# --- 명령 --------------------------------------------------------------------

cmd_acquire() {
  mkdir -p "$ROOT" || die "락 디렉토리를 만들 수 없습니다: $ROOT"
  cleanup_reaps

  local mine deadline waited age holder
  mine="$TOKEN"
  deadline=$(( $(now) + TIMEOUT ))
  waited=0

  while :; do
    take_guard
    if mkdir "$LOCK" 2>/dev/null || { [ ! -d "$LOCK" ] && mkdir "$LOCK" 2>/dev/null; }; then
      if ! write_owner "$mine"; then
        reap
        die "소유권 기록 실패: $LOCK"
      fi
      printf 'ACQUIRED key=%s waited=%ss lock=%s\n' "$KEY" "$waited" "$LOCK"
      return 0
    fi

    # mkdir 실패가 EEXIST(다른 보유자)가 아니면 환경 오류(권한·파일시스템) — 대기하지 않고 즉시 실패(exit 1).
    # 위에서 디렉토리 부재 시 1회 재시도했으므로, 보유자가 그 사이 해제한 경우는 이미 획득 경로로 빠져 있다.
    [ -d "$LOCK" ] || die "락 디렉토리를 만들 수 없습니다(권한·파일시스템 확인): $LOCK"

    # 재진입 — 이미 내가 들고 있으면 heartbeat 만 갱신하고 통과시킨다.
    holder="$(read_field token || true)"
    if [ -n "$mine" ] && [ "$mine" = "$holder" ]; then
      touch "$OWNER" 2>/dev/null || die "heartbeat 갱신 실패: $OWNER"
      printf 'ALREADY_HELD key=%s lock=%s\n' "$KEY" "$LOCK"
      return 0
    fi

    age="$(owner_age || true)"
    if [ -n "$age" ] && [ "$age" -gt "$TTL" ]; then
      if reap; then
        printf 'REAPED key=%s age=%ss ttl=%ss (죽은 락 회수)\n' "$KEY" "$age" "$TTL" >&2
      fi
      drop_guard
      continue
    fi

    if [ "$(now)" -ge "$deadline" ]; then
      printf 'TIMEOUT key=%s waited=%ss holder_label=%s holder_pid=%s age=%ss\n' \
        "$KEY" "$waited" "$(read_field label || echo '?')" \
        "$(read_field pid || echo '?')" "${age:-?}"
      return 2
    fi

    drop_guard
    sleep "$POLL"
    waited=$(( waited + POLL ))
  done
}

cmd_beat() {
  local mine holder
  [ -d "$ROOT" ] || return 1
  take_guard
  mine="$TOKEN"
  holder="$(read_field token || true)"
  if [ -n "$mine" ] && [ "$mine" = "$holder" ]; then
    touch "$OWNER" 2>/dev/null || die "heartbeat 갱신 실패: $OWNER"
    printf 'BEAT key=%s\n' "$KEY"
    return 0
  fi
  printf 'BEAT_SKIP key=%s (보유자가 아닙니다)\n' "$KEY"
  return 1
}

cmd_release() {
  [ -d "$ROOT" ] || return 0
  take_guard
  if [ ! -d "$LOCK" ]; then
    printf 'NOT_HELD key=%s (락이 이미 없습니다)\n' "$KEY"
    return 0
  fi

  local holder
  holder="$(read_field token || true)"
  if [ "$holder" = "$TOKEN" ]; then
    reap || die "락 해제 실패: $LOCK"
    printf 'RELEASED key=%s\n' "$KEY"
    return 0
  fi

  # 잘못된 토큰은 다른 보유자의 디렉토리를 이동/삭제하지 않는다.
  printf 'RELEASE_DENIED key=%s (다른 에이전트가 보유 중입니다)\n' "$KEY"
  return 1
}

cmd_status() {
  printf 'lock_root=%s\n' "$ROOT"
  [ -d "$ROOT" ] || { printf '(락 없음)\n'; return 0; }

  local d k age
  local found=0
  for d in "$ROOT"/*.lock; do
    [ -d "$d" ] || continue
    k=$(basename "$d" .lock)
    [ -n "${KEY_FILTER:-}" ] && [ "$k" != "$KEY_FILTER" ] && continue
    found=1
    LOCK="$d"; OWNER="$d/owner"
    age="$(owner_age || echo '?')"
    printf '  %-28s age=%ss pid=%s label=%s\n' \
      "$k" "$age" "$(read_field pid || echo '?')" "$(read_field label || echo '-')"
  done
  [ "$found" = 1 ] || printf '(보유 중인 락 없음)\n'
  return 0
}

# --- 진입점 ------------------------------------------------------------------

CMD="${1:-}"
[ -n "$CMD" ] || usage
shift || true

case "$CMD" in
  acquire|beat|release) RAW_KEY="${1:-}"; [ -n "$RAW_KEY" ] || die "key 가 필요합니다"; shift ;;
  status)               # key 는 선택. 옵션(--*)을 key 로 삼키지 않는다.
                        RAW_KEY=""
                        case "${1:-}" in
                          ""|--*) : ;;
                          *) RAW_KEY="$1"; shift ;;
                        esac ;;
  -h|--help|help)       usage ;;
  --version)            printf 'e2e-lock.sh %s\n' "$VERSION"; exit 0 ;;
  *)                    die "알 수 없는 명령: $CMD" ;;
esac

while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || die "옵션 값이 필요합니다: $1"
  case "$1" in
    --token)   TOKEN="$2";     shift 2 ;;
    --timeout) TIMEOUT="${2:-}"; shift 2 ;;
    --ttl)     TTL="${2:-}";     shift 2 ;;
    --poll)    POLL="${2:-}";    shift 2 ;;
    --label)   LABEL="${2:-}";   shift 2 ;;
    *) die "알 수 없는 옵션: $1" ;;
  esac
done

for value in "$TIMEOUT" "$TTL" "$POLL"; do
  case "$value" in ''|*[!0-9]*) die "--timeout/--ttl/--poll 은 정수(초)여야 합니다" ;; esac
done
[ "$POLL" -ge 1 ] || POLL=1

if [ "$CMD" != status ]; then
  case "$TOKEN" in ''|*[!A-Za-z0-9._-]*) die "실행별 --token 이 필요합니다 (영문·숫자·._-만 허용)" ;; esac
fi

ROOT="$(resolve_lock_root)"
KEY="$(normalize_key "$RAW_KEY")"
KEY_FILTER=""
[ -n "$RAW_KEY" ] && KEY_FILTER="$KEY"
LOCK="$ROOT/$KEY.lock"
OWNER="$LOCK/owner"
GUARD="$ROOT/$KEY.guard"

case "$CMD" in
  acquire) cmd_acquire ;;
  beat)    cmd_beat ;;
  release) cmd_release ;;
  status)  cmd_status ;;
esac
