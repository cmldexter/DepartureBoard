"""Table-driven scheduler cases. `now` is injected; the zone is America/New_York unless said."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.models import Message
from app.services.scheduler import rotation, state

NY = ZoneInfo("America/New_York")
MON, TUE, WED, THU, FRI, SAT, SUN = (1 << i for i in range(7))
WEEKDAYS = MON | TUE | WED | THU | FRI


def msg(**kw) -> Message:
    base = {
        "id": 1,
        "text": "X",
        "enabled": True,
        "priority": 0,
        "repeat": "none",
        "repeat_days": 0,
    }
    return Message(**{**base, **kw})


def ny(y, mo, d, h, mi=0) -> datetime:
    """A local New York instant, as UTC."""
    return datetime(y, mo, d, h, mi, tzinfo=NY).astimezone(UTC)


CASES = [
    # name, message, now (UTC), expected state
    ("always on", msg(), ny(2026, 10, 20, 12), "live"),
    ("disabled", msg(enabled=False), ny(2026, 10, 20, 12), "disabled"),
    ("before window", msg(starts_at=ny(2026, 10, 21, 9)), ny(2026, 10, 20, 12), "scheduled"),
    ("in window", msg(starts_at=ny(2026, 10, 20, 9), ends_at=ny(2026, 10, 20, 17)), ny(2026, 10, 20, 12), "live"),
    ("after window", msg(ends_at=ny(2026, 10, 19, 17)), ny(2026, 10, 20, 12), "expired"),
    ("naive stored UTC", msg(starts_at=datetime(2026, 10, 20, 15)), ny(2026, 10, 20, 12), "live"),
    ("daily in hours", msg(repeat="daily", repeat_start="09:00", repeat_end="17:00"), ny(2026, 10, 20, 12), "live"),
    ("daily out of hours", msg(repeat="daily", repeat_start="09:00", repeat_end="17:00"), ny(2026, 10, 20, 18), "scheduled"),
    ("daily end exclusive", msg(repeat="daily", repeat_start="09:00", repeat_end="17:00"), ny(2026, 10, 20, 17), "scheduled"),
    ("daily all day", msg(repeat="daily"), ny(2026, 10, 20, 3), "live"),
    ("midnight window at 01:00", msg(repeat="daily", repeat_start="22:00", repeat_end="06:00"), ny(2026, 10, 20, 1), "live"),
    ("midnight window at 23:00", msg(repeat="daily", repeat_start="22:00", repeat_end="06:00"), ny(2026, 10, 20, 23), "live"),
    ("midnight window at noon", msg(repeat="daily", repeat_start="22:00", repeat_end="06:00"), ny(2026, 10, 20, 12), "scheduled"),
    ("weekly Mon–Fri on a Tuesday", msg(repeat="weekly", repeat_days=WEEKDAYS), ny(2026, 10, 20, 12), "live"),
    ("weekly Mon–Fri on a Saturday", msg(repeat="weekly", repeat_days=WEEKDAYS), ny(2026, 10, 24, 12), "scheduled"),
    ("weekly Fri night window, Sat 01:00 counts as Friday", msg(repeat="weekly", repeat_days=FRI, repeat_start="22:00", repeat_end="02:00"), ny(2026, 10, 24, 1), "live"),
    ("weekly Fri night window, Fri 01:00 is Thursday's", msg(repeat="weekly", repeat_days=FRI, repeat_start="22:00", repeat_end="02:00"), ny(2026, 10, 23, 1), "scheduled"),
    ("weekly with window passed", msg(repeat="weekly", repeat_days=WEEKDAYS, ends_at=ny(2026, 10, 1, 0)), ny(2026, 10, 20, 12), "expired"),
    ("DST fall-back day, 01:30 local", msg(repeat="daily", repeat_start="01:00", repeat_end="02:00"), datetime(2026, 11, 1, 6, 30, tzinfo=UTC), "live"),
    ("DST spring-forward day, 03:30 local", msg(repeat="daily", repeat_start="03:00", repeat_end="04:00"), datetime(2026, 3, 8, 7, 30, tzinfo=UTC), "live"),
]  # fmt: skip


@pytest.mark.parametrize(("name", "m", "now", "expected"), CASES, ids=[c[0] for c in CASES])
def test_state(name, m, now, expected):
    assert state(m, now, NY) == expected


def test_rotation_among_top_priority():
    a, b, c = msg(id=1, priority=5), msg(id=2, priority=5), msg(id=3, priority=0)
    live = [a, b, c]
    t0 = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)
    seen = {rotation(live, t0.replace(second=s), 20).id for s in range(0, 60, 5)}
    assert seen == {1, 2}, "the lower priority message waits"
    assert rotation([], t0, 20) is None
    assert rotation([c], t0, 20) is c


def test_rotation_is_stateless_and_in_step():
    live = [msg(id=1), msg(id=2), msg(id=3)]
    t = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)
    assert rotation(live, t, 20) is rotation(live, t.replace(second=19), 20)
    assert rotation(live, t, 20) is not rotation(live, t.replace(second=20), 20)
