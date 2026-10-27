# Third-party work bundled or depended on

DepartureBoard is GPL-3.0 (see `LICENSE`). It ships or depends on:

| What | Where | Licence |
|---|---|---|
| Oswald, JetBrains Mono, Nunito (the board's fonts, bundled so the board works offline) | `app/static/fonts/` — see its `README.md` | SIL Open Font License 1.1, texts beside each file |
| `segno` — draws the QR codes (`POST /api/images/qr`); pure Python, no native code | a dependency in `pyproject.toml` | BSD-3-Clause — <https://github.com/heuer/segno> |
| The built-in backgrounds (*terminal*, *wood*, *gala*, *paper*) | `app/static/backgrounds/` | drawn by this project, GPL-3.0 with the rest |
| Lucide 1.61.0 — the icons in the chrome (the tabs, menus, buttons and the board's corner controls), the 27 used vendored as one sprite by `scripts/lucide-sprite.py` | `app/static/icons/lucide.svg`, the licence text in `app/static/icons/LICENSE-lucide.txt` | ISC — <https://lucide.dev> |

The Python stack (FastAPI, SQLAlchemy, Alembic, Jinja2, pydantic-settings, uvicorn) is installed from
PyPI at build time and is not bundled in this repository; `uv.lock` names every version.
