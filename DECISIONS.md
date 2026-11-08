# Decision Log

Project: NYC Yellow Taxi Trip Pipeline
Last updated: 2026-11-08

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
or in application code.

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
The raw trip frame measured **0.662 GB** with `memory_usage(deep=True)`. Each
rule calls `.copy()` and temporarily holds a second full frame, so the working
peak is roughly twice that plus sort/dedup overhead. The copies run
sequentially, so nine rules do not mean nine simultaneous copies. pandas is
already a dependency and makes column renaming, filtering, and zone joins easy
to iterate on and test. Keeping `raw` untouched preserves replayability.

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

---

## D-04: Count each rejected row under the first rule it fails

**Date:** 2026-11-07

**Status:** Accepted

**Context**
The profile counts are independent. A negative fare can also have an invalid
timestamp, so adding the individual counts would overstate the number of bad
rows and fail to reconcile against the raw input.

**Options considered**
1. **Log independent counts** — each rule reports every row it would reject,
   even if another rule also rejects it. Useful for profiling, but the counts
   cannot be added.
2. **Log sequential counts** — apply rules in a fixed order and count a row only
   under the first rule it fails.
3. **Log both** — keep independent profile counts as evidence and sequential
   counts as the pipeline result.

**Decision**
Run the rejection rules in this fixed order and log the sequential count for each:

1. Missing required fields
2. Pickup outside September 2026
3. Dropoff not after pickup
4. Duration over 12 hours
5. Non-positive fare
6. Implied speed over 100 mph
7. High-fare anomaly
8. Duplicate trip

Zero-distance rows are **not rejected**. They are kept and flagged with
`has_valid_distance = false` after the rejection rules. The flag is reported
separately from rejected rows.

The transform asserts `raw rows = clean rows + total rejected rows`.

**Why**
Sequential accounting gives every rejected row exactly one owner and makes the
final reconciliation meaningful. The fixed order also makes reruns comparable.

**Tradeoffs**
The rule that gets blamed for a row depends on order. For example, a negative
fare with an invalid timestamp is counted under the timestamp rule. The profile
therefore keeps independent counts for diagnosis, while the pipeline log uses
sequential counts for reconciliation.

---

## D-05: Define a duplicate trip by a natural key with a deterministic tie-break

**Date:** 2026-11-07

**Status:** Accepted

**Context**
The TLC data has no trip ID, so "duplicate" must be defined. Exact duplicate
rows do not occur (0), but repeated trip records do. The original key
`VendorID + pickup + PULocationID` removes 188,650 rows and is too weak: it
collapses different trips that start in the same zone at the same second.

**Options considered**
1. **Exact full-row duplicates** — removes 0 rows; misses repeated records that
   differ only in optional vendor fields.
2. **Weak natural key** — removes 188,650 rows and destroys legitimate trips.
3. **Full natural key** — `VendorID + pickup + dropoff + PULocationID +
   DOLocationID + fare_amount + trip_distance + total_amount`; removes 25,349
   rows before other rules and 25,310 after them.
4. **Full natural key plus arbitrary row order** — same key, but which copy
   survives is nondeterministic.

**Decision**
Use option 3. Sort by the key and all remaining columns, then keep the first row
in each duplicate group. The resulting duplicate-key count must be 0.

**Why**
The 25,349 recommended-key groups are pairs. The copies share the trip's
identity, fare, distance, and total, but differ in `passenger_count`,
`payment_type`, and `request_source`. That looks like duplicate reporting, not
two separate trips. Sorting all columns makes reruns select the same survivor.

**Tradeoffs**
Two legitimate trips with identical values for every key field would still be
collapsed. The key is a judgment call; it is stronger than the original and
weaker than full-row equality. Revisit it if TLC adds a trip identifier.

---

## D-06: Left-join zones and keep sentinel locations

**Date:** 2026-11-07

**Status:** Accepted

**Context**
`taxi_zone_lookup` has 265 rows and a unique `LocationID`. Every trip location
ID matches the lookup, including sentinel locations 264 and 265. Location 264
has Borough `Unknown` and a null Zone; location 265 has a null Borough and Zone
`Outside of NYC`.

**Options considered**
1. **Inner join** — drops trips with unknown IDs in future data and provides no
   benefit on this snapshot.
2. **Left join** — keeps every trip and adds zone labels where available.
3. **Left join, then drop sentinel-zone trips** — removes 264/265 as "unknown",
   but those are real source categories and dropping them loses valid trips.

**Decision**
Left-join the lookup twice, once on `pickup_location_id` and once on
`dropoff_location_id`. Keep sentinel trips and preserve the lookup labels:
264 becomes a null zone with borough `Unknown`; 265 becomes zone
`Outside of NYC` with a null borough. No rows are dropped by the join.

**Why**
The join should enrich, not filter. The lookup is unique, so a left join cannot
fan out rows, and unresolved zone names stay visible as nulls rather than
silently disappearing.

**Tradeoffs**
`clean.trips` contains null zone names for location 264 and null boroughs for
location 265. Analytics must treat those as sentinel/unknown values and not as
ordinary neighborhoods.

---

## D-07: Rebuild `clean.trips` on every transform run

**Date:** 2026-11-07

**Status:** Accepted

**Context**
The transform may be rerun while developing. It must be idempotent: two runs
over the same raw snapshot must produce the same clean table, not append a
second copy.

**Options considered**
1. **Append** — simple, but reruns duplicate every row.
2. **Truncate + insert** — preserves a pre-created table and indexes, but needs
   separate DDL that can drift from the DataFrame.
3. **Replace the table** — drop and recreate `clean.trips` from the transformed
   DataFrame on each run.
4. **Staging table + swap** — safest for concurrent readers, but more machinery
   than this single-user batch pipeline needs now.

**Decision**
Replace `clean.trips` on each run. Create the table from the DataFrame schema,
then load rows with PostgreSQL `COPY` through a temporary CSV file. Verify the
written count before declaring success.

**Why**
Replace gives an exact snapshot and makes idempotency trivial. `COPY` avoids the
row-by-row insert cost of `DataFrame.to_sql` at 3.6M rows.

**Tradeoffs**
The table is unavailable during a rebuild, and indexes, grants, comments, or
views attached to it are lost. Schema types are inferred from pandas. A failed
load can leave an empty table, so rerun the transform before consuming it. A
staging swap is the next step if concurrent readers or indexes become required.

---

## D-08: Use profile-derived validity thresholds and flag zero-distance trips

**Date:** 2026-11-08

**Status:** Accepted

**Context**
The profile found extreme values that are almost certainly errors, but a flat
cap on fare or distance would also remove plausible long trips. The hard case was
zero distance: 144,186 rows reached the old distance rule, and 117,516 of them
(81.5%) had different pickup and dropoff zones. Their median fare was $26.19,
higher than the overall $17.70, and their average total was $38.96. These look
like paid trips with a broken distance reading, not fabricated trips. The old
rule also removed 1,006 of the 1,809 zone-265 pickups (-56%), far more than the
overall rejection rate.

Negative fares were also checked by payment type: 8,671 were disputes, 1,518
were no-charge trips, 3,068 were cash, 873 were credit card, and 60 were Flex
Fare. Most are adjustments or non-revenue records, so rejecting them is
defensible.

**Options considered**
1. **No cleaning** — preserves everything, but leaves impossible timestamps,
   negative fares, and duplicate records in `clean`.
2. **Reject zero-distance rows** — keeps only distance-valid rows, but
   undercounts trips and revenue and disproportionately removes zone 265.
3. **Keep zero-distance rows with a flag** — preserves counts and revenue while
   letting distance-based metrics exclude them.
4. **Flat caps** — easy to explain, but rejects legitimate long airport/out-of-
   town trips along with bad rows.

**Decision**
Use these rules:

- Pickup must be in `[2026-09-01, 2026-10-01)`.
- Dropoff must be strictly after pickup.
- Duration must be at most 12 hours.
- `fare_amount` must be greater than 0.
- Keep `trip_distance <= 0` rows and set `has_valid_distance = false`. Report
  the flag separately from rejected rows.
- Implied speed must be at most 100 mph.
- Reject high-fare anomalies only when `fare_amount > 500` **and**
  `fare_amount / trip_distance > 30`.
- Do not impose a flat upper distance cap.
- Do not reject zero passenger counts or null optional fields.
- Do not drop sentinel zones.

**Why**
Zero distance is unusable for distance-based analysis, but it does not make the
trip's count or revenue disappear. Flagging preserves both and lets each metric
choose its denominator. This also avoids the zone-265 distortion caused by the
old rejection rule. The 12-hour and 100-mph limits are far beyond the observed
normal range but still retain plausible long trips. The fare-per-mile test
distinguishes a $990 trip of 0.21 miles from a $900 trip of 122 miles.

After the change, the transform produced **3,784,607** clean rows from
3,876,044 raw rows: **91,437 rejected** and **143,191 zero-distance rows
flagged** after deduplication.

**Tradeoffs**
The 143,191 flagged rows (3.7% of raw) must be excluded from distance and speed
metrics. A zero-distance trip with a high fare is kept and flagged rather than
rejected, so it still counts toward revenue. The thresholds remain data-driven
judgment calls: a genuine 13-hour trip or a trip above 100 mph would be
rejected, and the 12-hour limit is stricter than the profile's 99.9th
percentile.

---

## D-09: Report gross revenue as `total_amount`, with fare and tips separate

**Date:** 2026-11-08

**Status:** Accepted

**Context**
`total_amount` includes the base fare, tips, taxes, tolls, and surcharges.
`fare_amount` is only the metered fare. The business question asks for
“revenue,” which could mean either one.

**Options considered**
1. **Use only `fare_amount`** — clear metered fare, but omits tips and
   pass-through charges.
2. **Use only `total_amount`** — closest to the amount charged, but hides the
   fare/tip split.
3. **Report all three** — gross revenue from `total_amount`, plus
   `fare_revenue` and `tip_revenue` as separate columns.

**Decision**
Use option 3. `analytics.daily_trips_revenue` reports `gross_revenue` as
`SUM(total_amount)`, `fare_revenue` as `SUM(fare_amount)`, and `tip_revenue` as
`SUM(tip_amount)`.

**Why**
The analyst can see the total charged without losing the fare/tip breakdown.
Naming the columns explicitly prevents a hidden “revenue” definition.

**Tradeoffs**
Gross revenue includes pass-through taxes, tolls, and surcharges, and it is
reduced by negative adjustments in `total_amount`; it is not net profit. If the
business wants metered fare only, `fare_revenue` is available.

---

## D-10: Use a card-only tip denominator and explicit labels

**Date:** 2026-11-08

**Status:** Accepted

**Context**
TLC records tips reliably only for card payments, so averaging over all trips
would bias the result downward. Zone 264 has a null zone name, and payment
types are stored as numeric codes.

**Options considered**
1. **Average tips over every trip** — simple, but misleading because cash tips
   are not recorded.
2. **Average tips over card trips only** — consistent denominator for recorded
   tips.
3. **Store payment labels in a lookup table** — reusable, but unnecessary for a
   single query.
4. **Map labels with `CASE` and label sentinel zones explicitly** — simple and
   readable.

**Decision**
Use card trips (`payment_type = 1`) as the tip denominator. Label zone 264 as
`Unknown (264)`. Map payment types with a `CASE`: 0 Flex Fare, 1 Credit card,
2 Cash, 3 No charge, 4 Dispute, 5 Unknown, 6 Voided trip, and `Other` for any
unexpected code.

**Why**
The denominator matches the population where tips are actually recorded, and
explicit labels stop nulls and numeric codes from being silently misinterpreted.

**Tradeoffs**
The tip averages are not representative of cash trips. The `CASE` mapping must
be updated if TLC changes its codes. In this month's data, only codes 0–5
appear; code 6 is handled but has no rows.
