# Contributing

Thanks for looking. DepartureBoard is small on purpose, and the best contributions keep it that way.

## The scope rule

**Two pages, zero configuration, one command.** The board page and the settings page; nothing to
configure before it runs; `docker compose up`.

### What we will add

- **A new theme** — a stylesheet under `app/static/themes/`, a bundled font, a row in the
  README's theme table.
- **A new repeat rule or scheduling detail** — "the first Monday of the month", "every other
  week", a holiday skip. The scheduler is one pure function with its clock injected; a rule is
  a small change and a few tests.
- **Better TV support** — a keep-awake path that works on a browser where the current ones do
  not, a kiosk recipe for `docs/tv-setup.md`, a fix for a remote-control quirk.

Also: bug fixes, accessibility, docs, and integration recipes under `integrations/`.

### What we will not add

- **A calendar, weather or chat panel in the UI** — post those to the board from outside with
  one `curl`; that is what `/integrate` and the agent bundle are for.
- **User accounts, roles or multiple boards** — one token, one board. A second board is a
  second container.
- **A mobile app or a hosted service** — the settings page works on a phone; the server is
  yours.

Those start as a [discussion](https://github.com/cmldexter/DepartureBoard/discussions/categories/ideas).
Most of them are better done *outside* the app through the API, which is the point of the
`/integrate` page. If an idea fits the rule, it becomes an issue with a milestone.

## Running it

```bash
uv sync
uv run fastapi dev app/main.py        # http://localhost:8000, reloads on change
uv run pytest
uv run ruff check . && uv run ruff format .
```

Or the container, built from your checkout:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build   # http://localhost:8080
```

(`compose.yaml` alone pulls the published image; `compose.dev.yaml` swaps in a local build.
Put `COMPOSE_FILE=compose.yaml:compose.dev.yaml` in `.env` to keep typing `docker compose up --build`.)

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

## Releasing (maintainers)

1. Bump `version` in `pyproject.toml` and `__version__` in `app/__init__.py` to the same value
   (a test checks they agree), run `uv lock`, add the entry to `CHANGELOG.md`, merge.
2. Tag and publish from `main`; the release notes are the changelog entry:

   ```bash
   V=0.1.0
   awk -v v="$V" '/^## \[/{p = ($2 == "[" v "]")} p' CHANGELOG.md | tail -n +2 > /tmp/notes.md
   gh release create "v$V" --title "v$V" --notes-file /tmp/notes.md
   ```

3. The tag runs `release.yml`: it builds amd64 + arm64, pushes
   `ghcr.io/cmldexter/departureboard:{X.Y.Z, X.Y, latest}`, attests provenance, then pulls the
   image on a clean runner and checks `/api/health` reports the tag's version. A tag that does
   not match the code fails on the first step.
4. After the **first** release only: make sure the package is public —
   `gh api user/packages/container/departureboard --jq .visibility`; if it says `private`,
   set it to public in the package's settings on GitHub.

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
