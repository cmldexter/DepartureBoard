"""Hosting the feed: the queue the host works through, and the message each post becomes."""

import io
import re
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import Message, Post
from app.services import guest
from tests.test_api import PNG
from tests.test_exif import JPEG


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _rotate(client, auth):
    return client.post("/api/guest/rotate", headers=auth).json()["token"]


def _post(client, t, text="", nick="", photo=None, **headers):
    files = {"photo": photo} if photo else None
    r = client.post(f"/guest/{t}", data={"text": text, "nick": nick}, files=files, headers=headers)
    assert r.status_code == 200, r.text
    return r


def _jpeg():
    return ("IMG.jpg", io.BytesIO(JPEG), "image/jpeg")  # 743 × 116 — a wide banner


def _png():
    return ("p.png", io.BytesIO(PNG), "image/png")


def _messages(client, auth):
    return client.get("/api/messages", headers=auth).json()


def test_the_queue_needs_the_token(client):
    assert client.get("/api/posts").status_code == 401
    assert client.post("/api/posts/1/approve").status_code == 401
    assert client.post("/api/posts/1/reject").status_code == 401
    assert client.delete("/api/posts/1").status_code == 401
    assert client.delete("/api/posts").status_code == 401


def test_approve_makes_a_message_the_tv_shows(client, auth):
    t = _rotate(client, auth)
    _post(client, t, "happy birthday nick 🎉", "Ana", _jpeg())
    before = client.get("/api/board/current").json()["stamp"]
    queue = client.get("/api/posts", headers=auth).json()
    assert len(queue) == 1 and queue[0]["status"] == "pending" and queue[0]["message_id"] is None
    assert queue[0]["image"] == "guest-1" and queue[0]["created_at"].endswith("Z")

    r = client.post("/api/posts/1/approve", headers=auth)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["status"], out["message_state"], out["note"]) == ("approved", "live", None)
    m = client.get(f"/api/messages/{out['message_id']}", headers=auth).json()
    # the text, the photo sized to the rows left (6 - 2 = 4, but 22 columns cap a 6.4:1 banner
    # at 22 × 2), the nick last; priority and seconds from the settings; source and post_id
    assert m["text"] == "happy birthday nick 🎉\n{img:guest-1@22x2}\n- Ana"
    assert (m["source"], m["post_id"], m["priority"], m["show_seconds"], m["enabled"]) == (
        "guest",
        1,
        1,
        15,
        True,
    )
    assert (m["created_by"], m["state"]) == ("Ana", "live")
    board = client.get("/api/board/current").json()
    assert board["stamp"] != before and board["message_id"] == m["id"]
    rows = board["rows"]
    assert "".join(c for c in rows[0] if isinstance(c, str)).strip() == "HAPPY BIRTHDAY NICK"
    assert {"emoji": "🎉"} in rows[0]
    assert (
        all(isinstance(c, dict) and c["img"] == "guest-1" for c in rows[1]) and len(rows[1]) == 22
    )
    assert rows[1][0]["w"] == 22 and rows[1][0]["h"] == 2 and rows[2][0]["y"] == 1
    assert "".join(c for c in rows[3] if isinstance(c, str)).strip() == "- ANA"
    # approving again changes nothing
    again = client.post("/api/posts/1/approve", headers=auth).json()
    assert again["message_id"] == out["message_id"] and len(_messages(client, auth)) == 1


def test_a_line_alone_and_a_photo_alone(client, auth):
    t = _rotate(client, auth)
    _post(client, t, "JUST WORDS")
    _post(client, t, "", "", _png())
    a = client.post("/api/posts/1/approve", headers=auth).json()
    b = client.post("/api/posts/2/approve", headers=auth).json()
    texts = {m["id"]: m["text"] for m in _messages(client, auth)}
    assert texts[a["message_id"]] == "JUST WORDS"
    assert re.fullmatch(r"\{img:guest-2@\d+x\d+\}", texts[b["message_id"]])
    # the two take turns: equals at priority 1, each for 15 s
    board = client.get("/api/board/current").json()
    assert board["timer"]["seconds"] == 15 and board["timer"]["own"] is True


def test_a_small_board_shrinks_the_photo_or_leaves_the_message_off(client, auth):
    r = client.patch(
        "/api/settings", json={"grid_preset": "custom", "rows": 4, "cols": 16}, headers=auth
    )
    assert r.status_code == 200
    t = _rotate(client, auth)
    _post(client, t, "HI", "Bo", _jpeg())
    out = client.post("/api/posts/1/approve", headers=auth).json()
    assert out["note"] is None and out["message_state"] == "live"
    m = client.get(f"/api/messages/{out['message_id']}", headers=auth).json()
    assert m["text"] == "HI\n{img:guest-1@16x2}\n- Bo", "two rows left for the photo"
    # a line that wraps past the board: the message is kept, disabled, and the note says why
    _post(client, t, "x" * 120, "Cy")
    out = client.post("/api/posts/2/approve", headers=auth).json()
    assert out["message_state"] == "disabled" and "rows" in out["note"]
    m = client.get(f"/api/messages/{out['message_id']}", headers=auth).json()
    assert m["enabled"] is False and m["source"] == "guest"
    listed = client.get("/api/posts?status=approved", headers=auth).json()
    assert [p["message_state"] for p in listed] == ["live", "disabled"]
    assert all(p["note"] is None for p in listed), "the note is said once, on approve"


def test_reject_leaves_nothing_and_remove_takes_it_down(client, auth, settings):
    t = _rotate(client, auth)
    _post(client, t, "SPAM", "", _jpeg())
    assert (settings.data_dir / "images" / "guest-1.jpg").exists()
    r = client.post("/api/posts/1/reject", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["image"] is None
    assert not (settings.data_dir / "images" / "guest-1.jpg").exists()
    assert client.get("/images/guest-1").status_code == 404
    assert _messages(client, auth) == []
    with next(client.app.state.db.session()) as session:
        assert guest.posts_since(session, datetime(2000, 1, 1, tzinfo=UTC)) == 1, (
            "a rejected post still counts toward the hour"
        )
    # approve, then remove = reject: the message goes, the board falls back to idle
    _post(client, t, "HELLO", "Di", _png())
    out = client.post("/api/posts/2/approve", headers=auth).json()
    assert client.get("/api/board/current").json()["message_id"] == out["message_id"]
    client.post("/api/posts/2/reject", headers=auth)
    assert _messages(client, auth) == []
    assert client.get("/api/board/current").json()["message_id"] is None
    assert client.get("/images/guest-2").status_code == 404
    # a message deleted on its own leaves the post approved with no message
    _post(client, t, "AGAIN")
    out = client.post("/api/posts/3/approve", headers=auth).json()
    client.delete(f"/api/messages/{out['message_id']}", headers=auth)
    p = client.get("/api/posts?status=approved", headers=auth).json()
    assert [(x["id"], x["message_id"], x["message_state"]) for x in p] == [(3, None, None)]


def test_delete_and_clear_remove_messages_and_files(client, auth, settings):
    t = _rotate(client, auth)
    for i in range(3):
        _post(client, t, f"POST {i}", "", _png())
    client.post("/api/posts/1/approve", headers=auth)
    client.post("/api/posts/2/approve", headers=auth)
    assert client.delete("/api/posts/3", headers=auth).status_code == 204
    assert client.delete("/api/posts/3", headers=auth).status_code == 404
    assert not (settings.data_dir / "images" / "guest-3.png").exists()
    r = client.delete("/api/posts?status=approved", headers=auth)
    assert r.status_code == 200 and r.json() == {"removed": 2}
    assert _messages(client, auth) == []
    assert not list((settings.data_dir / "images").glob("guest-*"))
    assert client.get("/api/posts", headers=auth).json() == []
    with next(client.app.state.db.session()) as session:
        assert session.scalars(select(Post)).all() == []
        assert session.scalars(select(Message)).all() == []
    _post(client, t, "LEFTOVER")
    assert client.delete("/api/posts", headers=auth).json() == {"removed": 1}


def test_list_filters_and_the_404s(client, auth):
    t = _rotate(client, auth)
    for i in range(4):
        _post(client, t, f"P{i}")
    client.post("/api/posts/1/approve", headers=auth)
    client.post("/api/posts/2/reject", headers=auth)
    counts = {
        s: len(client.get(f"/api/posts?status={s}", headers=auth).json())
        for s in ("pending", "approved", "rejected", "all")
    }
    assert counts == {"pending": 2, "approved": 1, "rejected": 1, "all": 4}
    assert client.get("/api/posts?status=bogus", headers=auth).status_code == 422
    assert client.post("/api/posts/99/approve", headers=auth).status_code == 404
    assert client.post("/api/posts/99/reject", headers=auth).status_code == 404
    # a rejected post can still be approved — as words only, its photo is gone
    out = client.post("/api/posts/2/approve", headers=auth).json()
    assert out["status"] == "approved" and out["message_state"] == "live"


def test_auto_approve_puts_a_phone_post_on_the_board_at_once(client, auth):
    t = _rotate(client, auth)
    page = client.get(f"/guest/{t}").text
    assert "The host approves posts before they show" in page
    r = client.patch("/api/settings", json={"guest_auto_approve": True}, headers=auth)
    assert r.status_code == 200 and r.json()["guest_auto_approve"] is True
    page = client.get(f"/guest/{t}").text
    assert "It shows right away" in page and "approves" not in page
    r = _post(client, t, "WE ARE HERE", "Eve", _png())
    assert "It is on the board" in r.text and "Thanks, Eve!" in r.text
    posts = client.get("/api/posts", headers=auth).json()
    assert posts[0]["status"] == "approved" and posts[0]["message_state"] == "live"
    board = client.get("/api/board/current").json()
    assert board["message_id"] == posts[0]["message_id"]
    assert "".join(c for c in board["rows"][0] if isinstance(c, str)).strip() == "WE ARE HERE"
    # a post that does not fit still says thanks, without claiming the board
    client.patch(
        "/api/settings", json={"grid_preset": "custom", "rows": 4, "cols": 16}, headers=auth
    )
    r = _post(client, t, "y" * 120)
    assert "Thanks!" in r.text and "It is on the board" not in r.text


def test_guest_settings_defaults_bounds_and_privacy(client, auth):
    s = client.get("/api/settings", headers=auth).json()
    assert (s["guest_auto_approve"], s["guest_priority"], s["guest_show_seconds"]) == (False, 1, 15)
    for bad in (
        {"guest_priority": 101},
        {"guest_priority": -101},
        {"guest_show_seconds": 4},
        {"guest_show_seconds": 601},
    ):
        assert client.patch("/api/settings", json=bad, headers=auth).status_code == 422, bad
    r = client.patch(
        "/api/settings", json={"guest_priority": 5, "guest_show_seconds": 30}, headers=auth
    )
    assert (r.json()["guest_priority"], r.json()["guest_show_seconds"]) == (5, 30)
    t = _rotate(client, auth)
    _post(client, t, "HI")
    m = client.get(
        f"/api/messages/{client.post('/api/posts/1/approve', headers=auth).json()['message_id']}",
        headers=auth,
    ).json()
    assert (m["priority"], m["show_seconds"]) == (5, 30)
    # none of it reaches the TV
    board = client.get("/api/board/current").json()
    assert not any(k.startswith("guest_") for k in board["settings"])
    assert "guest_" not in client.get("/").text
