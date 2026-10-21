"""The version the app reports is the one pyproject.toml declares (release.yml checks the tag against it)."""

import tomllib
from pathlib import Path

from app import __version__


def test_version_matches_pyproject():
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == __version__
