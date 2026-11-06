import os
import tempfile

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

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
engine = create_engine(DATABASE_URL)

RAW_TRIPS_TABLE = "yellow_tripdata_2026_09"
RAW_ZONES_TABLE = "taxi_zone_lookup"
CLEAN_SCHEMA = "clean"
CLEAN_TABLE = "trips"

START_DATE = pd.Timestamp("2026-09-01 00:00:00")
END_DATE = pd.Timestamp("2026-10-01 00:00:00")
MAX_DURATION_HOURS = 12
MAX_SPEED_MPH = 100
HIGH_FARE_THRESHOLD = 500
HIGH_FARE_PER_MILE = 30

REQUIRED_COLUMNS = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "fare_amount",
    "trip_distance",
]

DEDUP_KEY = [
    "VendorID",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "fare_amount",
    "trip_distance",
    "total_amount",
]

TRIP_RENAME = {
    "VendorID": "vendor_id",
    "tpep_pickup_datetime": "pickup_datetime",
    "tpep_dropoff_datetime": "dropoff_datetime",
    "passenger_count": "passenger_count",
    "trip_distance": "trip_distance",
    "RatecodeID": "ratecode_id",
    "store_and_fwd_flag": "store_and_fwd_flag",
    "PULocationID": "pickup_location_id",
    "DOLocationID": "dropoff_location_id",
    "payment_type": "payment_type",
    "fare_amount": "fare_amount",
    "extra": "extra",
    "mta_tax": "mta_tax",
    "tip_amount": "tip_amount",
    "tolls_amount": "tolls_amount",
    "improvement_surcharge": "improvement_surcharge",
    "total_amount": "total_amount",
    "congestion_surcharge": "congestion_surcharge",
    "Airport_fee": "airport_fee",
    "cbd_congestion_fee": "cbd_congestion_fee",
    "request_source": "request_source",
}

LOOKUP_RENAME = {
    "LocationID": "location_id",
    "Borough": "borough",
    "Zone": "zone",
    "service_zone": "service_zone",
}


def load_raw_tables():
    """Read the trip and zone tables from the raw schema."""
    trips = pd.read_sql_table(RAW_TRIPS_TABLE, con=engine, schema="raw")
    zones = pd.read_sql_table(RAW_ZONES_TABLE, con=engine, schema="raw")

    for column in ("tpep_pickup_datetime", "tpep_dropoff_datetime"):
        if not pd.api.types.is_datetime64_any_dtype(trips[column]):
            trips[column] = pd.to_datetime(trips[column])

    return trips, zones


def _result(before, after):
    return after, len(before) - len(after)


def drop_missing_required_fields(df):
    """Reject rows missing a field the clean trip cannot be built without."""
    cleaned = df.dropna(subset=REQUIRED_COLUMNS).copy()
    return _result(df, cleaned)


def drop_out_of_period_trips(df):
    """Keep only trips whose pickup falls in September 2026."""
    mask = (
        (df["tpep_pickup_datetime"] >= START_DATE)
        & (df["tpep_pickup_datetime"] < END_DATE)
    )
    cleaned = df.loc[mask].copy()
    return _result(df, cleaned)


def drop_invalid_timestamps(df):
    """Reject trips whose dropoff is not after their pickup."""
    mask = df["tpep_dropoff_datetime"] > df["tpep_pickup_datetime"]
    cleaned = df.loc[mask].copy()
    return _result(df, cleaned)


def drop_invalid_duration(df):
    """Reject trips longer than the profiling-derived 12-hour limit."""
    duration = df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]
    mask = duration <= pd.Timedelta(hours=MAX_DURATION_HOURS)
    cleaned = df.loc[mask].copy()
    return _result(df, cleaned)


def drop_invalid_fares(df):
    """Reject negative and zero fares."""
    cleaned = df.loc[df["fare_amount"] > 0].copy()
    return _result(df, cleaned)


def drop_invalid_distances(df):
    """Reject zero and negative trip distances."""
    cleaned = df.loc[df["trip_distance"] > 0].copy()
    return _result(df, cleaned)


def drop_invalid_speed(df):
    """Reject trips implying a speed above the profiling-derived limit."""
    duration_hours = (
        df["tpep_dropoff_datetime"] - df["tpep_pickup_datetime"]
    ).dt.total_seconds() / 3600.0
    implied_speed = df["trip_distance"] / duration_hours
    mask = (duration_hours > 0) & (implied_speed <= MAX_SPEED_MPH)
    cleaned = df.loc[mask].copy()
    return _result(df, cleaned)


def drop_high_fares(df):
    """Reject high fares that are not explained by distance."""
    fare_per_mile = df["fare_amount"] / df["trip_distance"]
    anomaly = (
        (df["fare_amount"] > HIGH_FARE_THRESHOLD)
        & (df["trip_distance"] > 0)
        & (fare_per_mile > HIGH_FARE_PER_MILE)
    )
    cleaned = df.loc[~anomaly].copy()
    return _result(df, cleaned)


def drop_duplicate_trips(df):
    """Keep one deterministic copy of each repeated trip."""
    sort_columns = DEDUP_KEY + [c for c in df.columns if c not in DEDUP_KEY]
    sorted_df = df.sort_values(
        by=sort_columns,
        ascending=True,
        na_position="last",
        kind="mergesort",
    )
    cleaned = (
        sorted_df.drop_duplicates(subset=DEDUP_KEY, keep="first")
        .reset_index(drop=True)
    )
    return _result(df, cleaned)


def apply_cleaning_rules(df):
    """Run every rule in order and return cleaned rows with a rejection log."""
    rules = [
        ("missing required fields", drop_missing_required_fields),
        ("outside September 2026", drop_out_of_period_trips),
        ("invalid timestamps", drop_invalid_timestamps),
        ("invalid duration", drop_invalid_duration),
        ("invalid fares", drop_invalid_fares),
        ("invalid distances", drop_invalid_distances),
        ("invalid speed", drop_invalid_speed),
        ("high fares", drop_high_fares),
        ("duplicate trips", drop_duplicate_trips),
    ]

    rejected = {}
    for rule_name, rule in rules:
        before = len(df)
        df, count = rule(df)
        rejected[rule_name] = count
        print(f"{rule_name:<28} rejected {count:>10,} rows")

    return df, rejected


def rename_trip_columns(df):
    """Apply the explicit raw-to-clean column mapping."""
    missing = sorted(set(TRIP_RENAME) - set(df.columns))
    if missing:
        raise KeyError(f"Missing trip columns: {missing}")
    return df.rename(columns=TRIP_RENAME)


def enrich_with_zones(trips, zones):
    """Left-join the zone lookup once for pickup and once for dropoff."""
    missing = sorted(set(LOOKUP_RENAME) - set(zones.columns))
    if missing:
        raise KeyError(f"Missing lookup columns: {missing}")

    lookup = zones.rename(columns=LOOKUP_RENAME)[
        ["location_id", "borough", "zone"]
    ]

    pickup_lookup = lookup.rename(
        columns={
            "location_id": "pickup_location_id",
            "borough": "pickup_borough",
            "zone": "pickup_zone",
        }
    )
    dropoff_lookup = lookup.rename(
        columns={
            "location_id": "dropoff_location_id",
            "borough": "dropoff_borough",
            "zone": "dropoff_zone",
        }
    )

    before = len(trips)
    trips = trips.merge(
        pickup_lookup,
        how="left",
        on="pickup_location_id",
        validate="many_to_one",
    )
    if len(trips) != before:
        raise AssertionError("Pickup zone join changed the row count.")

    trips = trips.merge(
        dropoff_lookup,
        how="left",
        on="dropoff_location_id",
        validate="many_to_one",
    )
    if len(trips) != before:
        raise AssertionError("Dropoff zone join changed the row count.")

    return trips


def write_clean_trips(df):
    """Replace clean.trips with the transformed data using PostgreSQL COPY."""
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {CLEAN_SCHEMA};"))

    # Create the table from the DataFrame schema, then stream rows with COPY.
    df.head(0).to_sql(
        CLEAN_TABLE,
        con=engine,
        schema=CLEAN_SCHEMA,
        if_exists="replace",
        index=False,
    )

    raw_connection = engine.raw_connection()
    try:
        copy_sql = (
            f"COPY {CLEAN_SCHEMA}.{CLEAN_TABLE} "
            "FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
        )
        with tempfile.TemporaryFile(
            mode="w+", encoding="utf-8", newline=""
        ) as csv_file:
            df.to_csv(csv_file, index=False, header=True, na_rep="")
            csv_file.seek(0)
            with raw_connection.cursor() as cursor:
                cursor.copy_expert(copy_sql, csv_file)
        raw_connection.commit()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        raw_connection.close()


def get_clean_count():
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT COUNT(*) FROM {CLEAN_SCHEMA}.{CLEAN_TABLE}")
        ).scalar_one()


def print_rejection_summary(rejected, raw_count, clean_count):
    total_rejected = sum(rejected.values())

    print("\nRejected rows by rule")
    print("-" * 44)
    for rule, count in rejected.items():
        print(f"{rule:<28} {count:>10,}")
    print("-" * 44)
    print(f"{'total rejected':<28} {total_rejected:>10,}")
    print(f"{'raw rows':<28} {raw_count:>10,}")
    print(f"{'clean rows':<28} {clean_count:>10,}")

    if raw_count - total_rejected != clean_count:
        raise AssertionError(
            "Row-count reconciliation failed: "
            f"{raw_count:,} raw - {total_rejected:,} rejected "
            f"!= {clean_count:,} clean"
        )

    print("Reconciliation passed.")


def main():
    print("Loading raw tables...")
    trips, zones = load_raw_tables()
    raw_count = len(trips)
    print(f"Loaded {raw_count:,} raw trips and {len(zones):,} zone rows.")

    print("\nApplying cleaning rules...")
    clean, rejected = apply_cleaning_rules(trips)

    print("\nRenaming columns...")
    clean = rename_trip_columns(clean)

    print("Joining pickup and dropoff zones...")
    clean = enrich_with_zones(clean, zones)

    clean_key = [TRIP_RENAME[column] for column in DEDUP_KEY]
    duplicate_count = clean.duplicated(subset=clean_key).sum()
    if duplicate_count:
        raise AssertionError(
            f"Clean data still contains {duplicate_count:,} duplicate rows."
        )

    print(f"Writing {len(clean):,} rows to {CLEAN_SCHEMA}.{CLEAN_TABLE}...")
    write_clean_trips(clean)

    db_count = get_clean_count()
    if db_count != len(clean):
        raise AssertionError(
            f"Write verification failed: {len(clean):,} in memory "
            f"but {db_count:,} in {CLEAN_SCHEMA}.{CLEAN_TABLE}"
        )

    print_rejection_summary(rejected, raw_count, db_count)
    print("\nTransform completed successfully.")


if __name__ == "__main__":
    main()
