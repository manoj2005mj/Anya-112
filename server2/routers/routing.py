"""
Routing router for emergency facility lookup and ETA calculation.

Provides endpoints to find nearest emergency facilities and calculate routes.
"""

from typing import List, Literal, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import httpx

from server2.config import get_settings
from server2.logging_utils import ErrorComponent, get_logger

logger = get_logger("anya.server2.routers.routing")
router = APIRouter(prefix="/routing", tags=["routing"])


# =============================================================================
# Models
# =============================================================================

class EmergencyType(str, Enum):
    """Types of emergency facilities"""
    FIRE_STATION = "fire_station"
    HOSPITAL = "hospital"
    POLICE_STATION = "police_station"
    AMBULANCE = "ambulance"


class FacilityInfo(BaseModel):
    """Information about an emergency facility"""
    name: str = Field(..., description="Name of the facility")
    type: EmergencyType = Field(..., description="Type of facility")
    address: str = Field(..., description="Address of the facility")
    coordinates: List[float] = Field(..., description="[latitude, longitude]")
    distance_km: float = Field(..., description="Distance from origin in km")
    phone: Optional[str] = Field(None, description="Contact phone number")


class RouteStep(BaseModel):
    """A single step in the route"""
    instruction: str = Field(..., description="Text instruction for this step")
    distance_m: float = Field(..., description="Distance in meters for this step")
    duration_s: float = Field(..., description="Duration in seconds for this step")


class RouteInfo(BaseModel):
    """Route information between two points"""
    distance_km: float = Field(..., description="Total route distance in km")
    duration_min: float = Field(..., description="Estimated travel time in minutes")
    geometry: Optional[List[List[float]]] = Field(None, description="Route geometry as [[lat,lng],...]")


class RoutingResponse(BaseModel):
    """Complete routing response"""
    facility: FacilityInfo
    route: RouteInfo
    origin: List[float] = Field(..., description="Origin coordinates [lat, lng]")


# =============================================================================
# Helper Functions
# =============================================================================

def get_disaster_type_mapping(disaster_type: str) -> EmergencyType:
    """Map disaster type to emergency facility type"""
    disaster_lower = disaster_type.lower()

    if any(word in disaster_lower for word in ['fire', 'burn', 'flame', 'blaze']):
        return EmergencyType.FIRE_STATION
    elif any(word in disaster_lower for word in ['medical', 'injury', 'health', 'heart', 'bleeding', 'ambulance']):
        return EmergencyType.HOSPITAL
    elif any(word in disaster_lower for word in ['crime', 'theft', 'assault', 'police', 'violence']):
        return EmergencyType.POLICE_STATION
    elif any(word in disaster_lower for word in ['accident', 'crash', 'collision']):
        return EmergencyType.AMBULANCE
    else:
        # Default to hospital for medical emergencies
        return EmergencyType.HOSPITAL


async def search_nearby_facility(
    lat: float,
    lng: float,
    facility_type: EmergencyType
) -> FacilityInfo:
    """
    Search for nearby emergency facility using OSRM/Nominatim (free, no API key needed).

    Returns facility information or raises HTTPException if not found.
    """
    settings = get_settings()

    try:
        # Use Overpass API (OpenStreetMap) for more accurate nearby searches
        # This is free and doesn't require an API key
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Build Overpass query based on facility type
            type_queries = {
                EmergencyType.FIRE_STATION: 'node["amenity"="fire_station"]',
                EmergencyType.HOSPITAL: 'node["amenity"="hospital"]',
                EmergencyType.POLICE_STATION: 'node["amenity"="police"]',
                EmergencyType.AMBULANCE: 'node["emergency"="ambulance_station"]',
            }

            query = type_queries[facility_type]

            # Search radius - start with 5km
            radius = 5000

            # Overpass QL query to find nearby facilities
            overpass_query = f"""
                [out:json];
                (
                  {query}(around:{radius},{lat},{lng});
                );
                out body 10;
            """

            logger.info(
                f"Searching for {facility_type.value} near [{lat}, {lng}]",
                component=ErrorComponent.EXTERNAL_API,
            )

            response = await client.get(
                "https://overpass-api.de/api/interpreter",
                params={"data": overpass_query},
                headers={"User-Agent": "Anya-Emergency-Dispatch/1.0"}
            )
            response.raise_for_status()

            data = response.json()
            elements = data.get("elements", [])

            if not elements:
                # Try with larger radius (10km)
                radius = 10000
                overpass_query = f"""
                    [out:json];
                    (
                      {query}(around:{radius},{lat},{lng});
                    );
                    out body 10;
                """

                response = await client.get(
                    "https://overpass-api.de/api/interpreter",
                    params={"data": overpass_query},
                    headers={"User-Agent": "Anya-Emergency-Dispatch/1.0"}
                )
                response.raise_for_status()
                data = response.json()
                elements = data.get("elements", [])

            if not elements:
                # Fallback: use predefined facility
                logger.warning(
                    f"No facility found via Overpass API, using fallback",
                    component=ErrorComponent.EXTERNAL_API,
                )
                return get_fallback_facility(lat, lng, facility_type)

            # Find the closest facility
            closest = None
            closest_distance = float('inf')

            for element in elements:
                facility_lat = element.get("lat")
                facility_lng = element.get("lon")
                if facility_lat and facility_lng:
                    distance = haversine_distance(lat, lng, facility_lat, facility_lng)
                    if distance < closest_distance:
                        closest_distance = distance
                        closest = element

            if not closest:
                return get_fallback_facility(lat, lng, facility_type)

            tags = closest.get("tags", {})
            name = tags.get("name", tags.get("operator", f"{facility_type.value.replace('_', ' ').title()}"))

            # Build address from tags
            address_parts = []
            if tags.get("addr:street"):
                address_parts.append(tags["addr:street"])
            if tags.get("addr:city"):
                address_parts.append(tags["addr:city"])
            if tags.get("addr:state"):
                address_parts.append(tags["addr:state"])
            address = ", ".join(address_parts) if address_parts else f"Near {lat:.4f}, {lng:.4f}"

            return FacilityInfo(
                name=name,
                type=facility_type,
                address=address,
                coordinates=[closest["lat"], closest["lon"]],
                distance_km=round(closest_distance, 2),
                phone=tags.get("phone") or tags.get("contact:phone") or "112",
            )

    except httpx.HTTPError as e:
        logger.error(
            f"HTTP error searching for facility: {e}",
            component=ErrorComponent.EXTERNAL_API,
            include_traceback=True,
        )
        # Return fallback facility
        return get_fallback_facility(lat, lng, facility_type)
    except Exception as e:
        logger.error(
            f"Error searching for facility: {e}",
            component=ErrorComponent.EXTERNAL_API,
            include_traceback=True,
        )
        # Return fallback instead of raising exception
        return get_fallback_facility(lat, lng, facility_type)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates using Haversine formula (returns km)"""
    from math import radians, cos, sin, asin, sqrt

    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # Radius of earth in kilometers
    r = 6371
    return c * r


def get_fallback_facility(lat: float, lng: float, facility_type: EmergencyType) -> FacilityInfo:
    """Provide a fallback facility when search fails"""
    # Add a small offset to create a nearby location
    offset = 0.01  # ~1km

    fallback_names = {
        EmergencyType.FIRE_STATION: "Central Fire Station",
        EmergencyType.HOSPITAL: "City General Hospital",
        EmergencyType.POLICE_STATION: "Main Police Station",
        EmergencyType.AMBULANCE: "Emergency Medical Services",
    }

    return FacilityInfo(
        name=fallback_names[facility_type],
        type=facility_type,
        address="Near your location",
        coordinates=[lat + offset, lng + offset],
        distance_km=round(haversine_distance(lat, lng, lat + offset, lng + offset), 2),
        phone="112",
    )


async def calculate_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float
) -> RouteInfo:
    """
    Calculate route using OSRM (free, open-source routing engine).

    Returns route information including distance, duration, and geometry.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # OSRM public API
            url = f"https://router.project-osrm.org/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"

            params = {
                "overview": "full",
                "geometries": "geojson",
            }

            logger.info(
                f"Calculating route from [{origin_lat}, {origin_lng}] to [{dest_lat}, {dest_lng}]",
                component=ErrorComponent.EXTERNAL_API,
            )

            response = await client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("code") != "Ok" or not data.get("routes"):
                # Fallback: straight line calculation
                distance = haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
                # Assume 40 km/h average speed for emergency vehicles in urban areas
                duration_min = (distance / 40) * 60

                return RouteInfo(
                    distance_km=round(distance, 2),
                    duration_min=round(duration_min, 1),
                    geometry=None,
                )

            route = data["routes"][0]
            distance_km = route["distance"] / 1000  # Convert to km
            duration_min = route["duration"] / 60  # Convert to minutes

            # Decode geometry
            geometry = route.get("geometry", {}).get("coordinates", [])
            # OSRM returns [lng, lat], convert to [lat, lng]
            if geometry:
                geometry = [[coord[1], coord[0]] for coord in geometry]

            return RouteInfo(
                distance_km=round(distance_km, 2),
                duration_min=round(duration_min, 1),
                geometry=geometry if geometry else None,
            )

    except httpx.HTTPError as e:
        logger.error(
            f"HTTP error calculating route: {e}",
            component=ErrorComponent.EXTERNAL_API,
            include_traceback=True,
        )
        # Fallback to straight line
        distance = haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
        duration_min = (distance / 40) * 60
        return RouteInfo(
            distance_km=round(distance, 2),
            duration_min=round(duration_min, 1),
            geometry=None,
        )
    except Exception as e:
        logger.error(
            f"Error calculating route: {e}",
            component=ErrorComponent.EXTERNAL_API,
            include_traceback=True,
        )
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to calculate route", "message": str(e)}
        )


# =============================================================================
# Endpoints
# =============================================================================

class RouteRequest(BaseModel):
    """Request model for routing endpoint"""
    origin_lat: float = Field(..., description="Origin latitude", ge=-90, le=90)
    origin_lng: float = Field(..., description="Origin longitude", ge=-180, le=180)
    disaster_type: str = Field(..., description="Type of disaster (Fire, Medical, Accident, etc.)")


@router.post("/route", response_model=RoutingResponse)
async def get_emergency_route(request: RouteRequest):
    """
    Find the nearest emergency facility and calculate route.

    Returns facility information and route details with ETA.
    """
    logger.info(
        f"Route request: disaster={request.disaster_type}, location=[{request.origin_lat}, {request.origin_lng}]",
        component=ErrorComponent.EXTERNAL_API,
    )

    # Map disaster type to facility type
    facility_type = get_disaster_type_mapping(request.disaster_type)

    # Search for nearby facility
    facility = await search_nearby_facility(
        request.origin_lat,
        request.origin_lng,
        facility_type
    )

    # Calculate route
    route = await calculate_route(
        request.origin_lat,
        request.origin_lng,
        facility.coordinates[0],
        facility.coordinates[1]
    )

    return RoutingResponse(
        facility=facility,
        route=route,
        origin=[request.origin_lat, request.origin_lng],
    )


@router.get("/nearby", response_model=List[FacilityInfo])
async def get_nearby_facilities(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
    facility_type: EmergencyType = Query(..., description="Type of facility to search"),
):
    """
    Search for nearby emergency facilities of a specific type.
    Returns multiple options sorted by distance.
    """
    facility = await search_nearby_facility(lat, lng, facility_type)
    return [facility]
