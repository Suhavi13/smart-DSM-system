"""Preview a small set of sensor columns from the merged CSV."""

import pandas as pd

df = pd.read_csv(
    "../data/merged_timeseries_student.csv",
    usecols=[
        "ts",
        "SaitSolarLab_30000_TL2",
        "SaitSolarLab_30000_TL252",
        "SaitSolarLab_30000_TL253"
    ]
)

print(df.head(20))
