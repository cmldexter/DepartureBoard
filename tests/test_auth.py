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
