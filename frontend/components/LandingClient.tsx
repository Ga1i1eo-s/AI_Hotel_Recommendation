"use client";

import { FormEvent, useMemo, useState } from "react";
import { generateRecommendations } from "../lib/api";
import { PreferenceRequest, Recommendation } from "../lib/types";

type LandingClientProps = {
  locations: string[];
  cuisines: string[];
};

export function LandingClient({ locations, cuisines }: LandingClientProps) {
  const [location, setLocation] = useState(locations[0] ?? "Bangalore");
  const [cuisine, setCuisine] = useState(cuisines[0] ?? "Italian");
  const [budget, setBudget] = useState(1800);
  const [minRating, setMinRating] = useState(4);
  const [additional, setAdditional] = useState("family friendly");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<Recommendation[]>([]);

  const cuisineList = useMemo(
    () => [cuisine].filter(Boolean),
    [cuisine]
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload: PreferenceRequest = {
        location,
        budget,
        cuisine: cuisineList,
        min_rating: minRating,
        additional_preferences: additional
      };
      const response = await generateRecommendations(payload, 5);
      setResults(response.recommendations ?? []);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Something went wrong while fetching recommendations."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header className="topbar">
        <div className="brand">Culinary AI</div>
        <nav className="navlinks">
          <a href="#">Explore</a>
          <a href="#">AI Discoveries</a>
          <a href="#">Top Rated</a>
        </nav>
      </header>

      <section className="hero">
        <div className="hero-overlay">
          <h1>Taste the Future</h1>
          <p>Our AI curates perfect dining experiences based on your mood and locality.</p>
          <form className="search-panel" onSubmit={onSubmit}>
            <select value={location} onChange={(event) => setLocation(event.target.value)}>
              {locations.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <select value={cuisine} onChange={(event) => setCuisine(event.target.value)}>
              {cuisines.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <div className="range-field" aria-label="Budget for two">
              <div className="range-meta">
                <span>Budget</span>
                <strong>₹{budget}</strong>
              </div>
              <input
                type="range"
                min={100}
                max={5000}
                step={50}
                value={budget}
                onChange={(event) => setBudget(Number(event.target.value))}
              />
            </div>
            <div className="range-field" aria-label="Minimum rating">
              <div className="range-meta">
                <span>Rating</span>
                <strong>{minRating.toFixed(1)}★</strong>
              </div>
              <input
                type="range"
                min={0}
                max={5}
                step={0.1}
                value={minRating}
                onChange={(event) => setMinRating(Number(event.target.value))}
              />
            </div>
            <button type="submit" disabled={loading}>
              {loading ? "Loading..." : "Get AI Recommendations"}
            </button>
          </form>

          {error ? <p className="error-box">{error}</p> : null}
          {results.length > 0 ? (
            <div className="result-grid">
              {results.map((item) => (
                <article key={`${item.restaurant_id}-${item.rank}`} className="result-card">
                  <div className="result-head">
                    <h3>
                      {item.rank}. {item.candidate.name}
                    </h3>
                    <span>{item.candidate.rating ?? "N/A"}★</span>
                  </div>
                  <p>{item.reason}</p>
                  <p>
                    {item.candidate.city}, {item.candidate.area}
                  </p>
                  <p>{item.candidate.avg_cost_for_two} for two</p>
                </article>
              ))}
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}
