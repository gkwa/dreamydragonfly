"""Parse human-friendly duration strings like 1D2H, 36h, 1d12h30m."""

import datetime
import re


def parse_duration(s: str) -> datetime.timedelta:
    """
    Parse a duration string (case insensitive).

    Accepted format: any combination of <N>d, <N>h, <N>m in that order.
    Examples: 1D2H, 36h, 1d12h30m, 30M
    """
    upper = s.upper().strip()
    pattern = re.compile(r"^(?:(\d+)D)?(?:(\d+)H)?(?:(\d+)M)?$")
    match = pattern.fullmatch(upper)
    if not match or not any(match.groups()):
        raise ValueError(f"cannot parse duration {s!r} — expected format like 1D2H or 36H")
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    return datetime.timedelta(days=days, hours=hours, minutes=minutes)
