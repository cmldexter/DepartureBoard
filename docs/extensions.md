# Extensions

Another Python package can add to the board without forking it. At startup the app looks up the
entry-point group **`departureboard.extensions`**; each entry names a `register(app, hooks)`
callable, and `hooks` is how the package adds what it adds. With no extension installed nothing
changes — the same two pages, the same API — and an extension that fails to load is logged and
skipped: the board never fails to start because of one.

The complete minimal example is [`examples/extension-hello/`](../examples/extension-hello/): a
tab, a router, one stored key. Read it beside this page.

## The shape of one

```
departureboard-hello/
├── pyproject.toml                 # the entry point
└── departureboard_hello/
    ├── __init__.py                # register(app, hooks)
    ├── templates/hello_tab.html   # the tab's panel
    └── static/hello.js, hello.css
```

```toml
# pyproject.toml
[project]
name = "departureboard-hello"
version = "0.1.0"
dependencies = []                  # not the core — see "Where the core comes from"

[project.entry-points."departureboard.extensions"]
hello = "departureboard_hello:register"
```

```python
# departureboard_hello/__init__.py
from pathlib import Path

HERE = Path(__file__).resolve().parent


def register(app, hooks):
    hooks.templates(HERE / "templates")
    hooks.static("hello", HERE / "static")
    hooks.tab("hello", "Hello", "hello_tab.html", script="hello.js", style="hello.css")
    hooks.router(router)
```

`register` runs inside `create_app()`, before the routers are included and before the database is
up. It should only *register*: anything that needs the database or the token is a startup task.

## Where the core comes from

The core is **not a wheel** — its import name is `app`, and the image runs it from `/app`. An
extension therefore installs *into the board's environment*, beside the core, and imports from
it (`from app.services.auth import Authenticated`). Two ways:

- **On a checkout**, for development and tests: `uv pip install -e path/to/your-extension` into the
  checkout's `.venv`, then `uv run fastapi dev app/main.py`.
- **In an image**, for running it:

  ```dockerfile
  FROM ghcr.io/cmldexter/departureboard:0.5.0
  COPY . /tmp/ext
  RUN uv pip install --python /app/.venv/bin/python /tmp/ext
  ```

  The image's `uv` is on the path and `/app` belongs to the `board` user it runs as.

Pin the core's **`major.minor`** (the image tag, or a git submodule at the release tag for your
tests). Within a minor version the hooks below only gain parameters; a breaking change to them
bumps the minor and says so in `CHANGELOG.md`. `GET /api/health` tells you what you are running:
`{"ok": true, "version": "0.5.0", "edition": "community", "extensions": [{"name": "hello", "version": "0.1.0"}]}`.

## The hooks

Every method of `hooks` records; `create_app()` applies. Names (`static`, tab ids) are lowercase
letters, digits, `-` or `_`.

### `hooks.router(router)`

Include a FastAPI `APIRouter` under your own prefix. The core's dependencies are yours to use:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.deps import get_session
from app.services.auth import Authenticated

router = APIRouter(prefix="/api/hello", tags=["hello"], dependencies=[Authenticated])


@router.get("")
def get_greeting(session: Session = Depends(get_session)) -> dict: ...
```

`Authenticated` is the board's token: `Authorization: Bearer …` or the settings page's session
cookie (a write authorised by the cookie must also send `X-Requested-With: DepartureBoard`, as the
page's own JavaScript does). Leave it off a route the TV must reach, as `/api/board/current` does.
Your routes appear in `/docs` under your tag.

### `hooks.templates(directory)`

A Jinja templates directory, searched **after** the app's own — a package cannot replace a core
page, and your templates can import the core's macros (`{% from "_icons.html" import icon %}`).

### `hooks.static(name, directory)`

Files served under **`/static/ext/<name>/`** (mounted ahead of `/static`). Reference them by that
path, or let the tab load them (`script=`, `style=`).

### `hooks.tab(id, label, template, script=None, style=None, order=100, icon="puzzle")`

A settings tab. On a desk it follows the six built-in tabs (by `order`, then id); on a phone, where
the bar holds six, extension tabs sit behind a **More** tab that is a page of rows, and your panel
starts with a *Back* row the core adds. `template` is the panel's fragment, included inside
`<div id="panel-<id>" class="panel">`; `script` and `style` are files in your static directory,
loaded once by the settings page; `icon` names a symbol in the chrome's sprite
(`app/static/icons/lucide.svg` — `puzzle` is there for you). A symbol the sprite lacks can travel
with your panel: inline a hidden `<svg><symbol id="lucide-<name>" …></symbol></svg>` at the top of
the template and name it in `icon=` — the tab button's `<use>` resolves it wherever it sits in the
document (keep to the sprite's conventions: `viewBox="0 0 24 24"`, stroke only, `currentColor`).

A transient board source of yours (below) shows on the Board tab's live card as *On the board for
a moment — not a message · N s left*, from the slot you return.

**The panel's contract**, so it reads as part of the page (the example does all of this):

- Sections are `<section id="…" aria-labelledby="…-heading">` with an `<h2>`; the ids are yours
  (`#hello`, `#hello-form`) — a hash naming one of your sections opens your tab.
- **The phone**: the owner's rule is *no long scrolling pages — a flow goes to a page and comes
  back*. A block the user edits is a `.sheet-block` inside a `.sheet-host` section, and a
  `<nav class="rows phone-only">` row with `data-sheet="<block id>" data-title="…"` opens it as a
  sheet. The core's `settings.js` does the rest (moves the block in, Back brings it home); a save
  that should close the sheet calls nothing — the user presses Back, or your script can click
  `#sheet-back`.
- A button with `data-reach="<block id>"` (and optionally `data-sel="<selector>"`) goes to that
  block: its sheet on a phone, the block itself on a desk — the pattern of the core's empty states.
- Buttons: the core's classes (`secondary`, `quiet`, `link`, `danger`) and `aria-busy="true"`
  while a request runs; the `icon(name)` macro for icons. Colours come from the page's tokens
  (`--surface`, `--border`, `--accent`, `--muted` …) so light and dark both work.
- Fetch with the page header: `{"X-Requested-With": "DepartureBoard"}` on every write.

### `hooks.migrations(directory)`

An Alembic version location of your own. Your revisions form a **second base** — `down_revision =
None` on the first, a `branch_labels` of your name, revision ids prefixed with it — and migrate
with the core's at boot (`upgrade heads`). Prefix your table names too.

```python
revision = "hello_0001"
down_revision = None
branch_labels = ("hello",)


def upgrade():
    op.create_table("hello_rows", sa.Column("id", sa.Integer, primary_key=True), ...)
```

### `hooks.on_startup(task)` · `hooks.on_shutdown(task)`

`async def task(app)` run inside the lifespan: startup after the database and the token are up
(`app.state.db`, `app.state.api_token`), shutdown — in reverse order — before the database is
disposed. A background job that outlives a request is `asyncio.create_task(...)` in a startup task,
cancelled in the shutdown one. Something that must run every few seconds is a loop in that task;
log and continue on error, as the core's calendar loop does.

### `hooks.board_source(provider)`

`provider(session, at, display) -> BoardSource | None`, asked by `GET /api/board/current`
**before** the rotation. Return `None` and the rotation runs as usual. Return a
`BoardSource(text, seconds=None, remaining=None, own=True, poll=None)` and the board shows your
text for now — laid out exactly as a message is (rows × cols, word-wrap, `{img:…}`, tokens),
with `message_id` null, `timer` from your slot when you give one, and your `poll` hint (seconds)
on the wire, which the TV honours instead of its `poll_seconds` until the hint is gone. Nothing is
written to `messages`; the `ETag` follows your text. Providers are asked in registration order;
the first with text wins the board; one that raises is logged and skipped for that poll. The core's
layout keeps the first rows of a text that is too long — trim or wrap for the board's
`display["rows"]` and `display["cols"]` yourself if you want the tail.

**Standing by.** Return `BoardSource(None, poll=1)` and the rotation shows exactly as always, but
the TV comes back every second: for a source that expects something any moment (a live caption
between two sentences, a sensor about to trip) and wants it on the flaps within a second of
having it, instead of at the display's next `poll_seconds`. The quickest hint of every source
that answered rides on the wire; the hint joins the `ETag`, so the TV learns when it is gone.
Standing by costs the server one cheap `304` per TV per second — stop when the moment has passed.

### `hooks.edition(name)`

Name the build: the settings page's footer (`<name> edition`) and `/api/health`'s `edition`.

## Your own settings

The core's `SettingsOut`/`SettingsPatch` stay the core's — an extension's keys do not go through
`PATCH /api/settings`. Keep them in the same table with your own prefix, through your own router:

```python
from app.models import Setting

KEY = "hello.greeting"  # the key column holds 40 characters

row = session.get(Setting, KEY)  # read
session.merge(Setting(key=KEY, value="HELLO"))
session.commit()  # write
```

A saved board (a profile) carries the core's display keys and messages, not yours; if a key of
yours should travel with a board, your router can read and write the profile's JSON file too.

## Testing against the core

Clone the core at the tag you pin (or add it as a git submodule), install your package editable
into its `.venv`, and run both suites from the core's checkout: `uv run pytest` and
`uv run pytest path/to/your/tests`. The core's `tests/conftest.py` gives you `settings`, `client`
and `token` fixtures; `TestClient(create_app(settings))` runs the lifespan, so your migrations and
startup tasks run. To test without installing, register the way the core's own tests do:

```python
from types import SimpleNamespace
from app import extensions

monkeypatch.setattr(
    extensions,
    "entry_points",
    lambda group: [
        SimpleNamespace(name="hello", load=lambda: register, dist=SimpleNamespace(version="0.1.0")),
    ],
)
```

(`tests/test_extensions.py` and `tests/test_example_extension.py` in the core are the reference.)

## What the plug is not

It is not a way to change a core page or a core route: templates are searched after the app's,
routes under your prefix. A change the core needs — a new hook, a parameter on an existing one —
is a public issue and a public PR here, worded on its own merits, and ships to everyone.
