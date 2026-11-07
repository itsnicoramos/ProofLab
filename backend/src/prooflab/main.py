"""App factory. Run with: ``uvicorn prooflab.main:create_app --factory``."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from prooflab import __version__
from prooflab.api.routes import router
from prooflab.content import Registry, load_registry


class Settings(BaseModel):
    """Runtime settings (SPEC §7). Read from ``PROOFLAB_*`` environment variables."""

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    check_timeout: float = Field(default=10.0, gt=0)
    isolate: bool = True
    max_concurrent_checks: int = Field(default=4, ge=1)
    busy_wait: float = Field(default=2.0, ge=0)
    # The student's progress database (SPEC §17). None = PROOFLAB_DB or the per-user default.
    db_path: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        values: dict[str, object] = {}
        if origins := env.get("PROOFLAB_CORS_ORIGINS"):
            values["cors_origins"] = [o.strip() for o in origins.split(",") if o.strip()]
        if timeout := env.get("PROOFLAB_CHECK_TIMEOUT"):
            values["check_timeout"] = float(timeout)
        if isolate := env.get("PROOFLAB_ISOLATE"):
            values["isolate"] = isolate.strip() not in {"0", "false", "no"}
        if slots := env.get("PROOFLAB_MAX_CONCURRENT_CHECKS"):
            values["max_concurrent_checks"] = int(slots)
        if db := env.get("PROOFLAB_DB"):
            values["db_path"] = db
        return cls.model_validate(values)


def create_app(settings: Settings | None = None, registry: Registry | None = None) -> FastAPI:
    """Build the API. Content is loaded and validated here, so bad content fails startup."""
    logging.basicConfig(level=logging.INFO)
    settings = settings or Settings.from_env()
    registry = registry or load_registry()

    app = FastAPI(
        title="ProofLab",
        version=__version__,
        description="Deterministic, step-by-step checking of university math work. No AI.",
    )
    app.state.settings = settings
    app.state.registry = registry
    # Opened on first use, so serving problems never touches the progress database.
    app.state.db_path = str(Path(settings.db_path).expanduser()) if settings.db_path else None
    app.state.check_slots = threading.BoundedSemaphore(settings.max_concurrent_checks)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    return app
