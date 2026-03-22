"""SensorData: load temperature readings from the parquet file."""

import datetime
import pathlib

import polars


class SensorData:
    def __init__(self, path: pathlib.Path) -> None:
        self._path = path

    def readings_since(self, start: datetime.datetime) -> polars.DataFrame:
        """
        Return all temperature readings from start to the latest available,
        sorted ascending by datetime.

        start must be timezone-aware (UTC or local — polars will compare correctly
        as long as the tzinfo is set).
        """
        df = polars.read_parquet(self._path)
        start_utc = start.astimezone(datetime.timezone.utc)
        return (
            df.filter(
                polars.col("temperature_f").is_not_null()
                & (polars.col("datetime") >= start_utc)
            )
            .select(["datetime", "temperature_f"])
            .sort("datetime")
        )
