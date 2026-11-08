# M3 Analytics Summary

The analytics runner was executed twice. Both runs produced identical output and
all sanity checks passed.

| Table | Rows | What I would tell the analyst |
|---|---:|---|
| `analytics.daily_trips_revenue` | 30 | Across 30 days, the pipeline reports 3,784,607 trips and about $122.9M gross revenue, with 2026-09-17 the busiest day at 151,380 trips and $5.04M gross. |
| `analytics.top_pickup_zones` | 10 | Upper East Side South leads pickups with 167,015 trips (4.41%), followed by Upper East Side North and JFK Airport. |
| `analytics.avg_tip_by_hour` | 24 | Among 2,288,460 credit-card trips, average tip peaks at 16:00 ($5.10). |
| `analytics.trips_by_payment_type` | 6 | Credit card is 60.47% of trips, Flex Fare 30.75%, cash 8.22%, and disputes, no-charge, and unknown together are under 0.6%. |

## Sanity checks

Both runs passed the same six checks:

```text
PASS: daily has 30 rows
PASS: daily trips match clean.trips
PASS: top zones has 10 labeled rows
PASS: tips cover 24 hours with non-negative averages
PASS: payment percentages total 100
PASS: payment trips match clean.trips
All sanity checks passed.
```

## Evidence files

- `docs/evidence/m3/runner-run-1.txt`
- `docs/evidence/m3/runner-run-2.txt`
- `docs/evidence/m3/sanity-checks-run-1.txt`
- `docs/evidence/m3/sanity-checks-run-2.txt`
- `docs/evidence/m3/daily_trips_revenue-limit10.txt`
- `docs/evidence/m3/top_pickup_zones-limit10.txt`
- `docs/evidence/m3/avg_tip_by_hour-limit10.txt`
- `docs/evidence/m3/trips_by_payment_type-limit10.txt`

## Status

M3 is complete: four SQL queries, four analytics tables, an idempotent runner,
two identical runs, six passing sanity checks, sample outputs, and D-09/D-10.
