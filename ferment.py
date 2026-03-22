"""CLI: report bulk fermentation progress given a start time."""

import argparse
import datetime
import pathlib
import sys
import zoneinfo

import dateparser

import calculator as fermentation_calculator
import dough as dough_module
import sensor as sensor_module

PARQUET_PATH = pathlib.Path(
    "/Users/mtm/pdev/taylormonacelli/kindfinkitten/merged_data.parquet"
)
DEFAULT_DURATION_DISPLAY = "36h"
LOCAL_TZ = zoneinfo.ZoneInfo("America/Los_Angeles")


def _parse_start(value: str) -> datetime.datetime:
    parsed = dateparser.parse(
        value,
        settings={
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DAY_OF_MONTH": "first",
            "TIMEZONE": "America/Los_Angeles",
        },
    )
    if parsed is None:
        raise argparse.ArgumentTypeError(f"cannot parse date/time: {value!r}")
    return parsed



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report bulk fermentation progress based on temperature sensor data.",
    )
    parser.add_argument(
        "--start",
        required=True,
        type=_parse_start,
        metavar="TIME",
        help='when bulk fermentation began, e.g. "today 8am", "3 hours ago", "2026-01-22 11:09"',
    )
    parser.add_argument(
        "--parquet",
        type=pathlib.Path,
        default=PARQUET_PATH,
        metavar="PATH",
        help=f"path to sensor parquet file (default: {PARQUET_PATH})",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    sensor = sensor_module.SensorData(args.parquet)
    readings = sensor.readings_since(args.start)

    if len(readings) == 0:
        print(
            f"no sensor readings found since {args.start.astimezone(LOCAL_TZ).strftime('%Y-%m-%d %H:%M %Z')}",
            file=sys.stderr,
        )
        return 1

    subject = dough_module.DoughFermentation()
    calc = fermentation_calculator.FermentationCalculator(subject)
    progress = calc.compute(readings)

    start_local = args.start.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M %Z")
    total_min = round(progress.elapsed_hours * 60)
    elapsed = f"{total_min // 60}h{total_min % 60:02d}m"

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    age_min = round((now_utc - progress.last_reading_at).total_seconds() / 60)
    age_str = f"{age_min // 60}h{age_min % 60:02d}m ago" if age_min >= 60 else f"{age_min}m ago"

    rows = [
        ("bulk start", start_local),
        ("elapsed", elapsed),
        (f"temp ({age_str})", f"{progress.current_temp_f:.1f}°F"),
        ("avg temp", f"{progress.avg_temp_f:.1f}°F"),
        ("target rise", f"{progress.target_rise_pct:.0f}%"),
    ]
    width = max(len(label) for label, _ in rows) + 1
    for label, value in rows:
        print(f"{label + ':':{width}}  {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
