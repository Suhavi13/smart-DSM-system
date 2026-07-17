from pathlib import Path

import pandas as pd

from backend.app.database import SessionLocal
from backend.app.models import SensorPoint
from backend.app.sensor_metadata import get_sensor_metadata


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCEL_PATH = PROJECT_ROOT / "docs" / "Sensor_Inventory.xlsx"
SHEET_NAME = "Selected DSM Sensors"


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
        "Category",
        "Priority",
    ]

    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    if missing_columns:
        print("Missing Excel columns:", ", ".join(missing_columns))
        print("Columns found:", df.columns.tolist())
        return

    df = df.dropna(subset=["Trend Column", "Sensor Code"])
    db = SessionLocal()

    try:
        imported_count = 0
        updated_count = 0

        for _, row in df.iterrows():
            sensor_code = clean_text(row["Sensor Code"])
            metadata = get_sensor_metadata(sensor_code)

            sensor_data = {
                "sensor_code": sensor_code,
                "trend_column": clean_text(row["Trend Column"]),
                "display_name": clean_text(row["Display Name"]),
                "measurement_property": clean_integer(
                    row.get("Measurement Property")
                ),
                "category": clean_text(row.get("Category")),
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
        print(f"Imported: {imported_count} sensor(s)")
        print(f"Updated: {updated_count} sensor(s)")
        print(
            "Note: unit mappings are provisional until confirmed by the "
            "client's official data dictionary."
        )

    except Exception as error:
        db.rollback()
        print(f"Import failed: {error}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
