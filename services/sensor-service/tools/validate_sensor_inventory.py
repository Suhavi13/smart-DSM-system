"""Validate Sheet1 against the historical CSV before database import."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXCEL_PATH = PROJECT_ROOT / "docs" / "Sensor_Inventory.xlsx"
CSV_PATH = PROJECT_ROOT / "data" / "merged_timeseries_student.csv"
SHEET_NAME = "Sheet1"


def duplicated_values(series: pd.Series) -> list[str]:
    duplicate_mask = series.duplicated(keep=False) & series.notna()
    return sorted(series.loc[duplicate_mask].astype(str).unique().tolist())


def main():
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel file not found: {EXCEL_PATH}")
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV file not found: {CSV_PATH}")

    inventory = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    inventory.columns = inventory.columns.str.strip()
    inventory = inventory.dropna(subset=["Trend Column", "Sensor Code"])

    csv_columns = pd.read_csv(CSV_PATH, nrows=0).columns.tolist()
    csv_sensor_columns = [column for column in csv_columns if column != "ts"]

    trend_columns = inventory["Trend Column"].astype(str).str.strip().tolist()
    sensor_codes = inventory["Sensor Code"].astype(str).str.strip().tolist()

    duplicate_trends = duplicated_values(inventory["Trend Column"])
    duplicate_codes = duplicated_values(inventory["Sensor Code"])
    missing_from_csv = sorted(set(trend_columns) - set(csv_sensor_columns))
    csv_not_in_sheet = sorted(set(csv_sensor_columns) - set(trend_columns))

    print(f"Workbook: {EXCEL_PATH.name}")
    print(f"Sheet: {SHEET_NAME}")
    print(f"Inventory sensors: {len(sensor_codes)}")
    print(f"CSV sensor columns: {len(csv_sensor_columns)}")
    print(f"Duplicate sensor codes: {len(duplicate_codes)}")
    print(f"Duplicate trend columns: {len(duplicate_trends)}")
    print(f"Sheet columns missing from CSV: {len(missing_from_csv)}")
    print(f"CSV columns missing from Sheet1: {len(csv_not_in_sheet)}")

    if duplicate_codes:
        print("Duplicate sensor codes:", ", ".join(duplicate_codes))
    if duplicate_trends:
        print("Duplicate trend columns:", ", ".join(duplicate_trends))
    if missing_from_csv:
        print("Sheet columns missing from CSV:")
        for column in missing_from_csv:
            print(f"  - {column}")
    if csv_not_in_sheet:
        print("CSV columns missing from Sheet1:")
        for column in csv_not_in_sheet:
            print(f"  - {column}")

    is_valid = not any(
        [
            duplicate_codes,
            duplicate_trends,
            missing_from_csv,
            csv_not_in_sheet,
        ]
    )

    if not is_valid:
        raise SystemExit("Inventory validation failed.")

    print("Validation passed: Sheet1 and the CSV contain the same sensors.")


if __name__ == "__main__":
    main()
