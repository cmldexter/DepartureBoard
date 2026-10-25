"""Boards you can switch: the live board saved as a file, loaded back, copied, renamed, deleted."""

import io
import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_api import PNG


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _settings(client, auth):
    return client.get("/api/settings", headers=auth).json()


def _messages(client, auth):
    return client.get("/api/messages", headers=auth).json()


def _board(client):
    return client.get("/api/board/current").json()


def test_profiles_need_the_token(client):
    assert client.get("/api/profiles").status_code == 401
    assert client.post("/api/profiles/party/save").status_code == 401
    assert client.post("/api/profiles/party/load").status_code == 401


def test_save_and_load_round_trip(client, auth, settings):
    # a board: large, walnut, picture mode, three messages (one scheduled, one with a picture)
    client.patch(
        "/api/settings",
        json={"grid_preset": "large", "theme": "walnut", "cell_gap": 10, "idle_text": "HELLO"},
        headers=auth,
    )
    client.post(
        "/api/images", files={"file": ("cat.png", io.BytesIO(PNG), "image/png")}, headers=auth
    )
    client.post("/api/messages", json={"text": "WELCOME {yellow}", "priority": 2}, headers=auth)
    client.post(
        "/api/messages",
        json={
            "text": "STANDUP {blue}",
            "repeat": "daily",
            "repeat_start": "09:00",
            "repeat_end": "10:00",
            "show_seconds": 30,
        },
        headers=auth,
    )
    client.post("/api/messages", json={"text": "CAT {img:cat}", "enabled": False}, headers=auth)
    assert _settings(client, auth)["active_profile"] == ""
    r = client.post("/api/profiles/party", json={"name": "Party"}, headers=auth)
    assert r.status_code == 405, "save is an action, not a PUT"
    r = client.post("/api/profiles/party/save", json={"name": "Party"}, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json() == {
        "slug": "party",
        "name": "Party",
        "saved_at": r.json()["saved_at"],
        "messages": 3,
        "pictures_missing": [],
        "active": True,
        "changed": False,
    }
    assert _settings(client, auth)["active_profile"] == "party"
    path = settings.data_dir / "profiles" / "party.json"
    data = json.loads(path.read_text())
    assert data["name"] == "Party" and len(data["messages"]) == 3
    assert data["settings"]["grid_preset"] == "large" and data["settings"]["cell_gap"] == 10
    for key in ("guest_token", "active_profile", "calendar_everyday", "calendar_applied"):
        assert key not in data["settings"], key
    assert (
        data["messages"][1]["repeat_start"] == "09:00" and data["messages"][1]["show_seconds"] == 30
    )
    assert data["messages"][2]["enabled"] is False
    # change everything
    for m in _messages(client, auth):
        client.delete(f"/api/messages/{m['id']}", headers=auth)
    client.post("/api/messages", json={"text": "WORK WORK"}, headers=auth)
    client.patch(
        "/api/settings", json={"grid_preset": "compact", "theme": "midnight"}, headers=auth
    )
    stamp = _board(client)["stamp"]
    # load it back
    r = client.post("/api/profiles/party/load", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["kept_disabled"] == [] and r.json()["active"] is True
    msgs = _messages(client, auth)
    assert [m["text"] for m in msgs] == ["WELCOME {yellow}", "STANDUP {blue}", "CAT {img:cat}"]
    assert [m["priority"] for m in msgs] == [2, 0, 0]
    assert (msgs[1]["repeat"], msgs[1]["repeat_start"], msgs[1]["show_seconds"]) == (
        "daily",
        "09:00",
        30,
    )
    assert msgs[2]["enabled"] is False and all(m["source"] == "api" for m in msgs)
    s = _settings(client, auth)
    assert (s["grid_preset"], s["rows"], s["theme"], s["cell_gap"], s["idle_text"]) == (
        "large",
        8,
        "walnut",
        10,
        "HELLO",
    )
    board = _board(client)
    assert board["stamp"] != stamp and board["settings"]["theme"] == "walnut"
    assert "".join(c for c in board["rows"][0] if isinstance(c, str)).strip() == "WELCOME"
    # saving again overwrites: 200, the name kept
    r = client.post("/api/profiles/party/save", headers=auth)
    assert r.status_code == 200 and r.json()["name"] == "Party"
    listed = client.get("/api/profiles", headers=auth).json()
    assert [(p["slug"], p["messages"], p["active"]) for p in listed] == [("party", 3, True)]


def test_a_profile_from_a_file_keeps_what_does_not_fit_disabled(client, auth):
    file = {
        "name": "Hand made",
        "settings": {"grid_preset": "custom", "rows": 4, "cols": 16, "theme": "arctic-white"},
        "messages": [
            {"text": "SHORT"},
            {"text": "x" * 200, "priority": 5},
            {"text": "ALREADY OFF " * 10, "enabled": False},
        ],
    }
    r = client.put("/api/profiles/hand", json=file, headers=auth)
    assert r.status_code == 201 and r.json()["messages"] == 3 and r.json()["active"] is False
    assert client.put("/api/profiles/hand", json=file, headers=auth).status_code == 200
    assert client.get("/api/profiles/hand", headers=auth).json()["name"] == "Hand made"
    r = client.post("/api/profiles/hand/load", headers=auth)
    assert r.status_code == 200, r.text
    kept = r.json()["kept_disabled"]
    assert len(kept) == 1 and kept[0]["text"] == "x" * 200 and "rows" in kept[0]["reason"]
    msgs = _messages(client, auth)
    assert [(m["text"][:5], m["enabled"], m["state"]) for m in msgs] == [
        ("SHORT", True, "live"),
        ("xxxxx", False, "disabled"),
        ("ALREA", False, "disabled"),
    ]
    s = _settings(client, auth)
    assert (s["rows"], s["cols"], s["theme"], s["active_profile"]) == (
        4,
        16,
        "arctic-white",
        "hand",
    )
    # a profile with a bad message is refused whole, nothing half-applied
    bad = {"name": "Bad", "messages": [{"text": "OK"}, {"text": "", "priority": 999}]}
    assert client.put("/api/profiles/bad", json=bad, headers=auth).status_code == 422
    assert [m["text"][:5] for m in _messages(client, auth)] == ["SHORT", "xxxxx", "ALREA"]


def test_missing_pictures_are_listed_and_a_gone_background_is_cleared(client, auth):
    client.post(
        "/api/images", files={"file": ("cat.png", io.BytesIO(PNG), "image/png")}, headers=auth
    )
    client.post(
        "/api/images", files={"file": ("bg.png", io.BytesIO(PNG), "image/png")}, headers=auth
    )
    client.patch("/api/settings", json={"background_image": "img:bg"}, headers=auth)
    client.post("/api/messages", json={"text": "CAT {img:cat}"}, headers=auth)
    client.post("/api/profiles/pets/save", headers=auth)
    assert client.get("/api/profiles", headers=auth).json()[0]["pictures_missing"] == []
    client.delete("/api/images/cat", headers=auth)
    client.delete("/api/images/bg", headers=auth)
    assert client.get("/api/profiles", headers=auth).json()[0]["pictures_missing"] == ["bg", "cat"]
    r = client.post("/api/profiles/pets/load", headers=auth)
    assert r.status_code == 200 and r.json()["pictures_missing"] == ["bg", "cat"]
    assert _messages(client, auth)[0]["text"] == "CAT {img:cat}", (
        "the message is kept, the hole shows"
    )
    assert _settings(client, auth)["background_image"] == "", "a gone background is cleared"


def test_copy_rename_delete_and_the_slug_rules(client, auth, settings):
    client.post("/api/messages", json={"text": "ONE"}, headers=auth)
    assert (
        client.post("/api/profiles/party/save", json={"name": "Party"}, headers=auth).status_code
        == 201
    )
    r = client.post("/api/profiles/party/copy", json={"slug": "party-2"}, headers=auth)
    assert r.status_code == 201 and r.json()["name"] == "Party copy" and r.json()["active"] is False
    assert (settings.data_dir / "profiles" / "party-2.json").exists()
    assert (
        client.post("/api/profiles/party/copy", json={"slug": "party-2"}, headers=auth).status_code
        == 409
    )
    assert (
        client.post("/api/profiles/nope/copy", json={"slug": "x"}, headers=auth).status_code == 404
    )
    r = client.patch("/api/profiles/party-2", json={"name": "Work"}, headers=auth)
    assert r.status_code == 200 and r.json()["name"] == "Work"
    assert [p["slug"] for p in client.get("/api/profiles", headers=auth).json()] == [
        "party",
        "party-2",
    ]
    assert client.delete("/api/profiles/party", headers=auth).status_code == 204
    assert client.delete("/api/profiles/party", headers=auth).status_code == 404
    assert _settings(client, auth)["active_profile"] == "", (
        "deleting the active one clears the pointer"
    )
    assert _messages(client, auth)[0]["text"] == "ONE", "the live board is untouched"
    assert client.post("/api/profiles/Bad%20Slug/save", headers=auth).status_code == 422
    assert client.post("/api/profiles/party/load", headers=auth).status_code == 404
    assert client.get("/api/profiles/party", headers=auth).status_code == 404


def test_the_listing_says_when_the_live_board_changed(client, auth):
    client.post("/api/messages", json={"text": "ONE"}, headers=auth)
    client.post("/api/profiles/party/save", headers=auth)
    client.post("/api/profiles/party/copy", json={"slug": "other"}, headers=auth)

    def flags():
        return {p["slug"]: p["changed"] for p in client.get("/api/profiles", headers=auth).json()}

    assert flags() == {"other": False, "party": False}
    client.post("/api/messages", json={"text": "TWO"}, headers=auth)
    assert flags() == {"other": False, "party": True}, (
        "a new message = changed, the other untouched"
    )
    client.post("/api/profiles/party/save", headers=auth)
    assert flags() == {"other": False, "party": False}
    client.patch("/api/settings", json={"theme": "walnut"}, headers=auth)
    assert flags()["party"] is True, "a display change counts too"
    client.post("/api/profiles/party/load", headers=auth)
    assert flags()["party"] is False, "a load is the saved state"
    client.post("/api/guest/rotate", headers=auth)
    assert flags()["party"] is False, "the guest door is not part of a profile"


def test_the_guest_door_is_not_part_of_a_profile(client, auth):
    link = client.post("/api/guest/rotate", headers=auth).json()
    client.post("/api/profiles/party/save", headers=auth)
    client.patch("/api/settings", json={"guest_token": ""}, headers=auth)
    client.post("/api/profiles/party/load", headers=auth)
    assert _settings(client, auth)["guest_token"] == "", "a load does not reopen the door"
    client.patch("/api/settings", json={"guest_token": link["token"]}, headers=auth)
    client.post("/api/profiles/party/load", headers=auth)
    assert _settings(client, auth)["guest_token"] == link["token"], "nor close it"


def test_a_restart_keeps_the_files(client, auth, settings):
    client.post("/api/messages", json={"text": "KEEP ME"}, headers=auth)
    client.post("/api/profiles/party/save", json={"name": "Party"}, headers=auth)
    with TestClient(create_app(settings)) as again:
        h = {"Authorization": f"Bearer {again.app.state.api_token}"}
        listed = again.get("/api/profiles", headers=h).json()
        assert [(p["slug"], p["name"], p["messages"], p["active"]) for p in listed] == [
            ("party", "Party", 1, True)
        ]
        assert again.get("/api/settings", headers=h).json()["active_profile"] == "party"
