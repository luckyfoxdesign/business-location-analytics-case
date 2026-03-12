"""
Script for building population time series by district and MO for 2018-2025.

Creates two files:
- people-by-district-timeline.csv: population by district per year
- people-by-mo-timeline.csv: population by MO per year with district reference
"""

import csv
import re
import unicodedata
from pathlib import Path
from typing import TypedDict


class DistrictRow(TypedDict):
    id: str
    name: str
    people_count: str


class MORow(TypedDict):
    id: str
    name: str
    people_count: str
    district_id: str


def normalize_name(name: str) -> str:
    """
    Normalize a name for accurate matching.

    Handles:
    - Converting to lowercase
    - Removing MO prefixes
    - Normalizing spaces and hyphens
    - Replacing letter variants (ё, ѐ -> е)
    - Unicode normalization
    """
    # Normalize unicode (bring different symbol variants to a single form)
    name = unicodedata.normalize("NFKC", name)

    # Convert to lowercase and strip leading/trailing whitespace
    name = name.strip().lower()

    # Replace all variants of the letter ё with е (for robustness)
    # ё (U+0451), ѐ (U+0450), ё and other variants
    name = name.replace("ё", "е").replace("ѐ", "е").replace("ě", "е")

    # Strip prefixes (order matters!)
    # First "муниципальный округ" (even if merged without space)
    name = re.sub(r"^муниципальный\s*округ\s+", "", name)
    # Then just "округ"
    name = re.sub(r"^округ\s+", "", name)
    # City and settlement
    name = re.sub(r"^г\.\s*", "", name)
    name = re.sub(r"^поселок\s+", "", name)

    # Strip "район" suffix
    name = re.sub(r"\s+район$", "", name)

    # Normalize multiple spaces
    name = re.sub(r"\s{2,}", " ", name)

    # Normalize spaces around hyphens
    name = re.sub(r"\s*-\s*", "-", name)

    # Remove dots and commas
    name = name.replace(".", "").replace(",", "")

    return name.strip()


def is_district_name(name: str) -> bool:
    """
    Check whether a name refers to a district.
    A district is a string that ends with "район" and contains no MO prefixes.
    """
    name_lower = name.lower().strip()

    # It's a district if it contains "район" and no MO prefixes
    has_rayon = "район" in name_lower
    has_mo_prefix = (
        name_lower.startswith("муниципальный округ")
        or name_lower.startswith("муниципальный\xa0округ")  # non-breaking space
        or name_lower.startswith("поселок")
        or name_lower.startswith("г.")
    )

    return has_rayon and not has_mo_prefix


def load_historical_data(year: int) -> tuple[dict[str, int], dict[str, int]]:
    """
    Load population data for the given year.
    Returns two dicts:
    - {normalized_district_name: population}
    - {normalized_MO_name: population}
    """
    file_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "permanent"
        / f"permanent-population-by-municipalities-{year}.csv"
    )

    if not file_path.exists():
        return {}, {}

    districts: dict[str, int] = {}
    mos: dict[str, int] = {}

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("_name") or row.get("name", "")
            total = int(row["total"])
            normalized = normalize_name(name)

            if is_district_name(name):
                districts[normalized] = total
            else:
                mos[normalized] = total

    return districts, mos


def load_districts() -> list[DistrictRow]:
    """Load the district reference table."""
    file_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-district-2025.csv"
    )

    districts: list[DistrictRow] = []

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            districts.append(
                {
                    "id": row["id"],
                    "name": row["name"].strip(),
                    "people_count": row["people_count"],
                }
            )

    return districts


def load_mos() -> list[MORow]:
    """Load the municipal okrug reference table."""
    file_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-mo-2025.csv"
    )

    mos: list[MORow] = []

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mos.append(
                {
                    "id": row["id"].strip(),
                    "name": row[" name"].strip()
                    if " name" in row
                    else row["name"].strip(),
                    "people_count": row[" people_count"].strip()
                    if " people_count" in row
                    else row["people_count"].strip(),
                    "district_id": row[" district_id"].strip()
                    if " district_id" in row
                    else row["district_id"].strip(),
                }
            )

    return mos


def create_name_mapping() -> dict[str, str]:
    """
    Build a mapping for special rename cases and name variations.
    Key - old name (normalized), value - new name (normalized).
    """
    return {
        "парнас": "сергиевское",  # Парнас renamed to Сергиевское (from 2019)
        "черная речка": "ланское",  # Черная речка renamed to Ланское (from 2020)
    }


def get_abolished_mos() -> set[str]:
    """
    Return a set of normalized names of abolished MOs.
    These MOs appeared in historical data but were abolished and must not appear in the timeline.
    """
    return {
        "n 75",  # Abolished after 2022
    }


def build_district_timeline() -> None:
    """Build the population time series file by district."""
    districts = load_districts()
    years = range(2018, 2026)

    # Load data for all years
    historical_data = {}
    for year in years:
        districts_data, _ = load_historical_data(year)
        historical_data[year] = districts_data

    # Build special-case name mapping
    name_mapping = create_name_mapping()

    # Write output
    output_file = (
        Path(__file__).parent.parent
        / "data"
        / "output"
        / "people-by-district-timeline.csv"
    )

    not_found_cases: list[tuple[str, str, list[int]]] = []

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["district_id"] + [str(year) for year in years]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for district in districts:
            row_data = {"district_id": district["id"]}

            normalized_name = normalize_name(district["name"])
            # Apply mapping if applicable
            normalized_name = name_mapping.get(normalized_name, normalized_name)

            missing_years = []
            for year in years:
                year_data = historical_data.get(year, {})
                population = year_data.get(normalized_name)

                if population is not None:
                    row_data[str(year)] = str(population)
                else:
                    row_data[str(year)] = "-"
                    missing_years.append(year)

            if missing_years:
                not_found_cases.append(
                    (district["id"], district["name"], missing_years)
                )

            writer.writerow(row_data)

    print(f"✓ File created: {output_file}")

    if not_found_cases:
        print(f"\n⚠ Districts with missing data:")
        for dist_id, dist_name, years_list in not_found_cases:
            print(f"  - ID {dist_id} ({dist_name}): no data for {years_list}")


def build_mo_timeline() -> None:
    """Build the population time series file by MO."""
    mos = load_mos()
    years = range(2018, 2026)

    # Load data for all years
    historical_data = {}
    for year in years:
        _, mos_data = load_historical_data(year)
        historical_data[year] = mos_data

    # Build special-case name mapping
    name_mapping = create_name_mapping()

    # Write output
    output_file = (
        Path(__file__).parent.parent / "data" / "output" / "people-by-mo-timeline.csv"
    )

    not_found_cases: list[tuple[str, str]] = []

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["mo_id", "district_id"] + [str(year) for year in years]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Build reverse mapping (new -> old) for searching historical data
        reverse_mapping = {v: k for k, v in name_mapping.items()}

        for mo in mos:
            row_data = {"mo_id": mo["id"], "district_id": mo["district_id"]}

            normalized_name = normalize_name(mo["name"])

            found_any = False
            for year in years:
                year_data = historical_data.get(year, {})

                # First look up by current name
                population = year_data.get(normalized_name)

                # If not found and there is an old name (MO was renamed)
                if population is None and normalized_name in reverse_mapping:
                    old_name = reverse_mapping[normalized_name]
                    population = year_data.get(old_name)

                if population is not None:
                    row_data[str(year)] = str(population)
                    found_any = True
                else:
                    row_data[str(year)] = "-"

            if not found_any:
                not_found_cases.append((mo["id"], mo["name"]))

            writer.writerow(row_data)

    print(f"✓ File created: {output_file}")

    if not_found_cases:
        print(f"\n⚠ MOs with no data in any year ({len(not_found_cases)}):")
        for mo_id, mo_name in not_found_cases:
            print(f"  - ID {mo_id}: {mo_name}")


def main() -> None:
    """Main function."""
    print("Building population time series...\n")

    build_district_timeline()
    build_mo_timeline()

    print("\n✓ Done!")


if __name__ == "__main__":
    main()
