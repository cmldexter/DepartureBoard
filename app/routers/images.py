"""Uploaded images. Put one on the board with `{img:slug}` in a message."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.schemas import ImageOut, ImagePatch, QrIn
from app.services import images
from app.services.auth import Authenticated

api = APIRouter(prefix="/api/images", tags=["images"], dependencies=[Authenticated])
public = APIRouter(tags=["images"])


@api.get("", summary="List uploaded images", response_model=list[ImageOut])
def list_images(request: Request):
    return [images.describe(p) for p in images.list_all(request.app.state.settings)]


@api.post(
    "",
    summary="Upload an image",
    description=(
        "multipart/form-data with `file` (PNG, JPEG, GIF or WebP, up to 5 MB) and an optional "
        "`slug` (a–z, 0–9, dashes; defaults to the file name). The response's `token` goes in "
        "a message, e.g. `HELLO {img:my-cat}`. A new picture takes one cell; `PATCH "
        "/api/images/{slug}` sets its block (`w` × `h` cells, `fit`), and `suggested` lists the "
        "blocks that keep its shape. Uploading the same slug again replaces the file and keeps "
        "its size."
    ),
    response_model=ImageOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Replaced an existing image"}},
)
async def upload_image(
    request: Request,
    response: Response,
    file: Annotated[UploadFile, File()],
    slug: Annotated[str | None, Form()] = None,
):
    content_type = (file.content_type or "").split(";")[0].strip()
    if content_type not in images.CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"{content_type or 'unknown type'}: send PNG, JPEG, GIF or WebP.",
        )
    data = await file.read(images.MAX_BYTES + 1)
    if len(data) > images.MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Over {images.MAX_BYTES // (1024 * 1024)} MB — a phone screenshot fits, a camera "
            "photo may need resizing.",
        )
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Empty file.")
    slug = (slug or images.slugify(file.filename or "image")).strip().lower()
    if not images.SLUG_RE.match(slug):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "slug: a–z, 0–9 and dashes, up to 40."
        )
    path, replaced = images.save(request.app.state.settings, slug, content_type, data)
    if replaced:
        response.status_code = status.HTTP_200_OK
    return images.describe(path)


@api.post(
    "/qr",
    summary="Make a QR code picture",
    description=(
        "A QR code is a picture the server makes: the same token, size, panel and sidecar as any "
        "upload. Send `slug` and `data` (text or a URL, up to 1024 characters); the code is dark "
        "on white with a quiet zone, error correction M, and is drawn whole over its block "
        "(`solid`) so a phone can scan it from the sofa. A new one takes 4 × 3 cells; the same "
        "slug again remakes the picture and keeps its size. `qr.data` echoes the text."
    ),
    response_model=ImageOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Remade an existing QR code"}},
)
def make_qr(request: Request, response: Response, body: QrIn):
    path, replaced = images.save_qr(request.app.state.settings, body.slug, body.data)
    if replaced:
        response.status_code = status.HTTP_200_OK
    return images.describe(path)


@api.patch(
    "/{slug}",
    summary="Size an image on the board",
    description=(
        "`w` (1–36) × `h` (1–10) cells and `fit`: `contain` keeps the picture's shape inside the "
        "block, `cover` fills the block and crops, `stretch` fills it. The bounds are the biggest "
        "board; a message whose picture does not fit the board in use is refused when saved."
    ),
    response_model=ImageOut,
)
def patch_image(slug: str, body: ImagePatch, request: Request):
    path = images.find(request.app.state.settings, slug)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such image.")
    images.set_size(path, body.w, body.h, body.fit, body.solid)
    return images.describe(path)


@api.delete("/{slug}", summary="Delete an image", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(slug: str, request: Request):
    path = images.find(request.app.state.settings, slug)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such image.")
    images.remove(path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public.get("/images/{slug}", summary="An uploaded image (public; the board loads it)")
def serve_image(slug: str, request: Request):
    path = images.find(request.app.state.settings, slug)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such image.")
    return FileResponse(
        path, media_type=images.MEDIA_TYPES[path.suffix[1:]], headers={"Cache-Control": "no-cache"}
    )
