# Multi-stage Dockerfile for Cloud Run deployment — mirrors sync/Dockerfile.
#
# Build stage uses uv to lock and install deps into a venv; runtime stage
# is python:3.12-slim with the venv copied over. Non-root user, PORT env
# (Cloud Run injects 8080 by default), and uvicorn as the ASGI server.
#
# Layer order is tuned for cache reuse: pyproject.toml + uv.lock change
# rarely, source code (incl. knowledge/ FAQ+jobs data) changes more often.

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

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy the project source (incl. knowledge/faq.yaml + jobs_summary.json,
# bundled into the image per Phase A design — see README.md "知識ベースの鮮度")
# and install the project itself (no deps).
COPY src/ src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ──────────────────────────────── Runtime stage ────────────────────────────

FROM python:3.12-slim AS runtime

# Non-root user — Cloud Run does not require this but defence-in-depth.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid 1001 --create-home --shell /sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PORT=8080

USER app

# Cloud Run injects PORT at runtime; sh -c interpolates it while keeping CMD
# in JSON form (correct signal forwarding for SIGTERM). `--host 0.0.0.0` is
# mandatory for Cloud Run. Workers stays at 1 — Cloud Run scales horizontally.
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn chatbot.app:app --host 0.0.0.0 --port ${PORT} --workers 1"]
