"""Calculate workshop density by district and municipal okrug - export to CSV."""

import sys
from pathlib import Path
from typing import Dict, Tuple

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from geo_utils import clean_okrug_name


def load_org_assignments() -> pd.DataFrame:
    """Load organization-to-district/MO assignments."""
    csv_path = (
        Path(__file__).parent.parent
        / "data"
        / "output"
        / "organisations-by-district-and-mo.csv"
    )
    df = pd.read_csv(csv_path)
    return df[df["is_work"] == 1].copy()


def load_population_by_mo() -> Dict[str, int]:
    """Load population by MO from clean data."""
    csv_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-mo-2025.csv"
    )
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    return {
        clean_okrug_name(str(row["name"])): int(row["people_count"])
        for _, row in df.iterrows()
    }


def load_population_by_district() -> Dict[str, int]:
    """Load population by district from clean data."""
    csv_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-district-2025.csv"
    )
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    return {
        str(row["name"]).strip(): int(row["people_count"]) for _, row in df.iterrows()
    }


def load_salary_by_district() -> Dict[str, float]:
    """Load average salaries by district."""
    csv_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "salary"
        / "average_salary_by_district.csv"
    )
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    name_col = df.columns[0]
    salary_col = next(
        (c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])), df.columns[1]
    )
    return {
        str(row[name_col]).strip(): float(row[salary_col]) for _, row in df.iterrows()
    }


def load_mo_to_district() -> Dict[str, str]:
    """Load MO -> district mapping using district_id from clean data."""
    mo_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-mo-2025.csv"
    )
    district_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-district-2025.csv"
    )

    df_mo = pd.read_csv(mo_path)
    df_district = pd.read_csv(district_path)

    df_mo.columns = df_mo.columns.str.strip()
    df_district.columns = df_district.columns.str.strip()

    # Build district_id -> district_name mapping
    district_map = {
        int(row["id"]): str(row["name"]).strip() for _, row in df_district.iterrows()
    }

    # Build MO -> district mapping via district_id
    mapping = {}
    for _, row in df_mo.iterrows():
        mo_name = clean_okrug_name(str(row["name"]))
        district_id = int(row["district_id"])
        district_name = district_map.get(district_id, "Не определён")
        mapping[mo_name] = district_name

    return mapping


def calculate_district_stats(
    orgs: pd.DataFrame,
    pop_by_mo: Dict[str, int],
    pop_by_district: Dict[str, int],
    mo_to_district: Dict[str, str],
    salary_by_district: Dict[str, float],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate statistics by district and MO."""

    # Count workshops per MO from organizations
    mo_org_counts = {}
    for _, row in orgs.iterrows():
        mo_clean = clean_okrug_name(row["mo_name"])
        mo_org_counts[mo_clean] = mo_org_counts.get(mo_clean, 0) + 1

    # MO statistics - include ALL MOs from clean data
    mo_stats = []
    for mo_name_clean, population in pop_by_mo.items():
        district = mo_to_district.get(mo_name_clean, "Не определён")
        count = mo_org_counts.get(mo_name_clean, 0)

        # If no workshops, use None (NULL in BI)
        density = population / count if count > 0 else None
        mo_stats.append(
            {
                "district": district,
                "mo": mo_name_clean,
                "population": population,
                "workshops": count,
                "people_per_workshop": density,
            }
        )

    df_mo = pd.DataFrame(mo_stats)

    # Count workshops per district
    district_org_counts = {}
    for _, row in orgs.iterrows():
        district = row["district_name"]
        district_org_counts[district] = district_org_counts.get(district, 0) + 1

    # District statistics - include ALL districts from clean data
    district_stats = []
    for district_name, population in pop_by_district.items():
        workshops = district_org_counts.get(district_name, 0)
        # If no workshops, use None (NULL in BI)
        people_per_workshop = population / workshops if workshops > 0 else None
        avg_salary = salary_by_district.get(district_name, None)

        district_stats.append(
            {
                "district": district_name,
                "population": population,
                "workshops": workshops,
                "people_per_workshop": people_per_workshop,
                "avg_salary": avg_salary,
            }
        )

    district_agg = pd.DataFrame(district_stats)

    return district_agg, df_mo


def export_to_csv(district_stats: pd.DataFrame, mo_stats: pd.DataFrame):
    """Export statistics to CSV files using IDs."""

    # Load files with IDs
    mo_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-mo-2025.csv"
    )
    district_path = (
        Path(__file__).parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-district-2025.csv"
    )

    df_mo_ids = pd.read_csv(mo_path)
    df_district_ids = pd.read_csv(district_path)

    df_mo_ids.columns = df_mo_ids.columns.str.strip()
    df_district_ids.columns = df_district_ids.columns.str.strip()

    # Build name -> id mapping for districts
    district_name_to_id = {
        str(row["name"]).strip(): int(row["id"])
        for _, row in df_district_ids.iterrows()
    }

    # Build clean name -> id mapping for MOs
    mo_name_to_id = {}
    for _, row in df_mo_ids.iterrows():
        clean_name = clean_okrug_name(str(row["name"]))
        mo_name_to_id[clean_name] = int(row["id"])

    # Export district statistics
    district_export = []
    for _, row in district_stats.iterrows():
        district_id = district_name_to_id.get(row["district"])
        if district_id is not None:
            district_export.append(
                {
                    "district_id": district_id,
                    "population": int(row["population"]),
                    "workshops": int(row["workshops"]),
                    "people_per_workshop": row["people_per_workshop"]
                    if pd.notna(row["people_per_workshop"])
                    else None,
                    "avg_salary": row["avg_salary"]
                    if pd.notna(row["avg_salary"])
                    else None,
                }
            )

    df_district_export = pd.DataFrame(district_export)
    district_csv_path = (
        Path(__file__).parent.parent / "data" / "output" / "district_density_stats.csv"
    )
    df_district_export.to_csv(district_csv_path, index=False, encoding="utf-8")
    print(f"✅ District CSV: {district_csv_path}")

    # Export MO statistics
    mo_export = []
    for _, row in mo_stats.iterrows():
        mo_id = mo_name_to_id.get(row["mo"])
        if mo_id is not None:
            mo_export.append(
                {
                    "mo_id": mo_id,
                    "district_id": district_name_to_id.get(row["district"]),
                    "population": int(row["population"]),
                    "workshops": int(row["workshops"]),
                    "people_per_workshop": row["people_per_workshop"]
                    if pd.notna(row["people_per_workshop"])
                    else None,
                }
            )

    df_mo_export = pd.DataFrame(mo_export)
    mo_csv_path = (
        Path(__file__).parent.parent / "data" / "output" / "mo_density_stats.csv"
    )
    df_mo_export.to_csv(mo_csv_path, index=False, encoding="utf-8")
    print(f"✅ MO CSV: {mo_csv_path}")


def main():
    """Main function."""
    print("Loading data...")
    orgs = load_org_assignments()
    pop_by_mo = load_population_by_mo()
    pop_by_district = load_population_by_district()
    mo_to_district = load_mo_to_district()
    salary_by_district = load_salary_by_district()

    print("Calculating statistics...")
    district_stats, mo_stats = calculate_district_stats(
        orgs, pop_by_mo, pop_by_district, mo_to_district, salary_by_district
    )

    print("Exporting to CSV...")
    export_to_csv(district_stats, mo_stats)


if __name__ == "__main__":
    main()
