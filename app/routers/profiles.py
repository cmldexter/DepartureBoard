"""Boards you can switch: the live board saved under a name, loaded back, copied, renamed,
deleted; the JSON file itself read and written. Bearer token."""

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import app_settings, get_session, now
from app.schemas import (
    ProfileCopyIn,
    ProfileFile,
    ProfileLoaded,
    ProfileOut,
    ProfileRenameIn,
    ProfileSaveIn,
)
from app.services import profiles
from app.services.auth import Authenticated
from app.services.display import display_settings

router = APIRouter(prefix="/api/profiles", tags=["profiles"], dependencies=[Authenticated])


def _slug(slug: str, settings: Settings) -> Path:
    path = profiles.path_of(settings, slug)
    if path is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "slug: a–z, 0–9 and dashes, up to 40."
        )
    return path


def _existing(slug: str, settings: Settings) -> Path:
    path = _slug(slug, settings)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such profile.")
    return path


def _out(path: Path, session: Session, settings: Settings) -> ProfileOut:
    try:
        active = display_settings(session)["active_profile"]
        return ProfileOut(**profiles.describe(settings, path, active, session))
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e


@router.get(
    "",
    summary="List saved boards",
    description=(
        "Every profile under the data directory's `profiles/`: name, when it was saved, how many "
        "messages, which pictures it names that are gone (`pictures_missing`), and whether it is "
        "the one loaded last (`active`)."
    ),
    response_model=list[ProfileOut],
)
def list_profiles(
    session: Session = Depends(get_session), settings: Settings = Depends(app_settings)
):
    active = display_settings(session)["active_profile"]
    out = []
    for path in profiles.list_all(settings):
        try:
            out.append(ProfileOut(**profiles.describe(settings, path, active, session)))
        except ValueError:
            continue  # a hand-edited file that does not parse is left out, not fatal
    return out


@router.post(
    "/{slug}/save",
    summary="Save the live board under this slug",
    description=(
        "Writes the current messages and display settings to `profiles/<slug>.json` (overwriting "
        "— 200 — or new — 201) and makes it the active profile. `name` defaults to the file's old "
        "name, else the slug. The guest link's token and the active-profile pointer are not part "
        "of a profile; pictures are shared by slug and stay on disk."
    ),
    response_model=ProfileOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Overwrote an existing profile"}},
)
def save_profile(
    slug: str,
    response: Response,
    body: ProfileSaveIn | None = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(app_settings),
    at: datetime = Depends(now),
):
    _slug(slug, settings)
    path, replaced = profiles.save(settings, session, slug, body.name if body else None, at)
    session.commit()
    if replaced:
        response.status_code = status.HTTP_200_OK
    return _out(path, session, settings)


@router.post(
    "/{slug}/load",
    summary="Load a saved board — it replaces the live one",
    description=(
        "Replaces every live message and the display settings with the profile's, in one "
        "transaction (message ids are new). A message that cannot lay out on the profile's own "
        "grid is kept **disabled** with its reason in `kept_disabled`; a background picture that "
        "is gone is cleared. The TV follows on its next poll."
    ),
    response_model=ProfileLoaded,
)
def load_profile(
    slug: str,
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(app_settings),
):
    path = _existing(slug, settings)
    source = "ui" if request.cookies.get("db_session") else "api"
    try:
        _, kept = profiles.load(settings, session, path, source)
    except ValueError as e:
        session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    session.commit()
    return ProfileLoaded(**profiles.describe(settings, path, slug), kept_disabled=kept)


@router.post(
    "/{slug}/copy",
    summary="Duplicate a saved board",
    response_model=ProfileOut,
    status_code=status.HTTP_201_CREATED,
)
def copy_profile(
    slug: str,
    body: ProfileCopyIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(app_settings),
):
    path = _existing(slug, settings)
    target = _slug(body.slug, settings)
    if target.exists():
        raise HTTPException(status.HTTP_409_CONFLICT, f"A profile {body.slug!r} exists already.")
    try:
        profiles.copy(settings, path, body.slug, body.name)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    return _out(target, session, settings)


@router.patch("/{slug}", summary="Rename a saved board", response_model=ProfileOut)
def rename_profile(
    slug: str,
    body: ProfileRenameIn,
    session: Session = Depends(get_session),
    settings: Settings = Depends(app_settings),
):
    path = _existing(slug, settings)
    try:
        profiles.rename(path, body.name)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    return _out(path, session, settings)


@router.delete(
    "/{slug}",
    summary="Delete a saved board (the live board is untouched)",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_profile(
    slug: str, session: Session = Depends(get_session), settings: Settings = Depends(app_settings)
):
    profiles.remove(session, _existing(slug, settings))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{slug}",
    summary="The profile file itself (export)",
    description="The JSON as stored: `name`, `saved_at`, `settings`, `messages`. Hand-editable.",
    response_model=ProfileFile,
)
def read_profile(slug: str, settings: Settings = Depends(app_settings)):
    try:
        return profiles.read(_existing(slug, settings))
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e


@router.put(
    "/{slug}",
    summary="Write a profile file (import)",
    description=(
        "Stores the JSON under this slug (new — 201 — or replaced — 200). Messages are validated "
        "like `POST /api/messages`; settings like `PATCH /api/settings`. Nothing is loaded until "
        "you ask."
    ),
    response_model=ProfileOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Replaced an existing profile"}},
)
def put_profile(
    slug: str,
    body: ProfileFile,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(app_settings),
):
    path = _slug(slug, settings)
    replaced = path.exists()
    profiles.write(path, body)
    if replaced:
        response.status_code = status.HTTP_200_OK
    return _out(path, session, settings)
