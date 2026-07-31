"""Print basic metadata about the merged sensor CSV."""

import pandas as pd

df = pd.read_csv("../data/merged_timeseries_student.csv")

print("Shape:", df.shape)

counts = df.count().sort_values(ascending=False)

print("\nTop 20 columns with most data:")
print(counts.head(20))

print("\nBottom 20 columns with least data:")
print(counts.tail(20))

print("\nDate Range:")
print(df["ts"].min())
print(df["ts"].max())
