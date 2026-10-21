# AGENTS.md

Notes for coding agents working in this repository.

## What this is

A split-flap departure board for a TV. FastAPI serves two HTML pages (`/` the board, `/settings`
the message organizer) plus `/integrate`, a JSON API, and Swagger at `/docs`. SQLite in the data
volume. Vanilla JS and CSS on the board; no bundler, no SPA.

## Layout

| Path | What |
|---|---|
| `app/main.py` | App factory, lifespan (migrations + token bootstrap) |
| `app/__main__.py` · `app/services/tls.py` | `python -m app`: the container's start; optional HTTPS (own pair, or self-signed on first boot via `openssl`) |
| `app/config.py` | Env settings, prefix `DEPARTUREBOARD_` |
| `app/db.py` · `app/models.py` | SQLAlchemy 2, two tables; Alembic in `migrations/` |
| `app/routers/` | `pages.py` (HTML), `health.py`, and the API routers |
| `app/services/auth.py` | The bearer token; `require_token` dependency |
| `app/services/scheduler.py` | Which messages are live; rotation among equals |
| `app/services/text.py` | Message text → cells: the flap set (`static/flapset.json`), `{chip}` / `{img:slug}` / emoji tokens, word-wrap, capacity |
| `app/services/images.py` | Uploaded images under `<data_dir>/images/`, shown with `{img:slug}` |
| `app/deps.py` | `get_session`, `now` (tests set `app.state.clock`), `tz` |
| `app/templates/` · `app/static/` | Jinja2 pages; CSS, JS, themes, fonts |
| `integrations/` | curl examples, the Agent Skill, agent examples |
| `tests/` | pytest + httpx `TestClient` |

## Run, test, lint

```bash
uv sync
uv run fastapi dev app/main.py       # http://localhost:8000
DEPARTUREBOARD_TLS=self-signed uv run python -m app   # try HTTPS locally (no reload)
uv run pytest -q
uv run ruff check . && uv run ruff format .
docker compose -f compose.yaml -f compose.dev.yaml up --build   # http://localhost:8080 (compose.yaml alone pulls the published image)
```

Tests set `DEPARTUREBOARD_DATA_DIR` to a temp dir and build the app with `create_app()`.

## Rules

- `main` is protected: branch, PR, green CI, maintainer review.
- Every write endpoint uses `Depends(require_token)`. `GET /api/board/current` stays public.
- New schema = a new Alembic revision; the app migrates on startup.
- No CDN assets on the board page; it must work offline on a LAN.
- The flap set is `app/static/flapset.json`; `flap.js` mirrors it and a test keeps them equal.
- Keep the scope: two pages, zero configuration, one command (see `CONTRIBUTING.md`).
- Never commit tokens, `.env`, or anything from `data/`.
