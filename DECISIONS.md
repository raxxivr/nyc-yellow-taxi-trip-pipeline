# Decision Log

Project: NYC Yellow Taxi Trip Pipeline
Last updated: 2026-11-03

Each entry records the context, alternatives, choice, and consequences. Status
and setup live in `README.md`; this file is only the reasoning behind decisions.

---

## D-01: Replace raw tables on every rerun

**Date:** 2026-11-03  
**Status:** Accepted

**Context**
`load.py` can be rerun while developing, and both source files are full monthly
snapshots. A rerun must produce the same raw tables instead of adding duplicate
rows or leaving partially refreshed data.

**Options considered**
1. **Append** (`if_exists="append"`) — simple, but reruns duplicate rows and
   counts grow silently.
2. **Truncate + insert** — clears rows while preserving the existing table
   definition, indexes, and grants, but requires a pre-created table and DDL
   separate from pandas' inferred schema.
3. **Replace** (`if_exists="replace"`) — drop and recreate the table from the
   DataFrame on every load.
4. **Upsert** — avoids duplicates without a full reload, but needs a stable
   primary key that these raw snapshots do not define.

**Decision**
Use `if_exists="replace"` for both raw loads.

**Why**
The raw tables are fully derived from local files and have no keys, indexes,
constraints, grants, or downstream consumers yet. Replace is the smallest
operation that guarantees a clean, exact copy of each snapshot.

**Tradeoffs**
`replace` drops the table, so any indexes, constraints, grants, comments, or
views built on it are lost and the schema is inferred from pandas dtypes. It
also holds a lock during the reload. This is acceptable for disposable staging
tables, but must be revisited before incremental loads or once `clean` depends
on `raw` objects.

---

## D-02: Run transformation in Python/pandas, not inside Postgres

**Date:** 2026-11-03  
**Status:** Accepted

**Context**
M1 only lands source files in `raw`. M2 requires filtering, type normalization,
and joining trips to the zone lookup. That work can run either in the warehouse
or in application code. An earlier draft said transformation happened "inside
the warehouse", which conflicted with the plan to clean with pandas.

**Options considered**
1. **In-database SQL (ELT)** — load raw, then transform with SQL inside
   Postgres. Keeps data local and scales with the database, but mixes logic into
   ad-hoc SQL files.
2. **Python/pandas between `raw` and `clean`** — read raw tables through
   SQLAlchemy, transform in `scripts/transform.py`, write to `clean`.
3. **dbt** — SQL-based, testable, and dependency-aware, but adds a framework
   before the transformation logic exists.

**Decision**
Use pandas in `scripts/transform.py`: read from `raw`, transform in Python, and
write results to the `clean` schema.

**Why**
The dataset is about 3.9M rows, which fits comfortably in memory on this
machine. pandas is already a dependency and makes column renaming, filtering,
and zone joins easy to iterate on and test. Keeping `raw` untouched preserves
replayability.

**Tradeoffs**
This pulls the full trip table out of Postgres and makes transformation
memory-bound rather than using the warehouse's execution engine. Logic lives in
Python instead of SQL, so heavier aggregation and larger-than-memory data would
eventually justify moving to SQL/dbt.

---

## D-03: Keep source column names in `raw`, standardize in `clean`

**Date:** 2026-11-03  
**Status:** Accepted

**Context**
The TLC parquet columns mix casing: `VendorID`, `RatecodeID`, `PULocationID`,
`DOLocationID`, and `Airport_fee` alongside lowercase names such as
`fare_amount`. Postgres preserves that casing, so those columns must be quoted
in SQL. The zone lookup has its own convention (`LocationID`, `Borough`,
`Zone`, `service_zone`).

**Options considered**
1. **Rename before loading raw** — every raw query is snake_case, but raw is no
   longer a faithful copy of the source.
2. **Keep raw as-is, rename while building `clean`** — raw stays auditable;
   downstream tables get stable names.
3. **Create renaming views over raw** — avoids copying names, but adds another
   layer and hides the original columns without simplifying the pipeline.

**Decision**
Preserve source names in `raw`. In `transform.py`, rename all columns to
snake_case while writing `clean` (for example `VendorID` → `vendor_id`,
`Airport_fee` → `airport_fee`), and treat those names as the contract for
`analytics`.

**Why**
Raw should show exactly what the TLC delivered, including naming changes
between releases. A single explicit rename step gives `clean` and `analytics`
predictable identifiers without sacrificing source fidelity.

**Tradeoffs**
Raw SQL must quote mixed-case columns until the clean layer exists, and the
rename mapping becomes maintenance work whenever TLC changes its schema. The
inconsistency is contained to `raw` rather than spreading downstream.
