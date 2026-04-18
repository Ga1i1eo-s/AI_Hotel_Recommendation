import { PreferenceRequest, RecommendationResponse } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function getLocations(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/locations`, {
    cache: "no-store"
  });
  const data = (await response.json()) as { locations?: string[]; detail?: string };
  if (!response.ok) {
    throw new Error(data.detail ?? "Could not load locations.");
  }
  return data.locations ?? [];
}

export async function getCuisines(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/cuisines`, {
    cache: "no-store"
  });
  const data = (await response.json()) as { cuisines?: string[]; detail?: string };
  if (!response.ok) {
    throw new Error(data.detail ?? "Could not load cuisines.");
  }
  return data.cuisines ?? [];
}

export async function generateRecommendations(
  preferences: PreferenceRequest,
  topK: number
): Promise<RecommendationResponse> {
  const response = await fetch(`${API_BASE_URL}/api/recommendations/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preferences,
      top_k: topK
    })
  });

  const data = (await response.json()) as RecommendationResponse & { detail?: string };
  if (!response.ok) {
    throw new Error(data.detail ?? "Recommendation request failed.");
  }
  return data;
}
