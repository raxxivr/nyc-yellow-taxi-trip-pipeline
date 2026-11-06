# Raw Data Profile — NYC Yellow Taxi, September 2026

**Source:** `raw.yellow_tripdata_2026_09`  
**Rows:** 3,876,044  
**Lookup:** `raw.taxi_zone_lookup` (265 rows; `LocationID` is unique)  
**Profiled:** 2026-11-06  
**Transform verified:** 2026-11-07 (`clean.trips` = 3,641,416 rows; duplicate-key count 0)  
**Method:** whole-table Postgres aggregates against the `raw` tables.

> Counts in the findings table are **independent**. They can overlap, so do not add them together. The transform must count each row only under the first rule it fails, and the final log must reconcile as `raw rows = clean rows + rejected rows`.

## 1. Null profile

| Column | Null count | Assessment |
|---|---:|---|
| `VendorID` | 0 | No nulls |
| `tpep_pickup_datetime` | 0 | No nulls |
| `tpep_dropoff_datetime` | 0 | No nulls |
| `passenger_count` | 1,190,413 | 30.7%; structural, keep |
| `trip_distance` | 0 | No nulls |
| `RatecodeID` | 1,190,413 | 30.7%; structural, keep |
| `store_and_fwd_flag` | 1,190,413 | 30.7%; structural, keep |
| `PULocationID` | 0 | No nulls |
| `DOLocationID` | 0 | No nulls |
| `payment_type` | 0 | No nulls |
| `fare_amount` | 0 | No nulls |
| `extra` | 0 | No nulls |
| `mta_tax` | 0 | No nulls |
| `tip_amount` | 0 | No nulls |
| `tolls_amount` | 0 | No nulls |
| `improvement_surcharge` | 0 | No nulls |
| `total_amount` | 0 | No nulls |
| `congestion_surcharge` | 1,190,413 | 30.7%; structural, keep |
| `Airport_fee` | 1,190,413 | 30.7%; structural, keep |
| `cbd_congestion_fee` | 0 | No nulls |
| `request_source` | 2,685,952 | 69.3%; optional, keep |

The five 1,190,413-count columns are null on **exactly the same rows** (all five null together). They also cluster by vendor:

| VendorID | Rows | `passenger_count` nulls | `request_source` nulls |
|---:|---:|---:|---:|
| 1 | 694,912 | 112,068 | 583,165 |
| 2 | 3,128,003 | 1,073,109 | 2,054,894 |
| 6 | 5,236 | 5,236 | 0 |
| 7 | 47,893 | 0 | 47,893 |

This is source/vendor structure, not random missing data. Keep these rows; do not drop optional nulls.

## 2. Findings and validity checks

| Check | Column(s) | Issue found | Count | Observed values / note |
|---|---|---|---:|---|
| Pickup range | `tpep_pickup_datetime` | Outside September 2026 | 22 | Min `2009-01-01 09:32:44`; max `2026-10-07 07:40:40`; 3 before September, 19 after |
| Dropoff range | `tpep_dropoff_datetime` | No separate period filter needed | N/A | Min `2009-01-01 10:22:44`; max `2026-10-07 07:59:16`; filter on pickup, not dropoff |
| Timestamp order | pickup/dropoff | Dropoff is before or equal to pickup | 48,202 | Impossible/negative trip duration |
| Duration upper tail | pickup/dropoff | Trips longer than 12 hours | 477 | p50 0.26h, p99 1.165h, p99.9 1.746h; max 129.98h; 634 trips over 6h, 477 over 12h, 18 over 24h |
| Fare range | `fare_amount` | Negative fares | 14,190 | Min -1,800.00; p50 17.70; p90 45.92; p99 85.17; p99.9 156.30; p99.99 337.88; max 9,999.70 |
| Fare zero | `fare_amount` | Zero fares | 2,352 | Zero is not a usable metered fare |
| Fare upper tail | `fare_amount` | High fares | 65 above 500; 4 above 1,000 | Max values: 9,999.70; 5,000; 1,800; 1,800. After distance/speed checks, 43 above 500 remain; 11 of those are short trips with fare-per-mile above 30 |
| Distance range | `trip_distance` | Zero distances | 147,158 | p50 1.96; p90 8.77; p99 19.45; p99.9 31.72; p99.99 65.53; max 232,644.80 |
| Negative distance | `trip_distance` | Negative distances | 0 | Minimum is 0 |
| Distance upper tail | `trip_distance` | High distances | 125 above 100; 46 above 1,000 | Max 232,644.80 in 14 minutes, which implies about 997,049 mph |
| Implied speed | distance/duration | Implausible speed | 947 above 100 mph; 1,168 above 80 mph | Only rows with positive distance and duration |
| Passenger range | `passenger_count` | Nulls, zeros, upper values | 1,190,413 null; 10,537 zero; max 8 | Min 0; no negatives; only 2 rows above 6 |
| Pickup locations | `PULocationID` | Sentinel IDs | 264: 3,471; 265: 1,809 | 0 nulls, 0 zeros, 0 unmatched to lookup |
| Dropoff locations | `DOLocationID` | Sentinel IDs | 264: 4,101; 265: 19,382 | 0 nulls, 0 zeros, 0 unmatched to lookup |
| Lookup sentinel rows | `taxi_zone_lookup` | Placeholder zones | 2 rows | 264: Borough `Unknown`, Zone null, service_zone null. 265: Borough null, Zone `Outside of NYC`, service_zone null |
| Lookup ID 246 | `taxi_zone_lookup` | **This was misidentified** | 1 row | 246 is real: Manhattan / West Chelsea/Hudson Yards / Yellow Zone. It is not an unknown zone |
| Exact duplicates | all 21 columns | Exact duplicate rows | 0 | Full-row deduplication would remove nothing |
| Candidate duplicates | chosen key | Repeated trip records | 25,349 recommended | Your original key removes 188,650; see the duplicate-key comparison below |
| Negative total | `total_amount` | Negative totals | 14,688 | Informational; `fare_amount` is the primary fare validation field |

## 3. Duplicate-key comparison

The TLC data has no trip ID, so “duplicate” is a definition.

| Key | Rows removed if keeping one | Duplicate groups | Assessment |
|---|---:|---:|---|
| `VendorID + tpep_pickup_datetime + PULocationID` (your original key) | 188,650 | 186,091 | Too weak. Same vendor, same pickup second, and same pickup zone do not identify one trip |
| `VendorID + pickup + dropoff + PULocationID + DOLocationID` | 125,094 | 125,094 | Still too aggressive; it groups trips that differ in fare, distance, or total |
| **Recommended:** add `fare_amount + trip_distance + total_amount` | **25,349** | **25,349** | Best candidate: all groups are size 2 |
| All 21 columns | 0 | 0 | No exact duplicates |

The 25,349 recommended-key groups are pairs. In the examples checked, the two rows share vendor, pickup/dropoff timestamps, pickup/dropoff zones, fare, distance, and total, but differ in `passenger_count`, `payment_type`, and `request_source`. That looks like duplicate reporting of the same trip rather than two separate trips.

Because the rows differ in non-key columns, deduplication must use a **deterministic tie-break**. Do not rely on arbitrary database row order to decide which copy survives.

After the implemented rules, the recommended key removes **24,315** rows. The transform log confirms that count and checks that the clean table has no duplicate keys.

## 4. Zone lookup findings

- `LocationID` is unique in the lookup; joins will not fan out rows.
- All trip location IDs match the lookup: 0 nulls, 0 zeros, 0 unmatched.
- `264` and `265` are sentinel rows, not neighborhoods:
  - **264** — Borough `Unknown`, Zone null, service_zone null.
  - **265** — Borough null, Zone `Outside of NYC`, service_zone null.
- `246` is a real zone: Manhattan / West Chelsea/Hudson Yards / Yellow Zone.

**Implemented join:** left join twice, once for pickup and once for dropoff. Keep trips with sentinel zones and give them the lookup labels (`Unknown`, `Outside of NYC`) or null zone names. Do not use an inner join: it would silently discard trips if future data contains unknown IDs, and it provides no benefit on this snapshot because there are no unmatched IDs.

After the transform, 2,856 pickup rows and 3,340 dropoff rows have null zone names (location 264), while 727 pickup rows and 17,530 dropoff rows are labeled `Outside of NYC` (location 265).

## 5. Implemented cleaning policy

Counts below are sequential: each row is counted under the first rule it fails.
Independent counts earlier in this document can overlap and should not be added.

| Order | Rule | Action | Rows removed | Why |
|---:|---|---|---:|---|
| 1 | Required nulls | Reject nulls in critical fields; keep optional nulls | 0 | All critical fields are non-null; optional nulls are structural |
| 2 | Period | Reject pickups outside `[2026-09-01, 2026-10-01)` | 22 | The file is a September table; 22 rows are outside scope |
| 3 | Timestamp order | Reject dropoff <= pickup | 48,202 | Negative or zero duration cannot be trusted |
| 4 | Duration | Reject trips over 12 hours | 477 | p99.9 is 1.75h; max is 130h. Twelve hours is already far outside normal taxi trips |
| 5 | Fare | Reject `fare_amount <= 0` | 16,488 | Negative and zero fares are not usable metered fares |
| 6 | Distance | Reject `trip_distance <= 0` | 144,186 | Zero distance is not usable for distance analysis; median fare on these rows is $25.84 |
| 7 | Speed | Reject implied speed above 100 mph | 928 | Removes GPS/timestamp errors such as 232,644.8 miles in 14 minutes; keeps plausible long trips |
| 8 | High-fare consistency | Reject `fare_amount > 500` **and** `fare_amount / trip_distance > 30` | 10 | Removes short high-fare errors such as $990 for 0.21 miles, while keeping $900 for 122 miles and $850 for 216 miles |
| 9 | Passenger | Keep all values; no rule | 0 | Nulls are structural; zero is ambiguous but not a reason to discard an otherwise valid trip; no negatives |
| 10 | Duplicates | Use the recommended key with a deterministic tie-break | 24,315 | Catches repeated trips without collapsing every same-second pickup in the same zone |
| 11 | Zones | Left join pickup and dropoff | 0 rows dropped | Preserves all trips; sentinel zones stay labeled |

### Why not a flat fare cap?

A flat `fare_amount > 500` rule would remove 43 rows after the distance checks, including 32 long trips over 50 miles. Some of those are plausible: $900 for 122.72 miles in 2.03 hours, and $850 for 215.76 miles in 4.18 hours. A flat cap would throw away legitimate long trips along with the bad short ones.

The inconsistency is better captured by fare per mile: $990 for 0.21 miles is $4,714/mile, while $900 for 122.72 miles is $7.33/mile. The implemented rule only rejects high fares that are not explained by distance.

### Why not a flat distance cap?

A flat 100-mile cap would remove 125 rows, but after removing impossible speeds, 70 trips over 100 miles remain, with a maximum of 227.35 miles. Those remaining rows have plausible speeds; for example, 227 miles in about 4.7 hours is roughly 48 mph. The extreme 232,644-mile row is a speed/timestamp error, not evidence that every long trip is invalid.

### Implemented transform result

Two consecutive runs over the same raw snapshot produced identical counts and identical logs.

```text
raw                         3,876,044
missing required fields            0 removed
outside September 2026            22 removed
invalid timestamps            48,202 removed
invalid duration                 477 removed
invalid fares                 16,488 removed
invalid distances            144,186 removed
invalid speed                    928 removed
high fares                        10 removed
duplicate trips               24,315 removed
clean                       3,641,416
```

`clean.trips` has 3,641,416 rows, no duplicate keys, and pickup/dropoff zone columns. The final write is a full table rebuild, so rerunning the transform does not append duplicates.

## 6. Corrections to the first draft

- `fare_count` is not a column; the statistic is the minimum/count for **`fare_amount`**.
- The negative-value count was fare-only: 14,190 negative fares, **0 negative distances**.
- `LocationID` **246** is not unknown; **264 and 265** are the sentinel rows.
- The original duplicate key over-counts duplicates; 188,650 is correct for that key but the key is too weak.
- Exact duplicates are 0, so full-row deduplication would not catch the repeated trip records.
- Additional checks added: fare/distance upper tails, implied speed, duration, lookup uniqueness, unmatched IDs, sentinel-zone labels, and null co-occurrence by vendor.
