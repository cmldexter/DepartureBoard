# python:3.13-slim — pinned by digest (multi-arch index). Dependabot bumps it.
FROM python:3.15-slim@sha256:2da676046630d7bf14c6764ae1143dc7fa0377a53f94bf5a642f0b214aca5bce

# uv 0.13.1 — pinned by digest.
COPY --from=ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEPARTUREBOARD_DATA_DIR=/data \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid 10001 board \
 && useradd --uid 10001 --gid board --create-home board \
 && mkdir -p /app /data \
 && chown board:board /app /data

WORKDIR /app
USER board

# Dependencies first, so the layer is cached while the app changes.
COPY --chown=board:board pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --python /usr/local/bin/python3

COPY --chown=board:board app ./app
COPY --chown=board:board migrations ./migrations
COPY --chown=board:board alembic.ini llms.txt ./

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
