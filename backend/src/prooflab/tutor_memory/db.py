"""Connecting to the tutor's Postgres memory and keeping its schema current (SPEC §20).

Configuration, first match wins:

- ``PROOFLAB_TUTOR_DATABASE_URL``: any Postgres URL.
- otherwise the repo's ``docker compose`` service ``tutor-db`` on 127.0.0.1:5433, with the
  password ``TUTOR_DB_PASSWORD`` (default ``prooflab-local``).

Both variables are also read from the repository's ``.env`` file when they aren't set in the
environment. ``PROOFLAB_TUTOR_DB_SCHEMA`` (default ``tutor``) picks the Postgres schema, so
tests can use a throwaway one.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
DEFAULT_PASSWORD = "prooflab-local"
DEFAULT_SCHEMA = "tutor"
START_HINT = "Start it from the repo root with: docker compose up -d tutor-db"
INSTALL_HINT = "Install the tutor extra: cd backend && uv sync --extra tutor"
_SCHEMA_RE = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")
_LOCK_KEY = 48_211_907  # pg_advisory_xact_lock key: one migration at a time


class MemoryUnavailable(RuntimeError):
    """The memory can't be used right now; the message says what to do."""


def _dotenv(path: Path | None = None) -> dict[str, str]:
    path = path or REPO_ROOT / ".env"
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _setting(name: str, dotenv: dict[str, str]) -> str | None:
    return os.environ.get(name) or dotenv.get(name) or None


def database_url() -> str:
    dotenv = _dotenv()
    if url := _setting("PROOFLAB_TUTOR_DATABASE_URL", dotenv):
        return url
    password = _setting("TUTOR_DB_PASSWORD", dotenv) or DEFAULT_PASSWORD
    return f"postgresql://prooflab:{quote(password, safe='')}@127.0.0.1:5433/prooflab_tutor"


def schema_name() -> str:
    name = _setting("PROOFLAB_TUTOR_DB_SCHEMA", _dotenv()) or DEFAULT_SCHEMA
    if not _SCHEMA_RE.match(name):
        raise MemoryUnavailable(f"PROOFLAB_TUTOR_DB_SCHEMA {name!r} isn't a plain schema name.")
    return name


def redact(url: str) -> str:
    """The URL with any password replaced, safe to print."""
    parts = urlsplit(url)
    if parts.password is None:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    user = f"{parts.username}:***@" if parts.username else "***@"
    return urlunsplit((parts.scheme, user + host, parts.path, parts.query, parts.fragment))


def migrations() -> list[tuple[int, str]]:
    out = []
    for path in sorted(SCHEMA_DIR.glob("[0-9][0-9][0-9]_*.sql")):
        out.append((int(path.name[:3]), path.read_text(encoding="utf-8")))
    return out


def _psycopg() -> Any:
    try:
        import psycopg
        import psycopg.sql  # noqa: F401 - psycopg.sql is used through the package
    except ImportError:
        raise MemoryUnavailable(f"The tutor memory needs psycopg. {INSTALL_HINT}") from None
    return psycopg


def migrate(conn: Any, schema: str) -> int:
    """Apply any migrations the schema doesn't have yet; returns the schema version."""
    psycopg = _psycopg()
    ident = psycopg.sql.Identifier(schema)
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
        conn.execute(psycopg.sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(ident))
        conn.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(ident))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            " version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        row = conn.execute("SELECT coalesce(max(version), 0) AS v FROM schema_version").fetchone()
        current = row["v"] if isinstance(row, dict) else row[0]
        for version, sql in migrations():
            if version > current:
                conn.execute(sql)
                conn.execute("INSERT INTO schema_version (version) VALUES (%s)", (version,))
                current = version
    return current


@contextmanager
def connect(url: str | None = None, schema: str | None = None) -> Iterator[Any]:
    """An open connection with the schema migrated and on the search path."""
    psycopg = _psycopg()
    from psycopg.rows import dict_row

    url = url or database_url()
    schema = schema or schema_name()
    try:
        conn = psycopg.connect(url, connect_timeout=3, row_factory=dict_row, autocommit=True)
    except psycopg.OperationalError as exc:
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        raise MemoryUnavailable(
            f"Can't reach the tutor memory at {redact(url)} ({first}). {START_HINT}"
        ) from None
    try:
        migrate(conn, schema)
        conn.execute(
            psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema))
        )
        yield conn
    finally:
        conn.close()
