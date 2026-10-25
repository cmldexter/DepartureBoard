"""The guest link: a per-board token in a URL, a queue of posts, and the limits that keep the
first public write path narrow. The numbers here are the ones docs/guests.md promises."""

import hashlib
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Message, Post
from app.services import images
from app.services.display import display_settings
from app.services.text import capacity_error, layout

MAX_TEXT = 120  # characters in a post
MAX_NICK = 16  # a first name
MAX_PHOTO = images.MAX_BYTES  # 5 MB, the picture limit everywhere
PHOTO_TYPES = ("image/png", "image/jpeg", "image/webp")
PER_IP_HOUR = 20  # posts per hour from one address
PER_BOARD_HOUR = 200  # posts per hour for the whole board
PHOTO_ROWS = 4  # a guest photo keeps its shape at this height in cells
TOKEN_CHARS = 20
QR_SLUG = "guest-qr"  # the picture of the guest link, made by POST /api/guest/qr
QR_TOKEN = "{img:guest-qr}"
QR_TEXT = f"SCAN TO POST A PHOTO\n{QR_TOKEN}"  # the ready-made message, created disabled


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


# ---- approve = make a message


def photo_fit(size: Mapping[str, Any], rows_free: int, cols: int) -> tuple[int, int]:
    """The photo's block on this board: up to PHOTO_ROWS tall within the rows left under the
    text, as wide as keeps its shape, never wider than the board (then shorter to match)."""
    h = max(1, min(PHOTO_ROWS, rows_free))
    ar = size.get("ar")
    if not ar:
        return (max(1, min(cols, int(size["w"]))), max(1, min(h, int(size["h"]))))
    w = round(ar * images.CELL_ASPECT * h)
    if w > cols:
        w, h = cols, max(1, min(h, round(cols / (ar * images.CELL_ASPECT))))
    return (max(1, w), h)


def message_text(post: Post, d: Mapping[str, Any], sizes: Mapping[str, Any]) -> str:
    """The lines a post becomes: its text, the photo sized to the rows left, `- NICK` last."""
    words = [post.text] if post.text else []
    if post.nick:
        words.append(f"- {post.nick}")
    if not post.image:
        return "\n".join(words)
    used = len(layout("\n".join(words), d["rows"], d["cols"], sizes).rows) if words else 0
    w, h = photo_fit(sizes.get(post.image, images.LEGACY), d["rows"] - used, d["cols"])
    words.insert(1 if post.text else 0, f"{{img:{post.image}@{w}x{h}}}")
    return "\n".join(words)


def message_of(session: Session, post: Post) -> Message | None:
    return session.scalar(select(Message).where(Message.post_id == post.id))


def approve(session: Session, settings: Settings, post: Post) -> tuple[Message, str | None]:
    """Approve a post: make the message it becomes (or keep the one it has). Returns the message
    and, when the post does not fit the board, why it was left disabled instead of dropped."""
    post.status = "approved"
    if existing := message_of(session, post):
        return existing, None
    if post.image and images.find(settings, post.image) is None:
        post.image = None  # the photo was deleted from the Images panel; the words still count
    d = display_settings(session)
    sizes = images.sizes(settings)
    text = message_text(post, d, sizes)
    note = capacity_error(layout(text, d["rows"], d["cols"], sizes))
    m = Message(
        text=text,
        enabled=note is None,
        priority=d["guest_priority"],
        show_seconds=d["guest_show_seconds"],
        source="guest",
        post_id=post.id,
        created_by=post.nick or None,
    )
    session.add(m)
    session.flush()
    return m, note


def _drop_message(session: Session, post: Post) -> None:
    if m := message_of(session, post):
        session.delete(m)


def _drop_photo(settings: Settings, post: Post) -> None:
    if post.image and (path := images.find(settings, post.image)):
        images.remove(path)
    post.image = None


def reject(session: Session, settings: Settings, post: Post) -> None:
    """Take a post off the board (its message) and off the disk (its photo). The row stays, so
    the hour's count still sees it."""
    post.status = "rejected"
    _drop_message(session, post)
    _drop_photo(settings, post)


def remove(session: Session, settings: Settings, post: Post) -> None:
    """Reject, then forget the row too."""
    reject(session, settings, post)
    session.delete(post)


# ---- the QR that opens the guest page


def qr_messages(session: Session) -> list[Message]:
    """Every message that carries the guest QR — the ready-made one, or one the host wrote."""
    return list(session.scalars(select(Message).where(Message.text.contains(QR_TOKEN))))


def make_qr(
    session: Session, settings: Settings, url: str, source: str
) -> tuple[bool, Message, bool]:
    """Make (or remake) the picture of the guest link and the message that carries it.
    Returns (picture remade, the message, message created). The message is created disabled —
    the host switches it on when the party starts; an existing one keeps its state."""
    _, remade = images.save_qr(settings, QR_SLUG, url)
    existing = qr_messages(session)
    if existing:
        return remade, existing[0], False
    m = Message(text=QR_TEXT, enabled=False, source=source)
    session.add(m)
    session.flush()
    return remade, m, True


def refresh_qr(settings: Settings, url: str) -> bool:
    """After a rotate: the picture, when there is one, now carries the new link."""
    if images.find(settings, QR_SLUG) is None:
        return False
    images.save_qr(settings, QR_SLUG, url)
    return True


def disable_qr_messages(session: Session) -> int:
    """Guests off: a code to a closed door comes off the board."""
    found = qr_messages(session)
    for m in found:
        m.enabled = False
    return len(found)
