import os

import pandas as pd

# Read the district file with IDs
districts_df = pd.read_csv("data/source/rosstat/population/people-by-district-2025.csv")
district_mapping = dict(zip(districts_df["name"], districts_df["id"]))

print("District mapping:")
for name, id in district_mapping.items():
    print(f"{name} -> {id}")

# Read the housing commissioning data
housing_df = pd.read_csv(
    "data/source/rosstat/housing/commissioning-housing-by-district.csv"
)

print("\nOriginal district names in housing data:")
print(housing_df["district_name"].tolist())

# Replace district names with their IDs
housing_df["district_id"] = housing_df["district_name"].map(district_mapping)

# Check for districts without a match
missing = housing_df[housing_df["district_id"].isna()]["district_name"].unique()
if len(missing) > 0:
    print(f"\nWarning! IDs not found for districts: {missing}")

# Drop the name column and move district_id to first position
housing_df = housing_df.drop("district_name", axis=1)
cols = ["district_id"] + [col for col in housing_df.columns if col != "district_id"]
housing_df = housing_df[cols]

print("\nProcessed data:")
print(housing_df.head())

# Create output directory if it doesn't exist
os.makedirs("data/output", exist_ok=True)

# Save result
output_path = "data/output/commissioning-housing-by-district.csv"
housing_df.to_csv(output_path, index=False)

print(f"\nFile saved: {output_path}")
print(f"Row count: {len(housing_df)}")
