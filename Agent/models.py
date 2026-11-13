"""
models.py - Core Data Models and Types for Travel Itinerary Planner Agent

Defines strongly-typed dataclasses for places, travel estimates, itinerary schedules,
traveler profile memory, and data-loading utilities.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any


@dataclass
class PlaceRecord:
    """Represents a grounded physical venue, attraction, or food establishment."""
    id: str
    name: str
    category: str  # attraction | food | culture | nature
    tags: List[str]
    address: str
    lat: float
    lng: float
    typical_duration_mins: int
    price_level: str  # $, $$, $$$
    ticket_price_inr: float
    operating_hours: str
    open_days: List[str]
    rating: float
    accessibility: str
    verified: bool
    last_verified: str
    source_url: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlaceRecord:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            category=data.get("category", "attraction"),
            tags=data.get("tags", []),
            address=data.get("address", ""),
            lat=float(data.get("lat", 0.0)),
            lng=float(data.get("lng", 0.0)),
            typical_duration_mins=int(data.get("typical_duration_mins", 60)),
            price_level=data.get("price_level", "$"),
            ticket_price_inr=float(data.get("ticket_price_inr", 0.0)),
            operating_hours=data.get("operating_hours", "Check locally"),
            open_days=data.get("open_days", []),
            rating=float(data.get("rating", 4.0)),
            accessibility=data.get("accessibility", "Not verified"),
            verified=bool(data.get("verified", False)),
            last_verified=data.get("last_verified", ""),
            source_url=data.get("source_url", "")
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TravelEstimate:
    """Transit calculation between two locations."""
    origin: str
    destination: str
    distance_km: float
    duration_mins: int
    mode: str  # driving | walking | transit
    notes: str = ""
    is_estimate: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ItineraryItem:
    """A single scheduled activity or meal break within an itinerary."""
    time_slot: str
    plan: str
    location: str
    travel_notes: str
    why_selected: str
    is_estimate: bool = True
    verified: bool = False
    source_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DayPlan:
    """A collection of scheduled activities for one day."""
    day_number: int
    title: str
    items: List[ItineraryItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day_number": self.day_number,
            "title": self.title,
            "items": [item.to_dict() for item in self.items]
        }


@dataclass
class TripOverview:
    """High-level summary of the planned trip."""
    destination: str
    duration_days: int
    budget: str
    pace: str
    assumptions_or_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TravelerProfile:
    """Cross-session traveler preferences and history."""
    name: str = "Traveler"
    default_pace: str = "relaxed"
    dietary_preferences: str = "vegetarian"
    budget_level: str = "moderate"
    mobility_needs: str = "none"
    visited_places: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TravelerProfile:
        return cls(
            name=data.get("name", "Traveler"),
            default_pace=data.get("default_pace", "relaxed"),
            dietary_preferences=data.get("dietary_preferences", "vegetarian"),
            budget_level=data.get("budget_level", "moderate"),
            mobility_needs=data.get("mobility_needs", "none"),
            visited_places=data.get("visited_places", [])
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DestinationDataLoader:
    """
    Loads destination datasets from disk (e.g., data/jaipur_places.json).
    Supports loading any city if its JSON dataset is present, or falling back
    to Jaipur as the primary MVP reference city.
    """
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self._cache: Dict[str, List[PlaceRecord]] = {}

    def load_places(self, destination: str = "Jaipur") -> List[PlaceRecord]:
        dest_normalized = destination.strip().lower()
        # Common city alias mappings
        alias_map = {
            "calicut": "kozhikode",
            "bombay": "mumbai",
            "bengaluru": "bangalore",
            "madras": "chennai",
            "calcutta": "kolkata",
            "banaras": "varanasi",
            "kashi": "varanasi"
        }
        dest_key = alias_map.get(dest_normalized, dest_normalized)

        if dest_key in self._cache:
            return self._cache[dest_key]

        filepath = os.path.join(self.data_dir, f"{dest_key}_places.json")

        # Also search other JSON files in data_dir to match destination or aliases
        if not os.path.exists(filepath) and os.path.isdir(self.data_dir):
            for fname in os.listdir(self.data_dir):
                if fname.endswith("_places.json"):
                    cand_path = os.path.join(self.data_dir, fname)
                    try:
                        with open(cand_path, "r", encoding="utf-8") as f:
                            cand_data = json.load(f)
                            cand_dest = cand_data.get("destination", "").lower()
                            cand_aliases = [a.lower() for a in cand_data.get("aliases", [])]
                            # Match if destination key/normalized name is in aliases list OR
                            # if the destination name appears as a substring of any alias
                            alias_match = dest_normalized in cand_aliases or dest_key in cand_aliases
                            partial_match = any(dest_normalized in a or a in dest_normalized for a in cand_aliases if len(a) > 3)
                            if dest_key in cand_dest or alias_match or partial_match or cand_dest in dest_key:
                                filepath = cand_path
                                break
                    except Exception:
                        pass

        if not os.path.exists(filepath):
            return []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            places_raw = data.get("places", [])
            records = [PlaceRecord.from_dict(p) for p in places_raw]
            self._cache[dest_key] = records
            self._cache[dest_normalized] = records
            return records
        except Exception:
            return []

    def get_place_by_name(self, destination: str, name: str) -> Optional[PlaceRecord]:
        places = self.load_places(destination)
        name_lower = name.strip().lower()
        for p in places:
            if name_lower in p.name.lower() or name_lower in p.id.lower():
                return p
        return None

