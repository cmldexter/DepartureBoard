"""Uploaded videos, played muted in a loop behind the board (`background_image: video:<slug>`).

Plain files under <data_dir>/videos/<slug>.<ext>, no table and no sidecar: the browser reads the
file's own header, the server only stores and serves it. A video is big (a 1080p minute is tens
of MB), so an upload is streamed to disk in chunks and never held in memory.
"""

import os
import re
from pathlib import Path
from typing import Protocol

from app.config import Settings

CONTENT_TYPES = {
    "video/mp4": "mp4",
    "video/webm": "webm",
}
MEDIA_TYPES = {ext: ct for ct, ext in CONTENT_TYPES.items()}
MAX_BYTES = 250 * 1024 * 1024  # a 1080p h264 clip of a few minutes; the docs show how to shrink
CHUNK = 1024 * 1024
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class TooBig(ValueError):
    """The upload passed MAX_BYTES; nothing was kept."""


class Readable(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


def videos_dir(settings: Settings) -> Path:
    d = settings.data_dir / "videos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(name: str) -> str:
    stem = Path(name).stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")[:40]
    return slug or "video"


def find(settings: Settings, slug: str) -> Path | None:
    if not SLUG_RE.match(slug):
        return None
    for ext in MEDIA_TYPES:
        p = videos_dir(settings) / f"{slug}.{ext}"
        if p.exists():
            return p
    return None


def list_all(settings: Settings) -> list[Path]:
    return sorted(p for p in videos_dir(settings).iterdir() if p.suffix[1:] in MEDIA_TYPES)


async def save_stream(
    settings: Settings, slug: str, content_type: str, upload: Readable, limit: int | None = None
) -> tuple[Path, bool]:
    """Write the upload in chunks to `<slug>.<ext>` through a temp file; (path, replaced).

    Over `limit` (MAX_BYTES by default) the temp file is removed and TooBig raised; an empty
    upload raises ValueError. Replacing a slug removes a file of the other container type.
    """
    limit = MAX_BYTES if limit is None else limit
    ext = CONTENT_TYPES[content_type]
    path = videos_dir(settings) / f"{slug}.{ext}"
    tmp = path.with_name(f".{slug}.{ext}.part")
    existing = find(settings, slug)
    total = 0
    try:
        with tmp.open("wb") as out:
            while chunk := await upload.read(CHUNK):
                total += len(chunk)
                if total > limit:
                    raise TooBig(limit)
                out.write(chunk)
        if total == 0:
            raise ValueError("Empty file.")
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    if existing is not None and existing != path:
        existing.unlink(missing_ok=True)
    os.replace(tmp, path)
    return path, existing is not None


def remove(path: Path) -> None:
    path.unlink(missing_ok=True)


def describe(path: Path) -> dict:
    return {
        "slug": path.stem,
        "url": f"/videos/{path.stem}",
        "token": f"video:{path.stem}",
        "content_type": MEDIA_TYPES[path.suffix[1:]],
        "bytes": path.stat().st_size,
    }
