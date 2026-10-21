"""The version the app reports is the one pyproject.toml declares (release.yml checks the tag against it)."""

import tomllib
from pathlib import Path

from app import __version__


def test_version_matches_pyproject():
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == __version__


def test_readme_images_exist():
    """Every picture the README shows is in the repo (GitHub renders them from the path)."""
    import re

    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text()
    paths = set(re.findall(r'(?:src="|\]\()(docs/media/[^")]+)', readme))
    assert paths, "the README has pictures"
    for rel in sorted(paths):
        assert (root / rel).is_file(), rel
