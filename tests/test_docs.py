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
        ("CHANGELOG.md", ("#116", "#117", "#124", "#125")),
        (
            "README.md",
            ("**From your phone.**", "phone-now.png", "Add to Home Screen", "Show something now"),
        ),
        (
            "docs/tv-setup.md",
            ("The phone as the remote", "Add to Home Screen", "Show something now"),
        ),
    ):
        text = (ROOT / path).read_text()
        for needle in needles:
            assert needle in text, f"{path}: {needle}"


# --- Kubernetes mode (Epic 20): the chart and the doc agree with the app ---

CHART = ROOT / "deploy" / "helm" / "departureboard"


def _values() -> dict:
    import yaml

    return yaml.safe_load((CHART / "values.yaml").read_text())


def test_chart_version_is_the_app_version():
    """release.yml pushes the chart with the tag; Chart.yaml must already say so."""
    import yaml

    from app import __version__

    chart = yaml.safe_load((CHART / "Chart.yaml").read_text())
    assert chart["appVersion"] == __version__
    assert chart["version"] == __version__


def test_chart_env_covers_env_example():
    """Every DEPARTUREBOARD_* variable a user can set in Compose has a place in the chart (R1 of the
    epic): either an `env` key, the token Secret, or a deliberate exclusion listed here."""
    import re

    names = set(
        re.findall(r"^#?\s*(DEPARTUREBOARD_[A-Z_]+)=", (ROOT / ".env.example").read_text(), re.M)
    )
    values = _values()
    in_chart = set(values["env"])
    excluded = {
        "DEPARTUREBOARD_PORT",  # compose publishes a port; the Service does on a cluster
        "DEPARTUREBOARD_IMAGE",  # image.repository / image.tag
        "DEPARTUREBOARD_API_TOKEN",  # existingSecret / secretKey
        "DEPARTUREBOARD_TLS",  # the Ingress ends TLS; the probes speak http to the pod
        "DEPARTUREBOARD_TLS_HOSTS",
        "DEPARTUREBOARD_TLS_CERT",
        "DEPARTUREBOARD_TLS_KEY",
    }
    assert names, ".env.example names variables"
    missing = names - in_chart - excluded
    assert not missing, missing
    assert values["secretKey"] == "DEPARTUREBOARD_API_TOKEN"
    assert "DEPARTUREBOARD_TLS" not in in_chart


def test_kubernetes_doc_names_real_values():
    """Every `values` key the doc names exists in values.yaml (the epic's acceptance for #128)."""
    import re

    doc = (ROOT / "docs" / "kubernetes.md").read_text()
    values = _values()
    keys = set(
        re.findall(
            r"`((?:env|persistence|ingress|image|service)\.[A-Za-z_.]+|existingSecret|secretKey|resources|extraEnv)`",
            doc,
        )
    )
    assert keys, "the doc names values"
    for key in sorted(keys):
        node = values
        for part in key.rstrip(".*").split("."):
            if part == "*":
                break
            assert isinstance(node, dict) and part in node, key
            node = node[part]


def test_every_doc_knows_about_kubernetes():
    for path, needles in (
        (
            "README.md",
            (
                "helm install board oci://ghcr.io/cmldexter/charts/departureboard",
                "docs/kubernetes.md",
            ),
        ),
        (
            "docs/kubernetes.md",
            (
                "## Why one replica",
                "## The token",
                "## Upgrading",
                "## Backup",
                "deploy/kubernetes.yaml",
            ),
        ),
        (
            "deploy/helm/departureboard/README.md",
            ("strategy: Recreate", "helm.sh/resource-policy: keep"),
        ),
        ("CHANGELOG.md", ("#126", "#128")),
        ("llms.txt", ("oci://ghcr.io/cmldexter/charts/departureboard",)),
        ("SECURITY.md", ("Ingress",)),
    ):
        text = (ROOT / path).read_text()
        for needle in needles:
            assert needle in text, f"{path}: {needle}"


def test_rendered_manifest_is_the_chart():
    """deploy/kubernetes.yaml is `helm template` of the chart with defaults — CI diffs it; here the
    cheap half: it exists, carries the chart version and no Ingress."""
    rendered = (ROOT / "deploy" / "kubernetes.yaml").read_text()
    from app import __version__

    assert f"ghcr.io/cmldexter/departureboard:{__version__}" in rendered
    assert "kind: Deployment" in rendered and "kind: PersistentVolumeClaim" in rendered
    assert "kind: Ingress" not in rendered
    assert "namespace: departureboard" in rendered
