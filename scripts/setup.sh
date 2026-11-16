#!/bin/sh
# One-step setup for the ProofLab tutor on Linux or macOS (POSIX sh).
#
#   scripts/setup.sh
#
# 1. installs the backend and the tutor's tools with uv,
# 2. starts the tutor's memory (Postgres in Docker, 127.0.0.1:5433) and creates its tables,
# 3. runs `prooflab-tutor doctor`, which says what is still missing and how to fix it.
#
# Without Docker the tutor still teaches and checks; it just can't save progress (SPEC §20).
set -eu
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is missing. Install it: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

echo "==> Installing the backend and the tutor's tools (uv sync --extra tutor)"
(cd backend && uv sync --extra tutor)

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "==> Starting the tutor's memory (Postgres on 127.0.0.1:5433)"
  docker compose up -d --wait tutor-db
  echo "==> Creating the memory's tables"
  uv run --project backend --extra tutor prooflab-tutor memory init
else
  echo "==> Docker isn't running, so the memory was skipped. The tutor still teaches and" \
    "checks. Start Docker and run this again to save progress."
fi

echo "==> Checking the setup"
uv run --project backend --extra tutor prooflab-tutor doctor
