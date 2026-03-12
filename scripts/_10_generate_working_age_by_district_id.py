#!/usr/bin/env python3
"""
Script for generating CSV files with population age group data by district
using district IDs from people-by-district-2025.csv.
"""

import csv
from pathlib import Path


def read_csv_to_dict(file_path):
    """Read a CSV file and return a dict {district_name: row data}."""
    data = {}
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            district_name = row["district_name"]
            data[district_name] = row
    return data


def read_district_mapping(file_path):
    """Read the district file and return a dict {name: id}."""
    mapping = {}
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row["name"]] = row["id"]
    return mapping


def write_csv_with_ids(output_path, district_mapping, age_data):
    """Write a CSV file with district_id instead of district names."""
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["district_id", "total", "younger", "working", "older"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()

        # Sort by ID for convenience
        for district_name in sorted(
            district_mapping.keys(), key=lambda x: int(district_mapping[x])
        ):
            if district_name in age_data:
                data = age_data[district_name]
                writer.writerow(
                    {
                        "district_id": district_mapping[district_name],
                        "total": data["both"],
                        "younger": data["younger"],
                        "working": data["working"],
                        "older": data["older"],
                    }
                )


def main():
    # Define paths
    base_dir = Path(__file__).parent.parent
    source_dir = base_dir / "data" / "source" / "rosstat"
    output_dir = base_dir / "data" / "output"

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read district mapping
    district_mapping_file = source_dir / "population" / "people-by-district-2025.csv"
    district_mapping = read_district_mapping(district_mapping_file)

    # Files to process
    files = [
        (
            "working-age-population-both-2024.csv",
            "working-age-population-both-by-district-id.csv",
        ),
        (
            "working-age-population-female-2024.csv",
            "working-age-population-female-by-district-id.csv",
        ),
        (
            "working-age-population-male-2024.csv",
            "working-age-population-male-by-district-id.csv",
        ),
    ]

    working_age_dir = source_dir / "working-age-population"

    for input_file, output_file in files:
        # Read age group data
        input_path = working_age_dir / input_file
        age_data = read_csv_to_dict(input_path)

        # Write with district IDs
        output_path = output_dir / output_file
        write_csv_with_ids(output_path, district_mapping, age_data)

        print(f"✓ File created: {output_file}")

    print(f"\nAll files saved to: {output_dir}")


if __name__ == "__main__":
    main()
