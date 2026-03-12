import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "source" / "other" / "organizations.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "source" / "other" / "organizations_normalized.csv"

IS_WORK_MAP = {"1": "1", "2": "0"}


def main():
    with open(INPUT_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    for row in rows:
        original = row["is_work"].strip()
        if original not in IS_WORK_MAP:
            raise ValueError(f"Unexpected is_work value: '{original}' in row id={row['id']}")
        row["is_work"] = IS_WORK_MAP[original]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    working = sum(1 for r in rows if r["is_work"] == "1")
    closed = sum(1 for r in rows if r["is_work"] == "0")
    print(f"Saved {len(rows)} organizations to {OUTPUT_PATH}")
    print(f"  Working (1): {working}, Closed (0): {closed}")


if __name__ == "__main__":
    main()
