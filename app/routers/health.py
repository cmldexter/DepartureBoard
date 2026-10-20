from fastapi import APIRouter

from app import __version__

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", summary="Liveness check")
def health() -> dict[str, object]:
    return {"ok": True, "version": __version__}
