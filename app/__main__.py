"""`python -m app`: how the container starts. Runs uvicorn, with HTTPS when configured.

Development keeps `uv run fastapi dev app/main.py` (reload, plain http). To try HTTPS locally:
`DEPARTUREBOARD_TLS=self-signed uv run python -m app` (no reload).
"""

import logging

import uvicorn

from app.config import Settings, get_settings
from app.services.tls import tls_paths

HOST = "0.0.0.0"  # the container's port is published by compose
PORT = 8000


def main(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    paths = tls_paths(settings)
    cert, key = (str(paths[0]), str(paths[1])) if paths else (None, None)
    uvicorn.run("app.main:app", host=HOST, port=PORT, ssl_certfile=cert, ssl_keyfile=key)


if __name__ == "__main__":
    main()
