#!/usr/bin/env python3
"""
Script for generating an MD file with an age distribution table by district.
"""

from pathlib import Path

import pandas as pd


def load_data(csv_path: str) -> pd.DataFrame:
    """Load a CSV file with data."""
    df = pd.read_csv(csv_path, skipinitialspace=True)
    # Strip whitespace from column names
    df.columns = df.columns.str.strip()
    return df


def prepare_pivot_table(df: pd.DataFrame, gender: str) -> pd.DataFrame:
    """Build a pivot table: districts as rows, age groups as columns.

    Args:
        df: DataFrame with data
        gender: 'both', 'male', or 'female'
    """

    # Define age group order for correct sorting
    age_order = [
        "до 1 года",
        "1",
        "0–2",
        "3–5",
        "6",
        "1–6",
        "7",
        "8–13",
        "14–15",
        "16–17",
        "18–19",
        "20–24",
        "25–29",
        "30–34",
        "35–39",
        "40–44",
        "45–49",
        "50–54",
        "55–59",
        "60–64",
        "65–69",
        "70 и старше",
    ]

    # Build pivot table
    pivot = df.pivot(index="district", columns="age", values=gender)

    # Reorder columns according to age_order, keeping only those present in the data
    ordered_cols = [col for col in age_order if col in pivot.columns]
    pivot = pivot[ordered_cols]

    # Sort districts alphabetically
    pivot = pivot.sort_index()

    return pivot


def format_number(num):
    """Format a number for display in a table."""
    if pd.isna(num):
        return ""
    return f"{int(num):,}"


def create_markdown_table(pivot: pd.DataFrame) -> str:
    """Create a Markdown table from a pivot DataFrame."""

    # Abbreviation mapping for age group names
    age_abbrev = {"до 1 года": "до 1", "70 и старше": "70+"}

    md_lines = []

    # Table header - column names (age groups)
    header = (
        "| район | "
        + " | ".join([age_abbrev.get(col, col) for col in pivot.columns])
        + " |"
    )
    md_lines.append(header)

    # Separator (left align for district, right align for numbers)
    separator = (
        "| --- |" + "|".join([" ---: " for _ in range(len(pivot.columns))]) + "|"
    )
    md_lines.append(separator)

    # Data rows by district
    for district, row in pivot.iterrows():
        # Remove the word "район" from the name
        district_name = district.replace(" район", "")
        values = [format_number(val) for val in row]
        data_row = f"| {district_name} | " + " | ".join(values) + " |"
        md_lines.append(data_row)

    return "\n".join(md_lines)


def generate_markdown_file(csv_path: str, output_path: str, gender: str, title: str):
    """Main function for generating an MD file.

    Args:
        csv_path: path to CSV file
        output_path: path to save the MD file
        gender: 'both', 'male', or 'female'
        title: table title
    """

    print(f"Generating table: {title}...")
    df = load_data(csv_path)
    pivot = prepare_pivot_table(df, gender)
    md_table = create_markdown_table(pivot)

    # Build full MD file with title
    md_content = f"""# {title}

{md_table}
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"✓ Saved: {output_path}")


if __name__ == "__main__":
    csv_path = (
        "../../data/source/rosstat/population/population-age-sex-structure-2024.csv"
    )

    print("Loading data from age_districts.csv...\n")

    # Generate three tables for different categories
    tables = [
        {
            "gender": "both",
            "output": "../../data/report-md/age_districts_both.md",
            "title": "Распределение населения по районам и возрастам (оба пола)",
        },
        {
            "gender": "male",
            "output": "../../data/report-md/age_districts_male.md",
            "title": "Распределение населения по районам и возрастам (мужчины)",
        },
        {
            "gender": "female",
            "output": "../../data/report-md/age_districts_female.md",
            "title": "Распределение населения по районам и возрастам (женщины)",
        },
    ]

    for table in tables:
        generate_markdown_file(
            csv_path, table["output"], table["gender"], table["title"]
        )

    print("\n✓ All tables generated successfully!")
