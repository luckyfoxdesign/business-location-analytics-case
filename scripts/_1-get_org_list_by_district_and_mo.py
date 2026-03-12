"""Determine the district and municipal okrug (MO) for each organization based on coordinates."""

import json
import sys
from pathlib import Path

# Add parent directory to path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import geopandas as gpd
import pandas as pd
from geo_utils import clean_okrug_name
from shapely.geometry import Point


def load_organizations():
    """Load organizations from the CSV file."""
    data_dir = Path(__file__).parent.parent / "data" / "source" / "other"

    df_orgs = pd.read_csv(data_dir / "organizations_normalized.csv")

    # Filter active (is_work = 1) and closed (is_work = 0) organizations
    df_active = df_orgs[df_orgs["is_work"] == 1].copy()
    df_closed = df_orgs[df_orgs["is_work"] == 0].copy()

    return df_active, df_closed


def load_geojson():
    """Load GeoJSON with MO boundaries."""
    geojson_path = (
        Path(__file__).parent.parent / "data" / "source" / "other" / "spb.geojson"
    )

    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {geojson_path}")

    with open(geojson_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_mo_to_district_mapping():
    """Load MO -> district mapping from clean data."""
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
        if pd.notna(row["district_id"]):
            district_id = int(row["district_id"])
            district_name = district_map.get(district_id, "Не определён")
            mapping[mo_name] = district_name

    return mapping


def assign_districts_and_mo() -> pd.DataFrame:
    """Determine the district and MO for each organization."""

    print("Loading organizations...")
    df_active, df_closed = load_organizations()
    df_orgs = pd.concat([df_active, df_closed], ignore_index=True)
    print(f"Total organizations: {len(df_orgs)}")

    print("Loading GeoJSON with MO boundaries...")
    geojson_data = load_geojson()

    print("Loading MO -> district mapping...")
    mo_to_district = load_mo_to_district_mapping()

    print("Assigning MO by coordinates...")

    # Preserve important columns before join
    df_orgs["org_original_id"] = df_orgs.get("id", range(len(df_orgs)))
    df_orgs["org_is_work"] = df_orgs["is_work"]

    geometry = [Point(lon, lat) for lat, lon in zip(df_orgs["lat"], df_orgs["lon"])]
    gdf_orgs = gpd.GeoDataFrame(df_orgs, geometry=geometry, crs="EPSG:4326")

    gdf_mo = gpd.GeoDataFrame.from_features(geojson_data["features"], crs="EPSG:4326")
    gdf_mo["mo_name"] = gdf_mo.apply(
        lambda row: row.get("district")
        or row.get("NAME")
        or row.get("name")
        or "Неизвестно",
        axis=1,
    )

    result = gpd.sjoin(
        gdf_orgs, gdf_mo[["mo_name", "geometry"]], how="left", predicate="within"
    )
    result["mo"] = result["mo_name"].fillna("Не определён")

    print("Assigning districts...")

    # Mapping of old MO names to new ones (renames)
    old_to_new_names = {
        "парнас": "сергиевское",
    }

    def normalize_name(name):
        """Normalize name: replace ё with е for comparison."""
        return name.replace("ё", "е").replace("Ё", "Е")

    def find_district(mo_name):
        if pd.isna(mo_name) or mo_name == "Не определён":
            return "Не определён"

        clean_mo = clean_okrug_name(mo_name)
        clean_mo_normalized = normalize_name(clean_mo)

        # Check if this is an old name
        if clean_mo_normalized in old_to_new_names:
            clean_mo_normalized = old_to_new_names[clean_mo_normalized]

        # Use mapping from clean data
        if clean_mo in mo_to_district:
            return mo_to_district[clean_mo]

        # Try matching with ё -> е normalization
        for key, district in mo_to_district.items():
            key_normalized = normalize_name(key)
            if clean_mo_normalized == key_normalized:
                return district

        # Try partial match
        for key, district in mo_to_district.items():
            key_normalized = normalize_name(key)
            if (
                key_normalized in clean_mo_normalized
                or clean_mo_normalized in key_normalized
            ):
                return district

        return "Не определён"

    result["district"] = result["mo"].apply(find_district)

    # Load data to get IDs
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

    # Build name -> id and id -> name mappings
    district_name_to_id = {}
    district_id_to_name = {}
    for _, row in df_district_ids.iterrows():
        name = str(row["name"]).strip()
        id_val = int(row["id"])
        district_name_to_id[name] = id_val
        district_id_to_name[id_val] = name

    mo_name_to_id = {}
    mo_id_to_name = {}
    for _, row in df_mo_ids.iterrows():
        clean_name = clean_okrug_name(str(row["name"]))
        original_name = str(row["name"]).strip()
        id_val = int(row["id"])
        mo_name_to_id[clean_name] = id_val
        mo_id_to_name[id_val] = original_name

    # Function to look up district ID and name
    def get_district_info(district_name):
        if district_name == "Не определён":
            return None, None
        district_id = district_name_to_id.get(district_name)
        if district_id:
            return district_id, district_id_to_name[district_id]
        return None, None

    # Function to look up MO ID and name
    def get_mo_info(mo_name):
        if mo_name == "Не определён":
            return None, None
        clean_mo = normalize_name(clean_okrug_name(mo_name))

        # Strip additional prefixes not handled by clean_okrug_name
        clean_mo = clean_mo.replace("поселок ", "").replace("округ ", "").strip()

        # Check old names
        if clean_mo in old_to_new_names:
            clean_mo = old_to_new_names[clean_mo]

        mo_id = mo_name_to_id.get(clean_mo)
        if mo_id:
            return mo_id, mo_id_to_name[mo_id]
        return None, None

    # Apply functions to get IDs and names
    district_info = result["district"].apply(get_district_info)
    mo_info = result["mo"].apply(get_mo_info)

    output = pd.DataFrame(
        {
            "org_id": result["org_original_id"],
            "district_id": [info[0] for info in district_info],
            "mo_id": [info[0] for info in mo_info],
            "district_name": [
                info[1] if info[1] else "Не определён" for info in district_info
            ],
            "mo_name": [info[1] if info[1] else "Не определён" for info in mo_info],
            "is_work": result["org_is_work"],
        }
    )

    return output


def main():
    result_df = assign_districts_and_mo()

    output_dir = Path(__file__).parent.parent / "data" / "output"

    # Combined file
    output_path = output_dir / "organisations-by-district-and-mo.csv"
    result_df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\n✅ Combined file saved: {output_path}")

    # Additional: file with districts only (drop MO columns)
    districts_df = result_df[
        ["org_id", "district_id", "district_name", "is_work"]
    ].copy()
    districts_output = output_dir / "organisations-by-district.csv"
    districts_df.to_csv(districts_output, index=False, encoding="utf-8")
    print(f"✅ District file saved: {districts_output}")

    # Additional: file with MOs only (drop district columns)
    mo_df = result_df[["org_id", "mo_id", "mo_name", "is_work"]].copy()
    mo_output = output_dir / "organisations-by-mo.csv"
    mo_df.to_csv(mo_output, index=False, encoding="utf-8")
    print(f"✅ MO file saved: {mo_output}")

    print(f"\n📊 Statistics:")
    print(f"   - Total organizations: {len(result_df)}")
    print(f"   - Active (is_work=1): {(result_df['is_work'] == 1).sum()}")
    print(f"   - Closed (is_work=0): {(result_df['is_work'] == 0).sum()}")
    print(
        f"   - With assigned district (district_id): {result_df['district_id'].notna().sum()}"
    )
    print(f"   - With assigned MO (mo_id): {result_df['mo_id'].notna().sum()}")

    # Check for mismatches
    has_mo_no_district = result_df[
        result_df["mo_id"].notna() & result_df["district_id"].isna()
    ]
    if len(has_mo_no_district) > 0:
        print(f"\n⚠️  MOs without district ({len(has_mo_no_district)} organizations):")
        unique_mo = has_mo_no_district["mo_name"].unique()
        for mo in unique_mo[:10]:  # Show first 10
            count = (has_mo_no_district["mo_name"] == mo).sum()
            print(f"   - {mo}: {count} org.")


if __name__ == "__main__":
    main()
