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

# Show extra metadata
uv run ferment.py --start "today 8:41am" --parquet-path /path/to/merged_data.parquet --meta

# Machine-readable JSON output
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

## Example output

```
$ uv run ferment.py --start "today 8:41am" --parquet-path /path/to/merged_data.parquet --meta

bulk start:        2026-03-21 08:41 PDT
elapsed:           14h47m
data elapsed:      11h33m
temp (3h14m ago):  67.3°F
avg temp:          67.4°F
est. rise:         70%
target rise:       88%

run at:              2026-03-22T06:28:22Z
bulk start ISO:      2026-03-21T15:41:00Z
last reading ISO:    2026-03-22T03:14:00Z
readings:            694
temp range:          65.8–70.0°F
integral:            0.7934
ref. duration:       14h36m (author's estimate at 67.4°F)
ref. end time:       2026-03-21 23:17 PDT
ref. offset (data):  3h03m under
ref. offset (wall):  0h11m over
```

### Primary fields

`bulk start: 2026-03-21 08:41 PDT`
When you told the script bulk fermentation began. Supplied via --start.

`elapsed: 14h47m`
Wall clock time from bulk start to right now. This is real time — not bounded by
when the sensor last reported.

`data elapsed: 11h33m`
Time from bulk start to the most recent sensor reading in the parquet file. Will
lag behind elapsed when the parquet has not been updated recently.

`temp (3h14m ago): 67.3°F`
The last recorded temperature and how long ago that reading was taken. The age
tells you how stale the data is. In a live bake with the pipeline running, this
will be under 30 minutes.

`avg temp: 67.4°F`
Time-weighted mean temperature since bulk start. Each reading is weighted by how
long the sensor stayed at that value before the next reading arrived. Used to look
up the target rise from the reference table.

`est. rise: 70%`
Estimated current dough rise, derived from the fermentation integral. Computed as
integral x target rise. This is an estimate — you have not observed it directly.
Compare it to your jar marker to cross-check the model against your actual dough.

`target rise: 88%`
The rise percentage at which you should stop bulk fermentation, per the reference
table at the session's average temperature (67.4°F -> 88%). Watch your dough and
end bulk when you observe this much rise.

### Metadata fields (--meta)

`run at: 2026-03-22T06:28:22Z`
UTC timestamp of when this script ran. Useful for logging or correlating with
other records.

`bulk start ISO: 2026-03-21T15:41:00Z`
Bulk start expressed in UTC ISO 8601. Same moment as bulk start above, different
format for machine consumption.

`last reading ISO: 2026-03-22T03:14:00Z`
UTC timestamp of the most recent sensor reading used in the calculation.

`readings: 694`
Number of temperature readings included in the fermentation integral since bulk
start. A low number (e.g. under 5) means the parquet is stale and the estimate
is unreliable.

`temp range: 65.8–70.0°F`
Minimum and maximum temperature recorded since bulk start. A narrow range (like
this one) means conditions were stable. A wide range suggests the kitchen changed
significantly and the single target rise figure should be treated with more
caution.

`integral: 0.7934`
Raw fermentation integral value. Accumulates as (interval / expected_hours(temp))
for each reading. Reaches 1.0 when bulk fermentation is complete by the model's
definition. est. rise = integral x target rise.

`ref. duration: 14h36m (author's estimate at 67.4°F)`
How long the reference table author expects bulk fermentation to take at 67.4°F.
His kitchen, his starter, his flour. Use as rough context only.

`ref. end time: 2026-03-21 23:17 PDT`
Absolute local timestamp for when the author's model predicts bulk should be done
(bulk start + ref. duration). More actionable than the duration alone.

`ref. offset (data): 3h03m under`
How far the data elapsed time is from the reference duration. 3h03m under means
the sensor data covers 3h03m less than the author expects for a full bulk at this
temperature.

`ref. offset (wall): 0h11m over`
How far wall clock elapsed time is from the reference duration. 0h11m over means
real time has slightly exceeded the author's estimate. The gap between data offset
and wall offset (3h03m vs 0h11m here) is explained by the 3h14m stale data.

## Duration format

--end accepts either a natural language timestamp or a duration from --start:

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
