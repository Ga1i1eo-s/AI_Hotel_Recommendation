# Phase 1 Canonical Schema

Canonical `restaurants` entity produced by `scripts/run_phase1.py`.

## Fields

- `restaurant_id` (text): deterministic UUID5 from `name|city|area`.
- `name` (text): normalized restaurant name.
- `city` (text): title-cased city/location string.
- `area` (text): title-cased locality/area string.
- `cuisines` (array[string]): normalized cuisine list.
- `avg_cost_for_two` (numeric): cleaned numeric cost value.
- `budget_band` (enum): `low`, `medium`, `high`.
- `rating` (numeric): clipped to `[0, 5]`.
- `rating_count` (integer): number of votes/ratings.
- `attributes` (json): extra flags (placeholder `{}` in Phase 1).
- `source_updated_at` (timestamp): ingestion timestamp in UTC.

## Data Quality Outputs

Running the Phase 1 pipeline generates:

- `reports/phase1_data_quality_report.json`
- `data/canonical_restaurants_sample.csv`
- `data/catalog.db` (SQLite operational store for local development)

