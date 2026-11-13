"""
memory.py - Persistent Cross-Session Memory Store

Fulfills Requirement 4: Memory between tasks (📘 L4).
Persists traveler profile preferences, pace, dietary needs, and previously visited places
across sessions in 'traveler_memory.json'.
"""

from __future__ import annotations
import json
import os
from typing import Dict, Any, List, Optional
from models import TravelerProfile


DEFAULT_MEMORY_FILE = "traveler_memory.json"


class PersistentMemoryStore:
    """
    Manages cross-session persistence of traveler preferences, historical trips,
    and visited locations.
    """
    def __init__(self, filepath: str = DEFAULT_MEMORY_FILE, persist: bool = True):
        self.filepath = filepath
        self.persist = persist
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """Loads memory state from disk or initializes default profile."""
        if self.persist and os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                    return self._data
            except Exception:
                pass

        # Default initial state
        self._data = {
            "traveler_profile": {
                "name": "Traveler",
                "default_pace": "relaxed",
                "dietary_preferences": "vegetarian",
                "budget_level": "moderate",
                "mobility_needs": "none"
            },
            # Visited places persisted from previous trip (e.g. Jantar Mantar already visited)
            "visited_places": ["Jantar Mantar"],
            "past_trips": []
        }
        self.save()
        return self._data

    def save(self) -> bool:
        """Saves current memory state to disk when persistence is enabled."""
        if not self.persist:
            return True
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get_profile(self) -> TravelerProfile:
        """Returns the TravelerProfile dataclass."""
        profile_data = self._data.get("traveler_profile", {})
        profile_data["visited_places"] = self.get_visited_places()
        return TravelerProfile.from_dict(profile_data)

    def update_profile(self, **kwargs) -> TravelerProfile:
        """Updates specific traveler profile fields (e.g. pace, budget)."""
        profile = self._data.setdefault("traveler_profile", {})
        for key, value in kwargs.items():
            if value is not None:
                profile[key] = value
        self.save()
        return self.get_profile()

    def get_visited_places(self) -> List[str]:
        """Returns the list of places the traveler has already visited."""
        return list(self._data.get("visited_places", []))

    def add_visited_place(self, place_name: str) -> None:
        """Records a venue as visited to avoid re-recommending in future tasks."""
        visited = self._data.setdefault("visited_places", [])
        if place_name not in visited:
            visited.append(place_name)
            self.save()

    def record_completed_trip(self, destination: str, duration_days: int, itinerary_summary: str) -> None:
        """Archives a completed trip into history."""
        trips = self._data.setdefault("past_trips", [])
        trips.append({
            "destination": destination,
            "duration_days": duration_days,
            "summary": itinerary_summary
        })
        self.save()

    def clear(self) -> None:
        """Resets memory to clean slate (useful for tests)."""
        self._data = {
            "traveler_profile": {
                "name": "Traveler",
                "default_pace": "moderate",
                "dietary_preferences": "none",
                "budget_level": "moderate",
                "mobility_needs": "none"
            },
            "visited_places": [],
            "past_trips": []
        }
        self.save()

