# Restaurant Recommendation System

## Phase 1 to Phase 5 Implemented

This repository currently includes Phase 1:
- Dataset ingestion from Hugging Face.
- Data cleaning and canonical schema mapping.
- Feature derivation (`budget_band`).
- Deduplication using deterministic `restaurant_id`.
- Local database load (SQLite).
- Data quality report generation.

And Phase 2:
- Preference validation and canonicalization service.
- Numeric budget capture (`max cost for two`) and cost-range mapping.
- Location validation against Phase 1 catalog DB.
- Additional preference text tagging.
- API endpoint: `POST /api/preferences/validate`.
- Location options endpoint: `GET /api/locations`.

And Phase 3:
- Deterministic candidate retrieval and pre-ranking.
- Hard constraints: location, min rating, budget range, cuisine overlap.
- Weighted heuristic score:
  - `fit_score = 0.35*cuisine_match + 0.30*rating_norm + 0.20*budget_fit + 0.15*popularity_norm`
- Fallback relaxation:
  - expand nearby areas in city
  - lower rating threshold by 0.2
  - expand cuisines to related options
- API endpoint: `POST /api/candidates/shortlist`.
- Fixed internal shortlist size from config (`default_shortlist_size`).
- Configurable dedup strategy via `config/phase3_scoring.json`:
  - `name`
  - `name_area`
  - `restaurant_id`

And Phase 4:
- Prompt builder with versioned config (`config/phase4_prompt.json`).
- Groq LLM gateway with retries and timeout.
- Structured JSON parser and validator for LLM output.
- Deterministic fallback when LLM is unavailable/invalid.
- API endpoint: `POST /api/recommendations/generate`.

And Phase 5:
- Results UI served at `/` with recommendation cards.
- End-to-end tester actions in UI:
  - `1) Validate Preferences`
  - `2) Shortlist Candidates`
  - `3) Generate Recommendations`
- Refinement controls:
  - stricter budget
  - higher minimum rating
- Clear no-result and error states.
- API response-to-UI mapping with explanation and badges.

## Run

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Execute pipeline:
   - `python scripts/run_phase1.py`
3. Run Phase 2 demo:
   - `python scripts/run_phase2_demo.py`
4. Run Phase 3 demo:
   - `python scripts/run_phase3_demo.py`
5. Run Phase 4 demo:
   - `python scripts/run_phase4_demo.py`
6. Start API server:
   - `uvicorn src.app:app --reload`
7. Open UI in browser:
   - `http://127.0.0.1:8000/`

## Next.js Frontend (Design-Oriented UI)

A new Next.js frontend has been added in `frontend/` to match the design direction and provide a scalable UI foundation.

1. Start backend API (from project root):
   - `uvicorn src.app:app --reload`
2. Start frontend (in a new terminal):
   - `cd frontend`
   - `npm install`
   - `npm run dev`
3. Open frontend:
   - `http://127.0.0.1:3000/`

Set frontend API base URL:
- Copy `frontend/.env.local.example` to `frontend/.env.local`
- Ensure `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`

## Streamlit Backend Deployment

The repository now includes a Streamlit backend console in `streamlit_app.py` for deploying backend recommendation workflow on Streamlit Cloud.

### Run locally

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Start Streamlit backend app:
   - `streamlit run streamlit_app.py`
3. Open:
   - `http://localhost:8501/`

### Deploy to Streamlit Cloud

1. Push this repository to GitHub.
2. In Streamlit Cloud, create a new app:
   - **Main file path:** `streamlit_app.py`
3. Add environment variables in Streamlit app settings:
   - `GROQ_API_KEY` (or `LLM_API_KEY` / `OPENAI_API_KEY`)
   - `LLM_API_URL` (optional)
   - `LLM_MODEL` (optional)
4. Ensure dataset pipeline has produced:
   - `data/catalog.db`

Use the Streamlit app URL as backend deployment URL in architecture and operations planning.

## Outputs

- `data/catalog.db`
- `data/canonical_restaurants_sample.csv`
- `reports/phase1_data_quality_report.json`
- `sql/postgres_phase1_schema.sql`

## Phase 2 API Contract

- `POST /api/preferences/validate`
  - Request:
    - `location` (string)
    - `budget` (number: max cost for two)
    - `cuisine` (string or string[])
    - `min_rating` (number in `[0,5]`)
    - `additional_preferences` (string)
  - Response:
    - `canonical_preferences`
    - `warnings`

## Phase 3 API Contract

- `POST /api/candidates/shortlist`
  - Request:
    - `preferences` (same as Phase 2 request body)
  - Response:
    - `canonical_preferences`
    - `warnings`
    - `relaxation_steps_applied`
    - `total_candidates_considered`
    - `shortlisted_candidates` with `fit_score` and `score_breakdown`

## Phase 4 API Contract

- `POST /api/recommendations/generate`
  - Request:
    - `preferences` (same as Phase 2 request body)
    - `top_k` (1 to 20)
  - Response:
    - `canonical_preferences`
    - `warnings`
    - `llm_used`
    - `fallback_reason`
    - `prompt_version`
    - `recommendations` (`restaurant_id`, `rank`, `reason`, `match_tags`, `candidate`)

## Phase 4 Environment Variables

- `GROQ_API_KEY` or `LLM_API_KEY` or `OPENAI_API_KEY` (accepted key variable name)
- `LLM_API_URL` (optional override)
- `LLM_MODEL` (optional override)
- You can place these in a local `.env` file (see `.env.example`).

