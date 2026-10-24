"""Uploaded images, shown on the board with `{img:slug}` — one cell, or a block of cells.

Plain files under <data_dir>/images/<slug>.<ext>, no table. Beside each picture a sidecar
`<slug>.json` holds how it sits on the board: `w` × `h` cells, `fit`, and the pixel size read at
upload. A picture without a sidecar (uploaded before sizes existed) is one cell, stretched.
"""

import json
import re
from pathlib import Path
from typing import TypedDict

from app.config import Settings
from app.services.imagesize import dimensions

CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}
MEDIA_TYPES = {ext: ct for ct, ext in CONTENT_TYPES.items()}
MAX_BYTES = 512 * 1024
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

# A block is at most the biggest board (custom 36 × 10); the preset in use may be smaller, and
# a message whose picture does not fit is refused at save time with the board's size.
MAX_W, MAX_H = 36, 10
FITS = ("contain", "cover", "stretch")
CELL_ASPECT = 1.45  # a flap cell is 1 wide × 1.45 tall; the gap between cells is ignored


class Size(TypedDict):
    w: int
    h: int
    fit: str
    ar: float | None  # pixel aspect (width / height), None when unknown


LEGACY: Size = {"w": 1, "h": 1, "fit": "stretch", "ar": None}


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


def _sidecar(path: Path) -> Path:
    return path.with_suffix(".json")


def _read_meta(path: Path) -> dict:
    try:
        meta = json.loads(_sidecar(path).read_text())
    except (OSError, ValueError):
        return {}
    return meta if isinstance(meta, dict) else {}


def _write_meta(path: Path, meta: dict) -> None:
    _sidecar(path).write_text(json.dumps(meta, separators=(",", ":")))


def _px(path: Path, meta: dict) -> list[int] | None:
    """The pixel size: from the sidecar, else read from the file (a picture uploaded before
    sidecars existed still gets its suggestions)."""
    px = meta.get("px")
    if isinstance(px, list) and len(px) == 2:
        return px
    try:
        found = dimensions(path.read_bytes())
    except OSError:
        return None
    return list(found) if found else None


def _size_of(meta: dict) -> Size:
    if not meta:
        return dict(LEGACY)
    px = meta.get("px")
    ar = (px[0] / px[1]) if isinstance(px, list) and len(px) == 2 and px[0] and px[1] else None
    w = min(MAX_W, max(1, int(meta.get("w", 1))))
    h = min(MAX_H, max(1, int(meta.get("h", 1))))
    fit = meta.get("fit") if meta.get("fit") in FITS else "contain"
    return {"w": w, "h": h, "fit": fit, "ar": ar}


def size_of(path: Path) -> Size:
    return _size_of(_read_meta(path))


def sizes(settings: Settings) -> dict[str, Size]:
    """Every sized picture's block, by slug — what the text layout needs. A picture without a
    sidecar is left out, so it stays the bare one-cell token it always was."""
    return {p.stem: size_of(p) for p in list_all(settings) if _sidecar(p).exists()}


def suggested(px: list[int] | None) -> list[list[int]]:
    """Blocks that keep the picture's shape: one to three rows tall, as wide as the aspect says."""
    if not px or not px[0] or not px[1]:
        return []
    ar = px[0] / px[1]
    out: list[list[int]] = []
    for h in (1, 2, 3):
        w = max(1, round(ar * CELL_ASPECT * h))
        if w <= MAX_W and [w, h] not in out:
            out.append([w, h])
    return out


def save(settings: Settings, slug: str, content_type: str, data: bytes) -> tuple[Path, bool]:
    """Write the file and its sidecar; returns (path, replaced).

    Other extensions of the slug are removed. Replacing a picture keeps the size its owner set
    and refreshes the pixel size.
    """
    existing = find(settings, slug)
    kept = _read_meta(existing) if existing else {}
    for ext in MEDIA_TYPES:
        old = images_dir(settings) / f"{slug}.{ext}"
        if old.exists():
            old.unlink()
    if existing:
        _sidecar(existing).unlink(missing_ok=True)
    path = images_dir(settings) / f"{slug}.{CONTENT_TYPES[content_type]}"
    path.write_bytes(data)
    px = dimensions(data)
    size = _size_of(kept) if kept else {"w": 1, "h": 1, "fit": "contain", "ar": None}
    _write_meta(
        path,
        {"w": size["w"], "h": size["h"], "fit": size["fit"], "px": list(px) if px else None},
    )
    return path, existing is not None


def set_size(path: Path, w: int | None, h: int | None, fit: str | None) -> None:
    """Change how the picture sits on the board; unset fields keep their value."""
    meta = _read_meta(path)
    current = _size_of(meta)
    if fit is None:  # a legacy picture sized for the first time keeps its shape from now on
        fit = current["fit"] if meta else "contain"
    meta.update(
        {
            "w": w if w is not None else current["w"],
            "h": h if h is not None else current["h"],
            "fit": fit,
            "px": _px(path, meta),
        }
    )
    _write_meta(path, meta)


def remove(path: Path) -> None:
    path.unlink()
    _sidecar(path).unlink(missing_ok=True)


def describe(path: Path) -> dict:
    slug = path.stem
    meta = _read_meta(path)
    size = _size_of(meta)
    px = _px(path, meta)
    return {
        "slug": slug,
        "url": f"/images/{slug}",
        "token": f"{{img:{slug}}}",
        "content_type": MEDIA_TYPES[path.suffix[1:]],
        "bytes": path.stat().st_size,
        "w": size["w"],
        "h": size["h"],
        "fit": size["fit"],
        "width": px[0] if px else None,
        "height": px[1] if px else None,
        "suggested": suggested(px),
    }
