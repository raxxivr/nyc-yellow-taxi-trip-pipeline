import csv
import os
from pathlib import Path

import pyarrow.parquet as pq
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nyc_yellow_taxi_trip")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not DB_PASSWORD:
    raise RuntimeError(
        "DB_PASSWORD is not set. Copy .env.example to .env and set DB_PASSWORD."
    )

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
engine = create_engine(DATABASE_URL)

PARQUET_PATH = Path("data/raw/yellow_tripdata_2026-09.parquet")
ZONE_CSV_PATH = Path("data/raw/taxi_zone_lookup.csv")

CHECKS = [
    (
        "clean keys have no nulls",
        """
        SELECT COUNT(*) FILTER (
            WHERE vendor_id IS NULL
               OR pickup_datetime IS NULL
               OR dropoff_datetime IS NULL
               OR pickup_location_id IS NULL
               OR dropoff_location_id IS NULL
               OR fare_amount IS NULL
               OR trip_distance IS NULL
               OR total_amount IS NULL
        ) = 0
        FROM clean.trips
        """,
    ),
    (
        "clean keys are unique",
        """
        SELECT COUNT(*) = 0
        FROM (
            SELECT 1
            FROM clean.trips
            GROUP BY
                vendor_id,
                pickup_datetime,
                dropoff_datetime,
                pickup_location_id,
                dropoff_location_id,
                fare_amount,
                trip_distance,
                total_amount
            HAVING COUNT(*) > 1
        ) duplicate_keys
        """,
    ),
    (
        "fares and distances are in range",
        """
        SELECT COUNT(*) FILTER (
            WHERE fare_amount <= 0 OR trip_distance < 0
        ) = 0
        FROM clean.trips
        """,
    ),
    (
        "timestamps, duration, and speed are in range",
        """
        SELECT COUNT(*) FILTER (
            WHERE pickup_datetime < TIMESTAMP '2026-09-01 00:00:00'
               OR pickup_datetime >= TIMESTAMP '2026-10-01 00:00:00'
               OR dropoff_datetime <= pickup_datetime
               OR dropoff_datetime - pickup_datetime > INTERVAL '12 hours'
               OR (
                   EXTRACT(EPOCH FROM (dropoff_datetime - pickup_datetime)) > 0
                   AND trip_distance
                       / (EXTRACT(EPOCH FROM (dropoff_datetime - pickup_datetime)) / 3600.0)
                       > 100
               )
        ) = 0
        FROM clean.trips
        """,
    ),
    (
        "location and payment codes are in range",
        """
        SELECT COUNT(*) FILTER (
            WHERE payment_type IS NULL
               OR payment_type NOT BETWEEN 0 AND 6
               OR pickup_location_id NOT BETWEEN 1 AND 265
               OR dropoff_location_id NOT BETWEEN 1 AND 265
        ) = 0
        FROM clean.trips
        """,
    ),
    (
        "analytics trip counts reconcile to clean.trips",
        """
        SELECT
            (SELECT SUM(trip_count) FROM analytics.daily_trips_revenue)
                = (SELECT COUNT(*) FROM clean.trips)
            AND
            (SELECT SUM(trip_count) FROM analytics.trips_by_payment_type)
                = (SELECT COUNT(*) FROM clean.trips)
        """,
    ),
    (
        "analytics table shapes and percentages are valid",
        """
        SELECT
            (SELECT COUNT(*) FROM analytics.daily_trips_revenue) = 30
            AND (SELECT COUNT(*) FROM analytics.avg_tip_by_hour) = 24
            AND (SELECT COUNT(*) FROM analytics.top_pickup_zones) = 10
            AND (SELECT COUNT(*) FROM analytics.top_pickup_zones
                 WHERE zone_label IS NULL) = 0
            AND (SELECT SUM(pct_of_trips) FROM analytics.trips_by_payment_type)
                BETWEEN 99.99 AND 100.01
        """,
    ),
    (
        "clean and analytics columns are snake_case",
        """
        SELECT COUNT(*) = 0
        FROM information_schema.columns
        WHERE table_schema IN ('clean', 'analytics')
          AND column_name !~ '^[a-z][a-z0-9_]*$'
        """,
    ),
]


def _report(name, passed, failures):
    print(f"{'PASS' if passed else 'FAIL'}: {name}")
    if not passed:
        failures.append(name)


def _source_row_counts():
    parquet_rows = pq.ParquetFile(PARQUET_PATH).metadata.num_rows

    with ZONE_CSV_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        zone_rows = sum(1 for _ in csv.reader(csv_file)) - 1

    return parquet_rows, zone_rows


def run_checks():
    failures = []
    print("Quality checks")
    print("-" * 44)

    with engine.connect() as conn:
        source_trip_rows, source_zone_rows = _source_row_counts()
        raw_trip_rows = conn.execute(
            text("SELECT COUNT(*) FROM raw.yellow_tripdata_2026_09")
        ).scalar_one()
        raw_zone_rows = conn.execute(
            text("SELECT COUNT(*) FROM raw.taxi_zone_lookup")
        ).scalar_one()

        _report(
            "source files match raw table rows",
            source_trip_rows == raw_trip_rows
            and source_zone_rows == raw_zone_rows,
            failures,
        )

        for name, check_sql in CHECKS:
            passed = bool(conn.execute(text(check_sql)).scalar())
            _report(name, passed, failures)

    if failures:
        raise AssertionError(f"Quality checks failed: {', '.join(failures)}")

    print("All quality checks passed.")


if __name__ == "__main__":
    run_checks()
