"""
planner.py - Pre-Action Task Planning Engine

Fulfills Requirement 5: A plan before it acts (📘 L5).
Decomposes user requests into an explicit 5-milestone roadmap before executing tool actions.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from models import TravelerProfile


@dataclass
class Milestone:
    """Represents a discrete milestone in the agent's pre-action roadmap."""
    id: int
    title: str
    description: str
    status: str = "PENDING"  # PENDING | IN_PROGRESS | COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TaskPlanner:
    """
    Decomposes the traveler's request into a structured milestone roadmap
    before the ReAct execution loop takes action.
    """
    def __init__(self):
        self.milestones: List[Milestone] = []
        self.current_milestone_index: int = 0
        self.extracted_params: Dict[str, Any] = {}

    def formulate_plan(self, user_request: str, profile: Optional[TravelerProfile] = None) -> List[Milestone]:
        """
        Analyzes the traveler request and formulates a 5-milestone execution roadmap.
        """
        self.extracted_params = self._extract_parameters(user_request, profile)

        dest = self.extracted_params.get("destination", "Jaipur")
        days = self.extracted_params.get("duration_days", 2)
        pace = self.extracted_params.get("pace", "relaxed")
        budget = self.extracted_params.get("budget", "moderate")
        interests = ", ".join(self.extracted_params.get("interests", ["history", "culture"]))
        visited = profile.visited_places if profile else []
        visited_str = f" (excluding previously visited: {', '.join(visited)})" if visited else ""

        self.milestones = [
            Milestone(
                id=1,
                title="Trip Parameter Extraction & Memory Retrieval",
                description=f"Confirm trip to {dest} for {days} days at a {pace} pace and {budget} budget{visited_str}."
            ),
            Milestone(
                id=2,
                title="Candidate Attraction & Dining Discovery",
                description=f"Query places matching interests [{interests}] and dining options matching preferences."
            ),
            Milestone(
                id=3,
                title="Logistics & Operating Hours Verification",
                description="Check venue opening hours, ticket pricing, and compute transit times between adjacent stops."
            ),
            Milestone(
                id=4,
                title="Itinerary Synthesis & Geographic Clustering",
                description="Assemble day-by-day schedules with meal breaks and travel buffers following PRD Section 11 layout."
            ),
            Milestone(
                id=5,
                title="Presentation & Human-in-the-Loop Export",
                description="Present finalized itinerary with verification warnings and prompt for HITL approval before saving."
            )
        ]

        self.current_milestone_index = 0
        if self.milestones:
            self.milestones[0].status = "IN_PROGRESS"

        return self.milestones

    def _extract_parameters(self, request: str, profile: Optional[TravelerProfile]) -> Dict[str, Any]:
        """Extracts basic trip parameters from text using heuristic regex matching."""
        req_lower = request.lower()

        # Destination
        dest = "Jaipur"
        # Match explicit city patterns
        dest_match = re.search(r'(?:in|to|for|visit|visiting)\s+([a-zA-Z\s]+?)(?:\s+for|\s+with|\s+trip|\s+itinerary|\s+in|\s*\.|\s*,|\s*$)', req_lower)
        if dest_match:
            candidate_dest = dest_match.group(1).strip()
            # Avoid matching words like 'a', 'the', 'two', 'three', '2', '3'
            if candidate_dest and not re.match(r'^(?:a|an|the|\d+|one|two|three|four|five|my|our)$', candidate_dest):
                dest = candidate_dest.title()
        elif "jaipur" in req_lower:
            dest = "Jaipur"
        elif "paris" in req_lower:
            dest = "Paris"
        elif "delhi" in req_lower:
            dest = "Delhi"
        elif "mumbai" in req_lower:
            dest = "Mumbai"
        elif "tokyo" in req_lower:
            dest = "Tokyo"
        elif "london" in req_lower:
            dest = "London"

        # Duration (days)
        duration = 2
        # Accept the common forms produced by the website and natural language:
        # "3-day", "3 days", "three-day", and "three days".
        day_match = re.search(r'\b(\d+)\s*[- ]?\s*days?\b', req_lower)
        if day_match:
            duration = int(day_match.group(1))
        else:
            written_days = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
            written_match = re.search(
                r'\b(' + '|'.join(written_days) + r')\s*[- ]?\s*days?\b', req_lower
            )
            if written_match:
                duration = written_days[written_match.group(1)]

        # Pace (user stated or memory default)
        pace = profile.default_pace if profile else "relaxed"
        if "relaxed" in req_lower or "slow" in req_lower or "leisurely" in req_lower:
            pace = "relaxed"
        elif "fast" in req_lower or "packed" in req_lower or "intense" in req_lower:
            pace = "fast"
        elif "moderate" in req_lower or "balanced" in req_lower:
            pace = "moderate"

        # Budget
        budget = profile.budget_level if profile else "moderate"
        if "budget" in req_lower or "cheap" in req_lower or "low cost" in req_lower:
            budget = "budget"
        elif "luxury" in req_lower or "high end" in req_lower:
            budget = "luxury"
        elif "moderate" in req_lower:
            budget = "moderate"

        # Interests
        interests = []
        for kw in ["history", "culture", "food", "nature", "scenic", "photography", "shopping", "architecture"]:
            if kw in req_lower:
                interests.append(kw)
        if not interests:
            interests = ["history", "culture", "food"]

        return {
            "destination": dest,
            "duration_days": duration,
            "pace": pace,
            "budget": budget,
            "interests": interests
        }

    def get_current_milestone(self) -> Optional[Milestone]:
        if 0 <= self.current_milestone_index < len(self.milestones):
            return self.milestones[self.current_milestone_index]
        return None

    def advance_milestone(self) -> Optional[Milestone]:
        """Marks current milestone COMPLETED and sets next milestone IN_PROGRESS."""
        if 0 <= self.current_milestone_index < len(self.milestones):
            self.milestones[self.current_milestone_index].status = "COMPLETED"
            self.current_milestone_index += 1
            if self.current_milestone_index < len(self.milestones):
                self.milestones[self.current_milestone_index].status = "IN_PROGRESS"
                return self.milestones[self.current_milestone_index]
        return None

    def is_complete(self) -> bool:
        return all(m.status == "COMPLETED" for m in self.milestones)

    def format_plan_for_prompt(self) -> str:
        """Renders the milestone roadmap for injection into the ReAct thought loop."""
        lines = ["=== EXECUTION PLAN (A Plan Before It Acts) ==="]
        for m in self.milestones:
            prefix = "[x]" if m.status == "COMPLETED" else ("[>]" if m.status == "IN_PROGRESS" else "[ ]")
            lines.append(f"{prefix} Milestone {m.id}: {m.title} - {m.description}")
        lines.append("===============================================")
        return "\n".join(lines)

