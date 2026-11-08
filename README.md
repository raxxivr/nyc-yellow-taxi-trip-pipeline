# NYC Yellow Taxi Trip Pipeline

A reproducible batch ELT pipeline for NYC TLC yellow-taxi trip data. It
downloads the September 2026 trip parquet and the taxi zone lookup, loads both
files into PostgreSQL, cleans and enriches the trips, builds four analytics
tables, and runs automated quality checks.

## Status

M1 through M4 are complete. The extract, load, transform, analytics, and quality
check stages are wired together in `run_pipeline.py`.

## Problem

The TLC publishes monthly yellow-taxi data as a large parquet file plus a small
zone lookup. Answering basic operational questions from that raw data requires
repeated cleaning, joins, and validation.

The pipeline answers four business questions:

| Question | Analytics table |
|---|---|
| How many trips and how much revenue per day? | `analytics.daily_trips_revenue` |
| Which pickup zones had the most trips? | `analytics.top_pickup_zones` |
| What is the average card tip by pickup hour? | `analytics.avg_tip_by_hour` |
| How are trips split by payment type? | `analytics.trips_by_payment_type` |

The pipeline is a full refresh. Each run replaces the raw tables, `clean.trips`,
and the analytics tables, so reruns do not append duplicate rows.

## Architecture

```text
TLC parquet + zone CSV
          |
          v
  data/raw/  (gitignored)
          |
          v
  raw schema  (source columns preserved)
          |
          v
  clean.trips  (cleaned, typed, zone-enriched)
          |
          v
  analytics.*  (four SQL business queries)
          |
          v
  quality checks
```

| Stage | Script | Output |
|---|---|---|
| Extract | `scripts/extract.py` | `data/raw/yellow_tripdata_2026-09.parquet`, `data/raw/taxi_zone_lookup.csv` |
| Load | `scripts/load.py` | `raw.yellow_tripdata_2026_09`, `raw.taxi_zone_lookup` |
| Transform | `scripts/transform.py` | `clean.trips` |
| Analytics | `scripts/run_analytics.py` | Four `analytics.*` tables |
| Quality checks | `scripts/checks.py` | PASS/FAIL report; non-zero exit on failure |

`run_pipeline.py` runs the five stages in order and stops at the first failure.

## Setup

### Prerequisites

- Python 3.11
- PostgreSQL running locally
- A PostgreSQL user that can create schemas and tables

### 1. Create the database

The pipeline expects the database to exist, but it creates the `raw`, `clean`,
and `analytics` schemas itself.

Using `psql`:

```powershell
psql -U postgres -c "CREATE DATABASE nyc_yellow_taxi_trip;"
```

If the database already exists, skip this step. If `psql` is not on `PATH`, use
pgAdmin or another PostgreSQL client.

### 2. Clone and install

```powershell
git clone https://github.com/raxxivr/nyc-yellow-taxi-trip-pipeline.git
cd nyc-yellow-taxi-trip-pipeline

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure the environment

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your PostgreSQL password:

```text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=nyc_yellow_taxi_trip
DB_USER=postgres
DB_PASSWORD=your-password
```

`.env` is gitignored. Only `.env.example` with placeholder values is committed.

### 4. Run the pipeline

From the repository root:

```powershell
python run_pipeline.py
```

The first run downloads the source files. Later runs download them again and
fully rebuild the database tables.

The pipeline prints each stage, the cleaning-rule rejection counts, analytics
table creation, and the quality-check results. It exits non-zero if any stage
or check fails.

The individual stages can still be run separately for debugging:

```powershell
python scripts/extract.py
python scripts/load.py
python scripts/transform.py
python scripts/run_analytics.py
python scripts/checks.py
```

## Sample results

These are from the September 2026 run. Full `LIMIT 10` outputs are in
`docs/evidence/m3/`.

| Table | Rows | Sample finding |
|---|---:|---|
| `analytics.daily_trips_revenue` | 30 | 3,784,607 trips and about $122.9M gross revenue; 2026-09-17 was the busiest day with 151,380 trips. |
| `analytics.top_pickup_zones` | 10 | Upper East Side South led with 167,015 trips (4.41%). |
| `analytics.avg_tip_by_hour` | 24 | Average card tip peaked at 16:00 at $5.10. |
| `analytics.trips_by_payment_type` | 6 | Credit card was 60.47% of trips, followed by Flex Fare at 30.75% and cash at 8.22%. |

## Quality checks

`scripts/checks.py` runs these checks after the analytics tables are built:

1. Source parquet/CSV row counts match the raw table row counts.
2. `clean.trips` key columns contain no nulls.
3. `clean.trips` contains no duplicate keys.
4. Fares are positive and distances are non-negative.
5. Pickup dates are in September 2026, dropoff is after pickup, duration is at
   most 12 hours, and implied speed is at most 100 mph.
6. Payment codes and location IDs are in their expected ranges.
7. Daily and payment trip counts reconcile to `clean.trips`.
8. Daily, hourly-tip, and top-zone table shapes are correct; payment
   percentages total 100%.
9. `clean` and `analytics` column names are snake_case.

The loader also validates raw row counts, and the transform prints every
cleaning rule with its rejection count and validates raw-to-clean
reconciliation. Any failing check stops `run_pipeline.py` with a non-zero exit
code.

## Reruns and raw data

All writes are full replacements:

- `load.py` uses `if_exists="replace"` for the raw tables.
- `transform.py` rebuilds `clean.trips` from scratch.
- `run_analytics.py` drops and recreates each analytics table.

This keeps reruns idempotent. The duplicate-key and reconciliation checks
provide additional protection.

`data/raw/` is gitignored. Only `extract.py` writes source files there; the
load, transform, and analytics stages only read them. Raw source column names
are intentionally preserved in the `raw` schema. The `clean` and `analytics`
schemas use snake_case names.

## Project layout

```text
run_pipeline.py           # single entry point; runs all five stages
scripts/extract.py        # download TLC parquet and zone CSV
scripts/load.py           # load raw files and validate row counts
scripts/transform.py      # clean, flag, enrich, and rebuild clean.trips
scripts/run_analytics.py  # build analytics tables and run analytics checks
scripts/checks.py         # cross-stage quality checks
sql/                      # four business-question queries
docs/profile.md           # raw-data profile and cleaning rationale
docs/evidence/            # saved run outputs, grouped by milestone
  m1/                     # raw-load validation
  m2/                     # transform runs and idempotency
  m3/                     # analytics outputs and sanity checks
  m4/                     # full pipeline and fresh-clone verification
DECISIONS.md              # decision log
```

## Limitations

- The dataset is hardcoded to September 2026.
- Loads are full refreshes; there is no incremental or append strategy.
- There is no scheduler or orchestration service.
- `clean.trips` has no indexes or constraints beyond the runtime checks.
- Tip averages use card payments only; cash tips are not reliably recorded.

## Decisions

See [DECISIONS.md](DECISIONS.md) for the reasoning behind the cleaning rules,
zero-distance handling, revenue definition, tip denominator, and labels. The
raw-data findings are in [docs/profile.md](docs/profile.md).
