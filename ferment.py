"""CLI: report bulk fermentation progress given a start time."""

import argparse
import datetime
import json
import logging
import pathlib
import sys
import dateparser

import calculator as fermentation_calculator
import dough as dough_module
import duration as duration_module
import sensor as sensor_module

LOCAL_TZ = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

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


def _resolve_end(value: str, start: datetime.datetime) -> datetime.datetime:
    """
    Parse --end as either a duration offset from start (e.g. '11h') or an
    absolute/relative datetime (e.g. '2026-03-01 8pm', 'yesterday 9pm').
    Duration is tried first.
    """
    try:
        delta = duration_module.parse_duration(value)
        return start + delta
    except ValueError:
        pass
    parsed = dateparser.parse(
        value,
        settings={
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DAY_OF_MONTH": "first",
            "TIMEZONE": "America/Los_Angeles",
        },
    )
    if parsed is None:
        raise argparse.ArgumentTypeError(f"cannot parse end time: {value!r}")
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
        "--end",
        default=None,
        metavar="TIME",
        help='when bulk fermentation ended, e.g. "2026-03-01 8pm", "yesterday 9pm", or a duration from start like "11h"',
    )
    parser.add_argument(
        "--parquet-path",
        required=True,
        type=pathlib.Path,
        metavar="PARQUET_PATH",
        help="path to sensor parquet file, e.g. /path/to/kindfinkitten/merged_data.parquet",
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
        "--volume",
        default=None,
        type=float,
        metavar="ML",
        help="initial dough volume in mL; used to compute target volume",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="increase log verbosity (-v for INFO, -vv for DEBUG)",
    )
    return parser


def _fmt_hm(total_minutes: int) -> str:
    h, m = divmod(total_minutes, 60)
    return f"{h}h{m}m" if m else f"{h}h"


def _print_rows(rows: list[tuple[str, str]]) -> None:
    width = max(len(label) for label, _ in rows) + 1
    for label, value in rows:
        print(f"{label + ':':{width}}  {value}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    log_level = {0: logging.WARNING, 1: logging.INFO}.get(args.verbose, logging.DEBUG)
    logging.basicConfig(level=log_level, stream=sys.stderr, format="%(levelname)s %(message)s")

    log.info("loading parquet from %s", args.parquet_path)

    end = _resolve_end(args.end, args.start) if args.end else None

    sensor = sensor_module.SensorData(args.parquet_path)
    readings = sensor.readings_since(args.start, end)

    if len(readings) == 0:
        print(
            f"no sensor readings found since {args.start.astimezone(LOCAL_TZ).strftime('%Y-%m-%d %a %-I:%M %p %Z')}",
            file=sys.stderr,
        )
        return 1

    log.info("computing fermentation progress from %d readings", len(readings))

    subject = dough_module.DoughFermentation()
    calc = fermentation_calculator.FermentationCalculator(subject)
    progress = calc.compute(readings)

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    start_local = args.start.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %a %-I:%M %p %Z")
    elapsed_end = end if end is not None else now_utc
    elapsed_min = round((elapsed_end - args.start).total_seconds() / 60)
    elapsed = _fmt_hm(elapsed_min)
    data_min = round((progress.last_reading_at - args.start).total_seconds() / 60)
    data_elapsed = _fmt_hm(data_min)
    age_min = round((now_utc - progress.last_reading_at).total_seconds() / 60)
    age_str = f"{age_min // 60}h{age_min % 60:2d}m ago" if age_min >= 60 else f"{age_min}m ago"

    ref_hours = subject.expected_hours(progress.avg_temp_f)

    if args.json:
        payload: dict = {
            "bulk_start": args.start.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %a %-I:%M:%S %p %Z"),
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
                "run_at": now_utc.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %a %-I:%M:%S %p %Z"),
                "last_reading": progress.last_reading_at.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %a %-I:%M:%S %p %Z"),
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
        ("data elapsed", data_elapsed),
        (f"temp ({age_str})", f"{progress.current_temp_f:.1f}°F"),
        ("avg temp", f"{progress.avg_temp_f:.1f}°F"),
        ("est. rise", f"{progress.est_rise_pct:.0f}%"),
        ("target rise", f"{progress.target_rise_pct:.0f}%"),
    ]
    if args.volume is not None:
        target_volume = args.volume * (1 + round(progress.target_rise_pct) / 100)
        primary.append(("target volume", f"{args.volume:.0f} → {target_volume:.0f} mL"))
    _print_rows(primary)

    if args.meta:
        ref_min = round(ref_hours * 60)
        ref_duration = _fmt_hm(ref_min)
        ref_end_abs = args.start + datetime.timedelta(hours=ref_hours)
        ref_end_local = ref_end_abs.astimezone(LOCAL_TZ).strftime("%m-%d %a %-I:%M %p %Z")

        data_diff_min = abs(round((ref_hours - progress.elapsed_hours) * 60))
        data_diff_str = _fmt_hm(data_diff_min)
        data_offset = f"{data_diff_str} under" if progress.elapsed_hours < ref_hours else f"{data_diff_str} over"

        wall_elapsed_hours = elapsed_min / 60
        wall_diff_min = abs(round((ref_hours - wall_elapsed_hours) * 60))
        wall_diff_str = _fmt_hm(wall_diff_min)
        wall_offset = f"{wall_diff_str} under" if wall_elapsed_hours < ref_hours else f"{wall_diff_str} over"

        print()
        meta = [
            ("run at", now_utc.astimezone(LOCAL_TZ).strftime("%m-%d %a %-I:%M:%S %p %Z")),
            ("bulk start", args.start.astimezone(LOCAL_TZ).strftime("%m-%d %a %-I:%M:%S %p %Z")),
            ("last reading", progress.last_reading_at.astimezone(LOCAL_TZ).strftime("%m-%d %a %-I:%M:%S %p %Z")),
            ("readings", str(progress.reading_count)),
            ("temp range", f"{progress.min_temp_f:.1f}–{progress.max_temp_f:.1f}°F"),
            ("integral", f"{progress.integral:.4f}"),
            ("ref. duration", f"{ref_duration} (author's estimate at {progress.avg_temp_f:.1f}°F)"),
            ("ref. end time", ref_end_local),
            ("ref. offset (data)", data_offset),
            ("ref. offset (wall)", wall_offset),
        ]
        _print_rows(meta)

    return 0


if __name__ == "__main__":
    sys.exit(main())
