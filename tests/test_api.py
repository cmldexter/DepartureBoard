"""The API: auth, messages, settings, images, the board endpoint."""

import io
from datetime import UTC, datetime, timedelta

import pytest

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478"
    "9c6360000000020001e221bc330000000049454e44ae426082"
)


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clock(client):
    """Freeze the server clock; tests move it."""
    state = {"now": datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)}
    client.app.state.clock = lambda: state["now"]
    return state


def test_writes_need_token(client):
    assert client.get("/api/messages").status_code == 401
    assert client.post("/api/messages", json={"text": "X"}).status_code == 401
    assert client.get("/api/settings").status_code == 401
    assert client.get("/api/images").status_code == 401
    assert client.get("/api/board/current").status_code == 200, "the board is public"


def test_message_lifecycle(client, auth, clock):
    r = client.post("/api/messages", json={"text": "hello world"}, headers=auth)
    assert r.status_code == 201
    m = r.json()
    assert r.headers["Location"] == f"/api/messages/{m['id']}"
    assert m["state"] == "live" and m["rows"][0] == list("HELLO WORLD")
    assert (m["used"], m["capacity"], m["source"]) == (11, 132, "api")
    assert m["created_at"].endswith("Z") or "+00:00" in m["created_at"], "timestamps are UTC-aware"

    r = client.get("/api/messages?state=live", headers=auth)
    assert [x["id"] for x in r.json()] == [m["id"]]
    assert client.get("/api/messages?state=expired", headers=auth).json() == []

    r = client.patch(f"/api/messages/{m['id']}", json={"enabled": False}, headers=auth)
    assert r.json()["state"] == "disabled"

    assert client.delete(f"/api/messages/{m['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/messages/{m['id']}", headers=auth).status_code == 404


def test_schedule_validation(client, auth):
    bad = {"text": "X", "starts_at": "2026-10-21T10:00:00Z", "ends_at": "2026-10-21T09:00:00Z"}
    assert client.post("/api/messages", json=bad, headers=auth).status_code == 422
    bad = {"text": "X", "repeat": "weekly"}
    assert client.post("/api/messages", json=bad, headers=auth).status_code == 422
    bad = {"text": "X", "repeat": "daily", "repeat_start": "25:00", "repeat_end": "09:00"}
    assert client.post("/api/messages", json=bad, headers=auth).status_code == 422
    ok = {"text": "X", "repeat": "daily", "repeat_start": "22:00", "repeat_end": "06:00"}
    assert client.post("/api/messages", json=ok, headers=auth).status_code == 201


def test_capacity_and_unknown_characters(client, auth):
    r = client.post("/api/messages", json={"text": "\n".join("ABCDEFG")}, headers=auth)
    assert r.status_code == 422 and "7 rows" in r.json()["detail"]
    r = client.post("/api/messages", json={"text": "5€ and ß"}, headers=auth)
    assert r.status_code == 201
    assert r.json()["unknown"] == ["ß", "€"]


def test_now_shortcut_outranks(client, auth, clock):
    client.post("/api/messages", json={"text": "A", "priority": 7}, headers=auth)
    r = client.post("/api/messages/now", json={"text": "B"}, headers=auth)
    assert r.status_code == 201 and r.json()["priority"] == 8
    board = client.get("/api/board/current").json()
    assert board["rows"][0][0] == "B"


def test_board_rotation_idle_and_etag(client, auth, clock):
    r = client.get("/api/board/current")
    assert r.json()["message_id"] is None
    assert all(c == " " for row in r.json()["rows"] for c in row), "idle = blank board"
    client.patch(
        "/api/settings", json={"idle_text": "NOTHING ON", "rotate_seconds": 20}, headers=auth
    )
    r = client.get("/api/board/current")
    assert r.json()["rows"][0][:10] == list("NOTHING ON")
    etag = r.headers["ETag"]
    assert client.get("/api/board/current", headers={"If-None-Match": etag}).status_code == 304

    a = client.post("/api/messages", json={"text": "A"}, headers=auth).json()["id"]
    b = client.post("/api/messages", json={"text": "B"}, headers=auth).json()["id"]
    r = client.get("/api/board/current", headers={"If-None-Match": etag})
    assert r.status_code == 200, "a new message changes the stamp"
    seen = set()
    for s in range(0, 60, 10):
        clock["now"] = datetime(2026, 10, 20, 12, 0, s, tzinfo=UTC)
        seen.add(client.get("/api/board/current").json()["message_id"])
    assert seen == {a, b}
    assert r.json()["settings"]["rows"] == 6 and "rotate_seconds" not in r.json()["settings"]


def test_board_shows_scheduled_message_on_time(client, auth, clock):
    start = (clock["now"] + timedelta(minutes=2)).isoformat()
    client.post("/api/messages", json={"text": "SOON", "starts_at": start}, headers=auth)
    assert client.get("/api/board/current").json()["message_id"] is None
    clock["now"] += timedelta(minutes=3)
    assert client.get("/api/board/current").json()["rows"][0][:4] == list("SOON")


def test_settings_bounds_and_presets(client, auth):
    r = client.get("/api/settings", headers=auth)
    assert r.json()["rows"] == 6 and r.json()["grid_preset"] == "compact"
    r = client.patch("/api/settings", json={"grid_preset": "large"}, headers=auth)
    assert (r.json()["rows"], r.json()["cols"]) == (8, 28)
    r = client.patch("/api/settings", json={"rows": 10, "cols": 36}, headers=auth)
    assert r.json()["grid_preset"] == "custom" and r.json()["cols"] == 36
    assert client.patch("/api/settings", json={"rows": 99}, headers=auth).status_code == 422
    assert client.patch("/api/settings", json={"animation": 101}, headers=auth).status_code == 422
    assert (
        client.patch("/api/settings", json={"theme": "Bad Theme"}, headers=auth).status_code == 422
    )
    r = client.patch(
        "/api/settings", json={"sound_enabled": False, "sound_volume": 0.25}, headers=auth
    )
    assert r.json()["sound_enabled"] is False and r.json()["sound_volume"] == 0.25
    assert client.get("/api/board/current").json()["settings"]["cols"] == 36


def test_images_upload_token_and_board(client, auth, settings):
    files = {"file": ("My Cat.PNG", io.BytesIO(PNG), "image/png")}
    r = client.post("/api/images", files=files, headers=auth)
    assert r.status_code == 201
    img = r.json()
    assert img == {
        "slug": "my-cat",
        "url": "/images/my-cat",
        "token": "{img:my-cat}",
        "content_type": "image/png",
        "bytes": len(PNG),
        "w": 1,
        "h": 1,
        "fit": "contain",
        "width": 1,
        "height": 1,
        "suggested": [[1, 1], [3, 2], [4, 3]],
    }
    assert (settings.data_dir / "images" / "my-cat.png").read_bytes() == PNG
    assert (settings.data_dir / "images" / "my-cat.json").exists(), "the sidecar"
    assert client.get("/images/my-cat").status_code == 200, "public for the board"
    assert client.get("/images/nope").status_code == 404
    assert [i["slug"] for i in client.get("/api/images", headers=auth).json()] == ["my-cat"]

    r = client.post(
        "/api/images",
        files={"file": ("x.png", io.BytesIO(PNG), "image/png")},
        data={"slug": "my-cat"},
        headers=auth,
    )
    assert r.status_code == 200, "same slug replaces"
    r = client.post(
        "/api/images", files={"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")}, headers=auth
    )
    assert r.status_code == 415
    r = client.post(
        "/api/images",
        files={"file": ("big.png", io.BytesIO(b"0" * (512 * 1024 + 1)), "image/png")},
        headers=auth,
    )
    assert r.status_code == 413

    r = client.post("/api/messages", json={"text": "HI {img:my-cat} 🎉"}, headers=auth)
    assert r.status_code == 201
    cat = {"img": "my-cat", "w": 1, "h": 1, "x": 0, "y": 0, "fit": "contain", "ar": 1.0}
    assert r.json()["rows"][0] == ["H", "I", " ", cat, " ", {"emoji": "🎉"}]
    assert r.json()["used"] == 6
    board = client.get("/api/board/current").json()
    assert board["rows"][0][3] == cat

    r = client.post("/api/messages", json={"text": "{img:not-there}"}, headers=auth)
    assert r.status_code == 422 and "Upload it first" in r.json()["detail"]
    assert client.delete("/api/images/my-cat", headers=auth).status_code == 204
    assert client.delete("/api/images/my-cat", headers=auth).status_code == 404
    assert not (settings.data_dir / "images" / "my-cat.json").exists(), "sidecar goes too"


def png_header(w: int, h: int) -> bytes:
    """Just the signature and IHDR — enough for the size reader; the server never decodes."""
    import struct
    import zlib

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    chunk = struct.pack(">I", 13) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return b"\x89PNG\r\n\x1a\n" + chunk + b"\x00" * 16


def test_image_size_sidecar_patch_and_board(client, auth, settings):
    """The owner's banner: 743×116 → suggested 9×1 / 19×2 / 28×3; PATCH sizes it; the board
    carries the parts; the stamp changes; a legacy picture (no sidecar) is still one bare cell."""
    files = {"file": ("CUE flow.png", io.BytesIO(png_header(743, 116)), "image/png")}
    img = client.post("/api/images", files=files, headers=auth).json()
    assert (img["width"], img["height"], img["w"], img["h"], img["fit"]) == (
        743,
        116,
        1,
        1,
        "contain",
    )
    assert img["suggested"] == [[9, 1], [19, 2], [28, 3]]

    r = client.patch("/api/images/cue-flow", json={"w": 9, "h": 1}, headers=auth)
    assert r.status_code == 200 and (r.json()["w"], r.json()["h"]) == (9, 1)
    assert client.patch("/api/images/cue-flow", json={"w": 37}, headers=auth).status_code == 422
    assert (
        client.patch("/api/images/cue-flow", json={"fit": "zoom"}, headers=auth).status_code == 422
    )
    assert client.patch("/api/images/nope", json={"w": 2}, headers=auth).status_code == 404
    listed = client.get("/api/images", headers=auth).json()
    assert [(i["slug"], i["w"], i["h"]) for i in listed] == [("cue-flow", 9, 1)]

    m = client.post("/api/messages", json={"text": "HI {img:cue-flow} THERE"}, headers=auth)
    assert m.status_code == 201
    row = m.json()["rows"][0]
    assert row[:3] == ["H", "I", " "] and row[12:] == [" ", "T", "H", "E", "R", "E"]
    parts = row[3:12]
    assert [p["x"] for p in parts] == list(range(9))
    assert all(
        (p["img"], p["w"], p["h"], p["y"], p["fit"], p["ar"])
        == ("cue-flow", 9, 1, 0, "contain", 6.405)
        for p in parts
    )
    assert m.json()["used"] == 2 + 1 + 9 + 1 + 5
    board = client.get("/api/board/current")
    stamp = board.json()["stamp"]
    assert board.json()["rows"][0][3]["w"] == 9

    # a size change on the panel changes the board on its next poll
    client.patch("/api/images/cue-flow", json={"w": 19, "h": 2, "fit": "cover"}, headers=auth)
    board = client.get("/api/board/current").json()
    assert board["stamp"] != stamp
    # "HI " + 19 = 22 fits the row exactly; the row below holds the lower parts; THERE moves down
    assert board["rows"][0][3]["w"] == 19 and board["rows"][0][21]["x"] == 18
    assert board["rows"][1][:3] == [" ", " ", " "] and board["rows"][1][3]["y"] == 1
    assert board["rows"][2][:5] == ["T", "H", "E", "R", "E"], "the text is pushed down"

    # too wide for this board (6 × 22): refused with the size in the message
    client.patch("/api/images/cue-flow", json={"w": 24, "h": 1}, headers=auth)
    r = client.post("/api/messages", json={"text": "{img:cue-flow}"}, headers=auth)
    assert (
        r.status_code == 422 and "24×1" in r.json()["detail"] and "22 columns" in r.json()["detail"]
    )
    r = client.post("/api/messages/preview", json={"text": "{img:cue-flow}"}, headers=auth)
    assert r.status_code == 200 and r.json()["rows"][0][0]["w"] == 22, "the preview clamps"

    # the inline override wins over the stored size
    r = client.post("/api/messages/preview", json={"text": "{img:cue-flow@3x1}"}, headers=auth)
    assert [c["w"] for c in r.json()["rows"][0]] == [3, 3, 3]

    # a picture from before sizes existed: file without a sidecar → one bare cell
    (settings.data_dir / "images" / "old.png").write_bytes(PNG)
    r = client.post("/api/messages/preview", json={"text": "{img:old}"}, headers=auth)
    assert r.json()["rows"][0] == [{"img": "old"}]
    old = next(i for i in client.get("/api/images", headers=auth).json() if i["slug"] == "old")
    assert (old["w"], old["h"], old["fit"]) == (1, 1, "stretch")
    assert (old["width"], old["suggested"]) == (1, [[1, 1], [3, 2], [4, 3]]), (
        "px read from the file"
    )
    # sizing a legacy picture writes the sidecar with the pixel size, so contain has an aspect
    (settings.data_dir / "images" / "wide.png").write_bytes(png_header(600, 100))
    wide = next(i for i in client.get("/api/images", headers=auth).json() if i["slug"] == "wide")
    assert (wide["fit"], wide["width"], wide["suggested"]) == (
        "stretch",
        600,
        [[9, 1], [17, 2], [26, 3]],
    )
    r = client.patch("/api/images/wide", json={"w": 9, "h": 1}, headers=auth)
    assert (r.json()["fit"], r.json()["width"]) == ("contain", 600)
    r = client.post("/api/messages/preview", json={"text": "{img:wide}"}, headers=auth)
    assert r.json()["rows"][0][0]["ar"] == 6.0 and r.json()["rows"][0][0]["fit"] == "contain"

    # replacing the file keeps the size its owner set
    client.patch("/api/images/cue-flow", json={"w": 9, "h": 1, "fit": "contain"}, headers=auth)
    files = {"file": ("x.png", io.BytesIO(png_header(1486, 232)), "image/png")}
    r = client.post("/api/images", files=files, data={"slug": "cue-flow"}, headers=auth)
    assert r.status_code == 200 and (r.json()["w"], r.json()["width"]) == (9, 1486)


def test_openapi_builds(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert {
        "/api/messages",
        "/api/messages/now",
        "/api/board/current",
        "/api/settings",
        "/api/images",
        "/images/{slug}",
    } <= set(paths)


PAGE = {"X-Requested-With": "DepartureBoard"}


def test_ui_source_from_cookie(client, token):
    client.post("/settings/login", data={"token": token}, follow_redirects=False)
    r = client.post("/api/messages", json={"text": "FROM THE PAGE"}, headers=PAGE)
    assert r.status_code == 201 and r.json()["source"] == "ui"


def test_cookie_write_needs_the_page_header(client, token):
    client.post("/settings/login", data={"token": token}, follow_redirects=False)
    assert client.get("/api/messages").status_code == 200, "reads are fine"
    r = client.post("/api/messages", json={"text": "CROSS SITE"})
    assert r.status_code == 403
    assert client.get("/api/messages").json() == []


def test_preview(client, auth):
    r = client.post("/api/messages/preview", json={"text": "hello {img:nope} €"}, headers=auth)
    assert r.status_code == 200
    p = r.json()
    assert p["rows"][0][:5] == list("HELLO")
    assert (p["grid_rows"], p["grid_cols"], p["capacity"]) == (6, 22, 132)
    assert p["unknown"] == ["€"] and p["missing_images"] == ["nope"] and not p["overflow"]
    p = client.post(
        "/api/messages/preview", json={"text": "\n".join("ABCDEFG")}, headers=auth
    ).json()
    assert p["overflow"] and p["used"] == 7
    assert client.get("/api/messages", headers=auth).json() == [], "nothing stored"


def test_now_accepts_plain_text(client, auth):
    r = client.post(
        "/api/messages/now",
        content=b"DINNER AT 7 {orange}",
        headers={**auth, "Content-Type": "text/plain; charset=utf-8"},
    )
    assert r.status_code == 201
    assert (
        "".join(c if isinstance(c, str) else "#" for c in r.json()["rows"][0]).strip()
        == "DINNER AT 7 #"
    )
    r = client.post(
        "/api/messages/now", content=b"   ", headers={**auth, "Content-Type": "text/plain"}
    )
    assert r.status_code == 422
    r = client.post(
        "/api/messages/now",
        content=b"not json",
        headers={**auth, "Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_openapi_reads_as_docs(client):
    spec = client.get("/openapi.json").json()
    assert {t["name"] for t in spec["tags"]} == {
        "messages",
        "board",
        "settings",
        "images",
        "system",
    }
    assert "Bearer" in spec["info"]["description"]
    now = spec["paths"]["/api/messages/now"]["post"]
    assert "text/plain" in now["requestBody"]["content"]
    assert "application/json" in now["requestBody"]["content"]
    assert spec["components"]["schemas"]["MessageIn"]["examples"][0]["text"].startswith("DINNER")
    assert all("summary" in op for p in spec["paths"].values() for op in p.values())


def test_cors_off_by_default_and_on_by_env(client, tmp_path):
    r = client.options(
        "/api/board/current",
        headers={"Origin": "https://dash.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in r.headers

    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    s = Settings(
        data_dir=tmp_path,
        cors_origins="https://dash.example.com, http://localhost:5173",
        _env_file=None,
    )
    assert s.cors_origin_list == ["https://dash.example.com", "http://localhost:5173"]
    with TestClient(create_app(s)) as c:
        r = c.get("/api/board/current", headers={"Origin": "https://dash.example.com"})
        assert r.headers["access-control-allow-origin"] == "https://dash.example.com"
        r = c.get("/api/board/current", headers={"Origin": "https://evil.example.com"})
        assert "access-control-allow-origin" not in r.headers


def test_patch_enabled_alone_keeps_everything_else(client, auth):
    body = {"text": "SWITCH ME", "priority": 5, "ends_at": "2099-01-01T00:00:00Z"}
    m = client.post("/api/messages", json=body, headers=auth).json()
    assert m["state"] == "live"
    off = client.patch(f"/api/messages/{m['id']}", json={"enabled": False}, headers=auth).json()
    assert (off["state"], off["enabled"]) == ("disabled", False)
    for key in ("text", "priority", "ends_at", "repeat", "starts_at", "source"):
        assert off[key] == m[key], key
    on = client.patch(f"/api/messages/{m['id']}", json={"enabled": True}, headers=auth).json()
    assert (on["state"], on["enabled"], on["text"]) == ("live", True, "SWITCH ME")


def test_show_seconds_round_trip_bounds_and_now(client, auth, clock):
    r = client.post("/api/messages", json={"text": "A", "show_seconds": 45}, headers=auth)
    assert r.status_code == 201 and r.json()["show_seconds"] == 45
    a = r.json()["id"]
    assert client.get(f"/api/messages/{a}", headers=auth).json()["show_seconds"] == 45
    r = client.patch(f"/api/messages/{a}", json={"show_seconds": None}, headers=auth)
    assert r.status_code == 200 and r.json()["show_seconds"] is None
    for bad in (4, 601, 0):
        assert (
            client.post("/api/messages", json={"text": "X", "show_seconds": bad}, headers=auth)
        ).status_code == 422
        assert (
            client.patch(f"/api/messages/{a}", json={"show_seconds": bad}, headers=auth)
        ).status_code == 422
    r = client.post("/api/messages/now", json={"text": "B", "show_seconds": 10}, headers=auth)
    assert r.status_code == 201 and r.json()["show_seconds"] == 10
    plain = client.post(
        "/api/messages/now",
        content="C",
        headers={**auth, "Content-Type": "text/plain"},
    )
    assert plain.status_code == 201 and plain.json()["show_seconds"] is None


def test_board_timer_weighted_and_out_of_the_etag(client, auth, clock):
    a = client.post("/api/messages", json={"text": "A"}, headers=auth).json()["id"]
    b = client.post("/api/messages", json={"text": "B", "show_seconds": 40}, headers=auth).json()[
        "id"
    ]
    t0 = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)
    held = {a: 0, b: 0}
    for s in range(0, 60, 5):
        clock["now"] = t0 + timedelta(seconds=s)
        held[client.get("/api/board/current").json()["message_id"]] += 5
    assert held == {a: 20, b: 40}, "the message with its own time holds the board twice as long"

    clock["now"] = t0 + timedelta(seconds=25)
    r = client.get("/api/board/current")
    assert r.json()["message_id"] == b
    assert r.json()["timer"] == {"seconds": 40, "remaining": 35, "own": True}
    etag = r.headers["ETag"]
    clock["now"] = t0 + timedelta(seconds=27)
    again = client.get("/api/board/current", headers={"If-None-Match": etag})
    assert again.status_code == 304, "two seconds later in the same slot: the ETag holds"
    assert client.get("/api/board/current").json()["timer"]["remaining"] == 33

    clock["now"] = t0 + timedelta(seconds=5)
    r = client.get("/api/board/current").json()
    assert r["message_id"] == a and r["timer"] == {"seconds": 20, "remaining": 15, "own": False}

    client.delete(f"/api/messages/{a}", headers=auth)
    r = client.get("/api/board/current").json()
    assert r["message_id"] == b and r["timer"] is None, "one message alone: no slot"
    assert "rotate_seconds" not in r["settings"]


def test_timer_ring_setting(client, auth):
    assert client.get("/api/settings", headers=auth).json()["timer_ring"] == "off"
    assert client.get("/api/board/current").json()["settings"]["timer_ring"] == "off"
    r = client.patch("/api/settings", json={"timer_ring": "own"}, headers=auth)
    assert r.status_code == 200 and r.json()["timer_ring"] == "own"
    assert client.get("/api/board/current").json()["settings"]["timer_ring"] == "own"
    assert (
        client.patch("/api/settings", json={"timer_ring": "maybe"}, headers=auth).status_code == 422
    )
    r = client.patch("/api/settings", json={"timer_ring": "all"}, headers=auth)
    assert r.json()["timer_ring"] == "all"


def test_board_etag_changes_when_rotation_stops(client, auth, clock):
    """Two rotating messages → one alone with the same rows: the TV must learn the slot is gone."""
    a = client.post("/api/messages", json={"text": "A"}, headers=auth).json()["id"]
    b = client.post("/api/messages", json={"text": "B"}, headers=auth).json()["id"]
    clock["now"] = datetime(2026, 10, 20, 12, 0, 5, tzinfo=UTC)  # A's slot (0–20 s)
    r = client.get("/api/board/current")
    assert r.json()["message_id"] == a and r.json()["timer"]["seconds"] == 20
    etag = r.headers["ETag"]
    client.patch(f"/api/messages/{b}", json={"enabled": False}, headers=auth)
    r = client.get("/api/board/current", headers={"If-None-Match": etag})
    assert r.status_code == 200 and r.json()["message_id"] == a and r.json()["timer"] is None


def test_background_settings(client, auth):
    s = client.get("/api/settings", headers=auth).json()
    assert (
        s["background_image"],
        s["background_blur"],
        s["background_dim"],
        s["background_fit"],
    ) == (
        "",
        12,
        30,
        "cover",
    )
    before = client.get("/api/board/current")
    assert before.json()["settings"]["background_image"] == ""
    # an uploaded picture must exist
    r = client.patch("/api/settings", json={"background_image": "img:poster"}, headers=auth)
    assert r.status_code == 422 and "Upload it first" in r.json()["detail"]
    client.post(
        "/api/images", files={"file": ("poster.png", io.BytesIO(PNG), "image/png")}, headers=auth
    )
    r = client.patch(
        "/api/settings",
        json={"background_image": "img:poster", "background_blur": 20, "background_dim": 40},
        headers=auth,
    )
    assert r.status_code == 200
    assert (
        r.json()["background_image"],
        r.json()["background_blur"],
        r.json()["background_dim"],
    ) == (
        "img:poster",
        20,
        40,
    )
    after = client.get("/api/board/current", headers={"If-None-Match": before.headers["ETag"]})
    assert after.status_code == 200, "the TV learns about the picture on its next poll"
    assert after.json()["settings"]["background_image"] == "img:poster"
    assert after.json()["settings"]["background_blur"] == 20
    # bounds and shapes
    for bad in (
        {"background_image": "poster"},
        {"background_image": "img:Bad Slug"},
        {"background_image": "builtin:nope"},
        {"background_blur": 41},
        {"background_dim": 91},
        {"background_fit": "zoom"},
    ):
        assert client.patch("/api/settings", json=bad, headers=auth).status_code == 422, bad
    r = client.patch("/api/settings", json={"background_fit": "contain"}, headers=auth)
    assert r.json()["background_fit"] == "contain"
    r = client.patch("/api/settings", json={"background_image": "builtin:gala"}, headers=auth)
    assert r.status_code == 200 and r.json()["background_image"] == "builtin:gala"
    assert client.get("/api/board/current").json()["settings"]["background_image"] == "builtin:gala"
    r = client.patch("/api/settings", json={"background_image": ""}, headers=auth)
    assert r.json()["background_image"] == "" and r.json()["background_blur"] == 20, (
        "clearing keeps the sliders"
    )
    assert client.get("/").status_code == 200
