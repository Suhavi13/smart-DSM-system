# import pandas as pd

# df = pd.read_csv("../data/merged_timeseries_student.csv")

# top_sensors = [
#     "SaitSolarLab_30000_TL2",
#     "SaitSolarLab_30000_TL4",
#     "SaitSolarLab_30000_TL252",
#     "SaitSolarLab_30000_TL253"
# ]

# for sensor in top_sensors:
#     print("\n")
#     print(sensor)
#     print(df[sensor].describe())

import pandas as pd

df = pd.read_csv(
    "../data/merged_timeseries_student.csv",
    usecols=[
        "SaitSolarLab_30000_TL2",
        "SaitSolarLab_30000_TL252",
        "SaitSolarLab_30000_TL253"
    ]
)

for col in df.columns:
    print("\n", col)
    print("Unique values:", df[col].nunique())