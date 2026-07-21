from pathlib import Path

import pandas as pd

from backend.app.database import SessionLocal
from backend.app.models import SensorPoint
from backend.app.sensor_metadata import get_sensor_metadata


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCEL_PATH = PROJECT_ROOT / "docs" / "Sensor_Inventory.xlsx"
SHEET_NAME = "Sheet1"


def clean_text(value):
    if pd.isna(value):
        return None
    return str(value).strip()


def clean_integer(value):
    if pd.isna(value):
        return None
    return int(value)


def main():
    if not EXCEL_PATH.exists():
        print(f"Excel file not found: {EXCEL_PATH}")
        return

    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    df.columns = df.columns.str.strip()

    required_columns = [
        "Trend Column",
        "Sensor Code",
        "Display Name",
        "Measurement Property",
    ]

    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        print("Missing Excel columns:", ", ".join(missing_columns))
        print("Columns found:", df.columns.tolist())
        return

    df = df.dropna(subset=["Trend Column", "Sensor Code"])
    df = df.drop_duplicates(subset=["Sensor Code"], keep="last")
    db = SessionLocal()

    try:
        imported_count = 0
        updated_count = 0

        for _, row in df.iterrows():
            sensor_code = clean_text(row["Sensor Code"])
            source_display_name = clean_text(row["Display Name"])
            measurement_property = clean_integer(
                row.get("Measurement Property")
            )
            metadata = get_sensor_metadata(
                sensor_code=sensor_code,
                display_name=source_display_name,
                measurement_property=measurement_property,
            )

            sensor_data = {
                "sensor_code": sensor_code,
                "trend_column": clean_text(row["Trend Column"]),
                "display_name": metadata["display_name"],
                "measurement_property": measurement_property,
                "category": (
                    clean_text(row.get("Category"))
                    or metadata.get("category")
                ),
                "priority": clean_text(row.get("Priority")),
                "why_selected": clean_text(row.get("Why selected")),
                "dashboard_feature": clean_text(
                    row.get("Dashboard feature")
                ),
                "raw_unit": metadata["raw_unit"],
                "display_unit": metadata["display_unit"],
                "scale_factor": metadata["scale_factor"],
                "sign_convention": metadata["sign_convention"],
                "data_type": metadata["data_type"],
                "location": metadata["location"],
                # The user requested the complete Sheet1 inventory, so every
                # row is exposed by the Sensor Data Service.
                "is_selected": True,
            }

            existing_sensor = (
                db.query(SensorPoint)
                .filter(SensorPoint.sensor_code == sensor_code)
                .first()
            )

            if existing_sensor:
                for key, value in sensor_data.items():
                    setattr(existing_sensor, key, value)
                updated_count += 1
            else:
                db.add(SensorPoint(**sensor_data))
                imported_count += 1

        db.commit()
        total_count = imported_count + updated_count
        print(f"Sheet imported: {SHEET_NAME}")
        print(f"Inventory rows processed: {total_count}")
        print(f"New sensors imported: {imported_count}")
        print(f"Existing sensors updated: {updated_count}")
        print(
            "All Sheet1 sensors are marked for API display and reading import."
        )
        print(
            "Naming-derived units remain provisional unless a sensor has a "
            "confirmed override in backend/app/sensor_metadata.py."
        )

    except Exception as error:
        db.rollback()
        print(f"Import failed: {error}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
