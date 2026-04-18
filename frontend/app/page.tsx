import { LandingClient } from "../components/LandingClient";
import { getCuisines, getLocations } from "../lib/api";

export default async function HomePage() {
  let locations: string[] = ["Bangalore"];
  let cuisines: string[] = ["Italian"];

  try {
    const fetchedLocations = await getLocations();
    if (fetchedLocations.length > 0) {
      locations = fetchedLocations;
    }
  } catch {
    // Render with fallback location when backend is unavailable.
  }

  try {
    const fetchedCuisines = await getCuisines();
    if (fetchedCuisines.length > 0) {
      cuisines = fetchedCuisines;
    }
  } catch {
    // Render with fallback cuisines when backend is unavailable.
  }

  return <LandingClient locations={locations} cuisines={cuisines} />;
}
