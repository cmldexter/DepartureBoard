"""The guest link: a per-board token in a URL, a queue of posts, and the limits that keep the
first public write path narrow. The numbers here are the ones docs/guests.md promises."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Post
from app.services import images

MAX_TEXT = 120  # characters in a post
MAX_NICK = 16  # a first name
MAX_PHOTO = images.MAX_BYTES  # 5 MB, the picture limit everywhere
PHOTO_TYPES = ("image/png", "image/jpeg", "image/webp")
PER_IP_HOUR = 20  # posts per hour from one address
PER_BOARD_HOUR = 200  # posts per hour for the whole board
PHOTO_ROWS = 4  # a guest photo keeps its shape at this height in cells
TOKEN_CHARS = 20


def mint_token() -> str:
    return secrets.token_urlsafe(15)[:TOKEN_CHARS]  # 20 URL-safe characters


def client_ip(request: Request) -> str:
    """The poster's address: the first hop of X-Forwarded-For behind a proxy, else the peer."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def ip_hash(request: Request) -> str:
    """A short salted hash of the address — enough to count, not enough to name."""
    salt = request.app.state.api_token
    return hashlib.sha256(f"{salt}|{client_ip(request)}".encode()).hexdigest()[:16]


def posts_since(session: Session, since: datetime, ip: str | None = None) -> int:
    q = select(func.count(Post.id)).where(Post.created_at >= since.replace(tzinfo=None))
    if ip is not None:
        q = q.where(Post.ip_hash == ip)
    return int(session.scalar(q) or 0)


def over_limit(session: Session, at: datetime, ip: str) -> str | None:
    """A friendly line when the hour's limit is reached, else None."""
    since = at.astimezone(UTC) - timedelta(hours=1)
    if posts_since(session, since, ip) >= PER_IP_HOUR:
        return "That is a lot of posts from one phone — give it a little while."
    if posts_since(session, since) >= PER_BOARD_HOUR:
        return "The board is busy right now — try again in a little while."
    return None


def photo_block(px: tuple[int, int] | None) -> tuple[int, int]:
    """Cells wide × tall for a guest photo: PHOTO_ROWS tall, as wide as keeps its shape."""
    if not px or not px[0] or not px[1]:
        return (PHOTO_ROWS, PHOTO_ROWS)
    w = round(px[0] / px[1] * images.CELL_ASPECT * PHOTO_ROWS)
    return (min(images.MAX_W, max(1, w)), PHOTO_ROWS)
