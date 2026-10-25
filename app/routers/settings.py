"""Display settings: what the board looks like. Bearer token."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import app_settings, get_session
from app.models import PRESETS, Setting
from app.schemas import SettingsOut, SettingsPatch
from app.services import guest, images, profiles
from app.services.auth import Authenticated
from app.services.display import display_settings

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Authenticated])


@router.get("", summary="Read the display settings", response_model=SettingsOut)
def read_settings(session: Session = Depends(get_session)):
    return display_settings(session)


@router.patch(
    "",
    summary="Change display settings",
    description="Send only the keys to change. A preset sets rows and cols; `custom` keeps them.",
    response_model=SettingsOut,
)
def patch_settings(
    body: SettingsPatch,
    session: Session = Depends(get_session),
    settings: Settings = Depends(app_settings),
):
    changes = body.model_dump(exclude_unset=True)
    bg = changes.get("background_image") or ""
    if bg.startswith("img:") and images.find(settings, bg[4:]) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"No uploaded picture {bg[4:]!r}. Upload it first: POST /api/images.",
        )
    preset = changes.get("grid_preset")
    if preset in PRESETS:
        changes["rows"], changes["cols"] = PRESETS[preset]
    elif "rows" in changes or "cols" in changes:
        changes.setdefault("grid_preset", "custom")
    for key, value in changes.items():
        if value is None:
            continue
        stored = str(value).lower() if isinstance(value, bool) else str(value)
        session.merge(Setting(key=key, value=stored))
    everyday = changes.get("calendar_everyday")
    if everyday and profiles.find(settings, everyday) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"No saved board {everyday!r}. Save one first: POST /api/profiles/{{slug}}/save.",
        )
    if changes.get("guest_token") == "":
        guest.disable_qr_messages(session)  # a code to a closed door comes off the board
    session.commit()
    return display_settings(session)


@router.delete(
    "/setup_done",
    summary="Show the first-run walkthrough again",
    description=(
        "Clears `setup_done`, so the next visit to `/settings` opens the walkthrough — what "
        "*Setup → Run the walkthrough again* does. For agents and tests."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
)
def reset_setup_done(session: Session = Depends(get_session)):
    session.merge(Setting(key="setup_done", value=""))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
