export type PreferenceRequest = {
  location: string;
  budget: number;
  cuisine: string[];
  min_rating: number;
  additional_preferences: string;
};

export type Candidate = {
  restaurant_id: string;
  name: string;
  city: string;
  area: string;
  cuisines: string[];
  avg_cost_for_two: number;
  rating: number;
};

export type Recommendation = {
  restaurant_id: string;
  rank: number;
  reason: string;
  match_tags: string[];
  candidate: Candidate;
};

export type RecommendationResponse = {
  warnings: string[];
  llm_used: boolean;
  recommendations: Recommendation[];
};
