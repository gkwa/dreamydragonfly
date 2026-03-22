"""FermentationCalculator: compute progress via the fermentation integral."""

import dataclasses
import datetime

import polars

import subject as fermentation_subject


@dataclasses.dataclass
class FermentationProgress:
    elapsed_hours: float
    avg_temp_f: float
    current_temp_f: float
    last_reading_at: datetime.datetime
    target_rise_pct: float
    progress_pct: float


class FermentationCalculator:
    def __init__(self, subject: fermentation_subject.FermentationSubject) -> None:
        self._subject = subject

    def compute(self, readings: polars.DataFrame) -> FermentationProgress:
        """
        Compute fermentation progress from a time-ordered DataFrame of readings.

        readings must have columns [datetime, temperature_f] sorted ascending,
        containing all readings since fermentation start.

        Each reading's temperature contributes to the integral weighted by the
        time interval until the next reading.  Target rise is looked up from the
        time-weighted average temperature so it reflects the actual conditions
        experienced by the dough.
        """
        if len(readings) == 0:
            raise ValueError("no readings available since the given start time")

        df = readings.with_columns(
            polars.col("datetime").diff().dt.total_seconds().fill_null(0.0).alias("interval_s")
        )

        rows = df.to_dicts()
        total_seconds = sum(r["interval_s"] for r in rows)

        if total_seconds == 0:
            avg_temp_f = float(rows[0]["temperature_f"])
        else:
            avg_temp_f = (
                sum(r["temperature_f"] * r["interval_s"] for r in rows) / total_seconds
            )

        accumulated = sum(
            (r["interval_s"] / 3600.0) / self._subject.expected_hours(r["temperature_f"])
            for r in rows
        )

        current_temp_f = float(rows[-1]["temperature_f"])
        last_reading_at = rows[-1]["datetime"]
        target_rise = self._subject.target_rise_pct(avg_temp_f)
        progress_pct = min(accumulated * 100.0, 100.0)

        return FermentationProgress(
            elapsed_hours=total_seconds / 3600.0,
            avg_temp_f=avg_temp_f,
            current_temp_f=current_temp_f,
            last_reading_at=last_reading_at,
            target_rise_pct=target_rise,
            progress_pct=progress_pct,
        )
