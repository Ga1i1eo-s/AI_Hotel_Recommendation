# AI-Powered Restaurant Recommendation System

Detailed phase-wise architecture based on the problem statement for a Zomato-style recommendation product.

---

## 1) System Goals and Non-Goals

### Goals
- Recommend restaurants using structured filtering + LLM reasoning.
- Produce explainable, personalized output for each recommendation.
- Keep latency acceptable for interactive usage.
- Support iterative improvement through user feedback and analytics.

### Non-Goals (initial release)
- Real-time table booking integration.
- Fine-tuning custom LLM models.
- Multi-city geo-distance optimization with live maps traffic.

---

## 2) End-to-End Logical Architecture

1. **Data Ingestion Layer**
   - Pulls dataset from Hugging Face.
   - Cleans and normalizes data.
   - Loads into primary operational database.

2. **Preference Intake Layer**
   - Captures user preferences from UI/API.
   - Validates and canonicalizes input.

3. **Candidate Retrieval Layer (Deterministic)**
   - Filters by hard constraints.
   - Scores and shortlists top candidates.

4. **LLM Recommendation Layer (Reasoning)**
   - Prompts LLM with structured candidate list + user intent.
   - Produces ranked recommendations and explanations.

5. **Presentation Layer**
   - Returns user-friendly recommendation cards.
   - Supports sort/refine/follow-up interactions.

6. **Feedback + Observability Layer**
   - Tracks interactions and quality metrics.
   - Powers continuous prompt/ranking improvements.

---

## 3) Detailed Phase-Wise Architecture

## Phase 1: Data Ingestion and Canonical Data Model

### Objective
Build a stable and clean restaurant catalog from the Hugging Face dataset.

### Components
- **Dataset Connector**
  - Fetches `ManikaSaini/zomato-restaurant-recommendation`.
- **Data Quality Pipeline**
  - Handles null values, malformed records, duplicates.
- **Normalizer**
  - Standardizes cuisine labels, location names, and cost fields.
- **Catalog Storage**
  - Primary DB with indexed tables/collections.

### Data Model (suggested)
- `restaurant_id` (string/uuid)
- `name` (string)
- `city` (string)
- `area` (string)
- `cuisines` (array[string])
- `avg_cost_for_two` (number)
- `budget_band` (enum: low, medium, high)
- `rating` (number)
- `rating_count` (number)
- `attributes` (json: family_friendly, quick_service, etc.)
- `source_updated_at` (timestamp)

### Processing Steps
1. Pull raw records.
2. Map source columns to canonical schema.
3. Normalize text values (trim, lowercase for matching, canonical city names).
4. Derive features (`budget_band`, normalized rating score).
5. Upsert into DB (idempotent ingestion).

### Storage/Infra
- **DB:** PostgreSQL preferred (strong filtering/index performance).
- **Indexes:** `(city, budget_band)`, `(city, rating desc)`, `GIN(cuisines)`.
- **Batch jobs:** daily/weekly sync workflow.

### Deliverables
- Repeatable ingestion job.
- Canonical schema doc.
- Data quality report (missing fields, duplicates, row count).

---

## Phase 2: User Preference Capture and Validation

### Objective
Convert user intent into validated, machine-usable preference objects.

### Components
- **Frontend Preference Form**
  - Fields: location dropdown, numeric budget (max cost for two), cuisine, min rating, additional notes.
- **Validation Service**
  - Ensures input completeness and valid ranges.
- **Preference Canonicalizer**
  - Maps free text into normalized tags.

### API Contract (example)
- `POST /api/preferences/validate`
  - Request:
    - `location`: string
    - `budget`: number (max cost for two)
    - `cuisine`: string or string[]
    - `min_rating`: number (0-5)
    - `additional_preferences`: string
  - Response:
    - `canonical_preferences` object
    - `warnings` array
- `GET /api/locations`
  - Response:
    - `locations`: string[]

### Validation Rules
- `location` must map to known supported city/area.
- `min_rating` bounded in `[0, 5]`.
- Budget is captured as numeric max spend for two and mapped to:
  - `min`: 0
  - `max`: user budget value
- Additional preferences converted to tags when possible.

### Deliverables
- Form + API integration.
- Error handling UX for invalid input.
- Canonical preference schema.

---

## Phase 3: Deterministic Candidate Retrieval and Pre-Ranking

### Objective
Create a high-quality shortlist before LLM reasoning to reduce noise, cost, and latency.

### Components
- **Constraint Filter Engine**
  - Hard filters (city, min rating, budget range, cuisine match).
- **Heuristic Scorer**
  - Weighted score for preference fit.
- **Candidate Shortlister**
  - Selects top N candidates using fixed config-driven shortlist size.

### Candidate Score (example)
- `fit_score = 0.35*cuisine_match + 0.30*rating_norm + 0.20*budget_fit + 0.15*popularity_norm`

### Query Strategy
1. Apply city filter first.
2. Apply min rating and budget filters.
3. Apply cuisine overlap scoring.
4. Sort by `fit_score`, keep top N where N is internal config (`default_shortlist_size`).

### Fallback Handling
- If strict filters produce too few results, progressively relax:
  1. Expand nearby areas in same city.
  2. Lower rating threshold by 0.2.
  3. Expand cuisine to related cuisines.

### Deliverables
- Filtering service with deterministic behavior.
- Pre-ranking formula configuration file.
- Fallback policy implementation.

---

## Phase 4: LLM-Based Recommendation and Explanation Engine

### Objective
Use LLM to rank shortlisted restaurants with human-like reasoning and clear explanations.

### Components
- **Prompt Builder**
  - Constructs system + context + constraints prompt.
- **LLM Gateway**
  - Uses Groq LLM API for model calls with retries and timeout.
- **Output Parser**
  - Enforces strict JSON schema from LLM response.
- **Safety/Fallback Module**
  - Falls back to deterministic ranking if parse/model fails.

### Prompt Design
- Include:
  - user preference object
  - candidate list table
  - instruction to rank top K
  - instruction to give concise reasons grounded in candidate data
- Require structured JSON output:
  - `restaurant_id`
  - `rank`
  - `reason`
  - `match_tags`

### LLM Guardrails
- Do not hallucinate restaurants outside candidate list.
- Explanation must cite candidate attributes only.
- Max explanation length (e.g., 35-50 words each).

### API Contract (example)
- `POST /api/recommendations/generate`
  - Input: canonical preferences + candidate list
  - Output: ordered recommendation array with reasons

### Deliverables
- Prompt templates (versioned).
- JSON schema validator.
- Retry + fallback logic.

---

## Phase 5: Output Presentation and User Interaction

### Objective
Present recommendations in an understandable, trusted, and actionable format.

### Components
- **Recommendation API**
  - Serves final ranked response.
- **Results UI**
  - Recommendation cards/table.
- **Refinement Controls**
  - Update filters without full restart.

### UI Card Fields
- Restaurant Name
- Cuisine
- Rating
- Estimated Cost
- AI-generated explanation
- Optional badges: `Budget Fit`, `Highly Rated`, `Family Friendly`

### UX Behaviors
- Show "why recommended" per card.
- Provide "Regenerate with stricter budget" or similar quick actions.
- Handle no-result state with suggestions.

### Deliverables
- Responsive results page.
- Clear empty/error states.
- API response-to-UI mapping.

---

## Phase 6: Feedback Loop, Evaluation, and Monitoring

### Objective
Measure recommendation quality and continuously improve relevance, latency, and cost.

### Components
- **Event Tracker**
  - Logs impressions, clicks, saves, dismissals.
- **Quality Dashboard**
  - Aggregates KPIs by city/cuisine/budget segment.
- **Experimentation Framework**
  - A/B tests prompt variants and scoring weights.

### Core Metrics
- **Relevance:** CTR, save rate, positive feedback rate
- **Quality:** average rating of clicked items
- **Latency:** P50/P95 response times
- **Cost:** LLM tokens/request, cost/session
- **Robustness:** parse failures, fallback usage rate

### Improvement Loop
1. Identify weak segments (e.g., low CTR for budget-high users in a city).
2. Tune filter weights or prompt wording.
3. Run A/B experiment.
4. Roll out winning config.

### Deliverables
- Instrumentation schema.
- Dashboard with KPI alerts.
- Monthly model/prompt tuning cycle.

---

## 4) Frontend Architecture (Next.js)

### Objective
Build a scalable, modern frontend inspired by the visual direction in the latest design and keep it loosely coupled from the recommendation backend.

### Proposed Structure (`frontend/`)
- `app/`
  - App Router pages/layout and global styles.
  - Landing page composition and top-level data loading.
- `components/`
  - Reusable UI blocks (hero search, category strip, locality cards, recommendation cards).
- `lib/`
  - API client utilities and shared TypeScript types for backend contracts.
- `.env.local`
  - `NEXT_PUBLIC_API_BASE_URL` for backend endpoint configuration across environments.

### Frontend Flow
1. Render a branded landing page with hero search controls.
2. Load supported locations from `GET /api/locations`.
3. Submit user preference payload to `POST /api/recommendations/generate`.
4. Display recommendation cards with rating, locality, price, and explanation.
5. Gracefully degrade with fallback location/default states when backend is unavailable.

### Why This Architecture
- **Modular UI:** section-level components can be iterated independently.
- **Typed integration:** API payloads/responses are typed to reduce contract drift.
- **Deployment flexibility:** frontend can run independently (`next dev/start`) while backend remains FastAPI.
- **Future growth:** easy path to adding auth, user sessions, saved lists, and analytics tracking.

---

## 5) Suggested Technical Stack

- **Frontend:** Next.js (App Router, TypeScript)
- **Backend:** FastAPI (Python) or Node.js (Express/Nest)
- **Database:** PostgreSQL
- **Caching:** Redis (optional for hot queries)
- **Async Jobs:** Celery/Redis or cron + worker
- **LLM Provider:** Groq LLM API
- **Observability:** Prometheus + Grafana or hosted APM

---

## 6) Deployment Architecture

### Target Deployment
- **Frontend:** Vercel (Next.js app in `frontend/`)
- **Backend:** Streamlit deployment (Python backend service hosting recommendation APIs)

### Deployment Topology
1. User accesses UI on Vercel-hosted Next.js app.
2. Next.js calls backend endpoints hosted on Streamlit deployment URL.
3. Backend processes preference validation, shortlist generation, and recommendation generation.
4. Backend returns structured JSON for rendering recommendation cards in frontend.

### Environment and Configuration
- **Frontend env (`Vercel`)**
  - `NEXT_PUBLIC_API_BASE_URL=<streamlit-backend-base-url>`
- **Backend env (`Streamlit`)**
  - `GROQ_API_KEY` (or `LLM_API_KEY` / `OPENAI_API_KEY`)
  - `LLM_API_URL` (optional)
  - `LLM_MODEL` (optional)

### Deployment Notes
- Configure CORS on backend to allow Vercel domain(s).
- Keep secrets only in deployment platform env vars.
- Add health endpoint checks and deployment smoke tests after each release.
- Ensure catalog data source is available to backend runtime (DB or persistent storage).

---

## 7) Security, Reliability, and Operational Concerns

- Validate/sanitize all user input.
- Add request rate limits for recommendation API.
- Use environment variables for API keys (never hardcode).
- Add timeouts + retries for external API/LLM calls.
- Store prompt and model version with each recommendation event.
- Add circuit breaker to skip LLM when provider is degraded.

---

## 8) Release Plan (Practical Milestones)

- **Milestone A (MVP):** Phases 1-3 complete, deterministic recommendations only.
- **Milestone B:** Phase 4 integrated, LLM explanations live.
- **Milestone C:** Phase 5 polished UI + refine actions.
- **Milestone D:** Phase 6 analytics and A/B optimization loop.

---

## 9) Minimal Service Decomposition (Optional Microservice View)

- `ingestion-service`: dataset sync and cleaning
- `catalog-service`: restaurant query APIs
- `recommendation-service`: filter + LLM orchestration
- `ui-web` (Next.js): landing, discovery, and recommendation rendering
- `analytics-service`: event ingestion and reporting

For early stage, these can start as modules in a single backend and split later if traffic grows.
