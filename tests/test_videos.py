"""A video behind the board: uploads under videos/, served with Range, `video:<slug>` in the chain."""

import io

import pytest

from app.services import videos

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4096  # the server never decodes it


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _upload(client, auth, name="rain.mp4", data=MP4, ctype="video/mp4", slug=None):
    files = {"file": (name, io.BytesIO(data), ctype)}
    form = {"slug": slug} if slug else None
    return client.post("/api/videos", files=files, data=form, headers=auth)


def test_upload_list_replace_delete(client, auth, settings):
    assert client.get("/api/videos", headers=auth).json() == []
    r = _upload(client, auth)
    assert r.status_code == 201, r.text
    v = r.json()
    assert (v["slug"], v["url"], v["token"], v["content_type"], v["bytes"]) == (
        "rain",
        "/videos/rain",
        "video:rain",
        "video/mp4",
        len(MP4),
    )
    assert (settings.data_dir / "videos" / "rain.mp4").exists()
    assert not list((settings.data_dir / "videos").glob(".*.part")), "no temp file left"
    # the same slug again replaces; a WebM under the same slug replaces the mp4 file
    assert _upload(client, auth).status_code == 200
    r = _upload(client, auth, name="rain.webm", ctype="video/webm")
    assert r.status_code == 200 and r.json()["content_type"] == "video/webm"
    assert not (settings.data_dir / "videos" / "rain.mp4").exists()
    assert [x["slug"] for x in client.get("/api/videos", headers=auth).json()] == ["rain"]
    assert client.delete("/api/videos/rain", headers=auth).status_code == 204
    assert client.delete("/api/videos/rain", headers=auth).status_code == 404
    assert client.get("/videos/rain").status_code == 404


def test_upload_refusals(client, auth, monkeypatch):
    r = _upload(client, auth, name="x.png", ctype="image/png")
    assert r.status_code == 415 and "MP4 or WebM" in r.json()["detail"]
    r = _upload(client, auth, slug="Not OK!")
    assert r.status_code == 422
    r = _upload(client, auth, data=b"")
    assert r.status_code == 422 and "Empty" in r.json()["detail"]
    monkeypatch.setattr(videos, "MAX_BYTES", 1024)
    r = _upload(client, auth, slug="big")
    assert r.status_code == 413 and "1080p" in r.json()["detail"]
    assert client.get("/api/videos", headers=auth).json() == [], "nothing kept over the cap"
    # unauthenticated
    assert client.get("/api/videos").status_code == 401


def test_served_with_range_for_the_tv(client, auth):
    _upload(client, auth)
    r = client.get("/videos/rain")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("video/mp4")
    assert r.headers["accept-ranges"] == "bytes"
    assert r.headers["cache-control"] == "no-cache"
    r = client.get("/videos/rain", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206
    assert r.headers["content-range"] == f"bytes 0-99/{len(MP4)}"
    assert len(r.content) == 100


def test_video_in_the_settings_chain(client, auth):
    r = client.patch("/api/settings", json={"background_image": "video:rain"}, headers=auth)
    assert r.status_code == 422 and "Upload it first" in r.json()["detail"]
    r = client.patch("/api/settings", json={"background_image": "clip:rain"}, headers=auth)
    assert r.status_code == 422
    _upload(client, auth)
    before = client.get("/api/board/current")
    r = client.patch(
        "/api/settings", json={"background_image": "video:rain", "background_blur": 0}, headers=auth
    )
    assert r.status_code == 200 and r.json()["background_image"] == "video:rain"
    after = client.get("/api/board/current", headers={"If-None-Match": before.headers["ETag"]})
    assert after.status_code == 200 and after.json()["settings"]["background_image"] == "video:rain"
    # the board page renders the clip for the first paint, the embed and preview pages too
    for q in ("", "?embed", "?embed&preview"):
        html = client.get(f"/{q}").text
        assert '<video id="backdrop-video" muted playsinline loop autoplay' in html
        assert 'src="/videos/rain"' in html, q
        assert '"background_image": "video:rain"' in html
    # deleting the clip takes it off the TV
    assert client.delete("/api/videos/rain", headers=auth).status_code == 204
    assert client.get("/api/settings", headers=auth).json()["background_image"] == ""
    assert 'src="/videos/' not in client.get("/").text


def test_profile_with_a_gone_video_clears_it(client, auth):
    _upload(client, auth)
    client.patch("/api/settings", json={"background_image": "video:rain"}, headers=auth)
    assert client.post("/api/profiles/p/save", json={"name": "P"}, headers=auth).status_code == 201
    saved = client.get("/api/profiles/p", headers=auth).json()
    assert saved["settings"]["background_image"] == "video:rain"
    client.delete("/api/videos/rain", headers=auth)
    assert client.post("/api/profiles/p/load", headers=auth).status_code == 200
    assert client.get("/api/settings", headers=auth).json()["background_image"] == ""
