"""SensorData: load temperature readings from the parquet file."""

import datetime
import pathlib

import polars


class SensorData:
    def __init__(self, path: pathlib.Path) -> None:
        self._path = path

    def readings_since(
        self,
        start: datetime.datetime,
        end: datetime.datetime | None = None,
    ) -> polars.DataFrame:
        """
        Return temperature readings between start and end (inclusive), sorted ascending.

        If end is None, reads up to the latest available data.
        Both start and end must be timezone-aware.
        """
        df = polars.read_parquet(self._path)
        start_utc = start.astimezone(datetime.timezone.utc)
        mask = polars.col("temperature_f").is_not_null() & (polars.col("datetime") >= start_utc)
        if end is not None:
            end_utc = end.astimezone(datetime.timezone.utc)
            mask = mask & (polars.col("datetime") <= end_utc)
        return df.filter(mask).select(["datetime", "temperature_f"]).sort("datetime")
