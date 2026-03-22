#!/usr/bin/env python3
"""Investigate temperature spikes likely caused by oven use."""

import sys
import polars

PARQUET_PATH = "/Users/mtm/pdev/taylormonacelli/kindfinkitten/merged_data.parquet"

# Threshold for what counts as a spike event (°F rise within one reading interval)
SPIKE_RISE_THRESHOLD = 5.0
HIGH_TEMP_THRESHOLD = 85.0


def main() -> None:
    df = (
        polars.read_parquet(PARQUET_PATH)
        .filter(polars.col("temperature_f").is_not_null())
        .sort("datetime")
    )

    # Compute delta between consecutive readings
    df = df.with_columns(
        polars.col("temperature_f").diff().alias("temp_delta"),
        polars.col("datetime").diff().alias("time_delta"),
    )

    print("=== Temperature delta distribution ===")
    print(df["temp_delta"].drop_nulls().describe())
    print()

    # Readings above high-temp threshold
    hot = df.filter(polars.col("temperature_f") >= HIGH_TEMP_THRESHOLD)
    print(f"=== Readings >= {HIGH_TEMP_THRESHOLD}°F: {len(hot)} total ===")
    print(hot.select(["datetime", "temperature_f", "temp_delta"]).head(30))
    print()

    # Sharp rises — likely oven-on events
    spikes = df.filter(polars.col("temp_delta") >= SPIKE_RISE_THRESHOLD)
    print(f"=== Sharp rises >= {SPIKE_RISE_THRESHOLD}°F between readings: {len(spikes)} events ===")
    print(spikes.select(["datetime", "temperature_f", "temp_delta"]).head(30))
    print()

    # Distribution of spike magnitudes
    print("=== Spike magnitude distribution (rises >= 2°F) ===")
    spike_dist = (
        df.filter(polars.col("temp_delta") >= 2.0)
        .with_columns(polars.col("temp_delta").round(0).cast(polars.Int64).alias("delta_bucket"))
        .group_by("delta_bucket")
        .agg(polars.len().alias("count"))
        .sort("delta_bucket")
    )
    print(spike_dist)
    print()

    # How long do spike events last? Look at windows where temp > HIGH_TEMP_THRESHOLD
    print(f"=== Duration of high-temp (>= {HIGH_TEMP_THRESHOLD}°F) episodes ===")
    # Tag each row as "hot" or not, then find run-length episodes
    df2 = df.with_columns(
        (polars.col("temperature_f") >= HIGH_TEMP_THRESHOLD).alias("is_hot")
    )
    # Find transitions into hot
    df2 = df2.with_columns(
        polars.col("is_hot").cast(polars.Int8).diff().alias("hot_transition")
    )
    episode_starts = df2.filter(polars.col("hot_transition") == 1)
    episode_ends = df2.filter(polars.col("hot_transition") == -1)
    print(f"  Episodes starting: {len(episode_starts)}")
    print(f"  Episodes ending:   {len(episode_ends)}")
    print()

    if len(episode_starts) > 0:
        # Show the first few episodes with their peak temp
        print("=== First 10 high-temp episodes (start datetime, peak temp) ===")
        # For each start, find readings until next drop below threshold
        for i, row in enumerate(episode_starts.head(10).iter_rows(named=True)):
            start_dt = row["datetime"]
            window = df.filter(
                (polars.col("datetime") >= start_dt)
                & (polars.col("temperature_f") >= HIGH_TEMP_THRESHOLD)
            )
            # contiguous run only — stop at first gap
            window = window.with_columns(
                polars.col("datetime").diff().alias("gap")
            ).filter(
                polars.col("gap").is_null()
                | (polars.col("gap") <= polars.duration(minutes=10))
            )
            if len(window) == 0:
                continue
            duration_mins = (
                window["datetime"].max() - window["datetime"].min()
            ).total_seconds() / 60
            peak = window["temperature_f"].max()
            print(f"  {start_dt}  peak={peak}°F  duration={duration_mins:.0f}min  readings={len(window)}")

    print()

    # What does a "normal" day look like vs a day with oven use?
    print("=== Days with most high-temp readings (likely oven-heavy days) ===")
    hot_days = (
        df.filter(polars.col("temperature_f") >= HIGH_TEMP_THRESHOLD)
        .with_columns(polars.col("datetime").dt.date().alias("date"))
        .group_by("date")
        .agg(
            polars.len().alias("hot_readings"),
            polars.col("temperature_f").max().alias("peak_temp"),
        )
        .sort("hot_readings", descending=True)
    )
    print(hot_days.head(20))
    print()

    print("=== Days with zero high-temp readings (baseline days) ===")
    all_days = (
        df.with_columns(polars.col("datetime").dt.date().alias("date"))
        .group_by("date")
        .agg(
            polars.len().alias("total_readings"),
            polars.col("temperature_f").max().alias("peak_temp"),
            polars.col("temperature_f").median().alias("median_temp"),
        )
    )
    cool_days = all_days.filter(polars.col("peak_temp") < HIGH_TEMP_THRESHOLD).sort("date")
    print(f"  {len(cool_days)} days with peak < {HIGH_TEMP_THRESHOLD}°F")
    print(cool_days.head(10))


if __name__ == "__main__":
    sys.exit(main())
