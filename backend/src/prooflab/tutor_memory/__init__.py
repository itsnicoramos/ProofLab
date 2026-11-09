"""The repo tutor's memory in Postgres (SPEC §20). Only the tutor CLI uses this package; the
site and its SQLite progress database never touch it.

``psycopg`` is an optional extra (``uv sync --extra tutor``), so importing the query module
is deferred until a memory command actually runs.
"""

from prooflab.tutor_memory.db import MemoryUnavailable, connect, database_url, redact, schema_name

__all__ = ["MemoryUnavailable", "connect", "database_url", "redact", "schema_name"]
