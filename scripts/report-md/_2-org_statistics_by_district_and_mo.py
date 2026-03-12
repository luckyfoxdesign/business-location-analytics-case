"""Generate organization statistics report."""

import sys
from pathlib import Path

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd


def generate_statistics() -> str:
    """Generate statistics in Markdown format."""

    csv_path = (
        Path(__file__).parent.parent.parent
        / "data"
        / "output"
        / "organisations-by-district-and-mo.csv"
    )
    df = pd.read_csv(csv_path)

    df["status"] = df["is_work"].apply(
        lambda x: "Работает" if x == 1 else "Закрыта"
    )

    md = "# Статистика организаций по районам и муниципальным округам\n\n"

    # Overall statistics
    total = len(df)
    working = (df["is_work"] == 1).sum()
    closed = (df["is_work"] == 0).sum()

    md += "## Общая статистика\n\n"
    md += f"- **Всего организаций:** {total}\n"
    md += f"- **Работающих:** {working} ({working / total * 100:.1f}%)\n"
    md += f"- **Закрытых:** {closed} ({closed / total * 100:.1f}%)\n\n"

    # Load the full district list
    districts_path = (
        Path(__file__).parent.parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-district-2025.csv"
    )
    df_districts = pd.read_csv(districts_path)
    df_districts.columns = df_districts.columns.str.strip()
    all_districts = df_districts["name"].tolist()

    # Statistics by district
    md += "## Статистика по районам\n\n"
    md += "| Район | Всего | % | Работающих | % | Закрытых | % |\n"
    md += "|-------|------:|--:|-----------:|--:|---------:|--:|\n"

    district_stats = df.groupby("district_name").agg(
        total=("org_id", "count"),
        working=("is_work", lambda x: (x == 1).sum()),
        closed=("is_work", lambda x: (x == 0).sum()),
    )

    # Sort districts by organization count, then alphabetically
    district_stats = district_stats.sort_values("total", ascending=False)

    # Add districts with data
    for district, row in district_stats.iterrows():
        t = row["total"]
        w = row["working"]
        c = row["closed"]
        md += f"| {district} | {t} | {t / total * 100:.1f}% | {w} | {w / t * 100:.1f}% | {c} | {c / t * 100:.1f}% |\n"

    # Add districts without data
    districts_with_data = set(district_stats.index)
    districts_without_data = sorted(
        [d for d in all_districts if d not in districts_with_data]
    )
    for district in districts_without_data:
        md += f"| {district} | — | — | — | — | — | — |\n"

    # Load the full MO list with district info
    mo_path = (
        Path(__file__).parent.parent.parent
        / "data"
        / "source"
        / "rosstat"
        / "population"
        / "people-by-mo-2025.csv"
    )
    df_mo_full = pd.read_csv(mo_path)
    df_mo_full.columns = df_mo_full.columns.str.strip()

    # Build MO -> district mapping
    mo_to_district = {}
    for _, row in df_mo_full.iterrows():
        mo_name = row["name"]
        district_id = int(row["district_id"])
        district_name = df_districts[df_districts["id"] == district_id]["name"].values
        if len(district_name) > 0:
            mo_to_district[mo_name] = district_name[0]

    # MO statistics grouped by district
    md += "\n## Статистика по муниципальным округам\n\n"
    md += "| Муниципальный округ | Всего | % | Работающих | % | Закрытых | % |\n"
    md += "|---------------------|------:|--:|-----------:|--:|---------:|--:|\n"

    # Group by MO and district
    mo_stats = (
        df.groupby(["district_name", "mo_name"])
        .agg(
            total=("org_id", "count"),
            working=("is_work", lambda x: (x == 1).sum()),
            closed=("is_work", lambda x: (x == 0).sum()),
        )
        .reset_index()
    )

    # Build dict of MOs with data, grouped by district
    mo_with_data_by_district = {}
    for _, row in mo_stats.iterrows():
        district = row["district_name"]
        if district not in mo_with_data_by_district:
            mo_with_data_by_district[district] = []
        mo_with_data_by_district[district].append(
            {
                "mo_name": row["mo_name"],
                "total": row["total"],
                "working": row["working"],
                "closed": row["closed"],
            }
        )

    # Build dict of MOs without data, grouped by district
    mo_with_data_names = set(mo_stats["mo_name"])
    mo_without_data_by_district = {}
    for mo_name in df_mo_full["name"]:
        if mo_name not in mo_with_data_names:
            district = mo_to_district.get(mo_name, "Не определён")
            if district not in mo_without_data_by_district:
                mo_without_data_by_district[district] = []
            mo_without_data_by_district[district].append(mo_name)

    # Collect all unique districts and sort alphabetically
    all_districts_in_mo = set(mo_with_data_by_district.keys()) | set(
        mo_without_data_by_district.keys()
    )

    # Iterate over all districts alphabetically
    for district in sorted(all_districts_in_mo):
        # Add district header row
        md += f"| **{district}** | | | | | | |\n"

        # Add MOs with data, sorted by count descending
        if district in mo_with_data_by_district:
            mo_list = mo_with_data_by_district[district]
            mo_list_sorted = sorted(mo_list, key=lambda x: x["total"], reverse=True)
            for mo_data in mo_list_sorted:
                t = mo_data["total"]
                w = mo_data["working"]
                c = mo_data["closed"]
                md += f"| {mo_data['mo_name']} | {t} | {t / total * 100:.1f}% | {w} | {w / t * 100:.1f}% | {c} | {c / t * 100:.1f}% |\n"

        # Add MOs without data, sorted alphabetically
        if district in mo_without_data_by_district:
            for mo in sorted(mo_without_data_by_district[district]):
                md += f"| {mo} | — | — | — | — | — | — |\n"

    return md


def main():
    md_content = generate_statistics()

    output_path = (
        Path(__file__).parent.parent.parent
        / "data"
        / "report-md"
        / "organisations-statistics.md"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"✅ Statistics saved: {output_path}")


if __name__ == "__main__":
    main()
