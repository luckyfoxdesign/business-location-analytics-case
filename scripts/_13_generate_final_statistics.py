#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scoring of districts and municipal okrugs (MOs) for selecting a jewelry workshop location.
Two-stage model (variant A):

Stage 1: district scoring (district-level indicators only).
Stage 2: ranking MOs within selected districts (MO-level, not involved in district scoring).

Outputs:
- data/output/scoring_districts.csv
- data/output/scoring_mos.csv
- data/output/scoring_report.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ─── Paths ───────────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent.parent))
DATA_DIR = Path(__file__).parent.parent / "data"


# ─── Criteria configuration (variant A) ──────────────────────────────────────

PLANNED_WEIGHTS = {
    "1.1": 20,
    "1.2": 5,
    "2.1": 15,
    "2.2": 5,
    "2.3": 10,
    "3.1": 10,
    "4.3": 5,
}
PLANNED_TOTAL_WEIGHT = sum(PLANNED_WEIGHTS.values())  # 70

# Years for formulas
BASE_POP_YEAR_FOR_FEMALE_SHARE = 2024
GROWTH_FROM_YEAR = 2018
GROWTH_TO_YEAR = 2025

# Age cohorts for target audience (30–64 inclusive, in 5-year bins)
TARGET_AGE_BINS = ["30–34", "35–39", "40–44", "45–49", "50–54", "55–59", "60–64"]

# Criteria -> score column mapping
SCORE_COLUMNS = {
    "1.1": "score_1_1",
    "1.2": "score_1_2",
    "2.1": "score_2_1",
    "2.2": "score_2_2",
    "2.3": "score_2_3",
    "3.1": "score_3_1",
    "4.3": "score_4_3",
}


# ─── Utilities ────────────────────────────────────────────────────────────────

def normalize_district_name(name) -> str:
    """Remove the word 'район' and extra spaces to join with age-structure CSV."""
    if pd.isna(name):
        return ""
    s = str(name).strip().replace("район", "").strip()
    return " ".join(s.split())


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_data() -> Dict[str, pd.DataFrame]:
    """Load all CSVs needed for the calculation."""
    src = DATA_DIR / "source" / "rosstat"
    out = DATA_DIR / "output"

    data: Dict[str, pd.DataFrame] = {}

    # --- District density ---
    data["district_density"] = pd.read_csv(out / "district_density_stats.csv")

    # --- MO density ---
    data["mo_density"] = pd.read_csv(out / "mo_density_stats.csv")

    # --- Organizations (for survival_rate) ---
    data["orgs"] = pd.read_csv(out / "organisations-by-district-and-mo.csv")

    # --- Population by district (id <-> name mapping) ---
    pd_dist = pd.read_csv(src / "population" / "people-by-district-2025.csv")
    pd_dist["name"] = pd_dist["name"].astype(str).str.strip()
    data["people_district"] = pd_dist

    # --- Population by MO ---
    pd_mo = pd.read_csv(src / "population" / "people-by-mo-2025.csv")
    pd_mo.columns = pd_mo.columns.str.strip()
    if "name" in pd_mo.columns:
        pd_mo["name"] = pd_mo["name"].astype(str).str.strip()
    data["people_mo"] = pd_mo

    # --- Population timeline ---
    pt = pd.read_csv(out / "people-by-district-timeline.csv")
    for col in [str(y) for y in range(2018, 2026)]:
        if col in pt.columns:
            pt[col] = pd.to_numeric(pt[col], errors="coerce")
    data["people_timeline"] = pt

    # --- Age-sex structure ---
    age = pd.read_csv(src / "population" / "population-age-sex-structure-2024.csv")
    age.columns = age.columns.str.strip()
    for c in ["district", "age"]:
        if c in age.columns:
            age[c] = age[c].astype(str).str.strip()
    if "both" in age.columns:
        age["both"] = pd.to_numeric(age["both"], errors="coerce")
    data["age_structure"] = age

    # --- Working-age female population ---
    wf = pd.read_csv(src / "working-age-population" / "working-age-population-female-2024.csv")
    wf.columns = wf.columns.str.strip()
    if "district_name" in wf.columns:
        wf["district_name"] = wf["district_name"].astype(str).str.strip()
    for c in ["both", "younger", "working", "older"]:
        if c in wf.columns:
            wf[c] = pd.to_numeric(wf[c], errors="coerce")
    data["working_age_female"] = wf

    # --- Salaries ---
    sal = pd.read_csv(src / "salary" / "average_salary_by_district.csv")
    sal.columns = sal.columns.str.strip()
    if "name" in sal.columns:
        sal["name"] = sal["name"].astype(str).str.strip()
    if "salary" in sal.columns:
        sal["salary"] = pd.to_numeric(sal["salary"], errors="coerce")
    data["salary"] = sal

    # --- Housing commissioning ---
    hs = pd.read_csv(src / "housing" / "commissioning-housing-by-district.csv")
    hs.columns = hs.columns.str.strip()
    if "district_name" in hs.columns:
        hs["district_name"] = hs["district_name"].astype(str).str.strip()
    for col in ["2021", "2022", "2023"]:
        if col in hs.columns:
            hs[col] = pd.to_numeric(hs[col], errors="coerce")
    data["housing"] = hs

    return data


def build_district_mapping(people_district: pd.DataFrame) -> tuple:
    """Build district_name <-> district_id mapping."""
    df = people_district.copy()
    name_to_id = dict(zip(df["name"], df["id"]))
    id_to_name = dict(zip(df["id"], df["name"]))
    return name_to_id, id_to_name


# ─── Scoring functions (score 1/2/3) ─────────────────────────────────────────

def score_people_per_workshop(x) -> Optional[int]:
    """1.1: competitor density (more people per workshop = better)."""
    if pd.isna(x):
        return None
    if x > 40_000:
        return 3
    if x >= 25_000:
        return 2
    return 1


def score_survival_rate(x) -> Optional[int]:
    """1.2: business survival rate."""
    if pd.isna(x):
        return None
    if x > 0.70:
        return 3
    if x >= 0.60:
        return 2
    return 1


def score_target_30_65(x) -> Optional[int]:
    """2.1: size of target audience 30–64."""
    if pd.isna(x):
        return None
    if x > 200_000:
        return 3
    if x >= 100_000:
        return 2
    return 1


def score_female_share_tercile(x, p33: float, p67: float) -> Optional[int]:
    """2.2: share of working-age women (by terciles)."""
    if pd.isna(x):
        return None
    if x >= p67:
        return 3
    if x <= p33:
        return 1
    return 2


def score_growth(x) -> Optional[int]:
    """2.3: population growth dynamics 2018–2025."""
    if pd.isna(x):
        return None
    if x > 0.10:
        return 3
    if x >= 0.0:
        return 2
    return 1


def score_salary(x) -> Optional[int]:
    """3.1: average salary."""
    if pd.isna(x):
        return None
    if x > 140_000:
        return 3
    if x >= 120_000:
        return 2
    return 1


def score_housing(x) -> Optional[int]:
    """4.3: housing commissioning 2021–2023.
    Data in CSV is already in thousands of sq. m. Thresholds: >500, 200–500, <200 (thousands sq. m).
    """
    if pd.isna(x):
        return None
    if x > 500:
        return 3
    if x >= 200:
        return 2
    return 1


# ─── Metric computation ───────────────────────────────────────────────────────

def compute_survival_by_district(orgs: pd.DataFrame) -> pd.DataFrame:
    """Survival rate = working_orgs / total_orgs.
    NOTE: is_work == 1 -> active, is_work == 0 -> closed.
    """
    df = orgs.copy()
    df["is_work"] = pd.to_numeric(df["is_work"], errors="coerce")
    g = df.groupby("district_id", as_index=False).agg(
        total_orgs=("org_id", "count"),
        working_orgs=("is_work", lambda s: (s == 1).sum()),
    )
    g["survival_rate"] = np.where(g["total_orgs"] > 0, g["working_orgs"] / g["total_orgs"], np.nan)
    return g


def compute_target_30_65(age_structure: pd.DataFrame, name_to_id: Dict[str, int]) -> pd.DataFrame:
    """Target audience 30–64 by district from age-sex structure."""
    df = age_structure.copy()
    df["district_norm"] = df["district"].apply(normalize_district_name)
    df = df[df["age"].isin(TARGET_AGE_BINS)]
    g = df.groupby("district_norm", as_index=False).agg(target_30_65=("both", "sum"))
    g["district_id"] = g["district_norm"].map(name_to_id)
    g = g.dropna(subset=["district_id"])
    g["district_id"] = g["district_id"].astype(int)
    return g[["district_id", "target_30_65"]]


def compute_female_working_share(
    wf: pd.DataFrame, timeline: pd.DataFrame, name_to_id: Dict[str, int],
) -> pd.DataFrame:
    """Share of working-age women = female_working / population(base_year)."""
    df = wf.copy()
    df["district_id"] = df["district_name"].map(name_to_id)
    df = df.dropna(subset=["district_id"])
    df["district_id"] = df["district_id"].astype(int)
    df["female_working_age"] = pd.to_numeric(df["working"], errors="coerce")

    year_col = str(BASE_POP_YEAR_FOR_FEMALE_SHARE)
    pt = timeline[["district_id", year_col]].rename(columns={year_col: "population_base_year"})
    pt["population_base_year"] = pd.to_numeric(pt["population_base_year"], errors="coerce")

    out = df[["district_id", "female_working_age"]].merge(pt, on="district_id", how="left")
    out["female_working_share"] = np.where(
        out["population_base_year"] > 0, out["female_working_age"] / out["population_base_year"], np.nan,
    )
    return out[["district_id", "female_working_age", "population_base_year", "female_working_share"]]


def compute_growth(timeline: pd.DataFrame) -> pd.DataFrame:
    """Population growth: (pop_y1 - pop_y0) / pop_y0."""
    c0, c1 = str(GROWTH_FROM_YEAR), str(GROWTH_TO_YEAR)
    df = timeline[["district_id", c0, c1]].copy()
    df[c0] = pd.to_numeric(df[c0], errors="coerce")
    df[c1] = pd.to_numeric(df[c1], errors="coerce")
    df["growth_2018_2025"] = np.where(df[c0] > 0, (df[c1] - df[c0]) / df[c0], np.nan)
    return df.rename(columns={c0: "pop_2018", c1: "pop_2025"})


def compute_housing_sum(housing: pd.DataFrame) -> pd.DataFrame:
    """Total housing commissioning for 2021–2023 (data in thousands of sq. m)."""
    df = housing.copy()
    for col in ["2021", "2022", "2023"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["housing_2021_2023"] = df[["2021", "2022", "2023"]].sum(axis=1, min_count=1)
    return df[["district_name", "housing_2021_2023"]]


# ─── Stage 1: district scoring ────────────────────────────────────────────────

def build_district_scoring(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    name_to_id, id_to_name = build_district_mapping(data["people_district"])

    # Base table from district_density
    dd = data["district_density"].copy()
    dd["district_id"] = pd.to_numeric(dd["district_id"], errors="coerce").dropna().astype(int)
    dd["district_name"] = dd["district_id"].map(id_to_name)
    dd["population"] = pd.to_numeric(dd["population"], errors="coerce")
    # workshops column in district_density_stats = number of active workshops
    dd["workshops_working"] = pd.to_numeric(dd["workshops"], errors="coerce").fillna(0)
    # 1.1: smoothed density
    dd["people_per_workshop_smoothed"] = dd["population"] / (dd["workshops_working"] + 0.5)

    # 1.2: survival rate
    surv = compute_survival_by_district(data["orgs"])

    # 2.1: target audience 30–64
    target = compute_target_30_65(data["age_structure"], name_to_id)

    # 2.2: female share
    female = compute_female_working_share(data["working_age_female"], data["people_timeline"], name_to_id)

    # 2.3: population growth
    growth = compute_growth(data["people_timeline"])

    # 3.1: salary
    sal = data["salary"].copy()
    sal["district_id"] = sal["name"].map(name_to_id)
    sal = sal.dropna(subset=["district_id"])
    sal["district_id"] = sal["district_id"].astype(int)

    # 4.3: housing
    hs = compute_housing_sum(data["housing"])
    hs["district_id"] = hs["district_name"].map(name_to_id)
    hs = hs.dropna(subset=["district_id"])
    hs["district_id"] = hs["district_id"].astype(int)

    # Join
    df = (
        dd[["district_id", "district_name", "population", "workshops", "people_per_workshop", "avg_salary",
            "workshops_working", "people_per_workshop_smoothed"]]
        .merge(surv, on="district_id", how="left")
        .merge(target, on="district_id", how="left")
        .merge(female, on="district_id", how="left")
        .merge(growth, on="district_id", how="left")
        .merge(sal[["district_id", "salary"]], on="district_id", how="left")
        .merge(hs[["district_id", "housing_2021_2023"]], on="district_id", how="left")
    )

    # --- Scores ---
    df["score_1_1"] = df["people_per_workshop_smoothed"].apply(score_people_per_workshop)
    df["score_1_2"] = df["survival_rate"].apply(score_survival_rate)
    df["score_2_1"] = df["target_30_65"].apply(score_target_30_65)

    # 2.2: terciles by female_working_share
    fs = df["female_working_share"].dropna()
    p33 = float(np.nanpercentile(fs, 33)) if len(fs) >= 3 else np.nan
    p67 = float(np.nanpercentile(fs, 67)) if len(fs) >= 3 else np.nan
    df["female_share_p33"] = p33
    df["female_share_p67"] = p67
    df["score_2_2"] = df["female_working_share"].apply(lambda x: score_female_share_tercile(x, p33, p67))

    df["score_2_3"] = df["growth_2018_2025"].apply(score_growth)
    df["score_3_1"] = df["salary"].apply(score_salary)
    df["score_4_3"] = df["housing_2021_2023"].apply(score_housing)

    # --- Composite rating: R = Σ(Bi × Wi) / Σ(Wi) ---
    weighted_sum = np.zeros(len(df), dtype=float)
    used_weight = np.zeros(len(df), dtype=float)

    for criterion, col in SCORE_COLUMNS.items():
        w = PLANNED_WEIGHTS[criterion]
        scores = pd.to_numeric(df[col], errors="coerce")
        mask = scores.notna()
        weighted_sum[mask.values] += (scores[mask] * w).values
        used_weight[mask.values] += w

    df["used_weight"] = used_weight
    df["planned_weight"] = PLANNED_TOTAL_WEIGHT
    df["coverage"] = np.where(df["planned_weight"] > 0, df["used_weight"] / df["planned_weight"], np.nan)
    df["district_score"] = np.where(df["used_weight"] > 0, weighted_sum / df["used_weight"], np.nan)
    df["district_rank"] = df["district_score"].rank(ascending=False, method="min")

    return df


# ─── Stage 2: MO scoring ──────────────────────────────────────────────────────

def build_mo_scoring(data: Dict[str, pd.DataFrame], selected_district_ids: List[int]) -> pd.DataFrame:
    mo = data["mo_density"].copy()
    mo["district_id"] = pd.to_numeric(mo["district_id"], errors="coerce")
    mo["mo_id"] = pd.to_numeric(mo["mo_id"], errors="coerce")
    mo = mo.dropna(subset=["district_id", "mo_id"])
    mo["district_id"] = mo["district_id"].astype(int)
    mo["mo_id"] = mo["mo_id"].astype(int)

    mo["population"] = pd.to_numeric(mo["population"], errors="coerce")
    # workshops in mo_density = active workshops
    mo["workshops_working"] = pd.to_numeric(mo["workshops"], errors="coerce").fillna(0)
    mo["mo_people_per_workshop_smoothed"] = mo["population"] / (mo["workshops_working"] + 0.5)

    # Attach MO names
    pm = data.get("people_mo")
    if pm is not None:
        pm2 = pm.rename(columns={"id": "mo_id", "name": "mo_name"}).copy()
        pm2["mo_id"] = pd.to_numeric(pm2["mo_id"], errors="coerce")
        pm2["district_id"] = pd.to_numeric(pm2["district_id"], errors="coerce")
        pm2 = pm2.dropna(subset=["mo_id", "district_id"])
        pm2["mo_id"] = pm2["mo_id"].astype(int)
        pm2["district_id"] = pm2["district_id"].astype(int)
        pm2["mo_name"] = pm2["mo_name"].astype(str).str.strip()
        mo = mo.merge(pm2[["mo_id", "district_id", "mo_name"]], on=["mo_id", "district_id"], how="left")

    # Scale filter
    mo["low_priority_by_scale"] = mo["population"] < 30_000

    # White spots (flag, no weight)
    def white_spot_flag(row) -> str:
        pop, w = row["population"], row["workshops_working"]
        if pd.isna(pop) or pd.isna(w):
            return "unknown"
        if w == 0 and pop > 50_000:
            return "high"
        if w in (0, 1) and 30_000 <= pop <= 50_000:
            return "medium"
        return "normal"

    mo["white_spot_flag"] = mo.apply(white_spot_flag, axis=1)

    # Filter to selected districts only
    mo = mo[mo["district_id"].isin(selected_district_ids)].copy()

    # Sort: descending by mo_people_per_workshop (best first), then by population
    mo = mo.sort_values(
        ["district_id", "mo_people_per_workshop_smoothed", "population"],
        ascending=[True, False, False],
    )
    mo["mo_rank_within_district"] = mo.groupby("district_id")["mo_people_per_workshop_smoothed"].rank(
        ascending=False, method="min",
    )
    mo["mo_rank_overall"] = mo["mo_people_per_workshop_smoothed"].rank(ascending=False, method="min")

    return mo


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="District and MO scoring (two-stage model A)")
    parser.add_argument("--top-districts", type=int, default=8,
                        help="Top-N districts for stage 2 (if --min-district-score is not set)")
    parser.add_argument("--min-district-score", type=float, default=None,
                        help="Minimum district_score threshold for stage 2")
    args = parser.parse_args()

    data = load_data()
    out_dir = DATA_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1
    district_df = build_district_scoring(data)
    district_out = out_dir / "scoring_districts.csv"
    district_df.to_csv(district_out, index=False, encoding="utf-8")

    # Select districts for stage 2
    district_sorted = district_df.sort_values("district_score", ascending=False)
    if args.min_district_score is not None:
        selected = district_sorted[district_sorted["district_score"] >= args.min_district_score]
    else:
        selected = district_sorted.head(args.top_districts)
    selected_ids = selected["district_id"].dropna().astype(int).tolist()

    # Stage 2
    mo_df = build_mo_scoring(data, selected_district_ids=selected_ids)
    mo_out = out_dir / "scoring_mos.csv"
    mo_df.to_csv(mo_out, index=False, encoding="utf-8")

    print(f"[ok] districts: {district_out}")
    print(f"[ok] mos:       {mo_out}")
    print(f"[!]  To generate an MD report, run _14_generate_scoring_report.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
