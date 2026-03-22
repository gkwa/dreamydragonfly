"""DoughFermentation: reference table and interpolation for bulk fermentation."""

import subject as fermentation_subject

# Source: The Sourdough Journey dough temping guide
# https://thesourdoughjourney.com/wp-content/uploads/2024/08/TSJ-Dough-Temping-Guide.pdf
_TABLE: list[dict[str, float]] = [
    {"temp_f": 65, "hours": 16.0, "target_rise_pct": 100},
    {"temp_f": 66, "hours": 16.0, "target_rise_pct": 95},
    {"temp_f": 67, "hours": 15.0, "target_rise_pct": 90},
    {"temp_f": 68, "hours": 14.0, "target_rise_pct": 85},
    {"temp_f": 69, "hours": 13.0, "target_rise_pct": 80},
    {"temp_f": 70, "hours": 12.0, "target_rise_pct": 75},
    {"temp_f": 71, "hours": 11.0, "target_rise_pct": 70},
    {"temp_f": 72, "hours": 10.0, "target_rise_pct": 65},
    {"temp_f": 73, "hours": 9.0,  "target_rise_pct": 60},
    {"temp_f": 74, "hours": 8.0,  "target_rise_pct": 55},
    {"temp_f": 75, "hours": 7.0,  "target_rise_pct": 50},
    {"temp_f": 76, "hours": 7.0,  "target_rise_pct": 50},
    {"temp_f": 77, "hours": 6.0,  "target_rise_pct": 40},
    {"temp_f": 78, "hours": 6.0,  "target_rise_pct": 40},
    {"temp_f": 79, "hours": 5.5,  "target_rise_pct": 30},
    {"temp_f": 80, "hours": 5.5,  "target_rise_pct": 30},
]

_MIN_TEMP = float(min(r["temp_f"] for r in _TABLE))
_MAX_TEMP = float(max(r["temp_f"] for r in _TABLE))


def _clamp(temp_f: float) -> float:
    return max(_MIN_TEMP, min(_MAX_TEMP, temp_f))


def _interpolate(temp_f: float, col: str) -> float:
    temp_f = _clamp(temp_f)
    low = next(r for r in reversed(_TABLE) if r["temp_f"] <= temp_f)
    high = next(r for r in _TABLE if r["temp_f"] >= temp_f)
    if low["temp_f"] == high["temp_f"]:
        return low[col]
    frac = (temp_f - low["temp_f"]) / (high["temp_f"] - low["temp_f"])
    return low[col] + frac * (high[col] - low[col])


class DoughFermentation(fermentation_subject.FermentationSubject):
    def expected_hours(self, temp_f: float) -> float:
        return _interpolate(temp_f, "hours")

    def target_rise_pct(self, temp_f: float) -> float:
        return _interpolate(temp_f, "target_rise_pct")
