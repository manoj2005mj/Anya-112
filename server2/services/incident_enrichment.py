"""Normalize incident metadata so the dashboard can always render useful state."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

import httpx

from server2.logging_utils import ErrorComponent, get_logger

logger = get_logger("anya.server2.services.incident_enrichment")

JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)
LOCATION_PATTERNS = [
    re.compile(r"\b(?:at|in|near|from)\s+([A-Z][A-Za-z0-9 .,'()/-]{2,80}?)(?:[,.!?]|$)"),
    re.compile(r"\blocation(?:\s+is|\s*:)?\s+([A-Z][A-Za-z0-9 .,'()/-]{2,80}?)(?:[,.!?]|$)", re.IGNORECASE),
]

KNOWN_LOCATION_FALLBACKS: dict[str, list[float]] = {
    "tumkur": [13.3409, 77.1010],
    "gss bhavan in tumkur": [13.3409, 77.1010],
    "bengaluru": [12.9716, 77.5946],
    "bangalore": [12.9716, 77.5946],
    "new delhi": [28.6139, 77.2090],
    "delhi": [28.6139, 77.2090],
    "mumbai": [19.0760, 72.8777],
    "chennai": [13.0827, 80.2707],
    "hyderabad": [17.3850, 78.4867],
    "kolkata": [22.5726, 88.3639],
}

DEPARTMENT_SYNONYMS = {
    "police": "Police",
    "law enforcement": "Police",
    "fire": "Fire",
    "fire brigade": "Fire",
    "ambulance": "Ambulance",
    "medical": "Ambulance",
    "paramedic": "Ambulance",
    "hospital": "Ambulance",
    "electrical": "Electrical",
    "power": "Electrical",
    "utility": "Electrical",
    "disaster response": "Disaster Response",
    "rescue": "Disaster Response",
    "ndrf": "Disaster Response",
}

KEYWORD_ENTITIES = [
    "fire",
    "smoke",
    "burn",
    "injury",
    "injured",
    "bleeding",
    "unconscious",
    "trapped",
    "accident",
    "crash",
    "collision",
    "theft",
    "assault",
    "violence",
    "gas leak",
    "live wire",
    "electrical",
    "flood",
    "collapse",
]


def _strip_json_block(text: str) -> str:
    return JSON_BLOCK_RE.sub("", text).strip()


def _parse_json_block(text: str) -> dict[str, Any]:
    match = JSON_BLOCK_RE.search(text)
    if not match:
        return {}

    try:
        parsed = json.loads(match.group(1))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        logger.warning(
            "Failed to parse model JSON block",
            component=ErrorComponent.GEMINI_LLM,
        )
        return {}


def _normalize_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).strip(" ,.")
    return cleaned or None


def _normalize_coordinates(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None

    try:
        lat = float(value[0])
        lng = float(value[1])
    except (TypeError, ValueError):
        return None

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None

    return [round(lat, 6), round(lng, 6)]


def _title_case(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if not lowered:
        return None
    return lowered.capitalize()


def _normalize_disaster_type(value: Any, text: str) -> str | None:
    direct = _normalize_text(value)
    sample = (direct or text).lower()

    if any(token in sample for token in ("fire", "smoke", "burn", "blaze")):
        return "Fire"
    if any(token in sample for token in ("injury", "medical", "heart", "bleed", "unconscious", "ambulance")):
        return "Medical"
    if any(token in sample for token in ("accident", "crash", "collision", "vehicle")):
        return "Accident"
    if any(token in sample for token in ("theft", "crime", "assault", "violence", "police")):
        return "Crime"
    if any(token in sample for token in ("electric", "power", "live wire", "transformer")):
        return "Infrastructure"
    if any(token in sample for token in ("flood", "landslide", "collapse", "earthquake")):
        return "Disaster"

    return direct


def _normalize_department(value: Any) -> str | None:
    name = _normalize_text(value)
    if not name:
        return None

    lowered = name.lower()
    for token, canonical in DEPARTMENT_SYNONYMS.items():
        if token in lowered:
            return canonical

    return name.title()


def _normalize_departments(value: Any, disaster_type: str | None, text: str) -> list[str]:
    departments: list[str] = []

    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        for item in value:
            normalized = _normalize_department(item)
            if normalized and normalized not in departments:
                departments.append(normalized)

    source = text.lower()
    if disaster_type == "Fire":
        for item in ("Fire", "Ambulance"):
            if item not in departments:
                departments.append(item)
    elif disaster_type == "Medical":
        if "Ambulance" not in departments:
            departments.append("Ambulance")
    elif disaster_type == "Accident":
        for item in ("Ambulance", "Police"):
            if item not in departments:
                departments.append(item)
    elif disaster_type == "Crime":
        if "Police" not in departments:
            departments.append("Police")
    elif disaster_type in {"Infrastructure", "Disaster"}:
        for item in ("Electrical", "Disaster Response"):
            if item not in departments:
                departments.append(item)

    if any(token in source for token in ("trapped", "collapse", "flood")) and "Disaster Response" not in departments:
        departments.append("Disaster Response")
    if any(token in source for token in ("injured", "bleeding", "unconscious")) and "Ambulance" not in departments:
        departments.append("Ambulance")
    if any(token in source for token in ("electrical", "power", "live wire")) and "Electrical" not in departments:
        departments.append("Electrical")

    return departments


def _normalize_severity(value: Any, text: str, disaster_type: str | None) -> str | None:
    direct = _normalize_text(value)
    if direct:
        severity_map = {
            "low": "Low",
            "medium": "Medium",
            "moderate": "Medium",
            "high": "High",
            "critical": "Critical",
            "severe": "Critical",
        }
        mapped = severity_map.get(direct.lower())
        if mapped:
            return mapped

    source = text.lower()
    people_match = re.search(r"\b(\d+)\s*(?:people|persons|ppl|members)\b", source)
    people_count = int(people_match.group(1)) if people_match else 0

    if any(token in source for token in ("unconscious", "trapped", "not breathing", "major fire", "explosion")):
        return "Critical"
    if disaster_type == "Fire" and people_count >= 3:
        return "Critical"
    if any(token in source for token in ("fire", "bleeding", "injured", "accident", "crash", "gas leak")):
        return "High"
    if any(token in source for token in ("assault", "theft", "power", "electrical", "flood")):
        return "Medium"

    return "Low" if disaster_type else None


def _extract_location(text: str) -> str | None:
    for pattern in LOCATION_PATTERNS:
        for match in pattern.finditer(text):
            candidate = _normalize_text(match.group(1))
            if candidate and candidate.lower() not in {"my house", "home", "here", "there"}:
                return candidate
    return None


def _extract_entities(text: str, existing: Any) -> list[str]:
    entities: list[str] = []

    if isinstance(existing, Iterable) and not isinstance(existing, (str, bytes, dict)):
        for item in existing:
            normalized = _normalize_text(item)
            if normalized and normalized not in entities:
                entities.append(normalized)

    lowered = text.lower()
    for token in KEYWORD_ENTITIES:
        if token in lowered and token not in entities:
            entities.append(token)

    people_match = re.search(r"\b(\d+)\s*(?:people|persons|ppl|members)\b", lowered)
    if people_match:
        entity = f"{people_match.group(1)} people"
        if entity not in entities:
            entities.append(entity)

    return entities


async def _geocode_location(location: str | None) -> list[float] | None:
    if not location:
        return None

    lowered = location.lower()
    for known_name, coordinates in KNOWN_LOCATION_FALLBACKS.items():
        if known_name in lowered:
            return coordinates

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": f"{location}, India",
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "in",
                },
                headers={"User-Agent": "Anya-Emergency-Dispatch/1.0"},
            )
            response.raise_for_status()
            results = response.json()
            if not results:
                return None

            first = results[0]
            return _normalize_coordinates([first.get("lat"), first.get("lon")])
    except Exception as exc:
        logger.warning(
            f"Geocoding failed for location '{location}': {exc}",
            component=ErrorComponent.EXTERNAL_API,
        )
        return None


def _build_json_block(payload: dict[str, Any]) -> str:
    return "```json\n" + json.dumps(payload, ensure_ascii=True, indent=2) + "\n```"


async def enrich_incident_response(
    response_text: str,
    user_message: str,
    history: list[Any] | None = None,
) -> str:
    """Append a normalized incident JSON block so the frontend can render reliably."""

    parsed = _parse_json_block(response_text)

    history_text_parts: list[str] = []
    for item in history or []:
        if isinstance(item, dict):
            parts = item.get("parts") or []
            for part in parts:
                if isinstance(part, dict):
                    text = _normalize_text(part.get("text"))
                    if text:
                        history_text_parts.append(text)

    combined_text = " ".join(
        part for part in [_strip_json_block(response_text), user_message, *history_text_parts] if part
    )

    location = _normalize_text(parsed.get("incident_location")) or _extract_location(combined_text)
    disaster_type = _normalize_disaster_type(parsed.get("disaster_type"), combined_text)
    coordinates = _normalize_coordinates(parsed.get("coordinates"))
    if not coordinates:
        coordinates = await _geocode_location(location)

    payload = {
        "incident_location": location,
        "coordinates": coordinates,
        "disaster_type": disaster_type,
        "departments_required": _normalize_departments(parsed.get("departments_required"), disaster_type, combined_text),
        "severity": _normalize_severity(parsed.get("severity"), combined_text, disaster_type),
        "extracted_entities": _extract_entities(combined_text, parsed.get("extracted_entities")),
    }

    base_text = _strip_json_block(response_text)
    if not any(
        (
            payload["incident_location"],
            payload["coordinates"],
            payload["disaster_type"],
            payload["departments_required"],
            payload["severity"],
            payload["extracted_entities"],
        )
    ):
        return base_text

    if base_text:
        return f"{base_text}\n\n{_build_json_block(payload)}"
    return _build_json_block(payload)
