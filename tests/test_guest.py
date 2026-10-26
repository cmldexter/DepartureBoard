"""The guest link: the first public write path, narrow by design."""

import io
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Post
from app.services import guest
from app.services.imagesize import dimensions
from tests.test_api import PNG
from tests.test_exif import JPEG


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _rotate(client, auth):
    r = client.post("/api/guest/rotate", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def test_guests_are_off_until_a_token_is_minted(client, auth):
    assert client.get("/api/settings", headers=auth).json()["guest_token"] == ""
    assert client.get("/guest/").status_code == 404
    assert client.get("/guest/anything-at-all-here").status_code == 404
    assert client.post("/guest/anything-at-all-here", data={"text": "HI"}).status_code == 404
    link = _rotate(client, auth)
    assert len(link["token"]) == 20 and link["url"].endswith(f"/guest/{link['token']}")
    assert client.get("/api/settings", headers=auth).json()["guest_token"] == link["token"]
    r = client.get(link["url"].split("/guest/")[0] and f"/guest/{link['token']}")
    assert r.status_code == 200 and "Your line" in r.text and 'maxlength="120"' in r.text
    assert 'class="mark" src="/static/icons/icon-192.png"' in r.text
    assert "api_token" not in r.text and "settings" not in r.text.lower().replace(
        "the host approves", ""
    )


def test_rotate_needs_the_token_and_kills_the_old_link(client, auth):
    assert client.post("/api/guest/rotate").status_code == 401
    old = _rotate(client, auth)["token"]
    new = _rotate(client, auth)["token"]
    assert old != new
    assert client.get(f"/guest/{old}").status_code == 404
    assert client.get(f"/guest/{new}").status_code == 200
    # closing the door
    r = client.patch("/api/settings", json={"guest_token": ""}, headers=auth)
    assert r.status_code == 200 and r.json()["guest_token"] == ""
    assert client.get(f"/guest/{new}").status_code == 404
    # bring your own, within the rule
    assert (
        client.patch("/api/settings", json={"guest_token": "short"}, headers=auth).status_code
        == 422
    )
    r = client.patch(
        "/api/settings", json={"guest_token": "party-2026-saturday-night"}, headers=auth
    )
    assert (
        r.status_code == 200 and client.get("/guest/party-2026-saturday-night").status_code == 200
    )


def test_the_token_never_reaches_the_tv(client, auth):
    _rotate(client, auth)
    board = client.get("/api/board/current").json()
    assert "guest_token" not in board["settings"]
    assert "guest_token" not in client.get("/").text


def test_a_post_with_a_photo_lands_pending_with_its_metadata_gone(client, auth, settings):
    t = _rotate(client, auth)["token"]
    r = client.post(
        f"/guest/{t}",
        data={"text": "  happy   birthday nick 🎉 ", "nick": "Ana"},
        files={"photo": ("IMG_0042.jpg", io.BytesIO(JPEG), "image/jpeg")},
    )
    assert r.status_code == 200 and "Thanks, Ana!" in r.text and "approves" in r.text
    with next(client.app.state.db.session()) as session:
        post = session.scalars(select(Post)).one()
    assert (post.text, post.nick, post.status, post.image) == (
        "happy birthday nick 🎉",
        "Ana",
        "pending",
        "guest-1",
    )
    assert len(post.ip_hash) == 16 and "testclient" not in post.ip_hash
    saved = (settings.data_dir / "images" / "guest-1.jpg").read_bytes()
    assert b"\xff\xe1" not in saved and b"GPS" not in saved, "no APP1 segment"
    assert dimensions(saved) == (743, 116), "and it still decodes"
    img = next(i for i in client.get("/api/images", headers=auth).json() if i["slug"] == "guest-1")
    assert (img["w"], img["h"], img["fit"]) == (36, 4, "contain"), (
        "4 rows tall, as wide as keeps its shape, capped"
    )
    # it is a picture like any other, and the host sees it on the panel; the public can fetch it
    assert client.get("/images/guest-1").status_code == 200


def test_text_only_and_photo_only_posts(client, auth):
    t = _rotate(client, auth)["token"]
    assert client.post(f"/guest/{t}", data={"text": "JUST WORDS"}).status_code == 200
    r = client.post(
        f"/guest/{t}", data={"text": ""}, files={"photo": ("p.png", io.BytesIO(PNG), "image/png")}
    )
    assert r.status_code == 200
    with next(client.app.state.db.session()) as session:
        posts = session.scalars(select(Post).order_by(Post.id)).all()
    assert [(p.text, p.image) for p in posts] == [("JUST WORDS", None), ("", "guest-2")]


def test_the_limits_the_docs_promise(client, auth):
    t = _rotate(client, auth)["token"]
    r = client.post(f"/guest/{t}", data={"text": "", "nick": ""})
    assert r.status_code == 422 and "Write a line or add a photo" in r.text
    r = client.post(f"/guest/{t}", data={"text": "x" * 121})
    assert r.status_code == 422 and "Up to 120 characters" in r.text
    r = client.post(f"/guest/{t}", data={"text": "HI", "nick": "x" * 17})
    assert r.status_code == 422 and "up to 16" in r.text
    r = client.post(
        f"/guest/{t}",
        data={"text": "HI"},
        files={"photo": ("a.gif", io.BytesIO(b"GIF89a"), "image/gif")},
    )
    assert r.status_code == 422 and "PNG, JPEG or WebP" in r.text
    r = client.post(
        f"/guest/{t}",
        data={"text": "HI"},
        files={"photo": ("big.png", io.BytesIO(b"0" * (guest.MAX_PHOTO + 1)), "image/png")},
    )
    assert r.status_code == 413 and "5 MB" in r.text
    assert (guest.MAX_TEXT, guest.MAX_NICK, guest.PER_IP_HOUR, guest.PER_BOARD_HOUR) == (
        120,
        16,
        20,
        200,
    )


def test_twenty_posts_an_hour_from_one_phone(client, auth):
    t = _rotate(client, auth)["token"]
    for i in range(20):
        assert client.post(f"/guest/{t}", data={"text": f"POST {i}"}).status_code == 200
    r = client.post(f"/guest/{t}", data={"text": "ONE MORE"})
    assert r.status_code == 429 and "a lot of posts" in r.text
    # another phone (a proxy's X-Forwarded-For names it) still can
    other = {"X-Forwarded-For": "10.0.0.9, 192.168.1.1"}
    assert client.post(f"/guest/{t}", data={"text": "HELLO"}, headers=other).status_code == 200
    # an hour later the first phone can again
    client.app.state.clock = lambda: datetime.now(UTC) + timedelta(hours=1, minutes=1)
    assert client.post(f"/guest/{t}", data={"text": "LATER"}).status_code == 200


def test_two_hundred_posts_an_hour_for_the_board(client, auth):
    t = _rotate(client, auth)["token"]
    for i in range(200):
        headers = {"X-Forwarded-For": f"10.0.{i // 10}.{i % 10}"}  # 10 posts per phone, 20 phones
        assert (
            client.post(f"/guest/{t}", data={"text": "HI"}, headers=headers).status_code == 200
        ), i
    r = client.post(f"/guest/{t}", data={"text": "HI"}, headers={"X-Forwarded-For": "10.9.9.9"})
    assert r.status_code == 429 and "busy" in r.text


def test_the_page_keeps_what_was_typed_on_an_error(client, auth):
    t = _rotate(client, auth)["token"]
    r = client.post(f"/guest/{t}", data={"text": "x" * 121, "nick": "Ana"})
    assert 'value="Ana"' in r.text and "x" * 121 in r.text


def test_the_qr_that_opens_the_guest_page(client, auth, settings):
    from tests._qr import decode_qr as decode

    assert client.post("/api/guest/qr", headers=auth).status_code == 409, "guests are off"
    link = _rotate(client, auth)
    r = client.post("/api/guest/qr", headers=auth)
    assert r.status_code == 201, r.text
    out = r.json()
    assert (out["url"], out["token"], out["enabled"], out["state"]) == (
        link["url"],
        "{img:guest-qr}",
        False,
        "disabled",
    )
    assert decode((settings.data_dir / "images" / "guest-qr.png").read_bytes()) == link["url"]
    img = next(i for i in client.get("/api/images", headers=auth).json() if i["slug"] == "guest-qr")
    assert (img["w"], img["h"], img["solid"], img["qr"]["data"]) == (4, 3, True, link["url"])
    m = client.get(f"/api/messages/{out['message_id']}", headers=auth).json()
    assert (m["text"], m["enabled"], m["source"]) == (
        "SCAN TO POST A PHOTO\n{img:guest-qr}",
        False,
        "api",
    )
    assert client.get("/api/board/current").json()["message_id"] is None, "disabled until you say"
    # again: the picture is remade, the message is the same one
    r = client.post("/api/guest/qr", headers=auth)
    assert r.status_code == 200 and r.json()["message_id"] == out["message_id"]
    assert len(client.get("/api/messages", headers=auth).json()) == 1
    # switched on, it is on the TV: the words, then the code drawn whole
    client.patch(f"/api/messages/{m['id']}", json={"enabled": True}, headers=auth)
    board = client.get("/api/board/current").json()
    assert board["message_id"] == m["id"]
    assert (
        "".join(c for c in board["rows"][0] if isinstance(c, str)).strip() == "SCAN TO POST A PHOTO"
    )
    part = board["rows"][1][0]
    assert (part["img"], part["w"], part["h"], part["solid"], part["qr"]) == (
        "guest-qr",
        4,
        3,
        True,
        True,
    )
    stamp = board["stamp"]
    # rotate: the code now opens the new link, the message stays on
    link2 = _rotate(client, auth)
    assert decode((settings.data_dir / "images" / "guest-qr.png").read_bytes()) == link2["url"]
    board = client.get("/api/board/current").json()
    assert board["stamp"] != stamp and board["message_id"] == m["id"], (
        "a new version reaches the TV"
    )
    assert client.post("/api/guest/qr", headers=auth).json()["enabled"] is True
    # the door closed: the message goes off; the picture stays for next time
    client.patch("/api/settings", json={"guest_token": ""}, headers=auth)
    m = client.get(f"/api/messages/{m['id']}", headers=auth).json()
    assert m["enabled"] is False and m["state"] == "disabled"
    assert client.get("/api/board/current").json()["message_id"] is None
    assert client.post("/api/guest/qr", headers=auth).status_code == 409
    # a host-written message with the token counts too
    _rotate(client, auth)
    client.post("/api/messages", json={"text": "PHOTOS HERE {img:guest-qr}"}, headers=auth)
    client.patch(f"/api/messages/{m['id']}", json={"enabled": True}, headers=auth)
    client.patch("/api/settings", json={"guest_token": ""}, headers=auth)
    assert all(not x["enabled"] for x in client.get("/api/messages", headers=auth).json())
