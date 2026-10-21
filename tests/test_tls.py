"""Optional HTTPS: off by default, your own pair, or a self-signed pair made on first boot."""

import shutil
import ssl
import subprocess

import pytest
import uvicorn
from pydantic import ValidationError

from app import __main__ as launcher
from app.config import Settings
from app.services import tls

needs_openssl = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not on PATH")


def test_tls_off_by_default(settings):
    assert tls.tls_paths(settings) is None
    assert not (settings.data_dir / "tls").exists()


def test_own_cert_and_key(tmp_path):
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("x")
    key.write_text("x")
    s = Settings(data_dir=tmp_path / "data", tls_cert=cert, tls_key=key, _env_file=None)
    assert tls.tls_paths(s) == (cert, key)
    assert not (tmp_path / "data" / "tls").exists()


@pytest.mark.parametrize("which", ["tls_cert", "tls_key"])
def test_cert_or_key_alone_is_an_error(tmp_path, which):
    f = tmp_path / "one.pem"
    f.write_text("x")
    s = Settings(data_dir=tmp_path, _env_file=None, **{which: f})
    with pytest.raises(SystemExit) as e:
        tls.tls_paths(s)
    assert "DEPARTUREBOARD_TLS_CERT" in str(e.value) and "DEPARTUREBOARD_TLS_KEY" in str(e.value)


def test_missing_file_is_an_error(tmp_path):
    cert, key = tmp_path / "c.pem", tmp_path / "missing.pem"
    cert.write_text("x")
    s = Settings(data_dir=tmp_path, tls_cert=cert, tls_key=key, _env_file=None)
    with pytest.raises(SystemExit) as e:
        tls.tls_paths(s)
    assert "missing.pem" in str(e.value)


def test_tls_mode_is_validated(tmp_path):
    with pytest.raises(ValidationError):
        Settings(data_dir=tmp_path, tls="yes", _env_file=None)


def test_san_entries(monkeypatch, tmp_path):
    monkeypatch.setattr(tls.socket, "gethostname", lambda: "boardhost")
    monkeypatch.setattr(tls, "local_ipv4s", lambda: ["10.0.0.5", "10.0.0.5"])
    s = Settings(data_dir=tmp_path, tls_hosts="board.local, 192.168.1.20,localhost", _env_file=None)
    assert tls.san_entries(s) == [
        "DNS:localhost",
        "IP:127.0.0.1",
        "DNS:boardhost",
        "IP:10.0.0.5",
        "DNS:board.local",
        "IP:192.168.1.20",
    ]


def test_container_hostname_is_left_out(monkeypatch, tmp_path):
    monkeypatch.setattr(tls.socket, "gethostname", lambda: "0123456789ab")
    monkeypatch.setattr(tls, "local_ipv4s", lambda: [])
    s = Settings(data_dir=tmp_path, _env_file=None)
    assert tls.san_entries(s) == ["DNS:localhost", "IP:127.0.0.1"]


def test_local_ipv4s_has_no_loopback():
    for ip in tls.local_ipv4s():
        assert not ip.startswith("127.")


@needs_openssl
def test_self_signed_generates_and_reuses(tmp_path):
    s = Settings(
        data_dir=tmp_path / "data",
        tls="self-signed",
        tls_hosts="board.local,192.168.1.20",
        _env_file=None,
    )
    cert, key = tls.tls_paths(s)
    assert (cert, key) == (
        tmp_path / "data" / "tls" / "cert.pem",
        tmp_path / "data" / "tls" / "key.pem",
    )
    assert cert.exists() and key.exists()
    assert oct(key.stat().st_mode & 0o777) == "0o600"
    ssl.create_default_context().load_cert_chain(cert, key)  # parses and the key matches
    out = subprocess.run(
        ["openssl", "x509", "-noout", "-ext", "subjectAltName", "-in", str(cert)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    for needle in (
        "DNS:localhost",
        "IP Address:127.0.0.1",
        "DNS:board.local",
        "IP Address:192.168.1.20",
    ):
        assert needle in out, needle
    before = cert.read_bytes()
    assert tls.tls_paths(s) == (cert, key)
    assert cert.read_bytes() == before, "the second boot reuses the pair"


def test_self_signed_without_openssl_fails_clearly(monkeypatch, tmp_path):
    monkeypatch.setattr(tls.shutil, "which", lambda name: None)
    s = Settings(data_dir=tmp_path, tls="self-signed", _env_file=None)
    with pytest.raises(SystemExit) as e:
        tls.tls_paths(s)
    assert "openssl" in str(e.value)
    assert not (tmp_path / "tls").exists()


def test_launcher_passes_paths_to_uvicorn(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))
    launcher.main(Settings(data_dir=tmp_path, _env_file=None))
    (a, kw) = calls[-1]
    assert a == ("app.main:app",)
    assert (kw["host"], kw["port"], kw["ssl_certfile"], kw["ssl_keyfile"]) == (
        "0.0.0.0",
        8000,
        None,
        None,
    )
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("x")
    key.write_text("x")
    launcher.main(Settings(data_dir=tmp_path, tls_cert=cert, tls_key=key, _env_file=None))
    (a, kw) = calls[-1]
    assert (kw["ssl_certfile"], kw["ssl_keyfile"]) == (str(cert), str(key))
