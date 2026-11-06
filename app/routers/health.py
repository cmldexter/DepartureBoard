from fastapi import APIRouter, Request

from app import __version__

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", summary="Liveness check")
def health(request: Request) -> dict[str, object]:
    """Which build this is: the version, the edition and the extensions loaded (none in the
    community build)."""
    state = request.app.state
    return {
        "ok": True,
        "version": __version__,
        "edition": getattr(state, "edition", "community"),
        "extensions": list(getattr(state, "extensions", [])),
    }
