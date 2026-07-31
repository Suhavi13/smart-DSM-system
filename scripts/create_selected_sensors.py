"""Copy rows marked as selected into a separate workbook sheet."""

import pandas as pd

file = "../docs/Sensor_Inventory.xlsx"

df = pd.read_excel(file)

selected = df[df["Selected"] == "yes"]

with pd.ExcelWriter(
    file,
    engine="openpyxl",
    mode="a",
    if_sheet_exists="replace"
) as writer:
    selected.to_excel(
        writer,
        sheet_name="Selected DSM Sensors",
        index=False
    )

print("Sheet 2 created")
