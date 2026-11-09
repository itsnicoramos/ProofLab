#!/bin/sh
# Claude Code PreToolUse hook for the ProofLab tutor (SPEC §22).
#
# The tutor skill registers this in its frontmatter, so it runs only in sessions that used
# /tutor. It reads the hook's JSON on stdin and stops a tool call that breaks one of the
# tutor's hard rules: reading exercise files or credentials, starting a server, touching a
# database directly, or writing files. The rules live in backend/src/prooflab/tutor_guard.py.
#
# No Python means no guard, not a blocked lesson: the tutor's own rules still apply.
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
guard="$root/backend/src/prooflab/tutor_guard.py"
[ -f "$guard" ] || exit 0
for python in "$root/backend/.venv/bin/python" python3 python; do
  if command -v "$python" >/dev/null 2>&1; then
    exec "$python" "$guard" "$root"
  fi
done
exit 0
