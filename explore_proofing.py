#!/usr/bin/env python3
"""Investigate proofing box sessions vs ambient vs oven events."""

import sys
import polars

PARQUET_PATH = "/Users/mtm/pdev/taylormonacelli/kindfinkitten/merged_data.parquet"

# Working hypotheses for temp zones
AMBIENT_MAX = 82.0       # above this is likely proofing box or oven
PROOFING_LOW = 72.0      # proofing boxes often run 75-82°F
PROOFING_HIGH = 90.0     # above this is oven, not proofing
OVEN_THRESHOLD = 90.0


def main() -> None:
    df = (
        polars.read_parquet(PARQUET_PATH)
        .filter(polars.col("temperature_f").is_not_null())
        .sort("datetime")
    )

    total = len(df)
    print(f"Total readings: {total}")
    print()

    # Zone breakdown
    ambient = df.filter(polars.col("temperature_f") < AMBIENT_MAX)
    proofing = df.filter(
        (polars.col("temperature_f") >= AMBIENT_MAX)
        & (polars.col("temperature_f") < PROOFING_HIGH)
    )
    oven = df.filter(polars.col("temperature_f") >= OVEN_THRESHOLD)

    print("=== Temperature zone breakdown ===")
    print(f"  Ambient   (< {AMBIENT_MAX}°F):                     {len(ambient):>6} readings  ({100*len(ambient)/total:.1f}%)")
    print(f"  Elevated  ({AMBIENT_MAX}–{PROOFING_HIGH}°F, proofing?):  {len(proofing):>6} readings  ({100*len(proofing)/total:.1f}%)")
    print(f"  Oven      (>= {OVEN_THRESHOLD}°F):                    {len(oven):>6} readings  ({100*len(oven)/total:.1f}%)")
    print()

    # Look at the elevated zone more closely — what does the distribution look like?
    print("=== Elevated zone distribution (1°F buckets) ===")
    elev_dist = (
        proofing
        .with_columns(polars.col("temperature_f").round(0).cast(polars.Int64).alias("bucket"))
        .group_by("bucket")
        .agg(polars.len().alias("count"))
        .sort("bucket")
    )
    print(elev_dist)
    print()

    # Find sustained elevated episodes (proofing sessions)
    # A session = consecutive readings >= AMBIENT_MAX with gaps <= 5 min
    df2 = df.with_columns(
        (polars.col("temperature_f") >= AMBIENT_MAX).alias("is_elevated"),
        polars.col("datetime").diff().alias("time_gap"),
    )

    # Assign episode IDs: new episode when transitioning into elevated, or gap > 5 min
    df2 = df2.with_columns(
        (
            (polars.col("is_elevated") & (
                ~polars.col("is_elevated").shift(1).fill_null(False)
                | (polars.col("time_gap") > polars.duration(minutes=5))
            ))
        ).alias("episode_start")
    )
    df2 = df2.with_columns(
        polars.col("episode_start").cast(polars.Int32).cum_sum().alias("episode_id")
    )

    episodes = (
        df2.filter(polars.col("is_elevated"))
        .group_by("episode_id")
        .agg(
            polars.col("datetime").min().alias("start"),
            polars.col("datetime").max().alias("end"),
            polars.len().alias("readings"),
            polars.col("temperature_f").max().alias("peak_temp"),
            polars.col("temperature_f").median().alias("median_temp"),
        )
        .with_columns(
            ((polars.col("end") - polars.col("start")).dt.total_minutes()).alias("duration_min")
        )
        .sort("start")
    )

    # Filter to meaningful sessions (>= 10 minutes)
    sessions = episodes.filter(polars.col("duration_min") >= 10)

    print(f"=== Sustained elevated sessions (>= 10 min above {AMBIENT_MAX}°F): {len(sessions)} total ===")
    print(sessions.select(["start", "end", "duration_min", "peak_temp", "median_temp"]))
    print()

    # Separate proofing-looking sessions from oven sessions
    proofing_sessions = sessions.filter(polars.col("peak_temp") < OVEN_THRESHOLD)
    oven_sessions = sessions.filter(polars.col("peak_temp") >= OVEN_THRESHOLD)

    print(f"=== Proofing-range sessions (peak < {OVEN_THRESHOLD}°F): {len(proofing_sessions)} ===")
    print(proofing_sessions.select(["start", "duration_min", "peak_temp", "median_temp"]))
    print()

    print(f"=== Oven-range sessions (peak >= {OVEN_THRESHOLD}°F): {len(oven_sessions)} ===")
    print(oven_sessions.select(["start", "duration_min", "peak_temp", "median_temp"]))
    print()

    # For proofing sessions — what's the typical duration and temp?
    if len(proofing_sessions) > 0:
        print("=== Proofing session stats ===")
        print(proofing_sessions["duration_min"].describe())
        print()
        print(proofing_sessions["median_temp"].describe())
        print()

    # Sample a specific day that looks like it had proofing — show minute-by-minute
    # Pick a day with a proofing session
    if len(proofing_sessions) > 0:
        sample_date = proofing_sessions["start"].dt.date()[0]
        print(f"=== Sample day with proofing session: {sample_date} ===")
        day_data = df.filter(polars.col("datetime").dt.date() == sample_date)
        # Downsample to every 10 minutes for readability
        day_10min = (
            day_data
            .with_columns(
                (polars.col("datetime").dt.truncate("10m")).alias("bucket")
            )
            .group_by("bucket")
            .agg(polars.col("temperature_f").median().alias("temp_f"))
            .sort("bucket")
        )
        print(day_10min)


if __name__ == "__main__":
    sys.exit(main())
