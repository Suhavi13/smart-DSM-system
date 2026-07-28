import os
from pathlib import Path

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from backend.app.cache_service import cache
from backend.app.database import SessionLocal
from backend.app.models import SensorPoint, SensorReading


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "merged_timeseries_student.csv"

CHUNK_SIZE = int(os.getenv("IMPORT_CHUNK_SIZE", "100000"))
MAX_ROWS_PER_SENSOR = int(os.getenv("MAX_ROWS_PER_SENSOR", "10000"))
INSERT_BATCH_SIZE = int(os.getenv("INSERT_BATCH_SIZE", "5000"))
INVALID_ABSOLUTE_VALUE = float(os.getenv("INVALID_ABSOLUTE_VALUE", "1e12"))


def insert_rows_in_batches(db, rows_to_insert):
    total_inserted = 0

    for start in range(0, len(rows_to_insert), INSERT_BATCH_SIZE):
        batch = rows_to_insert[start:start + INSERT_BATCH_SIZE]
        statement = insert(SensorReading).values(batch)
        statement = statement.on_conflict_do_nothing(
            constraint="unique_sensor_reading"
        )
        result = db.execute(statement)
        total_inserted += max(result.rowcount or 0, 0)

    return total_inserted


def main():
    if not CSV_PATH.exists():
        print(f"CSV file not found: {CSV_PATH}")
        return

    db = SessionLocal()

    try:
        inventory_sensors = (
            db.query(SensorPoint)
            .filter(SensorPoint.is_selected.is_(True))
            .order_by(SensorPoint.sensor_code)
            .all()
        )

        if not inventory_sensors:
            print("No inventory sensors found in PostgreSQL.")
            print("Run: py -m backend.import_selected_sensors")
            return

        csv_columns = set(pd.read_csv(CSV_PATH, nrows=0).columns)
        sensors = [
            sensor
            for sensor in inventory_sensors
            if sensor.trend_column in csv_columns
        ]
        missing_from_csv = [
            sensor.trend_column
            for sensor in inventory_sensors
            if sensor.trend_column not in csv_columns
        ]

        if missing_from_csv:
            print("Database sensors missing from CSV:")
            for trend_column in missing_from_csv:
                print(f"  - {trend_column}")

        if not sensors:
            print("None of the PostgreSQL sensor columns exist in the CSV.")
            return

        sensor_map = {
            sensor.trend_column: {
                "sensor_point_id": sensor.sensor_point_id,
                "sensor_code": sensor.sensor_code,
            }
            for sensor in sensors
        }
        columns_to_read = ["ts", *sensor_map.keys()]

        print("Reading the historical CSV in chunks...")
        print(f"Inventory sensors in PostgreSQL: {len(inventory_sensors)}")
        print(f"Matching sensor columns in CSV: {len(sensors)}")
        print(f"Maximum readings retained per sensor: {MAX_ROWS_PER_SENSOR:,}")
        print(
            "Maximum rows prepared: "
            f"{len(sensors) * MAX_ROWS_PER_SENSOR:,}"
        )

        # The CSV is chronological. Retaining the tail after every chunk keeps
        # the latest N valid readings per sensor without loading the full CSV.
        latest_rows = {
            trend_column: pd.DataFrame(columns=["ts", trend_column])
            for trend_column in sensor_map
        }
        rejected_extreme_values = 0

        for chunk_number, chunk in enumerate(
            pd.read_csv(
                CSV_PATH,
                usecols=columns_to_read,
                chunksize=CHUNK_SIZE,
            ),
            start=1,
        ):
            chunk["ts"] = pd.to_datetime(chunk["ts"], errors="coerce")

            for trend_column in sensor_map:
                numeric_values = pd.to_numeric(
                    chunk[trend_column],
                    errors="coerce",
                )
                valid_mask = chunk["ts"].notna() & numeric_values.notna()
                extreme_mask = numeric_values.abs() > INVALID_ABSOLUTE_VALUE
                rejected_extreme_values += int((valid_mask & extreme_mask).sum())
                valid_mask &= ~extreme_mask

                if not valid_mask.any():
                    continue

                valid_rows = pd.DataFrame(
                    {
                        "ts": chunk.loc[valid_mask, "ts"],
                        trend_column: numeric_values.loc[valid_mask],
                    }
                )
                latest_rows[trend_column] = pd.concat(
                    [latest_rows[trend_column], valid_rows],
                    ignore_index=True,
                ).tail(MAX_ROWS_PER_SENSOR)

            print(f"Processed CSV chunk {chunk_number}")

        total_prepared = 0
        total_inserted = 0
        sensors_with_readings = 0

        # Commit each sensor separately. A full 124-sensor import can prepare
        # up to 1.24 million rows, so smaller transactions are safer and easier
        # to resume. Duplicate timestamps are ignored on reruns.
        for sensor_number, (trend_column, readings_df) in enumerate(
            latest_rows.items(),
            start=1,
        ):
            if readings_df.empty:
                print(f"No usable readings found for {trend_column}")
                continue

            sensor_data = sensor_map[trend_column]
            sensor_rows = [
                {
                    "sensor_point_id": sensor_data["sensor_point_id"],
                    "reading_time": reading_time.to_pydatetime(),
                    "value": float(value),
                }
                for reading_time, value in readings_df.itertuples(
                    index=False,
                    name=None,
                )
            ]

            prepared_count = len(sensor_rows)
            inserted_count = insert_rows_in_batches(db, sensor_rows)
            db.commit()

            total_prepared += prepared_count
            total_inserted += inserted_count
            sensors_with_readings += 1

            print(
                f"[{sensor_number}/{len(sensor_map)}] "
                f"{sensor_data['sensor_code']}: "
                f"{prepared_count:,} prepared, "
                f"{inserted_count:,} inserted"
            )

        print("Reading import complete.")
        print(f"Sensors with usable readings: {sensors_with_readings}")
        print(f"Rows prepared: {total_prepared:,}")
        print(f"Rows inserted: {total_inserted:,}")
        print(f"Extreme/sentinel values skipped: {rejected_extreme_values:,}")
        deleted_keys = cache.clear_namespace()
        print(f"Cleared {deleted_keys} cached dashboard response(s).")

    except Exception as error:
        db.rollback()
        print(f"Import failed: {error}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
