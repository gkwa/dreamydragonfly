#!/usr/bin/env python3
"""Explore temperature distribution to find the most common values."""

import sys
import polars

PARQUET_PATH = "/Users/mtm/pdev/taylormonacelli/kindfinkitten/merged_data.parquet"


def main() -> None:
    df = polars.read_parquet(PARQUET_PATH)

    print("=== Overall temperature distribution ===")
    print(f"Total rows: {len(df)}")
    print(f"Null temps: {df['temperature_f'].null_count()}")
    print()

    # Round to nearest degree to get meaningful buckets
    df = df.with_columns(
        polars.col("temperature_f").round(0).cast(polars.Int64).alias("temp_rounded")
    )

    # Value counts — the "most common" temperature
    freq = (
        df.filter(polars.col("temp_rounded").is_not_null())
        .group_by("temp_rounded")
        .agg(polars.len().alias("count"))
        .sort("count", descending=True)
    )

    print("=== Top 20 most common temperatures (rounded to nearest °F) ===")
    print(freq.head(20))
    print()

    # Mode (single most common)
    mode_temp = freq.row(0)[0]
    mode_count = freq.row(0)[1]
    total_non_null = len(df) - df["temperature_f"].null_count()
    print(f"Mode: {mode_temp}°F  ({mode_count} readings, {100*mode_count/total_non_null:.1f}% of data)")
    print()

    # Distribution by time-of-day bucket (to see if mode shifts)
    print("=== Most common temp by hour of day ===")
    hourly = (
        df.filter(polars.col("temperature_f").is_not_null())
        .with_columns(polars.col("datetime").dt.hour().alias("hour"))
        .group_by(["hour", "temp_rounded"])
        .agg(polars.len().alias("count"))
        .sort(["hour", "count"], descending=[False, True])
        .group_by("hour")
        .agg(
            polars.col("temp_rounded").first().alias("most_common_temp"),
            polars.col("count").first().alias("count"),
        )
        .sort("hour")
    )
    print(hourly)
    print()

    # Distribution by month
    print("=== Most common temp by month ===")
    monthly = (
        df.filter(polars.col("temperature_f").is_not_null())
        .with_columns(
            polars.col("datetime").dt.year().alias("year"),
            polars.col("datetime").dt.month().alias("month"),
        )
        .group_by(["year", "month", "temp_rounded"])
        .agg(polars.len().alias("count"))
        .sort(["year", "month", "count"], descending=[False, False, True])
        .group_by(["year", "month"])
        .agg(
            polars.col("temp_rounded").first().alias("most_common_temp"),
            polars.col("count").first().alias("count"),
        )
        .sort(["year", "month"])
    )
    print(monthly)
    print()

    # Percentile overview for context
    print("=== Percentiles (context) ===")
    percentiles = df["temperature_f"].drop_nulls().describe()
    print(percentiles)


if __name__ == "__main__":
    sys.exit(main())
