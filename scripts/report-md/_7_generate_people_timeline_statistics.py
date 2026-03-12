import numpy as np
import pandas as pd

# Read data, replacing '-' with NaN
districts_timeline = pd.read_csv("../../data/output/people-by-district-timeline.csv")
mo_timeline = pd.read_csv(
    "../../data/output/people-by-mo-timeline.csv", na_values=["-"]
)
districts_2025 = pd.read_csv(
    "../../data/source/rosstat/population/people-by-district-2025.csv"
)
mo_2025 = pd.read_csv("../../data/source/rosstat/population/people-by-mo-2025.csv")

# Strip whitespace from column names
mo_2025.columns = mo_2025.columns.str.strip()

# Build dicts for ID-to-name lookups
district_names = dict(zip(districts_2025["id"], districts_2025["name"]))
mo_names = dict(zip(mo_2025["id"], mo_2025["name"].str.strip()))

# Get latest data (2025)
districts_latest = districts_timeline[["district_id", "2025"]].copy()
districts_latest.columns = ["id", "population_2025"]

mo_latest = mo_timeline[["mo_id", "district_id", "2025"]].copy()
mo_latest.columns = ["mo_id", "district_id", "population_2025"]

# Add names
districts_latest["name"] = districts_latest["id"].map(district_names)
mo_latest["mo_name"] = mo_latest["mo_id"].map(mo_names)
mo_latest["district_name"] = mo_latest["district_id"].map(district_names)

# Sort districts by population descending
districts_latest = districts_latest.sort_values("population_2025", ascending=False)

# Sort MOs by district then by population
mo_latest = mo_latest.sort_values(
    ["district_id", "population_2025"], ascending=[True, False]
)

# Create markdown file
with open(
    "../../data/report-md/people-timeline-statistics.md", "w", encoding="utf-8"
) as f:
    f.write(
        "# Статистика населения Санкт-Петербурга по районам и муниципальным округам\n\n"
    )

    # Overall statistics
    total_population = districts_latest["population_2025"].sum()
    f.write("## Общая статистика (2025 год)\n\n")
    f.write(f"- **Общее население:** {total_population:,} чел.\n".replace(",", " "))
    f.write(f"- **Количество районов:** {len(districts_latest)}\n")
    f.write(f"- **Количество муниципальных округов:** {len(mo_latest)}\n\n")

    # District table
    f.write("## Население по районам (2025 год)\n\n")
    f.write("| Район | Население |\n")
    f.write("|-------|----------:|\n")

    for _, row in districts_latest.iterrows():
        f.write(f"| {row['name']} | {int(row['population_2025']):,} |\n")

    # District dynamics (2018-2025)
    f.write("\n## Динамика населения по районам (2018-2025)\n\n")
    f.write(
        "| Район | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Изменение | Изменение (%) |\n"
    )
    f.write(
        "|-------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|----------:|--------------:|\n"
    )

    years = ["2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"]

    for _, row in districts_latest.iterrows():
        district_id = row["id"]
        district_data = districts_timeline[
            districts_timeline["district_id"] == district_id
        ].iloc[0]
        change = district_data["2025"] - district_data["2018"]
        change_pct = (change / district_data["2018"]) * 100

        line = f"| {row['name']} |"
        for year in years:
            line += f" {int(district_data[year]):,} |"
        line += f" {int(change):+,} | {change_pct:+.1f} |\n"
        f.write(line)

    # MO table with dynamics (without "District" column)
    f.write("\n## Динамика населения по муниципальным округам (2018-2025)\n\n")
    f.write(
        "| Муниципальный округ | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Изменение | Изменение (%) |\n"
    )
    f.write(
        "|---------------------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|----------:|--------------:|\n"
    )

    current_district = None

    for _, row in mo_latest.iterrows():
        mo_id = row["mo_id"]
        mo_data = mo_timeline[mo_timeline["mo_id"] == mo_id].iloc[0]

        # Check if a new district has started
        if current_district != row["district_name"]:
            current_district = row["district_name"]
            # Add a district header row
            f.write(f"| **{current_district}** | | | | | | | | | | |\n")

        # Build MO data row
        if pd.isna(mo_data["2018"]):
            # If 2018 data is missing, show only available years
            mo_line = f"| {row['mo_name']} |"
            for year in years:
                if pd.isna(mo_data[year]):
                    mo_line += " — |"
                else:
                    mo_line += f" {int(mo_data[year]):,} |"
            mo_line += " — | — |\n"
        else:
            # If 2018 data exists, compute change
            change = mo_data["2025"] - mo_data["2018"]
            change_pct = (change / mo_data["2018"]) * 100

            mo_line = f"| {row['mo_name']} |"
            for year in years:
                if pd.isna(mo_data[year]):
                    mo_line += " — |"
                else:
                    mo_line += f" {int(mo_data[year]):,} |"
            mo_line += f" {int(change):+,} | {change_pct:+.1f} |\n"

        f.write(mo_line)

print("File people-timeline-statistics.md created successfully!")
