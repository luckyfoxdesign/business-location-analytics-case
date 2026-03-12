import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "source" / "rosstat" / "population" / "people-by-district-2025.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "output" / "district_ids.csv"


def main():
    with open(INPUT_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [(row["id"], row["name"]) for row in reader]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name"])
        writer.writerows(rows)

    print(f"Saved {len(rows)} districts to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
