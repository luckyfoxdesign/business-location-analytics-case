"""Calculate workshop density by district and municipal okrug - generate MD report."""

import sys
from pathlib import Path
from typing import Dict, Tuple

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from geo_utils import clean_okrug_name


def load_org_assignments() -> pd.DataFrame:
    """Load organization-to-district/MO assignments."""
    csv_path = (
        Path(__file__).parent.parent.parent
        / "data"
        / "output"
        / "organisations-by-district-and-mo.csv"
    )
    df = pd.read_csv(csv_path)
    return df[df["is_work"] == 1].copy()


def load_population_by_mo() -> Dict[str, int]:
    """Load population by MO from clean data."""
    csv_path = (
        Path(__file__).parent.parent.parent
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
        Path(__file__).parent.parent.parent
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
        Path(__file__).parent.parent.parent
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
        Path(__file__).parent.parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-mo-2025.csv"
    )
    district_path = (
        Path(__file__).parent.parent.parent
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


def generate_density_report(
    district_stats: pd.DataFrame, mo_stats: pd.DataFrame
) -> str:
    """Generate Markdown report."""

    md = "# Плотность мастерских по районам и муниципальным округам\n\n"

    # Overall statistics
    total_pop = district_stats["population"].sum()
    total_workshops = district_stats["workshops"].sum()
    avg_density = total_pop / total_workshops if total_workshops > 0 else 0
    avg_salary = district_stats["avg_salary"].mean()

    md += "## Общая статистика\n\n"
    md += f"- **Население:** {total_pop:,} чел.\n".replace(",", " ")
    md += f"- **Мастерских:** {total_workshops}\n"
    md += f"- **Средняя плотность:** {avg_density:,.0f} чел./мастерская\n".replace(
        ",", " "
    )
    md += f"- **Средняя зарплата:** {avg_salary:,.0f} ₽\n\n".replace(",", " ")

    # Statistics by district
    md += "## Плотность по районам\n\n"
    md += "| Район | Население | Мастерских | Человек на мастерскую | Средняя зарплата |\n"
    md += (
        "|-------|----------:|-----------:|---------------------:|-----------------:|\n"
    )

    # Sort districts by population descending
    district_stats_sorted = district_stats.sort_values("population", ascending=False)

    for _, row in district_stats_sorted.iterrows():
        if row["district"] == "Не определён":
            continue
        salary_str = (
            f"{row['avg_salary']:,.0f} ₽" if pd.notna(row["avg_salary"]) else "—"
        )
        # If no workshops, show a dash
        if row["workshops"] == 0 or pd.isna(row["people_per_workshop"]):
            density_str = "—"
        else:
            density_str = f"{row['people_per_workshop']:,.0f}".replace(",", " ")

        md += (
            f"| {row['district']} | {row['population']:,} | {row['workshops']} | "
            f"{density_str} | {salary_str} |\n"
        ).replace(",", " ")

    # MO statistics grouped by district
    md += "\n## Плотность по муниципальным округам\n\n"
    md += "| Муниципальный округ | Население | Мастерских | Человек на мастерскую |\n"
    md += "|---------------------|----------:|-----------:|---------------------:|\n"

    # Sort MOs first by district, then by population descending
    mo_stats_sorted = mo_stats.sort_values(
        ["district", "population"], ascending=[True, False]
    )

    current_district = None
    for _, row in mo_stats_sorted.iterrows():
        if row["district"] == "Не определён":
            continue

        # Add district separator row
        if row["district"] != current_district:
            current_district = row["district"]
            md += f"| **{current_district}** | | | |\n"

        # If no workshops, show a dash
        if row["workshops"] == 0 or pd.isna(row["people_per_workshop"]):
            density_str = "—"
        else:
            density_str = f"{row['people_per_workshop']:,.0f}".replace(",", " ")

        md += (
            f"| {row['mo']} | {row['population']:,} | {row['workshops']} | "
            f"{density_str} |\n"
        ).replace(",", " ")

    return md


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

    print("Generating report...")
    report = generate_density_report(district_stats, mo_stats)

    output_path = (
        Path(__file__).parent.parent.parent
        / "data"
        / "report-md"
        / "workshop-density-statistics.md"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ Report saved: {output_path}")


if __name__ == "__main__":
    main()
