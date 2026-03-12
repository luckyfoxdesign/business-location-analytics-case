"""
Validation script for population time series data.

Checks:
1. All districts from the reference people-by-district-2025.csv are present in the timeline
2. All MOs from the reference people-by-mo-2025.csv are present in the timeline
3. All values in the timeline match the source people_okrug_* data
4. No extra districts/MOs in people_okrug that are absent from the reference files
5. Correctness of district_id for MOs
"""

import csv
from pathlib import Path
from typing import TypedDict

from _5_build_people_timeline import is_district_name, normalize_name


class ValidationError(TypedDict):
    year: int
    entity_type: str  # 'district' or 'mo'
    entity_id: str
    entity_name: str
    error_type: str
    details: str


def load_reference_districts() -> dict[str, dict]:
    """Load the reference district table."""
    file_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-district-2025.csv"
    )
    districts = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            districts[row["id"]] = {
                "id": row["id"],
                "name": row["name"].strip(),
                "normalized": normalize_name(row["name"]),
            }

    return districts


def load_reference_mos() -> dict[str, dict]:
    """Load the reference MO table."""
    file_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-mo-2025.csv"
    )
    mos = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mo_id = row["id"].strip()
            mo_name = row[" name"].strip() if " name" in row else row["name"].strip()
            district_id = (
                row[" district_id"].strip()
                if " district_id" in row
                else row["district_id"].strip()
            )

            mos[mo_id] = {
                "id": mo_id,
                "name": mo_name,
                "normalized": normalize_name(mo_name),
                "district_id": district_id,
            }

    return mos


def load_timeline_districts() -> dict[str, dict]:
    """Load district timeline."""
    file_path = (
        Path(__file__).parent.parent
        / "data"
        / "output"
        / "people-by-district-timeline.csv"
    )
    timeline = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            timeline[row["district_id"]] = row

    return timeline


def load_timeline_mos() -> dict[str, dict]:
    """Load MO timeline."""
    file_path = (
        Path(__file__).parent.parent / "data" / "output" / "people-by-mo-timeline.csv"
    )
    timeline = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            timeline[row["mo_id"]] = row

    return timeline


def load_source_data(
    year: int,
) -> tuple[dict[str, int], dict[str, int], list[str], list[str]]:
    """
    Load source data for the given year.
    Returns:
    - dict of districts {normalized_name: population}
    - dict of MOs {normalized_name: population}
    - list of original district names
    - list of original MO names
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
        return {}, {}, [], []

    districts = {}
    mos = {}
    district_names = []
    mo_names = []

    with open(file_path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row.get("_name") or row.get("name", "")
            total = int(row["total"])
            normalized = normalize_name(name)

            if is_district_name(name):
                districts[normalized] = total
                district_names.append(name)
            else:
                mos[normalized] = total
                mo_names.append(name)

    return districts, mos, district_names, mo_names


def validate_districts() -> list[ValidationError]:
    """Validate districts."""
    errors: list[ValidationError] = []

    ref_districts = load_reference_districts()
    timeline_districts = load_timeline_districts()

    # Check 1: All reference districts are present in the timeline
    for dist_id, ref_data in ref_districts.items():
        if dist_id not in timeline_districts:
            errors.append(
                {
                    "year": 0,
                    "entity_type": "district",
                    "entity_id": dist_id,
                    "entity_name": ref_data["name"],
                    "error_type": "MISSING_IN_TIMELINE",
                    "details": "District from reference is missing from timeline",
                }
            )

    # Check 2: Values match across years
    for year in range(2018, 2026):
        source_districts, _, source_dist_names, _ = load_source_data(year)

        # Build reverse mapping for lookup by normalized name
        normalized_to_ref = {v["normalized"]: v for v in ref_districts.values()}

        # Check each reference district
        for dist_id, ref_data in ref_districts.items():
            if dist_id not in timeline_districts:
                continue  # Already flagged above

            timeline_value = timeline_districts[dist_id].get(str(year), "-")
            source_value = source_districts.get(ref_data["normalized"])

            # If the timeline has a value
            if timeline_value != "-":
                if source_value is None:
                    errors.append(
                        {
                            "year": year,
                            "entity_type": "district",
                            "entity_id": dist_id,
                            "entity_name": ref_data["name"],
                            "error_type": "VALUE_WITHOUT_SOURCE",
                            "details": f"timeline={timeline_value}, but NOT in source data",
                        }
                    )
                elif str(source_value) != timeline_value:
                    errors.append(
                        {
                            "year": year,
                            "entity_type": "district",
                            "entity_id": dist_id,
                            "entity_name": ref_data["name"],
                            "error_type": "VALUE_MISMATCH",
                            "details": f"timeline={timeline_value}, source={source_value}",
                        }
                    )
            # If the timeline has a gap
            else:
                if source_value is not None:
                    errors.append(
                        {
                            "year": year,
                            "entity_type": "district",
                            "entity_id": dist_id,
                            "entity_name": ref_data["name"],
                            "error_type": "MISSING_VALUE",
                            "details": f"GAP in timeline, but source data={source_value}",
                        }
                    )

        # Check 3: No extra districts in source that are absent from reference
        for source_name in source_dist_names:
            normalized = normalize_name(source_name)
            if normalized not in normalized_to_ref:
                errors.append(
                    {
                        "year": year,
                        "entity_type": "district",
                        "entity_id": "?",
                        "entity_name": source_name,
                        "error_type": "NOT_IN_REFERENCE",
                        "details": f"District in source data but NOT in reference (normalized: '{normalized}')",
                    }
                )

    return errors


def validate_mos() -> list[ValidationError]:
    """Validate MOs."""
    errors: list[ValidationError] = []

    ref_mos = load_reference_mos()
    timeline_mos = load_timeline_mos()

    # Load rename mapping and list of abolished MOs
    from _5_build_people_timeline import create_name_mapping, get_abolished_mos

    name_mapping = create_name_mapping()
    reverse_mapping = {v: k for k, v in name_mapping.items()}
    abolished_mos = get_abolished_mos()

    # Check 1: All reference MOs are present in the timeline
    for mo_id, ref_data in ref_mos.items():
        if mo_id not in timeline_mos:
            errors.append(
                {
                    "year": 0,
                    "entity_type": "mo",
                    "entity_id": mo_id,
                    "entity_name": ref_data["name"],
                    "error_type": "MISSING_IN_TIMELINE",
                    "details": "MO from reference is missing from timeline",
                }
            )
        else:
            # Check district_id
            if timeline_mos[mo_id]["district_id"] != ref_data["district_id"]:
                errors.append(
                    {
                        "year": 0,
                        "entity_type": "mo",
                        "entity_id": mo_id,
                        "entity_name": ref_data["name"],
                        "error_type": "WRONG_DISTRICT_ID",
                        "details": f"district_id in timeline={timeline_mos[mo_id]['district_id']}, in reference={ref_data['district_id']}",
                    }
                )

    # Check 2: Values match across years
    for year in range(2018, 2026):
        _, source_mos, _, source_mo_names = load_source_data(year)

        # Build reverse mapping
        normalized_to_ref = {v["normalized"]: v for v in ref_mos.values()}

        # Check each reference MO
        for mo_id, ref_data in ref_mos.items():
            if mo_id not in timeline_mos:
                continue  # Already flagged above

            timeline_value = timeline_mos[mo_id].get(str(year), "-")

            # Look up in source by current name
            source_value = source_mos.get(ref_data["normalized"])

            # If not found, check old name (for renamed MOs)
            if source_value is None and ref_data["normalized"] in reverse_mapping:
                old_name = reverse_mapping[ref_data["normalized"]]
                source_value = source_mos.get(old_name)

            # If the timeline has a value
            if timeline_value != "-":
                if source_value is None:
                    errors.append(
                        {
                            "year": year,
                            "entity_type": "mo",
                            "entity_id": mo_id,
                            "entity_name": ref_data["name"],
                            "error_type": "VALUE_WITHOUT_SOURCE",
                            "details": f"timeline={timeline_value}, but NOT in source data",
                        }
                    )
                elif str(source_value) != timeline_value:
                    errors.append(
                        {
                            "year": year,
                            "entity_type": "mo",
                            "entity_id": mo_id,
                            "entity_name": ref_data["name"],
                            "error_type": "VALUE_MISMATCH",
                            "details": f"timeline={timeline_value}, source={source_value}",
                        }
                    )
            # If the timeline has a gap
            else:
                if source_value is not None:
                    errors.append(
                        {
                            "year": year,
                            "entity_type": "mo",
                            "entity_id": mo_id,
                            "entity_name": ref_data["name"],
                            "error_type": "MISSING_VALUE",
                            "details": f"GAP in timeline, but source data={source_value}",
                        }
                    )

        # Check 3: No extra MOs in source that are absent from reference
        # (excluding known historical names and abolished MOs)
        for source_name in source_mo_names:
            normalized = normalize_name(source_name)

            # Check: MO not in reference AND not a known historical name AND not abolished
            is_in_reference = normalized in normalized_to_ref
            is_known_historical = (
                normalized in name_mapping
            )  # This is an old name from the mapping
            is_abolished = normalized in abolished_mos  # This is an abolished MO

            if not is_in_reference and not is_known_historical and not is_abolished:
                errors.append(
                    {
                        "year": year,
                        "entity_type": "mo",
                        "entity_id": "?",
                        "entity_name": source_name,
                        "error_type": "NOT_IN_REFERENCE",
                        "details": f"MO in source data but NOT in reference (normalized: '{normalized}')",
                    }
                )

    return errors


def print_report(
    district_errors: list[ValidationError], mo_errors: list[ValidationError]
) -> None:
    """Print the validation report."""
    print("=" * 100)
    print("POPULATION TIME SERIES VALIDATION REPORT")
    print("=" * 100)

    # Group errors by type
    error_types = {}
    for error in district_errors + mo_errors:
        error_type = error["error_type"]
        if error_type not in error_types:
            error_types[error_type] = []
        error_types[error_type].append(error)

    total_errors = len(district_errors) + len(mo_errors)

    if total_errors == 0:
        print("\n✅ VALIDATION PASSED SUCCESSFULLY!")
        print("\n   All data matches the reference and source files.")
        print("=" * 100)
        return

    print(f"\n❌ ERRORS FOUND: {total_errors}\n")

    # Print by type
    for error_type, errors in sorted(error_types.items()):
        print(f"\n{'─' * 100}")
        print(f"Error type: {error_type} ({len(errors)} items)")
        print(f"{'─' * 100}\n")

        for err in errors[:20]:  # Show first 20
            entity_label = "District" if err["entity_type"] == "district" else "MO"
            year_label = f"{err['year']}: " if err["year"] > 0 else ""

            print(
                f"  {year_label}{entity_label} ID {err['entity_id']} ({err['entity_name']})"
            )
            print(f"       → {err['details']}")

        if len(errors) > 20:
            print(f"\n  ... and {len(errors) - 20} more errors of this type")

    print("\n" + "=" * 100)
    print(
        f"TOTAL: {len(district_errors)} district errors, {len(mo_errors)} MO errors"
    )
    print("=" * 100)


def main() -> None:
    """Main function."""
    print("\nStarting validation...\n")

    print("Checking districts...")
    district_errors = validate_districts()

    print("Checking MOs...")
    mo_errors = validate_mos()

    print_report(district_errors, mo_errors)

    # Return error code if issues found
    if district_errors or mo_errors:
        exit(1)
    else:
        exit(0)


if __name__ == "__main__":
    main()
