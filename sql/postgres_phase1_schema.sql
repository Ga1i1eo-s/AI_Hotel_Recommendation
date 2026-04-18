CREATE TABLE IF NOT EXISTS restaurants (
    restaurant_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT,
    area TEXT,
    cuisines JSONB NOT NULL DEFAULT '[]'::jsonb,
    avg_cost_for_two NUMERIC,
    budget_band TEXT CHECK (budget_band IN ('low', 'medium', 'high')),
    rating NUMERIC CHECK (rating >= 0 AND rating <= 5),
    rating_count INTEGER NOT NULL DEFAULT 0,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_restaurants_city_budget
    ON restaurants (city, budget_band);

CREATE INDEX IF NOT EXISTS idx_restaurants_city_rating
    ON restaurants (city, rating DESC);

CREATE INDEX IF NOT EXISTS idx_restaurants_cuisines_gin
    ON restaurants USING GIN (cuisines);

