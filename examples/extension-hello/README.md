# departureboard-hello

The smallest complete extension, as described in [`docs/extensions.md`](../../docs/extensions.md):
a **Hello** tab on the settings page with one field, a router `GET`/`PUT /api/hello` behind the
board's token, and one key of its own in the settings table (`hello.greeting`). No migration, no
background task — those are two more lines, shown in the doc.

## Try it on a checkout

```bash
uv pip install -e examples/extension-hello     # into the checkout's .venv
uv run fastapi dev app/main.py                 # Settings → Hello; /api/health lists it
```

## Try it in the image

```dockerfile
FROM ghcr.io/cmldexter/departureboard:0.5.0
COPY examples/extension-hello /tmp/hello
RUN uv pip install --python /app/.venv/bin/python /tmp/hello
```

The board finds it at startup through the entry point in `pyproject.toml`; nothing else to configure.
