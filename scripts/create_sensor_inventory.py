"""Create a simple sensor inventory workbook from the merged time-series CSV."""

import pandas as pd

df = pd.read_csv("../data/merged_timeseries_student.csv")

counts = df.count()

inventory = pd.DataFrame({
    "Trend Column": counts.index[1:],
    "Non-Null Count": counts.values[1:]
})

inventory["Display Name"] = ""
inventory["Category"] = ""
inventory["Priority"] = ""
inventory["Selected"] = ""

inventory.to_excel(
    "../docs/Sensor_Inventory.xlsx",
    index=False
)

print("Inventory created")
