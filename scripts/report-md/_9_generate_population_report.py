#!/usr/bin/env python3
"""
Script for generating a report on district population by age groups
from CSV files into Markdown format for Obsidian.
"""

import csv
import os
from pathlib import Path


def read_csv_to_table(file_path):
    """Read a CSV file and return data as a list of lists."""
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        return list(reader)


def generate_markdown_table(data, title, gender_label):
    """Generate a Markdown table from data."""
    if not data:
        return ""

    lines = [f"## {title}\n"]

    # Table header with renamed columns
    translated_headers = [
        "Район",
        gender_label,
        "Моложе трудоспособного",
        "Трудоспособном",
        "Старше трудоспособного",
    ]

    header_line = "| " + " | ".join(translated_headers) + " |"
    separator_line = "|" + "|".join(["---" for _ in translated_headers]) + "|"

    lines.append(header_line)
    lines.append(separator_line)

    # Data rows
    for row in data[1:]:
        row_line = "| " + " | ".join(row) + " |"
        lines.append(row_line)

    return "\n".join(lines)


def main():
    # Define paths
    base_dir = Path(__file__).parent.parent.parent
    source_dir = base_dir / "data" / "source" / "rosstat" / "working-age-population"
    output_dir = base_dir / "data" / "report-md"

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Files to process
    files = [
        (
            "working-age-population-both-2024.csv",
            "Общая численность населения (мужчины и женщины)",
            "Оба пола",
        ),
        (
            "working-age-population-female-2024.csv",
            "Численность женского населения",
            "Только женщины",
        ),
        (
            "working-age-population-male-2024.csv",
            "Численность мужского населения",
            "Только мужчины",
        ),
    ]

    # Generate Markdown document
    md_content = ["# ЧИСЛЕННОСТЬ НАСЕЛЕНИЯ РАЙОНОВ ПО ОСНОВНЫМ ВОЗРАСТНЫМ ГРУППАМ\n"]

    for filename, title, gender_label in files:
        file_path = source_dir / filename
        data = read_csv_to_table(file_path)
        table = generate_markdown_table(data, title, gender_label)
        md_content.append(table)
        md_content.append("")  # Empty line between tables

    # Save result
    output_file = output_dir / "working-age-population-2024.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))

    print(f"✓ Report created successfully: {output_file}")


if __name__ == "__main__":
    main()
