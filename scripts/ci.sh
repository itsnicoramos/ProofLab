#!/bin/sh
# Every check a pull request must pass (CONTRIBUTING.md), in one place for laptops and CI.
#
#   scripts/ci.sh            backend and frontend
#   scripts/ci.sh backend    ruff, ruff format, pytest
#   scripts/ci.sh frontend   npm ci, npm test, tsc, eslint
#
# The tutor memory tests run only when PROOFLAB_TUTOR_TEST_DATABASE_URL points at a throwaway
# Postgres (each test makes its own schema and drops it). Never point it at real memory.
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
part="${1:-all}"

backend() {
  echo "==> Backend"
  cd "$root/backend"
  uv sync --locked --extra tutor
  uv run ruff check src tests
  uv run ruff format --check src tests
  if [ -z "${PROOFLAB_TUTOR_TEST_DATABASE_URL:-}" ]; then
    echo "    (PROOFLAB_TUTOR_TEST_DATABASE_URL isn't set: the memory tests will be skipped)"
  fi
  uv run pytest
}

frontend() {
  echo "==> Frontend"
  cd "$root/frontend"
  npm ci
  npm test
  npx tsc --noEmit
  npm run lint
}

case "$part" in
  backend) backend ;;
  frontend) frontend ;;
  all) backend; frontend ;;
  *) echo "usage: scripts/ci.sh [backend|frontend|all]" >&2; exit 1 ;;
esac
echo "==> All checks passed ($part)"
