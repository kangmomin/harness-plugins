#!/usr/bin/env bash
# Required verification; installs nothing and never uses an external application DB.
set -euo pipefail
cd "$(dirname "$0")/.."
export HARNESS_REQUIRE_OPENAPI=1 HARNESS_REQUIRE_POSTGRES=1 HARNESS_REQUIRE_GO=1 HARNESS_REQUIRE_GRPC=1
bash scripts/check-plugins.sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B -m unittest discover -s work-log/tests -p 'test_*.py' -v
node --test work-log/tests/*.test.js
node --test tests/docgen.test.mjs
python3 -B tests/fixtures/fe-components/verify.py
python3 -B tests/fixtures/grpcurl/verify.py
