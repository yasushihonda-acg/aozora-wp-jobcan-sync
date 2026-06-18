# Phase 2A.2 — multi-stage Dockerfile for Cloud Run deployment.
#
# Build stage uses uv to lock and install deps into a venv; runtime stage
# is python:3.12-slim with the venv copied over. Non-root user, PORT env
# (Cloud Run injects 8080 by default), and uvicorn as the ASGI server.
#
# Layer order is tuned for cache reuse: pyproject.toml + uv.lock change
# rarely, source code changes every commit. Putting the deps install
# above the COPY of src/ means most rebuilds reuse the cached venv.

# ─────────────────────────────── Build stage ───────────────────────────────

FROM python:3.12-slim AS builder

# uv pinned to a specific minor for reproducibility — bump deliberately.
COPY --from=ghcr.io/astral-sh/uv:0.5.1 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Copy only the files needed to resolve deps first so the layer is cached
# until pyproject.toml / uv.lock actually change.
COPY pyproject.toml uv.lock ./

# `uv sync --frozen --no-install-project` builds just the deps into .venv;
# the project itself is installed in the next layer so source changes don't
# bust the deps cache.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy the project source and install the project itself (no deps).
COPY src/ src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ──────────────────────────────── Runtime stage ────────────────────────────

FROM python:3.12-slim AS runtime

# Non-root user — Cloud Run does not require this but defence-in-depth.
# Fixed UID/GID for reproducibility across builds.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid 1001 --create-home --shell /sbin/nologin app

WORKDIR /app

# Copy the prepared venv and source from the build stage. Owning everything
# as `app` avoids runtime chown overhead.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

# Make the venv the default interpreter and add the package to PYTHONPATH.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

USER app

# Cloud Run injects PORT at runtime; sh -c is the cleanest way to interpolate
# it while keeping CMD in JSON form (recommended for correct signal forwarding
# — `docker stop` and Cloud Run shutdown need PID 1 to receive SIGTERM).
# `--host 0.0.0.0` is mandatory for Cloud Run (default 127.0.0.1 is unreachable).
# Workers stays at 1 — Cloud Run scales horizontally, not via worker processes.
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn sync.app:app --host 0.0.0.0 --port ${PORT} --workers 1"]
