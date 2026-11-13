"""
test_agent.py - Comprehensive Zero-Dependency Unit Test Suite

Fulfills Requirement 7: Tests: fake LLM first, then a real one (📘 L8).
Verifies all 7 Core Principles using Python's standard 'unittest' module:
1. ReAct Loop (think -> act -> look)
2. 4 Grounded Tools
3. Error Recovery & Self-Correction
4. Persistent Cross-Session Memory
5. Pre-Action Task Planning
6. Safety Guardrails (HITL, Step Limit, Audit Log)
7. PRD Section 11 Table Format Compliance
"""

import unittest
import os
import json
import shutil
from typing import Dict, Any

from models import DestinationDataLoader, TravelerProfile
from tools import ToolRegistry, haversine_distance
from memory import PersistentMemoryStore
from planner import TaskPlanner
from safety import AuditLogger, StepLimiter, HITLManager
from travel_agent import ReActAgent, MockLLMClient


class TestTravelPlannerAgent(unittest.TestCase):
    """
    Zero-dependency test suite validating all core agentic requirements.
    Runs 100% offline using deterministic Fake LLM emulation.
    """

    def setUp(self):
        self.test_dir = "test_workspace"
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_memory_file = os.path.join(self.test_dir, "test_traveler_memory.json")
        self.test_audit_file = os.path.join(self.test_dir, "test_agent_audit.jsonl")
        self.test_export_file = os.path.join(self.test_dir, "test_itinerary_export.md")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        # Clean any default artifacts if created
        for f in ["jaipur_2day_relaxed_itinerary.md", "test_itinerary_export.md"]:
            if os.path.exists(f):
                os.remove(f)

    # -------------------------------------------------------------------------
    # 1️⃣ Core Loop: think → act → look (📘 L1, L3)
    # -------------------------------------------------------------------------
    def test_react_loop_progression(self):
        """Validates that each step executes the full think -> act -> look cycle."""
        audit = AuditLogger(self.test_audit_file)
        agent = ReActAgent(
            audit_logger=audit,
            hitl_manager=HITLManager(auto_approve=True)
        )
        result = agent.run("I want to visit Jaipur for 2 days. I like history and relaxed pace.")

        self.assertGreater(result["steps_taken"], 0)
        self.assertIn("history", result)
        self.assertGreater(len(result["history"]), 0)

        # Inspect each step in the loop
        for step in result["history"]:
            self.assertIn("step", step)
            self.assertIn("thought", step)
            self.assertIn("action", step)
            self.assertIn("observation", step)
            self.assertTrue(len(step["thought"]) > 0, "Thought must not be empty.")
            self.assertIsNotNone(step["action"], "Action must be defined during loop.")
            self.assertIsNotNone(step["observation"], "Observation must be captured.")

    # -------------------------------------------------------------------------
    # 2️⃣ 2–4 Tools, Clearly Described (📘 L2)
    # -------------------------------------------------------------------------
    def test_tool_registry_valid_dispatch(self):
        """Validates that all 4 tools execute properly with valid parameters."""
        tools = ToolRegistry()
        self.assertEqual(len(tools.get_tool_names()), 4)
        self.assertIn("search_places", tools.get_tool_names())
        self.assertIn("get_travel_time", tools.get_tool_names())
        self.assertIn("check_venue_details", tools.get_tool_names())
        self.assertIn("save_itinerary", tools.get_tool_names())

        # Tool 1: search_places
        res1 = tools.execute("search_places", destination="Jaipur", category="attraction")
        self.assertEqual(res1.get("status"), "SUCCESS")
        self.assertGreater(res1.get("count", 0), 0)

        # Tool 2: get_travel_time
        res2 = tools.execute("get_travel_time", origin="Hawa Mahal", destination="Amber Palace", mode="driving")
        self.assertEqual(res2.get("status"), "SUCCESS")
        self.assertGreater(res2.get("distance_km", 0), 0)
        self.assertGreater(res2.get("duration_mins", 0), 0)

        # Tool 3: check_venue_details
        res3 = tools.execute("check_venue_details", venue_name="City Palace")
        self.assertEqual(res3.get("status"), "SUCCESS")
        self.assertEqual(res3.get("price_level"), "$$$")
        self.assertTrue(res3.get("verified"))

        # Tool 4: save_itinerary
        res4 = tools.execute("save_itinerary", filename=self.test_export_file, content="# Test Itinerary")
        self.assertEqual(res4.get("status"), "SUCCESS")
        self.assertTrue(os.path.exists(self.test_export_file))

    # -------------------------------------------------------------------------
    # 3️⃣ Fixing Errors When a Tool Fails (📘 L2)
    # -------------------------------------------------------------------------
    def test_error_handling_and_self_correction(self):
        """Validates that tool errors return actionable payloads and the agent self-corrects."""
        tools = ToolRegistry()

        # Tool error 1: Unknown venue
        err_venue = tools.execute("check_venue_details", venue_name="NonExistentFort")
        self.assertEqual(err_venue.get("status"), "ERROR")
        self.assertEqual(err_venue.get("error_code"), "VENUE_NOT_FOUND")
        self.assertIn("suggested_alternatives", err_venue)

        # Tool error 2: Unknown travel location
        err_loc = tools.execute("get_travel_time", origin="Atlantis", destination="Amber Palace")
        self.assertEqual(err_loc.get("status"), "ERROR")
        self.assertEqual(err_loc.get("error_code"), "LOCATION_NOT_FOUND")
        self.assertIn("available_locations", err_loc)

        # Verify agent self-correction ReAct loop
        audit = AuditLogger(self.test_audit_file)
        agent = ReActAgent(
            audit_logger=audit,
            llm_client=MockLLMClient(simulate_tool_error=True),
            hitl_manager=HITLManager(auto_approve=True)
        )
        result = agent.run("Test recovery")
        self.assertEqual(result["history"][0]["observation"]["status"], "ERROR")
        self.assertEqual(result["history"][0]["observation"]["error_code"], "VENUE_NOT_FOUND")
        # Step 2 thought must demonstrate self-correction analysis
        self.assertIn("self-correct", result["history"][1]["thought"].lower())
        self.assertEqual(result["history"][1]["action"]["args"]["venue_name"], "City Palace")

    # -------------------------------------------------------------------------
    # 4️⃣ Memory Between Tasks (📘 L4)
    # -------------------------------------------------------------------------
    def test_memory_persistence(self):
        """Validates cross-session memory persistence and exclusion of visited places."""
        mem = PersistentMemoryStore(self.test_memory_file)
        mem.clear()
        mem.update_profile(default_pace="relaxed", budget_level="moderate")
        mem.add_visited_place("Jantar Mantar")

        # Reload store to simulate new session
        new_session_mem = PersistentMemoryStore(self.test_memory_file)
        profile = new_session_mem.get_profile()
        self.assertEqual(profile.default_pace, "relaxed")
        self.assertIn("Jantar Mantar", profile.visited_places)

        # Agent should pass visited places to search tool as exclusions
        tools = ToolRegistry()
        res = tools.execute(
            "search_places",
            destination="Jaipur",
            category="attraction",
            exclude_names=profile.visited_places
        )
        returned_names = [p["name"] for p in res.get("places", [])]
        self.assertNotIn("Jantar Mantar", returned_names)

    # -------------------------------------------------------------------------
    # 5️⃣ A Plan Before It Acts (📘 L5)
    # -------------------------------------------------------------------------
    def test_planner_decomposition(self):
        """Validates that a 5-milestone roadmap is formulated before actions occur."""
        planner = TaskPlanner()
        profile = TravelerProfile(name="Traveler", default_pace="relaxed", visited_places=["Jantar Mantar"])
        milestones = planner.formulate_plan("Trip to Jaipur for 2 days relaxed", profile)

        self.assertEqual(len(milestones), 5)
        self.assertEqual(milestones[0].status, "IN_PROGRESS")
        self.assertIn("Extraction", milestones[0].title)
        self.assertIn("Discovery", milestones[1].title)
        self.assertIn("Logistics", milestones[2].title)
        self.assertIn("Synthesis", milestones[3].title)
        self.assertIn("Presentation", milestones[4].title)

        formatted_plan = planner.format_plan_for_prompt()
        self.assertIn("A Plan Before It Acts", formatted_plan)
        self.assertIn("Milestone 1", formatted_plan)

    # -------------------------------------------------------------------------
    # 6️⃣ Safety: Asks You First, Step Limit, Log (📘 L7)
    # -------------------------------------------------------------------------
    def test_hitl_safety_rejection(self):
        """Validates that human denial prevents state-modifying disk writes."""
        audit = AuditLogger(self.test_audit_file)
        agent = ReActAgent(
            audit_logger=audit,
            hitl_manager=HITLManager(auto_reject=True)  # Deny approval
        )
        result = agent.run("Save plan")
        self.assertTrue(result["hitl_prompted"])
        self.assertFalse(result["hitl_approved"])

        # Locate the save_itinerary step in history
        save_steps = [s for s in result["history"] if s["action"] and s["action"]["tool"] == "save_itinerary"]
        self.assertGreater(len(save_steps), 0)
        self.assertEqual(save_steps[0]["observation"]["status"], "DENIED")
        self.assertFalse(os.path.exists("jaipur_2day_relaxed_itinerary.md"))

    def test_hitl_safety_approval(self):
        """Validates that human approval permits save_itinerary execution."""
        audit = AuditLogger(self.test_audit_file)
        agent = ReActAgent(
            audit_logger=audit,
            hitl_manager=HITLManager(auto_approve=True)  # Grant approval
        )
        result = agent.run("Save plan")
        self.assertTrue(result["hitl_prompted"])
        self.assertTrue(result["hitl_approved"])
        self.assertTrue(os.path.exists("jaipur_2day_relaxed_itinerary.md"))

    def test_step_limit_guardrail(self):
        """Validates that runaway loops are halted when max_steps is reached."""
        limiter = StepLimiter(max_steps=3)
        audit = AuditLogger(self.test_audit_file)
        agent = ReActAgent(
            step_limiter=limiter,
            audit_logger=audit,
            hitl_manager=HITLManager(auto_approve=True)
        )
        result = agent.run("Loop test")
        self.assertEqual(result["steps_taken"], 3)
        self.assertTrue(limiter.is_exceeded())
        self.assertIn("Step limit (8 steps) reached", result["final_answer"])

    def test_audit_log_generation(self):
        """Validates that every step generates a valid, structured JSON record in audit log."""
        audit = AuditLogger(self.test_audit_file)
        audit.clear()
        agent = ReActAgent(
            audit_logger=audit,
            hitl_manager=HITLManager(auto_approve=True)
        )
        agent.run("Jaipur trip")

        logs = audit.read_logs()
        self.assertGreater(len(logs), 0)
        for entry in logs:
            self.assertIn("timestamp", entry)
            self.assertIn("session_id", entry)
            self.assertIn("step_index", entry)
            self.assertIn("thought", entry)
            self.assertIn("hitl_status", entry)

    # -------------------------------------------------------------------------
    # PRD Section 11 Compliance
    # -------------------------------------------------------------------------
    def test_prd_section_11_compliance(self):
        """Validates that the final itinerary adheres strictly to PRD Section 11 layout."""
        agent = ReActAgent(hitl_manager=HITLManager(auto_approve=True))
        result = agent.run("2-day Jaipur itinerary")
        itinerary = result["final_answer"]

        # PRD Section 11 required headings
        self.assertIn("### Trip overview", itinerary)
        self.assertIn("### Day 1", itinerary)
        self.assertIn("### Day 2", itinerary)
        self.assertIn("### Why this plan fits", itinerary)
        self.assertIn("### Please verify", itinerary)
        self.assertIn("### Sources", itinerary)

        # Tabular structure
        self.assertIn("| Time | Plan | Location | Travel / notes |", itinerary)


if __name__ == "__main__":
    unittest.main()

