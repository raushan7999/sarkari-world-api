"""IST date helpers.

Every timestamp this API emits is Indian Standard Time with an explicit
`+05:30` offset, never `Z`. The database connection is pinned to
Asia/Kolkata (see `src/db/session.py`), so naive values read back from
Postgres are already IST wall-clock time.
"""

from datetime import UTC, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def now_ist() -> datetime:
    """Current time as a naive IST value, matching what Postgres stores."""
    return datetime.now(IST).replace(tzinfo=None)


def to_ist(value: datetime | None) -> datetime | None:
    """Attach IST to a naive value, or convert an aware one into IST."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value.astimezone(IST)


def to_ist_iso(value: datetime | None) -> str | None:
    """Render as `YYYY-MM-DDTHH:MM:SS.sss+05:30`, matching the Node API."""
    aware = to_ist(value)
    if aware is None:
        return None
    millis = aware.microsecond // 1000
    return f"{aware.strftime('%Y-%m-%dT%H:%M:%S')}.{millis:03d}+05:30"


def ist_day_bounds(day: str) -> tuple[datetime, datetime]:
    """Naive IST start/end for an ISO `YYYY-MM-DD` day, for date filters."""
    parsed = datetime.strptime(day, "%Y-%m-%d")
    return parsed, parsed + timedelta(days=1)


def utc_now() -> datetime:
    """Timezone-aware UTC, for the one timestamptz column on User."""
    return datetime.now(UTC)
