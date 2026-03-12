# Business Location Analytics: Jewelry Workshop Site Selection in Saint Petersburg

[![Read the case study](https://img.shields.io/badge/Read%20the%20case%20study-luckyfox.design-black?style=flat-square)](https://luckyfox.design/ru/projects/brief-report-on-selecting-the-optimal-location-for-starting-a-business)

An end-to-end data analysis case study for selecting the optimal district and neighborhood to open a jewelry repair workshop in Saint Petersburg, Russia.

**Duration:** ~8 months (side project)
**Stack:** Python · Pandas · GeoPandas · Folium · Plotly · Google Sheets · Tableau
**Data sources:** Yandex Maps (organizations), Rosstat (population, salaries, housing, age structure), OpenStreetMap (GeoJSON boundaries)
**Scale:** 18 administrative districts · 111 municipal districts · 2018–2025 data range

---

## Background

A friend's acquaintance wanted to open a jewelry repair workshop in Saint Petersburg and needed to pick a location. The input: coordinates of 354 existing workshops scraped from Yandex Maps as of early 2025, their status (active / closed), ratings, and working hours.

The question: **Which district and neighborhood offer the best balance of demand and low competition?**

---

## Repository Structure

```
├── data/
│   ├── source/                       # Raw inputs (Rosstat CSVs, Yandex Maps export)
│   │   ├── rosstat/
│   │   │   ├── population/           # People by district/MO per year (2018–2025)
│   │   │   ├── working-age-population/
│   │   │   ├── salary/
│   │   │   └── housing/
│   │   └── organizations/
│   └── output/                       # Processed CSVs (pipeline output)
│       ├── organisations-by-district-and-mo.csv
│       ├── district_density_stats.csv
│       ├── mo_density_stats.csv
│       ├── people-by-district-timeline.csv
│       ├── people-by-mo-timeline.csv
│       ├── scoring_districts.csv
│       └── scoring_mos.csv
├── scripts/
│   ├── _1-get_org_list_by_district_and_mo.py        # Geo-join orgs → districts/MOs
│   ├── _1_1-save_org_stats_by_mo_for_each_district.py
│   ├── _3_org_density_by_district_and_mo_csv.py     # Density statistics
│   ├── _5_build_people_timeline.py                  # Population timelines 2018–2025
│   ├── _6_validate_people_timeline.py
│   ├── _10_generate_working_age_by_district_id.py
│   ├── _11_process_housing_data.py
│   ├── _13_generate_final_statistics.py             # Two-stage scoring model
│   ├── _15_population_age_sex_add_district_id.py
│   ├── report-md/                                   # Markdown report generators
│   └── utils/
├── config.py
└── geo_utils.py
```

---

## Data Pipeline

Scripts are numbered in execution order. Each script has a defined set of inputs and outputs.

```
[Yandex Maps]             [Rosstat CSVs]
      │                         │
      ▼                         ▼
_1  geo-join orgs         _5  build population
    to districts/MOs           timelines 2018–2025
      │                         │
      ▼                         ▼
_3  density stats         _10  working-age population
    per district/MO       _11  housing commissioning
      │                         │
      └──────────┬───────────────┘
                 ▼
         _13  scoring model
              (districts → MOs)
                 │
                 ▼
        scoring_districts.csv
        scoring_mos.csv
```

### Key data transformations

**Organization geo-join** (`_1`): each of the 354 organizations is matched to a district and municipal district using point-in-polygon with the OpenStreetMap GeoJSON boundary file.

**Population timelines** (`_5`): Rosstat publishes population files separately for each year with slightly inconsistent naming. The script normalizes municipal district names (strips prefixes, ё→е substitution, whitespace normalization), applies a rename mapping for MOs that changed names (e.g., "Парнас" → "Сергиевское" from 2019), and handles abolished MOs.

**Density stats** (`_3`): computes `people_per_workshop` with Laplace smoothing (`workshops + 0.5`) to avoid division-by-zero for districts with no workshops.

---

## Scoring Model

A two-stage model covering 70% of the relevant factors. The remaining 30% — foot traffic, rent prices, proximity to anchor businesses — require data not available from open sources.

### Stage 1 — District Ranking

Seven criteria scored 1–3 points each, combined into a weighted average:

| # | Group | Criterion | Weight |
|---|-------|-----------|--------|
| 1.1 | Competition | People per active workshop | 20% |
| 1.2 | Competition | Business survival rate | 5% |
| 2.1 | Demographics | Target audience size (ages 30–65) | 15% |
| 2.2 | Demographics | Female working-age population share | 5% |
| 2.3 | Demographics | Population growth 2018–2025 | 10% |
| 3.1 | Income | Average salary | 10% |
| 4.3 | Infrastructure | New housing commissioned 2021–2023 | 5% |

**Formula:** `district_score = Σ(score_i × weight_i) / Σ(weight_i)`

Score thresholds (examples):
- `people_per_workshop > 40,000` → 3 pts; `25,000–40,000` → 2 pts; `< 25,000` → 1 pt
- `survival_rate > 0.70` → 3 pts; `0.60–0.70` → 2 pts; `< 0.60` → 1 pt
- `population_growth > 10%` → 3 pts; `0–10%` → 2 pts; negative → 1 pt

### Stage 2 — Municipal District Ranking

Within the top-N districts, municipal districts are ranked by competitive pressure (`people_per_workshop`, smoothed) and flagged for "white spots" — large MOs (>50,000 people) with zero active workshops.

---

## Key Findings

**Competition landscape:**
- 354 total organizations: **219 active (61.9%), 135 closed (38.1%)**
- Workshops exist in 15 of 18 districts; 3 districts (Kronshtadtsky, Kurortny, Petrodvortsovy) have none, yet their combined population is 264,000
- The center is oversaturated: Central and Petrogradsky districts have fewer than 10,000 people per workshop
- The periphery is underserved: Kolpinsky district has 190,000 people per single workshop

**"White spots" — large municipal districts with zero active workshops:**

| Municipal district | District | Population |
|--------------------|----------|------------|
| Kolpino | Kolpinsky | 147,179 |
| Kolomyagi | Primorsky | 122,082 |
| Pushkin | Pushkinsky | 108,969 |
| Svetlanovskoye | Vyborgsky | 90,456 |
| Peterhof | Petrodvortsovy | 81,767 |

**Top-5 districts by scoring model:**

| Rank | District | Score | Key factors |
|------|----------|-------|-------------|
| 1 | Primorsky | 2.57 | Low competition, largest target audience, strong growth |
| 2 | Pushkinsky | 2.43 | Fewest competitors, record population growth (+33%) |
| 3 | Vyborgsky | 2.36 | Balanced population and competition |
| 4 | Krasnoselsky | 2.29 | Few workshops, growing district |
| 4 | Kalininsky | 2.29 | High business survival rate |

**Population trends (2018–2025):**
- Fastest-growing: Pushkinsky (+32.9%), Primorsky (+26.4%), Krasnoselsky (+15.1%)
- Shrinking: Petrogradsky (−12.3%), Centralny (−10.5%), Admiralteysky (−5.6%)

---

## Model Limitations

The model is sufficient for narrowing 18 districts down to a shortlist of 5–8. It is **not sufficient for picking a specific address.**

What's missing:
- **Foot and vehicle traffic** — the primary factor in professional site-selection models
- **Rent prices by location**
- **Proximity to complementary businesses** (shopping malls, bridal salons, jewelers)
- **Household median income** — average salary by district registration ≠ income of district residents
- **Small-sample bias** — with 1–39 workshops per district, closing 2–3 shops shifts the survival rate by 10–15%, reflecting individual circumstances rather than market conditions

---

## Lessons Learned

**What didn't work:**
- Jumping into visualization before defining the question — spent ~1 month on charts and maps that went unused
- Starting implementation without a methodological plan
- Treating it as a "dream project" instead of a series of small, deliverable steps

**What worked:**
- Adopting the Google Data Analytics framework (Ask → Prepare → Process → Analyze → Share → Act) gave clear direction
- Numbered scripts with explicit inputs/outputs made the pipeline reproducible and easy to resume after breaks
- Loading all CSVs into Google Sheets first — a cheap way to validate data and sketch charts before writing more Python
- Taking 1–2 week breaks; returning each time with a clearer view of what was actually needed

---

## How to Run

**Prerequisites:** Python 3.10+

```bash
# 1. Geo-join organizations to districts and MOs
python scripts/_1-get_org_list_by_district_and_mo.py

# 2. Build population timelines (2018–2025)
python scripts/_5_build_people_timeline.py

# 3. Validate population data
python scripts/_6_validate_people_timeline.py

# 4. Compute density statistics
python scripts/_3_org_density_by_district_and_mo_csv.py

# 5. Process supplementary data
python scripts/_10_generate_working_age_by_district_id.py
python scripts/_11_process_housing_data.py
python scripts/_15_population_age_sex_add_district_id.py

# 6. Run two-stage scoring model (outputs to data/output/)
python scripts/_13_generate_final_statistics.py

# Optional: generate markdown report
python scripts/report-md/_14_generate_scoring_report.py
```

**Main dependencies:**
```
pandas
numpy
geopandas
shapely
folium
plotly
```

---

## Data Sources

| Dataset | Source | Coverage |
|---------|--------|----------|
| Jewelry workshop locations + status | Yandex Maps (manual export) | 354 orgs, early 2025 |
| Population by district / municipal district | Rosstat | 2018–2025 |
| Age-sex population structure | Rosstat | 2024 |
| Working-age population by gender | Rosstat | 2024 |
| Average salary by district | Rosstat | 2023 |
| New housing commissioned | Rosstat | 2021–2023 |
| Administrative boundaries (GeoJSON) | OpenStreetMap | 2024 |

All data is from publicly available sources.
