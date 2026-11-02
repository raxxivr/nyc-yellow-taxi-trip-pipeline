import os

import pandas as pd
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

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)


def create_schema():
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS clean;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics;"))
        conn.commit()


def load_csv_to_raw():
    file_path = "data/raw/taxi_zone_lookup.csv"
    table_name = "taxi_zone_lookup"

    print(f"Reading {file_path}...")
    df = pd.read_csv(file_path)

    print(f"Loading to Postgres as raw.{table_name}...")
    df.to_sql(name=table_name, con=engine, schema="raw", if_exists="replace", index=False)
    print("CSV loaded successfully\n")
    return len(df)


def load_parquet_to_raw():
    file_path = "data/raw/yellow_tripdata_2026-09.parquet"
    table_name = "yellow_tripdata_2026_09"

    print(f"Reading {file_path}...")
    df = pd.read_parquet(file_path)

    print(f"Loading to Postgres as raw.{table_name}...")
    df.to_sql(
        name=table_name,
        con=engine,
        schema="raw",
        if_exists="replace",
        index=False,
        chunksize=10000,
        method="multi",
    )
    print("Parquet loaded successfully\n")
    return len(df)


def validate_rows(expected_rows):
    """Fail if any loaded table has a different row count than its source file."""
    for table_name, expected in expected_rows.items():
        with engine.connect() as conn:
            actual = conn.execute(
                text(f"SELECT COUNT(*) FROM raw.{table_name}")
            ).scalar_one()

        print(
            f"Row check raw.{table_name}: "
            f"expected {expected:,}, found {actual:,}"
        )

        if actual != expected:
            raise ValueError(
                f"Row count mismatch for raw.{table_name}: "
                f"expected {expected:,}, found {actual:,}"
            )


if __name__ == "__main__":
    create_schema()
    zone_rows = load_csv_to_raw()
    trip_rows = load_parquet_to_raw()
    validate_rows(
        {
            "taxi_zone_lookup": zone_rows,
            "yellow_tripdata_2026_09": trip_rows,
        }
    )
