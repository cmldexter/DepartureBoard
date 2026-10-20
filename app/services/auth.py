"""The one secret: a bearer token that guards every write and the settings page.

Set DEPARTUREBOARD_API_TOKEN to bring your own. Otherwise a token is generated on first boot,
stored in <data_dir>/api_token (mode 0600) and printed once in the server log.
"""

import logging
import secrets
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings

log = logging.getLogger("departureboard")

TOKEN_FILE = "api_token"
COOKIE_NAME = "db_session"


def load_or_create_token(settings: Settings) -> str:
    if settings.api_token:
        return settings.api_token.strip()

    path: Path = settings.data_dir / TOKEN_FILE
    if path.exists():
        token = path.read_text().strip()
        if token:
            return token

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    path.write_text(token + "\n")
    path.chmod(0o600)
    log.warning(
        "\n"
        "============================================================\n"
        "  DepartureBoard API token (generated on first boot)\n"
        "  %s\n"
        "  Stored in %s. Use it to sign in at /settings and in the\n"
        "  Authorization: Bearer header. Keep it out of screenshots.\n"
        "============================================================",
        token,
        path,
    )
    return token


def _presented_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(COOKIE_NAME)


def token_matches(request: Request, candidate: str | None) -> bool:
    expected: str = request.app.state.api_token
    return bool(candidate) and secrets.compare_digest(candidate, expected)


def require_token(request: Request) -> None:
    """FastAPI dependency: 401 unless a valid bearer header or session cookie is present."""
    if not token_matches(request, _presented_token(request)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid token is required (Authorization: Bearer <token>).",
            headers={"WWW-Authenticate": "Bearer"},
        )


Authenticated = Depends(require_token)
