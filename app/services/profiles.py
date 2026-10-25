"""Profiles: a board — its messages and its display settings — saved as a JSON file under
<data_dir>/profiles/<slug>.json. Plain files like pictures: no table, hand-editable, and the
export/import format for free. Pictures are shared by slug and are not inside a profile."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import DEFAULT_SETTINGS, Message, Setting
from app.schemas import MessageIn, ProfileFile, SettingsPatch
from app.services import images
from app.services.display import display_settings, resolve_display
from app.services.scheduler import as_utc
from app.services.text import capacity_error, layout, tokenize

SLUG_RE = images.SLUG_RE
# The door is not a look, the pointer to the loaded profile is not its content, and the
# calendar decides which board is up — it is not inside one.
EXCLUDED_SETTINGS = ("guest_token", "active_profile", "calendar_everyday", "calendar_applied")
PROFILE_SETTINGS = tuple(k for k in DEFAULT_SETTINGS if k not in EXCLUDED_SETTINGS)
MESSAGE_FIELDS = tuple(MessageIn.model_fields)


def profiles_dir(settings: Settings) -> Path:
    d = settings.data_dir / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def path_of(settings: Settings, slug: str) -> Path | None:
    """Where the profile would be; None for a slug that is not one."""
    if not SLUG_RE.match(slug):
        return None
    return profiles_dir(settings) / f"{slug}.json"


def find(settings: Settings, slug: str) -> Path | None:
    p = path_of(settings, slug)
    return p if p is not None and p.exists() else None


def list_all(settings: Settings) -> list[Path]:
    found = (p for p in profiles_dir(settings).glob("*.json") if SLUG_RE.match(p.stem))
    return sorted(found, key=lambda p: p.stem)  # by slug, not by path ("-" sorts before ".")


def read(path: Path) -> ProfileFile:
    """The file, validated; a hand-edited file that does not parse raises ValueError."""
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise ValueError(f"{path.name}: not readable JSON ({e})") from e
    return ProfileFile.model_validate(raw)


def write(path: Path, data: ProfileFile) -> None:
    path.write_text(json.dumps(data.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n")


def snapshot(session: Session, name: str, at: datetime) -> ProfileFile:
    """The live board as a profile: every display key but the excluded ones, every message."""
    d = display_settings(session)
    messages = []
    for m in session.scalars(select(Message).order_by(Message.id)):
        fields = {k: getattr(m, k) for k in MESSAGE_FIELDS}
        for k in ("starts_at", "ends_at"):
            fields[k] = as_utc(fields[k])
        messages.append(MessageIn.model_validate(fields))
    return ProfileFile(
        name=name,
        saved_at=at.astimezone(UTC),
        settings={k: d[k] for k in PROFILE_SETTINGS},
        messages=messages,
    )


def pictures_missing(settings: Settings, data: ProfileFile) -> list[str]:
    """Pictures the profile names that are not on disk (deleted since, or never imported)."""
    slugs: set[str] = set()
    for m in data.messages:
        for line in m.text.split("\n"):
            slugs.update(tokenize(line)[2])
    bg = str(data.settings.get("background_image") or "")
    if bg.startswith("img:"):
        slugs.add(bg[4:])
    return sorted(s for s in slugs if images.find(settings, s) is None)


def _content(data: ProfileFile) -> dict[str, Any]:
    return data.model_dump(mode="json", exclude={"name", "saved_at"})


def describe(
    settings: Settings, path: Path, active: str, session: Session | None = None
) -> dict[str, Any]:
    """The listing entry; with a session, the active profile also says whether the live board
    has changed since it was saved (the dot on the Boards strip)."""
    data = read(path)
    is_active = path.stem == active
    changed = False
    if is_active and session is not None:
        live = snapshot(session, data.name, datetime.now(UTC))
        changed = _content(live) != _content(data)
    return {
        "slug": path.stem,
        "name": data.name,
        "saved_at": data.saved_at,
        "messages": len(data.messages),
        "pictures_missing": pictures_missing(settings, data),
        "active": is_active,
        "changed": changed,
    }


def _set(session: Session, key: str, value: object) -> None:
    stored = str(value).lower() if isinstance(value, bool) else str(value)
    session.merge(Setting(key=key, value=stored))


def save(
    settings: Settings, session: Session, slug: str, name: str | None, at: datetime
) -> tuple[Path, bool]:
    """Write the live board to <slug>.json (overwriting) and make it the active profile.
    Returns (path, replaced). The name defaults to the file's old name, else the slug."""
    path = path_of(settings, slug)
    assert path is not None
    replaced = path.exists()
    if name is None:
        name = read(path).name if replaced else slug.replace("-", " ").title()
    write(path, snapshot(session, name, at))
    _set(session, "active_profile", slug)
    return path, replaced


def load(
    settings: Settings, session: Session, path: Path, source: str
) -> tuple[ProfileFile, list[dict[str, str]]]:
    """Replace the live messages and display settings with the profile's, in the caller's
    transaction. A message that cannot lay out on the profile's own grid is kept disabled with
    the reason (returned), never dropped; a background picture that is gone is cleared."""
    data = read(path)
    patch = SettingsPatch.model_validate(data.settings)  # the same rules as PATCH /api/settings
    values = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    bg = str(values.get("background_image") or "")
    if bg.startswith("img:") and images.find(settings, bg[4:]) is None:
        values["background_image"] = ""
    for key in PROFILE_SETTINGS:
        _set(session, key, values[key] if key in values else DEFAULT_SETTINGS[key])
    session.execute(delete(Message))
    stored = {row.key: row.value for row in session.scalars(select(Setting))}
    d = resolve_display(stored)
    sizes = images.sizes(settings)
    kept: list[dict[str, str]] = []
    for m in data.messages:
        fields = m.model_dump()
        reason = capacity_error(layout(m.text, d["rows"], d["cols"], sizes))
        if reason and fields["enabled"]:
            fields["enabled"] = False
            kept.append({"text": m.text, "reason": reason})
        session.add(Message(**fields, source=source))
    _set(session, "active_profile", path.stem)
    return data, kept


def copy(settings: Settings, path: Path, slug: str, name: str | None) -> Path:
    data = read(path)
    target = path_of(settings, slug)
    assert target is not None
    data.name = name or f"{data.name} copy"
    write(target, data)
    return target


def rename(path: Path, name: str) -> ProfileFile:
    data = read(path)
    data.name = name
    write(path, data)
    return data


def remove(session: Session, path: Path) -> None:
    path.unlink()
    active = session.get(Setting, "active_profile")
    if active is not None and active.value == path.stem:
        active.value = ""
