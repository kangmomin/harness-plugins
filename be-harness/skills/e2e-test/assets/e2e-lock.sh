#!/usr/bin/env bash
# E2E socket-resource leases v2.0.0. Canonical copy: be-harness; FE is identical.
# acquire/beat/release/status KEY --token RUN_TOKEN [--timeout SEC --ttl SEC --poll SEC --label TEXT]
# Return: 0 success, 2 acquisition timeout, 1 other errors. Python >=3.9 + POSIX required.
# Stop all v1 E2E runs before upgrading; mixed lock protocols are unsupported.
set -uo pipefail
if [ "${1:-}" = --version ]; then
  printf '%s\n' 'e2e-lock.sh 2.0.0'
  exit 0
fi
exec python3 -I -B "$(dirname "$0")/e2e_lock.py" "$@"
