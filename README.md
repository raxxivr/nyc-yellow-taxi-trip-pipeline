# NYC Yellow Taxi Trip Pipeline

A small batch ELT pipeline that downloads NYC TLC yellow-taxi trip data and the
taxi zone lookup, loads them into PostgreSQL, and prepares them for analysis.

## Status

M1 and M2 are complete: both source files load into the `raw` schema, and
`scripts/transform.py` builds an idempotent, zone-enriched `clean.trips` table.
Analytics models are planned for M3.

| Area | State |
|---|---|
| Extract | Downloads the monthly parquet and zone lookup CSV to `data/raw/` |
| Raw load | Loads both files into Postgres `raw` schema |
| Transform | Cleans `raw` trips, joins pickup/dropoff zones, rebuilds `clean.trips` |
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

The transform logs rejected rows by rule, reconciles raw and clean counts, and
rebuilds `clean.trips` from scratch so reruns do not create duplicates.

## Layout

```text
scripts/extract.py    # download TLC files to data/raw/
scripts/transform.py  # clean raw tables and build clean.trips
scripts/load.py       # load raw files, validate counts
data/raw/             # downloaded source files (gitignored)
DECISIONS.md          # decision log
```

## Known Gaps

- `main.py` and analytics models are not implemented.
- No automated tests; count checks run during `load.py` and `transform.py`.
- Dataset is hardcoded to September 2026.
- Full-refresh loads only; no incremental or append strategy.
- `clean.trips` has no indexes or constraints yet.

## Decisions

See [DECISIONS.md](DECISIONS.md) for the reasoning behind the pipeline design.

The raw-data findings that drive the cleaning thresholds are in
[docs/profile.md](docs/profile.md).
