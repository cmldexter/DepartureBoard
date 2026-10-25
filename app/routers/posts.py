"""The guest queue, for the host: list, approve, reject, remove, clear. Bearer token."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session, now, tz
from app.models import Post
from app.schemas import PostFilter, PostOut, PostsCleared
from app.services import guest
from app.services.auth import Authenticated
from app.services.scheduler import as_utc
from app.services.scheduler import state as message_state

router = APIRouter(prefix="/api/posts", tags=["guests"], dependencies=[Authenticated])


def to_out(
    post: Post, session: Session, at: datetime, zone: ZoneInfo, note: str | None = None
) -> PostOut:
    m = guest.message_of(session, post)
    return PostOut(
        id=post.id,
        created_at=as_utc(post.created_at),
        nick=post.nick,
        text=post.text,
        image=post.image,
        status=post.status,
        message_id=m.id if m else None,
        message_state=message_state(m, at, zone) if m else None,
        note=note,
    )


def _get(post_id: int, session: Session) -> Post:
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such post.")
    return post


def _select(status_filter: str):
    q = select(Post).order_by(Post.id)
    return q if status_filter == "all" else q.where(Post.status == status_filter)


@router.get(
    "",
    summary="List guest posts",
    description=(
        "What guests left through the guest link, oldest first. `pending` posts wait for you; "
        "`approved` ones are on the board as messages (`message_id`, `message_state`); `rejected` "
        "ones are kept only so the hour's limit still counts them."
    ),
    response_model=list[PostOut],
)
def list_posts(
    status_filter: PostFilter = Query("all", alias="status"),
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    return [to_out(p, session, at, zone) for p in session.scalars(_select(status_filter))]


@router.post(
    "/{post_id}/approve",
    summary="Approve a post — it becomes a message",
    description=(
        "Makes an ordinary message from the post: its text, the photo below it sized to the rows "
        "left on the current board, `- NICK` last; `source: guest`, `post_id`, the priority and "
        "`show_seconds` from the display settings `guest_priority` and `guest_show_seconds`. "
        "Guests at one priority take turns like any equals. When the post does not fit the board "
        "the message is made disabled and `note` says why. Approving again is a no-op."
    ),
    response_model=PostOut,
)
def approve_post(
    post_id: int,
    request: Request,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    post = _get(post_id, session)
    _, note = guest.approve(session, request.app.state.settings, post)
    session.commit()
    return to_out(post, session, at, zone, note)


@router.post(
    "/{post_id}/reject",
    summary="Reject a post — nothing on the board",
    description=(
        "Removes its message, if it had one, and its photo from disk. The row stays as "
        "`rejected` so the poster's hourly count still sees it; `DELETE` forgets it entirely."
    ),
    response_model=PostOut,
)
def reject_post(
    post_id: int,
    request: Request,
    session: Session = Depends(get_session),
    at: datetime = Depends(now),
    zone: ZoneInfo = Depends(tz),
):
    post = _get(post_id, session)
    guest.reject(session, request.app.state.settings, post)
    session.commit()
    return to_out(post, session, at, zone)


@router.delete(
    "/{post_id}",
    summary="Delete a post, its message and its photo",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_post(post_id: int, request: Request, session: Session = Depends(get_session)):
    guest.remove(session, request.app.state.settings, _get(post_id, session))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "",
    summary="Clear posts — messages and photos go too",
    description="`?status=pending|approved|rejected|all` (default all). Returns how many went.",
    response_model=PostsCleared,
)
def clear_posts(
    request: Request,
    status_filter: PostFilter = Query("all", alias="status"),
    session: Session = Depends(get_session),
):
    posts = session.scalars(_select(status_filter)).all()
    for post in posts:
        guest.remove(session, request.app.state.settings, post)
    session.commit()
    return PostsCleared(removed=len(posts))
