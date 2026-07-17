from pathlib import Path

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from backend.app.database import SessionLocal
from backend.app.models import SensorPoint, SensorReading


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "data" / "merged_timeseries_student.csv"

# Import all 19 sensors selected in docs/Sensor_Inventory.xlsx.
SELECTED_SENSOR_CODES = [
    "30000_TL212",
    "30000_TL210",
    "30000_TL3",
    "30000_TL335",
    "30000_TL342",
    "30000_TL388",
    "30000_TL211",
    "30000_TL208",
    "30000_TL4",
    "30000_TL209",
    "30000_TL252",
    "30000_TL253",
    "20000_TL92",
    "20016_TL5",
    "30000_TL213",
    "30000_TL343",
    "30000_TL344",
    "30000_TL345",
    "30000_TL207",
]

CHUNK_SIZE = 100_000
MAX_ROWS_PER_SENSOR = 10_000
INSERT_BATCH_SIZE = 5_000
INVALID_ABSOLUTE_VALUE = 1e12


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
        sensors = (
            db.query(SensorPoint)
            .filter(SensorPoint.sensor_code.in_(SELECTED_SENSOR_CODES))
            .all()
        )

        if not sensors:
            print("No matching selected sensors found in PostgreSQL.")
            return

        sensor_map = {
            sensor.trend_column: {
                "sensor_point_id": sensor.sensor_point_id,
                "sensor_code": sensor.sensor_code,
            }
            for sensor in sensors
        }

        missing_sensor_codes = sorted(
            set(SELECTED_SENSOR_CODES)
            - {sensor.sensor_code for sensor in sensors}
        )
        if missing_sensor_codes:
            print(
                "Selected sensors missing from PostgreSQL: "
                + ", ".join(missing_sensor_codes)
            )
            print("Run import_selected_sensors.py before importing readings.")

        columns_to_read = ["ts", *sensor_map.keys()]

        print("Reading CSV in chunks...")
        print("Selected sensors found:", len(sensors))

        # Keep only the newest rows per sensor while processing. This avoids
        # retaining every reading from the 600 MB CSV in memory.
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

                valid_rows = pd.DataFrame(
                    {
                        "ts": chunk.loc[valid_mask, "ts"],
                        trend_column: numeric_values.loc[valid_mask],
                    }
                )

                if valid_rows.empty:
                    continue

                latest_rows[trend_column] = pd.concat(
                    [latest_rows[trend_column], valid_rows],
                    ignore_index=True,
                ).tail(MAX_ROWS_PER_SENSOR)

            print(f"Processed chunk {chunk_number}")

        rows_to_insert = []

        for trend_column, readings_df in latest_rows.items():
            if readings_df.empty:
                print(f"No usable readings found for {trend_column}")
                continue

            sensor_data = sensor_map[trend_column]

            for row in readings_df.itertuples(index=False, name=None):
                reading_time, value = row
                rows_to_insert.append(
                    {
                        "sensor_point_id": sensor_data["sensor_point_id"],
                        "reading_time": reading_time.to_pydatetime(),
                        "value": float(value),
                    }
                )

            print(
                f"{sensor_data['sensor_code']}: "
                f"{len(readings_df)} readings prepared"
            )

        if not rows_to_insert:
            print("No readings were prepared for import.")
            return

        total_inserted = insert_rows_in_batches(db, rows_to_insert)
        db.commit()

        print("Import complete.")
        print(f"Rows prepared: {len(rows_to_insert)}")
        print(f"Rows inserted: {total_inserted}")
        print(f"Extreme/sentinel values skipped: {rejected_extreme_values}")

    except Exception as error:
        db.rollback()
        print(f"Import failed: {error}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
