# NYC Yellow Taxi Trip Pipeline

A small batch ELT pipeline that downloads NYC TLC yellow-taxi trip data and the
taxi zone lookup, loads them into PostgreSQL, and prepares them for analysis.

## Status

M1, M2, and M3 are complete: both source files load into `raw`,
`scripts/transform.py` builds an idempotent zone-enriched `clean.trips`, and the
four SQL queries build the `analytics` tables. Pipeline orchestration is planned
for M4.

| Area | State |
|---|---|
| Extract | Downloads the monthly parquet and zone lookup CSV to `data/raw/` |
| Raw load | Loads both files into Postgres `raw` schema |
| Transform | Cleans `raw` trips, flags zero-distance rows, joins pickup/dropoff zones, rebuilds `clean.trips` |
| Analytics | Runs four SQL queries into `analytics` tables and passes sanity checks |
| Orchestration | None; scripts run individually |

## Stack

- Python 3.11
- pandas + pyarrow
- PostgreSQL via SQLAlchemy + psycopg2
- `python-dotenv` for local configuration

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your PostgreSQL credentials. The database must already exist.

## Run

Download the source files:

```powershell
python scripts/extract.py
```

Load them into Postgres and validate row counts:

```powershell
python scripts/load.py
```

The loader creates the `raw`, `clean`, and `analytics` schemas, replaces the
raw tables, and fails with a `ValueError` if a loaded row count differs from the
source file.

Transform the raw tables into `clean.trips`:

```powershell
python scripts/transform.py
```

The transform logs rejected rows by rule, reports zero-distance rows separately,
reconciles raw and clean counts, and rebuilds `clean.trips` from scratch so
reruns do not create duplicates.

Build the analytics tables and run the sanity checks:

```powershell
python scripts/run_analytics.py
```

The runner drops and recreates each `analytics` table, so reruns are idempotent.

## Layout

```text
scripts/extract.py    # download TLC files to data/raw/
scripts/transform.py  # clean raw tables and build clean.trips
scripts/load.py       # load raw files, validate counts
scripts/run_analytics.py  # build analytics tables and run checks
sql/                  # four business-question queries
data/raw/             # downloaded source files (gitignored)
docs/profile.md       # raw-data profile and cleaning rationale
DECISIONS.md          # decision log
```

## Known Gaps

- `main.py` pipeline orchestration is not implemented.
- No automated test suite; `load.py`, `transform.py`, and `run_analytics.py`
  contain runtime checks.
- Dataset is hardcoded to September 2026.
- Full-refresh loads only; no incremental or append strategy.
- `clean.trips` has no indexes or constraints yet.

## Decisions

See [DECISIONS.md](DECISIONS.md) for the reasoning behind the pipeline design.

The raw-data findings that drive the cleaning thresholds are in
[docs/profile.md](docs/profile.md).
