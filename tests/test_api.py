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
    }
    assert (settings.data_dir / "images" / "my-cat.png").read_bytes() == PNG
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
    assert r.json()["rows"][0] == ["H", "I", " ", {"img": "my-cat"}, " ", {"emoji": "🎉"}]
    assert r.json()["used"] == 6
    board = client.get("/api/board/current").json()
    assert board["rows"][0][3] == {"img": "my-cat"}

    r = client.post("/api/messages", json={"text": "{img:not-there}"}, headers=auth)
    assert r.status_code == 422 and "Upload it first" in r.json()["detail"]
    assert client.delete("/api/images/my-cat", headers=auth).status_code == 204
    assert client.delete("/api/images/my-cat", headers=auth).status_code == 404


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
