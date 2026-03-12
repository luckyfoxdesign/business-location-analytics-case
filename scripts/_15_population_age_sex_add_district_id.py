#!/usr/bin/env python3
import argparse
import csv
import re
import sys
from pathlib import Path

import pandas as pd


def sniff_delimiter(path: Path, fallback: str = ",") -> str:
    try:
        sample = path.read_bytes()[:4096].decode("utf-8", errors="replace")
        return csv.Sniffer().sniff(sample).delimiter
    except Exception:
        return fallback


def read_csv_auto(path: Path) -> pd.DataFrame:
    sep = sniff_delimiter(path)
    try:
        df = pd.read_csv(path, sep=sep, encoding="utf-8-sig")
    except UnicodeDecodeError:
        # fallback for older exports
        df = pd.read_csv(path, sep=sep, encoding="cp1251")
    # note: source columns may have leading spaces like " age", " male"
    df.columns = [str(c).strip() for c in df.columns]
    return df


_name_cleanup_re = re.compile(r"\s+")
_word_raion_re = re.compile(r"\bрайон\b")
_word_rn_re = re.compile(r"\bр-?н\b")


def norm_district_name(s: str) -> str:
    s = str(s).strip().lower()
    s = s.replace("ё", "е").replace("–", "-").replace("—", "-")
    s = _name_cleanup_re.sub(" ", s)
    s = _word_raion_re.sub("", s).strip()
    s = _word_rn_re.sub("", s).strip()
    return s


def resolve_first_existing(candidates: list[Path]) -> Path:
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        "district_ids.csv not found. Checked paths:\n- " + "\n- ".join(str(p) for p in candidates)
    )


def guess_mapping_columns(df: pd.DataFrame) -> tuple[str, str]:
    cols_lower = {c.lower(): c for c in df.columns}

    # district name
    for k in ("district", "district_name", "name", "район"):
        if k in cols_lower:
            name_col = cols_lower[k]
            break
    else:
        # heuristic
        name_col = next(
            (c for c in df.columns if "district" in c.lower() or c.lower() == "name" or "район" in c.lower()),
            None,
        )

    # id
    for k in ("district_id", "id", "districtid"):
        if k in cols_lower:
            id_col = cols_lower[k]
            break
    else:
        id_col = next((c for c in df.columns if c.lower() in ("id", "district_id")), None)

    if not name_col or not id_col:
        raise ValueError(f"Could not determine columns in district_ids.csv. Columns: {list(df.columns)}")

    return name_col, id_col


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    default_input = project_root / "data/source/rosstat/population/population-age-sex-structure-2024.csv"
    default_output = project_root / "data/output/population-age-sex-structure-2024-by-district-id.csv"

    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_path", type=Path, default=default_input)
    parser.add_argument(
        "--map",
        dest="map_path",
        type=Path,
        default=None,
        help="Path to district_ids.csv (if not in the project root).",
    )
    parser.add_argument("--out", dest="out_path", type=Path, default=default_output)
    args = parser.parse_args()

    in_path: Path = args.in_path
    if not in_path.exists():
        raise FileNotFoundError(f"Input file not found: {in_path}")

    # default locations to look for district_ids.csv
    if args.map_path is None:
        map_path = resolve_first_existing(
            [
                project_root / "data/output/district_ids.csv",
                project_root / "district_ids.csv",
                project_root / "data/district_ids.csv",
                project_root / "data/source/district_ids.csv",
                project_root / "data/source/other/district_ids.csv",
                script_dir / "district_ids.csv",
            ]
        )
    else:
        map_path = args.map_path
        if not map_path.exists():
            raise FileNotFoundError(f"Mapping file not found: {map_path}")

    df = read_csv_auto(in_path)
    if "district" not in df.columns:
        raise ValueError(f"Input CSV has no 'district' column. Columns: {list(df.columns)}")

    df_map = read_csv_auto(map_path)
    name_col, id_col = guess_mapping_columns(df_map)

    df_map["_k"] = df_map[name_col].map(norm_district_name)
    if df_map["_k"].duplicated().any():
        dups = df_map.loc[df_map["_k"].duplicated(), name_col].tolist()
        raise ValueError(f"district_ids.csv has duplicate district names after normalization: {dups}")

    mapping = dict(zip(df_map["_k"], df_map[id_col]))

    # match
    norm_series = df["district"].map(norm_district_name)
    district_id = norm_series.map(mapping)

    missing = df.loc[district_id.isna(), "district"].dropna().unique().tolist()
    if missing:
        raise ValueError(
            "district_id not found for the following district values:\n- "
            + "\n- ".join(map(str, missing))
            + "\nCheck district_ids.csv and district name spelling."
        )

    # insert district_id in place of district and drop district
    district_id = district_id.astype(int)

    cols = list(df.columns)
    idx = cols.index("district")
    df.insert(idx, "district_id", district_id)
    df = df.drop(columns=["district"])

    out_path: Path = args.out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")

    print(f"OK: saved {out_path} (rows={len(df)})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
