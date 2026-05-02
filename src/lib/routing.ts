const API_BASE = "http://localhost:8000";

// Types for routing API
export interface RouteRequest {
  origin_lat: number;
  origin_lng: number;
  disaster_type: string;
}

export interface FacilityInfo {
  name: string;
  type: string;
  address: string;
  coordinates: [number, number];
  distance_km: number;
  phone: string | null;
}

export interface RouteInfo {
  distance_km: number;
  duration_min: number;
  geometry: number[][] | null;
}

export interface RoutingResponse {
  facility: FacilityInfo;
  route: RouteInfo;
  origin: [number, number];
}

export async function getEmergencyRoute(
  origin_lat: number,
  origin_lng: number,
  disaster_type: string
): Promise<RoutingResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/routing/route`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origin_lat,
        origin_lng,
        disaster_type,
      }),
    });
    if (!res.ok) {
      console.error("Routing API error:", res.status);
      return null;
    }
    return await res.json();
  } catch (error) {
    console.error("Routing fetch error:", error);
    return null;
  }
}
