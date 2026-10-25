from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_settings_requires_token(client):
    r = client.get("/settings")
    assert r.status_code == 401
    assert "Token" in r.text  # the login form


def test_settings_with_bearer(client, token):
    r = client.get("/settings", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "feltbykraft" in r.text


def test_settings_with_wrong_bearer(client):
    r = client.get("/settings", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_login_sets_cookie_then_page_opens(client, token):
    r = client.post("/settings/login", data={"token": token}, follow_redirects=False)
    assert r.status_code == 303
    assert "db_session" in r.cookies
    r = client.get("/settings")
    assert r.status_code == 200


def test_login_wrong_token(client):
    r = client.post("/settings/login", data={"token": "nope"}, follow_redirects=False)
    assert r.status_code == 401
    assert "did not match" in r.text


def test_logout_clears_cookie(client, token):
    client.post("/settings/login", data={"token": token}, follow_redirects=False)
    client.post("/settings/logout", follow_redirects=False)
    assert client.get("/settings").status_code == 401


def test_settings_page_panels(client, token):
    r = client.get("/settings", headers={"Authorization": f"Bearer {token}"})
    for needle in (
        "Messages",
        "Display",
        "Images",
        "settings.js",
        "Server time",
        "feltbykraft",
        'name="show_seconds"',
        'name="timer_ring"',
        "at the size set there",
        "give it a size below",
        'id="look"',
        'role="radiogroup"',
        'data-theme="walnut"',
        'id="backdrop-form"',
        'data-bg="builtin:gala"',
        "/static/backgrounds/thumbs/wood.jpg",
        'name="background_blur"',
        'name="background_dim"',
        'name="background_fit"',
        'id="backdrop-clear"',
        'id="flaps-form"',
        'name="cell_radius"',
        'name="cell_gap"',
        'name="split_line"',
        'id="flaps-picture"',
        'id="flaps-classic"',
        'id="qr-form"',
        'name="data"',
        'id="guests"',
        'id="guest-rotate"',
        'name="guest_auto_approve"',
        'name="guest_priority"',
        'name="guest_show_seconds"',
        'id="guest-pending"',
        'id="guest-approved"',
        'id="guest-clear"',
        'id="guests-count"',
        'id="guest-qr"',
        'id="boards"',
        'id="board-switch"',
        'id="board-save-as"',
        'id="board-delete"',
        'id="qr-board"',
    ):
        assert needle in r.text, needle
    assert 'name="theme"' not in r.text, "the theme left the Display form for the swatches"


def test_integrate_page(client, token):
    assert client.get("/integrate").status_code == 401
    r = client.get("/integrate", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert 'data-base="http://testserver"' in r.text
    assert f'data-token="{token}"' in r.text
    for kind in (
        "now",
        "now-plain",
        "window",
        "daily",
        "weekly",
        "image",
        "list",
        "delete",
        "preset",
        "board",
    ):
        assert f'data-kind="{kind}"' in r.text, kind
    assert "integrate.js" in r.text and "/llms.txt" in r.text


def test_login_redirects_to_next(client, token):
    r = client.post(
        "/settings/login", data={"token": token, "next": "/integrate"}, follow_redirects=False
    )
    assert r.status_code == 303 and r.headers["location"] == "/integrate"
    r = client.post(
        "/settings/login",
        data={"token": token, "next": "https://evil.example.com"},
        follow_redirects=False,
    )
    assert r.headers["location"] == "/settings"


def test_settings_page_embeds_the_board(client, token):
    html = client.get("/settings", headers={"Authorization": f"Bearer {token}"}).text
    assert 'id="live-board"' in html and 'src="/?embed"' in html
    assert 'id="preview-board"' in html and 'id="live-now"' in html
    assert "mini-board" not in html and "preview-grid" not in html
    # the accessibility pass
    assert 'id="toast" class="toast" role="status" aria-live="polite"' in html
    assert 'id="message-error" role="alert"' in html
    assert html.count('<th scope="col">') == 4
    assert '<fieldset id="repeat-days"' in html and "<legend>Days</legend>" in html


def test_login_cookie_is_secure_only_over_https(settings, client, token):
    r = client.post("/settings/login", data={"token": token}, follow_redirects=False)
    assert "secure" not in r.headers["set-cookie"].lower()
    with TestClient(create_app(settings), base_url="https://testserver") as https:
        r = https.post("/settings/login", data={"token": token}, follow_redirects=False)
    cookie = r.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie


def test_settings_page_has_the_cast_button(client, token):
    html = client.get("/settings", headers={"Authorization": f"Bearer {token}"}).text
    assert 'id="cast"' in html and 'aria-pressed="false"' in html
    assert '<dialog id="cast-help"' in html and 'id="cast-help-why"' in html
    assert "/static/js/cast.js" in html


def test_settings_page_lists_the_addresses(monkeypatch, client, token):
    """Without a name: the addresses the server sees, and a hint to name the board."""
    from app.routers import pages

    monkeypatch.setattr(pages, "local_ipv4s", lambda: ["10.0.0.5"])
    html = client.get("/settings", headers={"Authorization": f"Bearer {token}"}).text
    assert "Your board is at" in html
    assert 'data-copy="http://10.0.0.5"' in html and "as this server sees it" in html
    assert "DEPARTUREBOARD_HOST=dboard.localhost" in html
    assert "by name" not in html


def test_settings_page_shows_the_name(monkeypatch, tmp_path, token):
    from app.routers import pages

    monkeypatch.setattr(pages, "local_ipv4s", lambda: ["10.0.0.5", "10.0.0.5"])
    s = Settings(data_dir=tmp_path / "named", host="dboard.localhost", _env_file=None)
    with TestClient(create_app(s), base_url="http://192.168.1.20:8085") as c:
        tok = c.app.state.api_token
        html = c.get("/settings", headers={"Authorization": f"Bearer {tok}"}).text
        assert html.index('data-copy="http://dboard.localhost:8085"') < html.index(
            'data-copy="http://192.168.1.20:8085"'
        )
        assert "by name" in html and "the address you are using" in html
        assert html.count('data-copy="http://10.0.0.5:8085"') == 1
        assert "DEPARTUREBOARD_HOST=dboard.localhost" not in html
        # The integrate page pre-fills the name, with the request's scheme and port.
        r = c.get("/integrate", headers={"Authorization": f"Bearer {tok}"})
        assert 'data-base="http://dboard.localhost:8085"' in r.text


def test_host_must_be_a_bare_name(tmp_path):
    import pytest
    from pydantic import ValidationError

    for bad in ("http://dboard.localhost", "dboard.localhost:8080", "a b", "-x.localhost", "x/"):
        with pytest.raises(ValidationError, match="bare name"):
            Settings(data_dir=tmp_path, host=bad, _env_file=None)
    assert (
        Settings(data_dir=tmp_path, host=" DBoard.LocalHost ", _env_file=None).host
        == "dboard.localhost"
    )
    assert Settings(data_dir=tmp_path, host="", _env_file=None).host == ""


def test_login_page_says_where_the_token_is(client):
    """Three commands, one per way of running the board, each with a Copy button and a prompt
    that is not part of the copied text."""
    html = client.get("/settings").text
    assert 'id="where-token"' in html and "/static/js/login.js" in html
    for cmd in (
        "docker compose exec departureboard cat /data/api_token",
        "cat data/api_token",
        'docker compose logs departureboard | grep -A 1 "API token"',
    ):
        assert cmd in html, cmd
    assert html.count('class="link copy"') == 3
    assert html.count('<span class="prompt" aria-hidden="true">$ </span>') == 3
    assert "pbcopy &lt; data/api_token" not in html  # the old line that mixed the two servers up


def test_login_page_asks_for_a_fraction(client):
    """One muted line, one link, to a named relief effort; outside the form and the token help."""
    html = client.get("/settings").text
    assert 'id="give"' in html
    assert "https://www.directrelief.org/emergency/venezuela-earthquakes-2026/" in html
    assert 'rel="noopener" target="_blank"' in html
    assert html.index('id="where-token"') < html.index('id="give"')
