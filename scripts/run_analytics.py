import os
from pathlib import Path

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

SQL_FILES = [
    "sql/daily_trips_revenue.sql",
    "sql/top_pickup_zones.sql",
    "sql/avg_tip_by_hour.sql",
    "sql/trips_by_payment_type.sql",
]

CHECKS = [
    (
        "daily has 30 rows",
        "SELECT COUNT(*) = 30 FROM analytics.daily_trips_revenue",
    ),
    (
        "daily trips match clean.trips",
        "SELECT SUM(trip_count) = (SELECT COUNT(*) FROM clean.trips) "
        "FROM analytics.daily_trips_revenue",
    ),
    (
        "top zones has 10 labeled rows",
        "SELECT COUNT(*) = 10 "
        "AND COUNT(*) FILTER (WHERE zone_label IS NULL) = 0 "
        "FROM analytics.top_pickup_zones",
    ),
    (
        "tips cover 24 hours with non-negative averages",
        "SELECT COUNT(*) = 24 AND MIN(avg_tip) >= 0 "
        "FROM analytics.avg_tip_by_hour",
    ),
    (
        "payment percentages total 100",
        "SELECT SUM(pct_of_trips) BETWEEN 99.99 AND 100.01 "
        "FROM analytics.trips_by_payment_type",
    ),
    (
        "payment trips match clean.trips",
        "SELECT SUM(trip_count) = (SELECT COUNT(*) FROM clean.trips) "
        "FROM analytics.trips_by_payment_type",
    ),
]


def run_analytics():
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics;"))

            for file_path_str in SQL_FILES:
                file_path = Path(file_path_str)

                if not file_path.exists():
                    raise FileNotFoundError(f"SQL file not found: {file_path}")

                table_name = file_path.stem

                with open(file_path, "r", encoding="utf-8") as f:
                    select_query = f.read().strip()

                if select_query.endswith(";"):
                    select_query = select_query[:-1]

                drop_sql = f"DROP TABLE IF EXISTS analytics.{table_name};"
                create_sql = (
                    f"CREATE TABLE analytics.{table_name} AS {select_query};"
                )

                conn.execute(text(drop_sql))
                conn.execute(text(create_sql))

                print(f"Successfully created table: analytics.{table_name}")

        print("\nAll analytics tables built successfully within a single transaction.")

    except Exception as e:
        print(f"\nTransaction rolled back due to an error: {e}")
        raise


def run_checks():
    failures = []
    print("\nSanity checks")
    print("-" * 44)

    with engine.connect() as conn:
        for name, check_sql in CHECKS:
            passed = bool(conn.execute(text(check_sql)).scalar())
            print(f"{'PASS' if passed else 'FAIL'}: {name}")
            if not passed:
                failures.append(name)

    if failures:
        raise AssertionError(f"Sanity checks failed: {', '.join(failures)}")

    print("All sanity checks passed.")


if __name__ == "__main__":
    run_analytics()
    run_checks()
