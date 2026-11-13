"""
cli.py - Interactive Terminal REPL for Travel Itinerary Planner Agent

Provides an intuitive CLI experience with:
1. Offline Simulated Mode (Deterministic Fake LLM, zero API key required)
2. Live Interactive Mode (local Ollama with Llama)
3. Direct Unit Test Suite Runner (runs test_agent.py)
4. Inspection of Audit Logs (agent_audit.jsonl) and Memory (traveler_memory.json)
"""

from __future__ import annotations
import os
import sys
import json
import time
import unittest
import urllib.request

from models import DestinationDataLoader
from tools import ToolRegistry
from memory import PersistentMemoryStore
from planner import TaskPlanner
from safety import AuditLogger, StepLimiter, HITLManager
from travel_agent import ReActAgent, MockLLMClient, LiveLLMClient, OllamaLLMClient, get_active_llm_client


def print_banner():
    banner = """
================================================================================
    ✈️  TRAVEL ITINERARY PLANNER AGENT (ReAct Agentic Workflow)
================================================================================
    [1] Think -> Act -> Look ReAct Loop
    [2] 4 Grounded Tools (Places, Transit, Hours, Save)
    [3] Error Recovery & Self-Correction
    [4] Cross-Session Memory (Preferences & Visited Places)
    [5] Pre-Action Task Planning (5 Milestones)
    [6] Safety Invariants (HITL Approval, Max 8 Steps, Audit Log)
    [7] Dual LLM Adapters: Google Gemini AI & Local Ollama / Llama
================================================================================
"""
    print(banner)


def run_offline_demo():
    """Runs a full, transparent step-by-step demonstration of the agent using Mock LLM."""
    print("\n--- [MODE 1: Offline Simulated Demonstration (Deterministic Fake LLM)] ---")
    print("Scenario: Traveler requesting a 2-day relaxed trip to Jaipur with history & food.")
    print("Memory Invariant: Jantar Mantar was previously visited and must be excluded.")
    print("--------------------------------------------------------------------------------\n")

    mem_store = PersistentMemoryStore("traveler_memory.json")
    mem_store.load()
    if "Jantar Mantar" not in mem_store.get_visited_places():
        mem_store.add_visited_place("Jantar Mantar")

    audit_logger = AuditLogger("agent_audit.jsonl")
    tools = ToolRegistry()
    planner = TaskPlanner()

    # Interactive HITL callback
    def hitl_prompt(action_name: str, args: dict) -> bool:
        print(f"\n🛑 [HITL SAFETY GATE] Agent is attempting to call: '{action_name}'")
        print(f"Target File: {args.get('filename')}")
        print("This operation will write data to disk.")
        try:
            resp = input("👉 Grant permission to write itinerary file? [y/N]: ").strip().lower()
            return resp in ["y", "yes"]
        except (EOFError, KeyboardInterrupt):
            return False

    hitl = HITLManager(approval_callback=hitl_prompt)
    agent = ReActAgent(
        tool_registry=tools,
        memory_store=mem_store,
        task_planner=planner,
        audit_logger=audit_logger,
        step_limiter=StepLimiter(max_steps=8),
        hitl_manager=hitl,
        llm_client=MockLLMClient()
    )

    print("Enter your trip prompt below (or press Enter for default 2-day relaxed trip):")
    custom_prompt = input("Traveler Prompt > ").strip()
    prompt = custom_prompt if custom_prompt else "I'm visiting Jaipur for two days. I like history, prefer a relaxed pace, and have a moderate budget."
    print(f"\nProcessing Prompt: \"{prompt}\"\n")

    result = agent.run(prompt)

    print("\n" + "=" * 80)
    print("EXECUTION COMPLETED")
    print("=" * 80)
    print(f"• Total Steps Taken: {result['steps_taken']}")
    print(f"• HITL Safety Prompted: {result['hitl_prompted']}")
    print(f"• HITL File Export Approved: {result['hitl_approved']}")
    print(f"• Milestones Completed: {len(result['milestones_completed'])} / 5")
    print("=" * 80)
    print("\n" + result["final_answer"])
    print("=" * 80)
    print("✅ Audit log recorded in: agent_audit.jsonl")
    print("✅ Traveler profile stored in: traveler_memory.json\n")


def run_live_mode():
    """Runs the interactive agent through Google Gemini or local Ollama."""
    print("\n--- [MODE 2: Live Interactive AI Mode] ---")
    live_client = get_active_llm_client()

    if isinstance(live_client, LiveLLMClient):
        print(f"🔗 Connected to Google Gemini: {live_client.model} ({live_client.api_version})")
    elif isinstance(live_client, OllamaLLMClient):
        print(f"🔗 Connected to local Ollama: {live_client.model} at {live_client.base_url}")
    else:
        # Prompt for Gemini API key if not yet set
        print("No active Gemini API key or local Ollama model found.")
        key_input = input("Enter your GEMINI_API_KEY (or press Enter for demo): ").strip().strip("'\"").strip()
        if key_input:
            os.environ["GEMINI_API_KEY"] = key_input
            live_client = LiveLLMClient(api_key=key_input)
            print(f"🔗 Connected to Google Gemini: {live_client.model}")
        else:
            print("Using offline demonstration planner.")
            live_client = MockLLMClient()

    mem_store = PersistentMemoryStore("traveler_memory.json")
    audit_logger = AuditLogger("agent_audit.jsonl")
    tools = ToolRegistry()
    planner = TaskPlanner()

    def hitl_prompt(action_name: str, args: dict) -> bool:
        print(f"\n🛑 [HITL SAFETY GATE] Agent requests permission for: {action_name}")
        print(f"Args: {json.dumps(args, indent=2)}")
        try:
            choice = input("Approve action? [y/N]: ").strip().lower()
            return choice in ["y", "yes"]
        except (EOFError, KeyboardInterrupt):
            return False

    agent = ReActAgent(
        tool_registry=tools,
        memory_store=mem_store,
        task_planner=planner,
        audit_logger=audit_logger,
        hitl_manager=HITLManager(approval_callback=hitl_prompt),
        llm_client=live_client
    )

    print("\nAgent initialized. Type your travel request (or 'exit' to return to menu):")
    while True:
        try:
            user_input = input("\nTraveler > ").strip()
            if not user_input or user_input.lower() in ["exit", "quit", "q"]:
                break

            print("\n🤖 Agent is planning and executing ReAct loop...")
            res = agent.run(user_input)
            print("\n" + res["final_answer"])

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error during live execution: {e}")
            print("Tip: Check your API key or network connection and try again.")


def run_unit_tests():
    """Executes the standard unit test suite."""
    print("\n--- [Running test_agent.py Unit Test Suite] ---")
    loader = unittest.TestLoader()
    suite = loader.discover(".", pattern="test_agent.py")
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)


def view_audit_logs():
    """Displays the most recent entries from agent_audit.jsonl."""
    print("\n--- [Recent Audit Log Records: agent_audit.jsonl] ---")
    audit = AuditLogger("agent_audit.jsonl")
    logs = audit.read_logs()
    if not logs:
        print("No audit logs found yet. Run a planning scenario first.")
        return

    print(f"Total audit entries: {len(logs)}. Showing last 5:\n")
    for entry in logs[-5:]:
        step = entry.get("step_index")
        action = entry.get("action")
        tool = action.get("tool") if action else "Final Answer"
        hitl = entry.get("hitl_status")
        print(f"• [Step {step}] | Tool: {tool} | HITL: {hitl} | Timestamp: {entry.get('timestamp')}")
        print(f"  Thought: {entry.get('thought')[:120]}...\n")


def view_memory_profile():
    """Displays current persisted traveler profile."""
    print("\n--- [Traveler Memory Profile: traveler_memory.json] ---")
    mem = PersistentMemoryStore("traveler_memory.json")
    data = mem.load()
    print(json.dumps(data, indent=2))


def run_diagnostic():
    """Checks Gemini API key and local Ollama status."""
    print("\n--- [DIAGNOSTIC: AI Providers] ---")
    active = get_active_llm_client()
    print(f"👉 Default Active Provider: {type(active).__name__}")

    # 1. Gemini Check
    try:
        import test_gemini_key
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            env_file = os.path.join(os.path.dirname(__file__), ".env")
            if os.path.isfile(env_file):
                with open(env_file, "r", encoding="utf-8-sig") as f:
                    for line in f:
                        if "GEMINI_API_KEY" in line and "=" in line:
                            key = line.split("=", 1)[1].strip().strip("'\"").strip()
                            break
        if key:
            print("\n[Google Gemini AI]")
            test_gemini_key.diagnose_key(key)
        else:
            print("\n[Google Gemini AI] No GEMINI_API_KEY found in .env or environment.")
    except Exception as e:
        print(f"Gemini diagnostic error: {e}")

    # 2. Ollama Check
    print("\n[Local Ollama / Llama]")
    ollama_client = OllamaLLMClient()
    try:
        req = urllib.request.Request(f"{ollama_client.base_url}/api/tags", headers={"User-Agent": "TravelPlannerAgent/1.0"})
        with urllib.request.urlopen(req, timeout=3) as response:
            models = json.loads(response.read().decode("utf-8")).get("models", [])
        names = [item.get("name") or item.get("model") for item in models]
        if ollama_client.model in names:
            print(f"✅ Ollama is ready with model '{ollama_client.model}'.")
        else:
            print(f"⚠️ Ollama is running, but model '{ollama_client.model}' is not installed.")
            print(f"Run: ollama pull {ollama_client.model}")
    except Exception as exc:
        print(f"ℹ️ Ollama is not running on {ollama_client.base_url} (optional if using Gemini).")


def start_web_server():
    """Starts the local web interface on http://127.0.0.1:8001."""
    import subprocess
    print("\n" + "=" * 80)
    print("🌐 STARTING WEB INTERFACE (Roava Travel Planner)")
    print("=" * 80)
    print("👉 Open in your browser: http://127.0.0.1:8001")
    print("Press Ctrl+C to stop the web server and return to menu.")
    print("=" * 80 + "\n")
    try:
        from web_app import ThreadingHTTPServer, TravelPlannerHandler, HOST, PORT
        server = ThreadingHTTPServer((HOST, PORT), TravelPlannerHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb server stopped.")
    except Exception as e:
        print(f"Could not start web server: {e}")


def main():
    while True:
        print_banner()
        print("Choose an option:")
        print("  [1] Run Offline Demonstration (Fake LLM, Zero API Key)")
        print("  [2] Run Live Interactive Agent (Google Gemini / Ollama)")
        print("  [3] Run Unit Test Suite (python -m unittest test_agent.py)")
        print("  [4] View Audit Log (agent_audit.jsonl)")
        print("  [5] View Traveler Memory (traveler_memory.json)")
        print("  [6] Run AI Connection Diagnostic (Gemini & Ollama)")
        print("  [7] Start Web Interface (http://127.0.0.1:8001)")
        print("  [8] Exit")

        try:
            choice = input("\nEnter choice [1-8]: ").strip()
            if choice == "1":
                run_offline_demo()
            elif choice == "2":
                run_live_mode()
            elif choice == "3":
                run_unit_tests()
            elif choice == "4":
                view_audit_logs()
            elif choice == "5":
                view_memory_profile()
            elif choice == "6":
                run_diagnostic()
            elif choice == "7":
                start_web_server()
            elif choice in ["8", "exit", "quit", "q"]:
                print("\nGoodbye! Safe travels! 🎒✈️")
                sys.exit(0)
            else:
                print("Invalid option. Please choose between 1 and 8.")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            sys.exit(0)


if __name__ == "__main__":
    main()

