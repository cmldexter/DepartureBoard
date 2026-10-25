"""The docs name every limit the code enforces: the numbers in docs/guests.md are the code's."""

from pathlib import Path

from app.models import DEFAULT_SETTINGS
from app.services import guest

ROOT = Path(__file__).resolve().parents[1]


def test_guests_doc_names_every_limit():
    doc = (ROOT / "docs" / "guests.md").read_text()
    for needle in (
        f"**{guest.MAX_TEXT} characters**",
        f"**{guest.MAX_NICK} characters**",
        f"**{guest.MAX_PHOTO // (1024 * 1024)} MB**",
        f"**{guest.PHOTO_ROWS} rows**",
        f"**{guest.PER_IP_HOUR} posts** an hour",
        f"**{guest.PER_BOARD_HOUR} posts** an hour",
        f"**{guest.TOKEN_CHARS} characters**",
        "PNG, JPEG or WebP",
        f"default {DEFAULT_SETTINGS['guest_priority']}",
        f"default {DEFAULT_SETTINGS['guest_show_seconds']} s",
    ):
        assert needle in doc, needle
    assert set(guest.PHOTO_TYPES) == {"image/png", "image/jpeg", "image/webp"}


def test_every_doc_knows_about_guests():
    readme = (ROOT / "README.md").read_text()
    assert "**Guests.**" in readme and "docs/guests.md" in readme
    assert "twenty posts an hour" in readme and "two hundred" in readme
    assert guest.PER_IP_HOUR == 20 and guest.PER_BOARD_HOUR == 200, "the README says it in words"
    for path, needles in (
        ("CHANGELOG.md", ("#133", "#134", "#135")),
        (
            "README.md",
            (
                "walks you through",
                "welcome-step1.png",
                "welcome-step3.png",
                "Run the walkthrough again",
                "docs/tv-setup.md#the-one-minute-version",
            ),
        ),
        ("docs/tv-setup.md", ("walks you through", "## The one-minute version")),
        ("llms.txt", ("setup_done", "DELETE /api/settings/setup_done")),
        ("integrations/skills/departureboard/SKILL.md", ("setup_done",)),
        ("llms.txt", ("/api/guest/rotate", "/api/guest/qr", "/api/posts", "guest_auto_approve")),
        ("llms.txt", ("/api/profiles", "kept_disabled", "active_profile")),
        ("integrations/skills/departureboard/SKILL.md", ("/api/profiles",)),
        ("integrations/curl/examples.sh", ("profile save", "api/profiles")),
        ("docs/profiles.md", ("kept_disabled", "/now", "pictures_missing", "cron")),
        ("README.md", ("**Boards.**", "docs/profiles.md", "**Calendar.**", "docs/calendar.md")),
        ("llms.txt", ("/api/calendar", "calendar_everyday")),
        ("integrations/skills/departureboard/SKILL.md", ("/api/calendar",)),
        ("integrations/curl/examples.sh", ("calendar add", "api/calendar")),
        (
            "docs/calendar.md",
            (
                "saves the live board back",
                "later start wins",
                "calendar.json",
                "CALENDAR_TICK_SECONDS",
            ),
        ),
        ("integrations/skills/departureboard/SKILL.md", ("/api/guest/rotate", "/api/posts")),
        ("SECURITY.md", ("guest link", "docs/guests.md")),
        ("docs/qr.md", ("guests.md",)),
        ("CHANGELOG.md", ("#116", "#117")),
    ):
        text = (ROOT / path).read_text()
        for needle in needles:
            assert needle in text, f"{path}: {needle}"
