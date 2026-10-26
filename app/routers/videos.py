"""Uploaded videos. Put one behind the board with `background_image: video:<slug>`."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.models import Setting
from app.schemas import VideoOut
from app.services import videos
from app.services.auth import Authenticated

api = APIRouter(prefix="/api/videos", tags=["videos"], dependencies=[Authenticated])
public = APIRouter(tags=["videos"])


@api.get("", summary="List uploaded videos", response_model=list[VideoOut])
def list_videos(request: Request):
    return [videos.describe(p) for p in videos.list_all(request.app.state.settings)]


@api.post(
    "",
    summary="Upload a video",
    description=(
        "multipart/form-data with `file` (MP4 or WebM, up to 250 MB) and an optional `slug` "
        "(a–z, 0–9, dashes; defaults to the file name). The response's `token` goes in the "
        "`background_image` setting: the board plays the file muted in a loop under the frame. "
        "The file is stored as it is — a 1080p, audio-free, fast-start h264 file plays on the "
        "weakest TV browser (docs/backgrounds.md has the one-liner). Uploading the same slug "
        "again replaces the file."
    ),
    response_model=VideoOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Replaced an existing video"}},
)
async def upload_video(
    request: Request,
    response: Response,
    file: Annotated[UploadFile, File()],
    slug: Annotated[str | None, Form()] = None,
):
    content_type = (file.content_type or "").split(";")[0].strip()
    if content_type not in videos.CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"{content_type or 'unknown type'}: send MP4 or WebM.",
        )
    slug = (slug or videos.slugify(file.filename or "video")).strip().lower()
    if not videos.SLUG_RE.match(slug):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "slug: a–z, 0–9 and dashes, up to 40."
        )
    try:
        path, replaced = await videos.save_stream(
            request.app.state.settings, slug, content_type, file
        )
    except videos.TooBig:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Over {videos.MAX_BYTES // (1024 * 1024)} MB — resize to 1080p and drop the "
            "sound (docs/backgrounds.md shows the one-liner).",
        ) from None
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Empty file.") from None
    if replaced:
        response.status_code = status.HTTP_200_OK
    return videos.describe(path)


@api.delete(
    "/{slug}",
    summary="Delete a video",
    description="A video that is the board's backdrop is taken off the TV as it goes.",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_video(slug: str, request: Request):
    path = videos.find(request.app.state.settings, slug)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such video.")
    videos.remove(path)
    with next(request.app.state.db.session()) as session:
        row = session.scalar(select(Setting).where(Setting.key == "background_image"))
        if row is not None and row.value == f"video:{slug}":
            row.value = ""
            session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public.get("/videos/{slug}", summary="An uploaded video (public; the board plays it)")
def serve_video(slug: str, request: Request):
    path = videos.find(request.app.state.settings, slug)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such video.")
    return FileResponse(
        path, media_type=videos.MEDIA_TYPES[path.suffix[1:]], headers={"Cache-Control": "no-cache"}
    )
