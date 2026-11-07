"""Vercel entrypoint (SPEC §18): the same app, configured for a serverless host.

Vercel has no lasting disk and no macOS, so on Vercel the progress database is off (progress
stays in each browser), checks run in-process instead of in worker processes, and the reader
can only read text files (no Apple Vision). Locally, run ``uvicorn prooflab.main:create_app``.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
os.environ.setdefault("PROOFLAB_ISOLATE", "0")
os.environ.setdefault("PROOFLAB_STORE", "0")
os.environ.setdefault("PROOFLAB_CORS_ORIGINS", "*")

from prooflab.main import create_app  # noqa: E402

app = create_app()
