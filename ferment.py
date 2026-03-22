"""CLI: report bulk fermentation progress given a start time."""

import argparse
import datetime
import json
import logging
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
LOCAL_TZ = zoneinfo.ZoneInfo("America/Los_Angeles")

log = logging.getLogger(__name__)


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
    parser.add_argument(
        "--meta",
        action="store_true",
        help="show additional metadata below the primary output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="output as JSON instead of human-readable table",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="increase log verbosity (-v for INFO, -vv for DEBUG)",
    )
    return parser


def _print_rows(rows: list[tuple[str, str]]) -> None:
    width = max(len(label) for label, _ in rows) + 1
    for label, value in rows:
        print(f"{label + ':':{width}}  {value}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    log_level = {0: logging.WARNING, 1: logging.INFO}.get(args.verbose, logging.DEBUG)
    logging.basicConfig(level=log_level, stream=sys.stderr, format="%(levelname)s %(message)s")

    log.info("loading parquet from %s", args.parquet)

    sensor = sensor_module.SensorData(args.parquet)
    readings = sensor.readings_since(args.start)

    if len(readings) == 0:
        print(
            f"no sensor readings found since {args.start.astimezone(LOCAL_TZ).strftime('%Y-%m-%d %H:%M %Z')}",
            file=sys.stderr,
        )
        return 1

    log.info("computing fermentation progress from %d readings", len(readings))

    subject = dough_module.DoughFermentation()
    calc = fermentation_calculator.FermentationCalculator(subject)
    progress = calc.compute(readings)

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start_local = args.start.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M %Z")
    total_min = round(progress.elapsed_hours * 60)
    elapsed = f"{total_min // 60}h{total_min % 60:02d}m"
    age_min = round((now_utc - progress.last_reading_at).total_seconds() / 60)
    age_str = f"{age_min // 60}h{age_min % 60:02d}m ago" if age_min >= 60 else f"{age_min}m ago"

    ref_hours = subject.expected_hours(progress.avg_temp_f)

    if args.json:
        payload: dict = {
            "bulk_start_iso": args.start.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "elapsed_minutes": round(progress.elapsed_hours * 60),
            "last_temp_f": progress.current_temp_f,
            "last_temp_age_minutes": age_min,
            "avg_temp_f": round(progress.avg_temp_f, 1),
            "estimated_rise_pct": round(progress.est_rise_pct),
            "target_rise_pct": round(progress.target_rise_pct),
        }
        if args.meta:
            diff_min = abs(round((ref_hours - progress.elapsed_hours) * 60))
            payload["meta"] = {
                "run_at_iso": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "last_reading_iso": progress.last_reading_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "temperature_reading_count": progress.reading_count,
                "min_temp_f": progress.min_temp_f,
                "max_temp_f": progress.max_temp_f,
                "fermentation_integral": round(progress.integral, 4),
                "reference_duration_minutes": round(ref_hours * 60),
                "reference_offset_minutes": diff_min,
                "reference_offset_direction": "under" if progress.elapsed_hours < ref_hours else "over",
            }
        print(json.dumps(payload))
        return 0

    primary = [
        ("bulk start", start_local),
        ("elapsed", elapsed),
        (f"temp ({age_str})", f"{progress.current_temp_f:.1f}°F"),
        ("avg temp", f"{progress.avg_temp_f:.1f}°F"),
        ("est. rise", f"{progress.est_rise_pct:.0f}%"),
        ("target rise", f"{progress.target_rise_pct:.0f}%"),
    ]
    _print_rows(primary)

    if args.meta:
        ref_min = round(ref_hours * 60)
        ref_duration = f"{ref_min // 60}h{ref_min % 60:02d}m"
        diff_min = abs(round((ref_hours - progress.elapsed_hours) * 60))
        diff_str = f"{diff_min // 60}h{diff_min % 60:02d}m"
        ref_offset = f"{diff_str} under" if progress.elapsed_hours < ref_hours else f"{diff_str} over"

        print()
        meta = [
            ("run at", now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")),
            ("bulk start ISO", args.start.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
            ("last reading ISO", progress.last_reading_at.strftime("%Y-%m-%dT%H:%M:%SZ")),
            ("readings", str(progress.reading_count)),
            ("temp range", f"{progress.min_temp_f:.1f}–{progress.max_temp_f:.1f}°F"),
            ("integral", f"{progress.integral:.4f}"),
            ("ref. duration", f"{ref_duration} (author's estimate at {progress.avg_temp_f:.1f}°F)"),
            ("ref. offset", ref_offset),
        ]
        _print_rows(meta)

    return 0


if __name__ == "__main__":
    sys.exit(main())
