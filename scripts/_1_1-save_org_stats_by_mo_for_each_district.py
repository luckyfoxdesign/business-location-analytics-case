"""Save organization statistics by MO for each district into separate CSV files."""

import sys
from pathlib import Path

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd


def load_organizations_data():
    """Load organization data with district and MO assignments."""
    input_path = (
        Path(__file__).parent.parent
        / "data"
        / "output"
        / "organisations-by-district-and-mo.csv"
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"File not found: {input_path}\n"
            "Run _1-get_org_list_by_district_and_mo.py first"
        )

    df = pd.read_csv(input_path)
    return df


def create_stats_by_mo_for_districts(df):
    """Build MO-level statistics for each district."""

    # Keep only rows with valid district_id and mo_id
    df_valid = df[df["district_id"].notna() & df["mo_id"].notna()].copy()

    # Group by district
    districts = df_valid.groupby(["district_id", "district_name"])

    stats_by_district = {}

    for (district_id, district_name), district_data in districts:
        # Group by MO within the district
        mo_stats = (
            district_data.groupby(["mo_id", "mo_name"])
            .agg(
                total_orgs=("org_id", "count"),
                working_orgs=("is_work", lambda x: (x == 1).sum()),
                closed_orgs=("is_work", lambda x: (x == 0).sum()),
            )
            .reset_index()
        )

        # Sort by number of organizations
        mo_stats = mo_stats.sort_values("total_orgs", ascending=False)

        stats_by_district[district_name] = {
            "district_id": int(district_id),
            "stats": mo_stats,
        }

    return stats_by_district


def save_stats_to_csv(stats_by_district):
    """Save statistics to separate CSV files for each district."""

    output_dir = Path(__file__).parent.parent / "data" / "output" / "mo"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📁 Saving MO statistics for each district to {output_dir}")
    print("=" * 80)

    for district_name, data in stats_by_district.items():
        district_id = data["district_id"]
        stats_df = data["stats"]

        # Build filename
        safe_name = district_name.lower().replace(" ", "_").replace("-", "_")
        filename = f"{district_id:02d}_{safe_name}.csv"
        output_path = output_dir / filename

        # Save CSV
        stats_df.to_csv(output_path, index=False, encoding="utf-8")

        # Print statistics
        total_mo = len(stats_df)
        total_orgs = stats_df["total_orgs"].sum()
        working_orgs = stats_df["working_orgs"].sum()
        closed_orgs = stats_df["closed_orgs"].sum()

        print(f"\n✅ {district_name}")
        print(f"   File: {filename}")
        print(f"   MOs in district: {total_mo}")
        print(f"   Total organizations: {total_orgs}")
        print(f"   Active: {working_orgs}")
        print(f"   Closed: {closed_orgs}")


def main():
    print("Loading organization data...")
    df = load_organizations_data()

    print(f"Total records: {len(df)}")
    print(f"With assigned district: {df['district_id'].notna().sum()}")
    print(f"With assigned MO: {df['mo_id'].notna().sum()}")

    print("\nBuilding MO statistics for each district...")
    stats_by_district = create_stats_by_mo_for_districts(df)

    print(f"Districts found: {len(stats_by_district)}")

    save_stats_to_csv(stats_by_district)

    print("\n" + "=" * 80)
    print("✅ Done! All files saved.")


if __name__ == "__main__":
    main()
