"""A calendar of boards: saved boards on dates, and the switch that saves back before it loads."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _clock(client, y, m, d, h=9):
    client.app.state.clock = lambda: datetime(y, m, d, h, tzinfo=UTC)


def _board_named(client, auth, slug, text):
    """Save a board holding one message under `slug`, then empty the live board."""
    for m in client.get("/api/messages", headers=auth).json():
        client.delete(f"/api/messages/{m['id']}", headers=auth)
    client.post("/api/messages", json={"text": text}, headers=auth)
    r = client.post(f"/api/profiles/{slug}/save", json={"name": slug.title()}, headers=auth)
    assert r.status_code in (200, 201), r.text


def _live(client, auth):
    s = client.get("/api/settings", headers=auth).json()
    texts = [m["text"] for m in client.get("/api/messages", headers=auth).json()]
    return s["active_profile"], texts


def _plan(client, auth):
    """Three boards and the plan from the issue: Halloween on the 31st, Christmas 20–26."""
    _board_named(client, auth, "everyday", "DINNER AT 7")
    _board_named(client, auth, "halloween", "BOO")
    _board_named(client, auth, "xmas", "MERRY XMAS")
    r = client.patch("/api/settings", json={"calendar_everyday": "everyday"}, headers=auth)
    assert r.status_code == 200 and r.json()["calendar_everyday"] == "everyday"
    a = client.post(
        "/api/calendar",
        json={"profile": "halloween", "start": "2026-10-31", "end": "2026-10-31"},
        headers=auth,
    )
    b = client.post(
        "/api/calendar",
        json={"profile": "xmas", "start": "2026-12-20", "end": "2026-12-26", "note": "family"},
        headers=auth,
    )
    assert a.status_code == 201 and b.status_code == 201, (a.text, b.text)
    return a.json(), b.json()


def test_the_calendar_needs_the_token(client):
    assert client.get("/api/calendar").status_code == 401
    assert client.post("/api/calendar/apply").status_code == 401


def test_an_empty_calendar_changes_nothing(client, auth):
    r = client.get("/api/calendar", headers=auth)
    assert r.status_code == 200
    assert r.json()["entries"] == [] and r.json()["today"]["profile"] is None
    r = client.post("/api/calendar/apply", headers=auth)
    assert r.status_code == 200 and r.json()["changed"] is False and r.json()["applied"] == ""


def test_the_plan_from_the_issue(client, auth, settings):
    _clock(client, 2026, 10, 30)
    a, b = _plan(client, auth)
    assert (a["name"], a["missing"], b["note"], b["end"]) == (
        "Halloween",
        False,
        "family",
        "2026-12-26",
    )
    cal = client.get("/api/calendar", headers=auth).json()
    assert [e["id"] for e in cal["entries"]] == [a["id"], b["id"]]
    assert cal["today"] == {
        "date": "2026-10-30",
        "profile": "everyday",
        "entry_id": None,
        "until": None,
    }
    # the 30th: nothing planned → the everyday board
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert (out["changed"], out["loaded"], out["applied"]) == (
        True,
        "everyday",
        "everyday:everyday",
    )
    assert _live(client, auth) == ("everyday", ["DINNER AT 7"])
    assert client.post("/api/calendar/apply", headers=auth).json()["changed"] is False, "idempotent"
    # the 31st: Halloween, within a poll
    _clock(client, 2026, 10, 31)
    cal = client.get("/api/calendar", headers=auth).json()
    assert cal["today"] == {
        "date": "2026-10-31",
        "profile": "halloween",
        "entry_id": a["id"],
        "until": "2026-10-31",
    }
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert (out["loaded"], out["saved_back"]) == ("halloween", "everyday")
    assert _live(client, auth) == ("halloween", ["BOO"])
    board = client.get("/api/board/current").json()
    assert "".join(c for c in board["rows"][0] if isinstance(c, str)).strip() == "BOO"
    # edits on the day are saved back when the day ends
    client.post("/api/messages", json={"text": "TRICK OR TREAT"}, headers=auth)
    _clock(client, 2026, 11, 1)
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert (out["loaded"], out["saved_back"]) == ("everyday", "halloween")
    saved = json.loads((settings.data_dir / "profiles" / "halloween.json").read_text())
    assert [m["text"] for m in saved["messages"]] == ["BOO", "TRICK OR TREAT"], "nothing lost"
    assert _live(client, auth) == ("everyday", ["DINNER AT 7"])
    # Christmas
    _clock(client, 2026, 12, 24)
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert out["loaded"] == "xmas" and _live(client, auth)[1] == ["MERRY XMAS"]
    assert client.get("/api/calendar", headers=auth).json()["today"]["until"] == "2026-12-26"
    _clock(client, 2026, 12, 27)
    assert client.post("/api/calendar/apply", headers=auth).json()["loaded"] == "everyday"
    # the file is the plan
    plan = json.loads((settings.data_dir / "calendar.json").read_text())
    assert [e["profile"] for e in plan["entries"]] == ["halloween", "xmas"]


def test_overlaps_resolve_to_the_later_start(client, auth):
    _board_named(client, auth, "xmas", "MERRY XMAS")
    _board_named(client, auth, "party", "PARTY")
    client.post(
        "/api/calendar",
        json={"profile": "xmas", "start": "2026-12-20", "end": "2026-12-26"},
        headers=auth,
    )
    client.post(
        "/api/calendar",
        json={"profile": "party", "start": "2026-12-24", "end": "2026-12-24"},
        headers=auth,
    )
    _clock(client, 2026, 12, 23)
    assert client.post("/api/calendar/apply", headers=auth).json()["loaded"] == "xmas"
    _clock(client, 2026, 12, 24)
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert (out["loaded"], out["saved_back"]) == ("party", "xmas"), "the one-day entry wins its day"
    _clock(client, 2026, 12, 25)
    assert client.post("/api/calendar/apply", headers=auth).json()["loaded"] == "xmas", (
        "and the long one is back"
    )


def test_no_everyday_board_means_the_board_stays(client, auth):
    _board_named(client, auth, "halloween", "BOO")
    client.post(
        "/api/calendar",
        json={"profile": "halloween", "start": "2026-10-31", "end": "2026-10-31"},
        headers=auth,
    )
    _clock(client, 2026, 10, 31)
    assert client.post("/api/calendar/apply", headers=auth).json()["loaded"] == "halloween"
    _clock(client, 2026, 11, 1)
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert (out["changed"], out["loaded"], out["applied"]) == (False, None, "")
    assert _live(client, auth) == ("halloween", ["BOO"]), "stays on the last planned board"
    # and a later return to the same entry applies again
    client.post("/api/messages", json={"text": "NEW"}, headers=auth)
    _clock(client, 2026, 10, 31)
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert out["loaded"] == "halloween" and out["saved_back"] == "halloween"


def test_an_unsaved_live_board_is_kept_under_a_date(client, auth, settings):
    client.post("/api/messages", json={"text": "WORK IN PROGRESS"}, headers=auth)
    assert client.get("/api/settings", headers=auth).json()["active_profile"] == ""
    client.put(
        "/api/profiles/party", json={"name": "Party", "messages": [{"text": "PARTY"}]}, headers=auth
    )
    client.post(
        "/api/calendar",
        json={"profile": "party", "start": "2026-10-31", "end": "2026-10-31"},
        headers=auth,
    )
    _clock(client, 2026, 10, 31)
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert out["saved_back"] == "unsaved-2026-10-31" and out["loaded"] == "party"
    saved = json.loads((settings.data_dir / "profiles" / "unsaved-2026-10-31.json").read_text())
    assert [m["text"] for m in saved["messages"]] == ["WORK IN PROGRESS"]
    assert _live(client, auth) == ("party", ["PARTY"])
    # an empty unsaved board is not worth a file
    for m in client.get("/api/messages", headers=auth).json():
        client.delete(f"/api/messages/{m['id']}", headers=auth)
    client.delete("/api/profiles/party", headers=auth)  # clears the pointer
    client.put(
        "/api/profiles/party", json={"name": "Party", "messages": [{"text": "PARTY"}]}, headers=auth
    )
    client.patch("/api/settings", json={"calendar_everyday": "party"}, headers=auth)
    _clock(client, 2027, 1, 1)
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert out["saved_back"] is None and out["loaded"] == "party"


def test_a_deleted_board_is_missing_and_skipped(client, auth):
    _board_named(client, auth, "everyday", "DINNER")
    _board_named(client, auth, "gone", "GONE")
    client.patch("/api/settings", json={"calendar_everyday": "everyday"}, headers=auth)
    e = client.post(
        "/api/calendar", json={"profile": "gone", "start": "2026-10-31"}, headers=auth
    ).json()
    client.delete("/api/profiles/gone", headers=auth)
    cal = client.get("/api/calendar", headers=auth).json()
    assert cal["entries"][0]["missing"] is True and cal["entries"][0]["name"] is None
    _clock(client, 2026, 10, 31)
    assert cal["entries"][0]["id"] == e["id"]
    out = client.post("/api/calendar/apply", headers=auth).json()
    assert out["loaded"] == "everyday", "the missing entry is skipped"
    assert client.get("/api/calendar", headers=auth).json()["today"]["profile"] == "everyday"


def test_validation_edits_and_a_restart(client, auth, settings):
    _board_named(client, auth, "party", "PARTY")
    bad = client.post(
        "/api/calendar", json={"profile": "nope", "start": "2026-10-31"}, headers=auth
    )
    assert bad.status_code == 422 and "No saved board" in bad.text
    bad = client.post(
        "/api/calendar",
        json={"profile": "party", "start": "2026-10-31", "end": "2026-10-30"},
        headers=auth,
    )
    assert bad.status_code == 422 and "before start" in bad.text
    assert (
        client.post(
            "/api/calendar", json={"profile": "party", "start": "soon"}, headers=auth
        ).status_code
        == 422
    )
    bad = client.patch("/api/settings", json={"calendar_everyday": "nope"}, headers=auth)
    assert bad.status_code == 422 and "No saved board" in bad.text
    assert (
        client.patch(
            "/api/settings", json={"calendar_everyday": "Bad Slug"}, headers=auth
        ).status_code
        == 422
    )
    e = client.post(
        "/api/calendar",
        json={"profile": "party", "start": "2026-10-31", "end": "2026-11-02"},
        headers=auth,
    ).json()
    r = client.patch(
        f"/api/calendar/{e['id']}", json={"end": "2026-10-31", "note": "one night"}, headers=auth
    )
    assert r.status_code == 200 and (r.json()["end"], r.json()["note"]) == (
        "2026-10-31",
        "one night",
    )
    assert (
        client.patch(
            f"/api/calendar/{e['id']}", json={"end": "2026-10-01"}, headers=auth
        ).status_code
        == 422
    )
    assert client.patch("/api/calendar/99", json={"note": "x"}, headers=auth).status_code == 404
    assert client.delete("/api/calendar/99", headers=auth).status_code == 404
    with TestClient(create_app(settings)) as again:
        h = {"Authorization": f"Bearer {again.app.state.api_token}"}
        cal = again.get("/api/calendar", headers=h).json()
        assert [(x["id"], x["profile"], x["end"]) for x in cal["entries"]] == [
            (e["id"], "party", "2026-10-31")
        ]
        assert again.delete(f"/api/calendar/{e['id']}", headers=h).status_code == 204
        assert again.get("/api/calendar", headers=h).json()["entries"] == []
    # none of it reaches the TV
    board = client.get("/api/board/current").json()
    assert not any(k.startswith("calendar_") for k in board["settings"])


def test_the_background_tick_switches_on_its_own(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data", api_token=None, _env_file=None, calendar_tick_seconds=0.2
    )
    with TestClient(create_app(settings)) as client:
        auth = {"Authorization": f"Bearer {client.app.state.api_token}"}
        client.put(
            "/api/profiles/party",
            json={"name": "Party", "messages": [{"text": "PARTY"}]},
            headers=auth,
        )
        client.post("/api/calendar", json={"profile": "party", "start": "2026-10-31"}, headers=auth)
        _clock(client, 2026, 10, 31)
        import time

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if client.get("/api/settings", headers=auth).json()["active_profile"] == "party":
                break
            time.sleep(0.1)
        assert _live(client, auth) == ("party", ["PARTY"]), "the loop did it, nobody asked"
