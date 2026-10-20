"""Uploaded images, shown on the board as one cell each via `{img:slug}`.

Plain files under <data_dir>/images/<slug>.<ext>; no table. Small by design: a cell is a few
centimetres on the TV, so 512 KB is plenty.
"""

import re
from pathlib import Path

from app.config import Settings

CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}
MEDIA_TYPES = {ext: ct for ct, ext in CONTENT_TYPES.items()}
MAX_BYTES = 512 * 1024
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def images_dir(settings: Settings) -> Path:
    d = settings.data_dir / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(name: str) -> str:
    stem = Path(name).stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")[:40]
    return slug or "image"


def find(settings: Settings, slug: str) -> Path | None:
    if not SLUG_RE.match(slug):
        return None
    for ext in MEDIA_TYPES:
        p = images_dir(settings) / f"{slug}.{ext}"
        if p.exists():
            return p
    return None


def list_all(settings: Settings) -> list[Path]:
    return sorted(p for p in images_dir(settings).iterdir() if p.suffix[1:] in MEDIA_TYPES)


def save(settings: Settings, slug: str, content_type: str, data: bytes) -> tuple[Path, bool]:
    """Write the file; returns (path, replaced). Other extensions of the slug are removed."""
    existing = find(settings, slug)
    for ext in MEDIA_TYPES:
        old = images_dir(settings) / f"{slug}.{ext}"
        if old.exists():
            old.unlink()
    path = images_dir(settings) / f"{slug}.{CONTENT_TYPES[content_type]}"
    path.write_bytes(data)
    return path, existing is not None


def describe(path: Path) -> dict:
    slug = path.stem
    return {
        "slug": slug,
        "url": f"/images/{slug}",
        "token": f"{{img:{slug}}}",
        "content_type": MEDIA_TYPES[path.suffix[1:]],
        "bytes": path.stat().st_size,
    }
