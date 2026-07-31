"""Build the first sensor inventory workbook from CSV columns and metadata."""

import pandas as pd

trend_df = pd.read_csv(
    "../data/merged_timeseries_student.csv",
    nrows=0
)

meta_df = pd.read_excel(
    "../data/Sensor_Names.xlsx"
)

trend_columns = trend_df.columns.tolist()[1:]

inventory = []

for col in trend_columns:

    sensor_code = col.replace("SaitSolarLab_", "")

    match = meta_df[
        meta_df["sensor_name_source"] == sensor_code
    ]

    if not match.empty:
        display_name = match.iloc[0]["sensor_name_report"]
        property_id = match.iloc[0]["sensor_measurement_properties"]
    else:
        display_name = ""
        property_id = ""

    inventory.append({
        "Trend Column": col,
        "Sensor Code": sensor_code,
        "Display Name": display_name,
        "Measurement Property": property_id,
        "Category": "",
        "Priority": "",
        "Selected": ""
    })

inventory_df = pd.DataFrame(inventory)

inventory_df.to_excel(
    "../docs/Sensor_Inventory.xlsx",
    index=False
)

print("Inventory created!")
