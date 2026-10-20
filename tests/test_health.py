import re

from app import __version__


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "version": __version__}


def test_board_renders_placeholder(client):
    r = client.get("/")
    assert r.status_code == 200
    assert len(re.findall(r'<div class="cell">', r.text)) == 6 * 22
    glyphs = "".join(re.findall(r'<div class="half top"><span class="glyph">(.?)</span>', r.text))
    assert len(glyphs) == 6 * 22
    assert "DEPARTUREBOARD" in glyphs
    assert "SET UP AT /SETTINGS" in glyphs


def test_first_boot_creates_db_and_token(client, settings):
    assert (settings.data_dir / "departureboard.db").exists()
    token_file = settings.data_dir / "api_token"
    assert token_file.exists()
    assert token_file.read_text().strip() == client.app.state.api_token
    assert oct(token_file.stat().st_mode & 0o777) == "0o600"


def test_second_boot_reuses_token(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(settings)) as c1:
        first = c1.app.state.api_token
    with TestClient(create_app(settings)) as c2:
        assert c2.app.state.api_token == first


def test_env_token_wins(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    s = Settings(data_dir=tmp_path, api_token="my-own-token", _env_file=None)
    with TestClient(create_app(s)) as c:
        assert c.app.state.api_token == "my-own-token"
        assert not (tmp_path / "api_token").exists()
