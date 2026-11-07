# syntax=docker/dockerfile:1.7
# ProofLab backend: multi-stage build on python:3.12-slim.
#   docker build -t prooflab .                     # runtime image
#   docker build --target test -t prooflab-test .  # runs the test suite on Python 3.12

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM builder AS test
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
COPY tests ./tests
RUN uv run --frozen pytest

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 10001 prooflab
COPY --from=builder --chown=prooflab:prooflab /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER prooflab
WORKDIR /app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status != 200)"]
CMD ["uvicorn", "prooflab.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
