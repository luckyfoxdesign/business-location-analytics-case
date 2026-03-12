import os

import pandas as pd

housing_df = pd.read_csv(
    "data/source/rosstat/housing/commissioning-housing-by-district.csv"
)

# Create report directory if it doesn't exist
os.makedirs("data/report-md", exist_ok=True)

# Build markdown table
md_content = "# Ввод жилья по районам (тыс. кв. м)\n\n"
md_content += "Данные о вводе жилья в эксплуатацию по районам Санкт-Петербурга.\n\n"

# Create table header
md_content += "| Район | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |\n"
md_content += "|-------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|\n"

# Add data rows
for _, row in housing_df.iterrows():
    district_name = row["district_name"]
    values = [
        str(row[year])
        for year in ["2017", "2018", "2019", "2020", "2021", "2022", "2023"]
    ]
    md_content += f"| {district_name} | {' | '.join(values)} |\n"

# Save file
output_path = "data/report-md/commissioning-housing-by-district.md"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(md_content)

print(f"Markdown file saved: {output_path}")
print(f"District count: {len(housing_df)}")
print(f"\nFirst 5 table rows:")
print(md_content.split("\n")[4:9])
print(md_content.split("\n")[4:9])
