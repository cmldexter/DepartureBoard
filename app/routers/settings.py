"""Display settings: what the board looks like. Bearer token."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import PRESETS, Setting
from app.schemas import SettingsOut, SettingsPatch
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
def patch_settings(body: SettingsPatch, session: Session = Depends(get_session)):
    changes = body.model_dump(exclude_unset=True)
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
    session.commit()
    return display_settings(session)
