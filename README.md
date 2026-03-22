# dreamydragonfly

Sourdough bulk fermentation tracker. Reads temperature sensor data from a parquet
file and computes fermentation progress using the time-weighted integral of readings
against a reference table (The Sourdough Journey dough temping guide). Reports
estimated rise, target rise, and elapsed time.

The parquet file is maintained by a separate project (kindfinkitten). Always supply
it explicitly with `--parquet-path`.

## Install

```sh
uv sync
```

## CLI cheatsheet

```sh
# Live bake started this morning
uv run ferment.py --start "today 8:41am" --parquet-path /path/to/merged_data.parquet

# Started 3 hours ago
uv run ferment.py --start "3 hours ago" --parquet-path /path/to/merged_data.parquet

# Started at a specific time
uv run ferment.py --start "2026-01-22 11:09" --parquet-path /path/to/merged_data.parquet

# Historical bake — bound by end timestamp
uv run ferment.py --start "2026-01-22 11:09" --end "2026-01-22 8pm" --parquet-path /path/to/merged_data.parquet

# Historical bake — bound by duration from start
uv run ferment.py --start "2026-01-22 11:09" --end "10h28m" --parquet-path /path/to/merged_data.parquet

# Last tuesday, ran about 12 hours
uv run ferment.py --start "last tuesday 9am" --end "12h" --parquet-path /path/to/merged_data.parquet

# Show extra metadata (ISO timestamps, reading count, reference duration, offsets)
uv run ferment.py --start "today 8:41am" --parquet-path /path/to/merged_data.parquet --meta

# Machine-readable JSON output (pipe to other tools)
uv run ferment.py --start "today 8:41am" --parquet-path /path/to/merged_data.parquet --json

# JSON with metadata block
uv run ferment.py --start "today 8:41am" --parquet-path /path/to/merged_data.parquet --json --meta

# JSON piped to jq
uv run ferment.py --start "today 8:41am" --parquet-path /path/to/merged_data.parquet --json --meta | jq .

# Verbose logging to stderr (INFO level)
uv run ferment.py --start "today 8:41am" --parquet-path /path/to/merged_data.parquet -v

# More verbose (DEBUG level)
uv run ferment.py --start "today 8:41am" --parquet-path /path/to/merged_data.parquet -vv
```

## Output fields

Primary output:

| Field | Meaning |
|---|---|
| bulk start | when fermentation began (local time) |
| elapsed | wall clock time from start to now |
| data elapsed | time from start to most recent sensor reading |
| temp (Xm ago) | last recorded temperature and how stale it is |
| avg temp | time-weighted mean temperature since start |
| est. rise | estimated current dough rise, derived from fermentation integral |
| target rise | rise % to stop at, per reference table at avg temp |

`--meta` adds:

| Field | Meaning |
|---|---|
| run at | ISO timestamp when the script ran |
| bulk start ISO | bulk start in UTC ISO format |
| last reading ISO | most recent sensor reading in UTC ISO format |
| readings | number of temperature readings used |
| temp range | min–max temperature observed since start |
| integral | raw fermentation integral (1.0 = complete) |
| ref. duration | author's estimated total duration at avg temp |
| ref. end time | absolute expected completion time (local) |
| ref. offset (data) | data elapsed vs reference duration |
| ref. offset (wall) | wall clock elapsed vs reference duration |

## Duration format

`--end` accepts either a natural language timestamp or a duration from `--start`:

```
11h         11 hours
1d12h       1 day 12 hours
10h28m      10 hours 28 minutes
1D2H30M     case insensitive
```

## Notes

est. rise is computed from the fermentation integral, not observed. The reference
table durations reflect the author's specific kitchen and starter — treat ref.
duration and ref. offset as rough context, not ground truth.
