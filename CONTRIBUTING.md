# Contributing

Thanks for looking. DepartureBoard is small on purpose, and the best contributions keep it that way.

## The scope rule

**Two pages, zero configuration, one command.** The board page and the settings page; nothing to
configure before it runs; `docker compose up`.

Fits: a new theme, a new repeat rule, a keyboard shortcut, better TV support, a bug fix, docs,
an integration example under `integrations/`.

Does not fit: user accounts, a calendar or chat panel in the UI, a mobile app, a second board
type. Those start as a [discussion](https://github.com/cmldexter/DepartureBoard/discussions);
most of them are better done *outside* the app through the API, which is the point of the
`/integrate` page.

## Running it

```bash
uv sync
uv run fastapi dev app/main.py        # http://localhost:8000, reloads on change
uv run pytest
uv run ruff check . && uv run ruff format .
```

Or the container: `docker compose up --build` → `http://localhost:8080`.

## Making a change

1. Open an issue first for anything bigger than a small fix, so we agree on the shape.
2. Branch from `main`, keep the PR focused, add a test where one makes sense.
3. Run the checks above; CI runs the same.
4. For anything visual, attach a screenshot at 1920×1080 or a short recording.
5. Fill the PR template. A maintainer reviews every PR; `main` only changes through a reviewed PR.

Commit messages: `feat(board): …`, `fix(api): …`, `docs: …`, `infra: …`, `test: …`. Reference
the issue as `(#N)`.

## Dependencies

`uv.lock` is the truth; CI fails if `pyproject.toml` and the lock disagree (`uv lock --check`).
The base image and the `uv` binary in the `Dockerfile` are pinned by digest; Dependabot proposes
bumps. To bump by hand: `docker buildx imagetools inspect python:3.13-slim` and copy the index digest.

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
