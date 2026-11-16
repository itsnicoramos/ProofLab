#!/bin/sh
# Claude Code PreToolUse hook for the ProofLab tutor (SPEC §22).
#
# The tutor skill registers this in its frontmatter, so it runs only in sessions that used
# /tutor. It reads the hook's JSON on stdin and stops a tool call that breaks one of the
# tutor's hard rules: reading exercise files or credentials, starting a server, touching a
# database directly, or writing files. The rules live in backend/src/prooflab/tutor_guard.py.
#
# The guard fails closed: if it can't run (no guard file, no Python), the call is blocked
# with the fix, never let through. It needs only the standard library, so any Python 3 works.
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
guard="$root/backend/src/prooflab/tutor_guard.py"

deny() {
  echo "Blocked by ProofLab's tutor guard (guard-error). $1 so every tool call is stopped" \
    "to be safe. Fix: $2, then try again." >&2
  exit 2
}

[ -f "$guard" ] || deny "The guard file $guard is missing," "restore it with git checkout"

for python in "$root/backend/.venv/bin/python" python3 python; do
  if command -v "$python" >/dev/null 2>&1; then
    exec "$python" "$guard" "$root"
  fi
done
# No Python on PATH: a uv-managed one works too (--no-project skips syncing the backend).
if command -v uv >/dev/null 2>&1; then
  exec uv run --quiet --no-project python "$guard" "$root"
fi
deny "No Python 3 was found," "install Python 3 or uv, or run: cd backend && uv sync"
