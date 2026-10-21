from fastapi.testclient import TestClient

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
    for needle in ("Messages", "Display", "Images", "settings.js", "Server time", "feltbykraft"):
        assert needle in r.text, needle


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
