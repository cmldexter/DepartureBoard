"""Optional HTTPS: the certificate and key uvicorn serves with.

Off by default. DEPARTUREBOARD_TLS_CERT + DEPARTUREBOARD_TLS_KEY hand over a PEM pair of your
own; DEPARTUREBOARD_TLS=self-signed makes one on first boot under <data_dir>/tls/ with the
`openssl` command (present in the python:*-slim image) and reuses it on every later boot.
HTTPS is what lets a TV browser take the native Screen Wake Lock (secure contexts only) and
what the Presentation API needs; browsers warn once about a self-signed certificate, see
docs/tv-setup.md. Used by `python -m app` (app/__main__.py), not by the app itself.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path

from app.config import Settings

log = logging.getLogger(__name__)

TLS_DIR = "tls"
CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"
# The most Apple devices accept for a server certificate, even a user-trusted one.
DAYS = 825
# Docker gives a container a 12-hex hostname; it means nothing to a browser.
_CONTAINER_ID = re.compile(r"^[0-9a-f]{12}$")


def local_ipv4s() -> list[str]:
    """The machine's non-loopback IPv4 addresses, best effort, no dependencies."""
    found: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    try:
        # The outbound interface's address; nothing is sent (TEST-NET-1, UDP).
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 1))
            found.append(s.getsockname()[0])
    except OSError:
        pass
    out: list[str] = []
    for ip in found:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.is_loopback or addr.is_unspecified or ip in out:
            continue
        out.append(ip)
    return out


def san_entries(settings: Settings) -> list[str]:
    """Subject alternative names for a self-signed certificate: localhost, this host's name and
    addresses, the board's name (DEPARTUREBOARD_HOST) and whatever DEPARTUREBOARD_TLS_HOSTS adds
    (the address the TV types)."""
    names = ["DNS:localhost", "IP:127.0.0.1"]
    host = socket.gethostname()
    if host and not _CONTAINER_ID.match(host):
        names.append(f"DNS:{host}")
    names.extend(f"IP:{ip}" for ip in local_ipv4s())
    if settings.host:
        names.append(f"DNS:{settings.host}")
    for h in settings.tls_host_list:
        try:
            ipaddress.ip_address(h)
            names.append(f"IP:{h}")
        except ValueError:
            names.append(f"DNS:{h}")
    out: list[str] = []
    for n in names:
        if n not in out:
            out.append(n)
    return out


def ensure_self_signed(settings: Settings) -> tuple[Path, Path]:
    """The pair under <data_dir>/tls/, made on first boot and reused afterwards."""
    tls_dir = settings.data_dir / TLS_DIR
    cert, key = tls_dir / CERT_FILE, tls_dir / KEY_FILE
    if cert.exists() and key.exists():
        return cert, key
    openssl = shutil.which("openssl")
    if not openssl:
        raise SystemExit(
            "DEPARTUREBOARD_TLS=self-signed needs the openssl command, which is not on PATH; "
            "set DEPARTUREBOARD_TLS_CERT and DEPARTUREBOARD_TLS_KEY to a pair of your own instead."
        )
    tls_dir.mkdir(parents=True, exist_ok=True)
    names = san_entries(settings)
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            str(DAYS),
            "-subj",
            "/CN=departureboard",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-addext",
            "subjectAltName=" + ",".join(names),
            "-addext",
            "extendedKeyUsage=serverAuth",
            "-addext",
            "keyUsage=digitalSignature,keyEncipherment",
        ],
        check=True,
        capture_output=True,
    )
    key.chmod(0o600)
    log.warning(
        "\n"
        "============================================================\n"
        "  DepartureBoard made a self-signed certificate (first boot)\n"
        "  %s\n"
        "  Valid %d days for: %s\n"
        "  The board is now https:// on the same port; browsers warn\n"
        "  once. Delete %s to make a new one.\n"
        "============================================================",
        cert,
        DAYS,
        ", ".join(names),
        tls_dir,
    )
    return cert, key


def tls_paths(settings: Settings) -> tuple[Path, Path] | None:
    """(cert, key) to serve with, or None for plain http. Your own pair wins over self-signed."""
    cert, key = settings.tls_cert, settings.tls_key
    if (cert is None) != (key is None):
        raise SystemExit(
            "DEPARTUREBOARD_TLS_CERT and DEPARTUREBOARD_TLS_KEY go together: set both or neither."
        )
    if cert is not None and key is not None:
        for path in (cert, key):
            if not path.is_file():
                raise SystemExit(f"TLS file not found: {path}")
            if not os.access(path, os.R_OK):
                raise SystemExit(f"TLS file is not readable by uid {os.getuid()}: {path}")
        return cert, key
    if settings.tls == "self-signed":
        return ensure_self_signed(settings)
    return None
