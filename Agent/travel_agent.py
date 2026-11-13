"""
travel_agent.py - Core ReAct Agent Engine with Dual LLM Adapter (Mock & Live)

Fulfills:
- Requirement 1: A loop: think → act → look (📘 L1, L3).
- Requirement 2: 2–4 tools, clearly described (📘 L2).
- Requirement 3: Fixing errors when a tool fails (📘 L2).
- Requirement 4: Memory between tasks (📘 L4).
- Requirement 5: A plan before it acts (📘 L5).
- Requirement 6: Safety: asks you first, step limit, log (📘 L7).
- Requirement 7: Tests: fake LLM first, then a real one (📘 L8).
"""

from __future__ import annotations
import os
import json
import time
import uuid
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Callable

from models import TravelerProfile, DestinationDataLoader
from tools import ToolRegistry
from memory import PersistentMemoryStore
from planner import TaskPlanner, Milestone
from safety import AuditLogger, StepLimiter, HITLManager


class MockLLMClient:
    """
    Deterministic Mock LLM Client (Requirement 7: Fake LLM first).
    Simulates intelligent planning, tool invocations, error recovery,
    and PRD Section 11 formatting without requiring external API keys.
    """
    def __init__(self, simulate_tool_error: bool = False):
        self.simulate_tool_error = simulate_tool_error
        self.step_counter = 0

    def generate_response(self,
                          prompt_context: Dict[str, Any],
                          step_index: int) -> Dict[str, Any]:
        """
        Returns a deterministic (thought, action, is_final) tuple.
        """
        self.step_counter += 1
        memory_visited = prompt_context.get("visited_places", [])
        last_obs = prompt_context.get("last_observation")

        # Case: Error recovery test mode
        if self.simulate_tool_error:
            if step_index == 1:
                return {
                    "thought": "I need to check details for an attraction, but I will first test a non-existent venue to verify error recovery.",
                    "action": {
                        "tool": "check_venue_details",
                        "args": {"venue_name": "NonExistentFort"}
                    },
                    "is_final": False
                }
            elif step_index == 2:
                # Agent reads the error observation and self-corrects!
                err_code = last_obs.get("error_code") if last_obs else "UNKNOWN"
                return {
                    "thought": f"The previous tool failed with error code '{err_code}'. I will self-correct by checking a verified venue: City Palace.",
                    "action": {
                        "tool": "check_venue_details",
                        "args": {"venue_name": "City Palace"}
                    },
                    "is_final": False
                }

        # Standard Multi-Step ReAct Progression
        extracted_params = prompt_context.get("extracted_params", {})
        duration_days = extracted_params.get("duration_days", 2)
        destination = extracted_params.get("destination", "Jaipur")
        pace = extracted_params.get("pace", "relaxed")
        budget = extracted_params.get("budget", "moderate")
        interests = extracted_params.get("interests", ["history", "culture", "food"])
        target_filename = f"{destination.lower()}_{duration_days}day_{pace}_itinerary.md"

        if step_index == 1:
            return {
                "thought": (
                    f"Milestone 1: Trip parameters confirmed ({destination}, {duration_days} days, {pace} pace). "
                    f"Starting Milestone 2: Query candidate attractions and dining matching interests {interests}. "
                    f"Excluding previously visited: {memory_visited}."
                ),
                "action": {
                    "tool": "search_places",
                    "args": {
                        "destination": destination,
                        "category": "all",
                        "budget": budget,
                        "interests": interests,
                        "exclude_names": memory_visited
                    }
                },
                "is_final": False
            }

        elif step_index == 2:
            venue_to_check = "Amber Palace (Amer Fort)" if destination.lower() == "jaipur" else f"Major Attraction in {destination}"
            return {
                "thought": (
                    f"Milestone 2 completed with candidates for {destination}. Starting Milestone 3: Check operational hours "
                    f"and ticket pricing for primary morning attraction: {venue_to_check}."
                ),
                "action": {
                    "tool": "check_venue_details",
                    "args": {"venue_name": venue_to_check, "city": destination}
                },
                "is_final": False
            }

        elif step_index == 3:
            origin_p = "Amber Palace (Amer Fort)" if destination.lower() == "jaipur" else f"Morning Stop {destination}"
            dest_p = "Laxmi Mishthan Bhandar (LMB)" if destination.lower() == "jaipur" else f"Dining Stop {destination}"
            return {
                "thought": (
                    f"Primary attraction verified. Next, calculate transit time from {origin_p} to "
                    f"{dest_p} to ensure realistic travel buffers for a {pace} pace."
                ),
                "action": {
                    "tool": "get_travel_time",
                    "args": {
                        "origin": origin_p,
                        "destination": dest_p,
                        "city": destination,
                        "mode": "driving"
                    }
                },
                "is_final": False
            }

        elif step_index == 4:
            plan_content = self._build_dynamic_prd_itinerary(memory_visited, extracted_params)
            return {
                "thought": (
                    f"Transit buffers verified. Milestone 4 reached: Synthesizing {duration_days}-day {pace} schedule for "
                    f"{destination} (PRD Section 11 layout). Triggering save_itinerary to '{target_filename}' (Milestone 5)."
                ),
                "action": {
                    "tool": "save_itinerary",
                    "args": {
                        "filename": target_filename,
                        "content": plan_content
                    }
                },
                "is_final": False
            }

        else:
            plan_content = self._build_dynamic_prd_itinerary(memory_visited, extracted_params)
            return {
                "thought": (
                    f"All milestones completed. Presenting the final formatted {duration_days}-day itinerary complying with PRD Section 11."
                ),
                "action": None,
                "is_final": True,
                "final_answer": plan_content
            }

    def _build_dynamic_prd_itinerary(self, visited: List[str], params: Optional[Dict[str, Any]] = None) -> str:
        params = params or {}
        duration_days = int(params.get("duration_days", 2))
        destination = params.get("destination", "Jaipur")
        pace = params.get("pace", "relaxed")
        budget = params.get("budget", "moderate")
        visited_note = f" (Excluded previously visited: {', '.join(visited)})" if visited else ""

        # Build day-by-day blocks based on duration_days
        days_markdown = []

        # Day 1: North Forts & Royal Palaces
        days_markdown.append(f"""### Day 1
| Time | Plan | Location | Travel / notes |
|---|---|---|---|
| 09:30 | Morning Heritage Tour | Amber Palace (Amer Fort) | Start of day; grand Rajput architecture and views. |
| 12:30 | Scenic Lakeside Stop | Jal Mahal (Water Palace) | ~15 mins drive from Amber Palace. Exterior promenade view. |
| 13:30 | Traditional Lunch & Sweets | Laxmi Mishthan Bhandar (LMB) | ~20 mins drive into Pink City. Famous Rajasthani thali. |
| 15:30 | Royal Residence & Museum | City Palace Jaipur | ~10 mins walk/drive. Courtyards, armory, and textiles. |
| 18:30 | Relaxed Dinner with View | Peacock Rooftop Restaurant | ~15 mins taxi. Open-air dinner, calm atmosphere. |""")

        # Day 2: City Landmarks, Textiles & Sunset
        if duration_days >= 2:
            days_markdown.append(f"""### Day 2
| Time | Plan | Location | Travel / notes |
|---|---|---|---|
| 09:30 | Architectural Wonder | Hawa Mahal (Palace of Winds) | Iconic 953-window honeycomb facade. Morning light. |
| 11:30 | Heritage Textile Crafts | Anokhi Museum of Hand Printing | ~25 mins drive. Peaceful haveli showcasing block-printing. |
| 13:30 | Casual Lunch | Rawat Mishthan Bhandar | Authentic pyaaz kachoris and snacks. |
| 15:30 | Nature & Stroll | Central Park Jaipur | Lush greenery, shaded walking paths, peaceful break. |
| 17:30 | Sunset Panorama | Nahargarh Fort | ~30 mins scenic uphill drive. Sunset view over the Pink City. |""")

        # Day 3: Museums, Historic Bazaars & Cultural Folk Village
        if duration_days >= 3:
            days_markdown.append(f"""### Day 3
| Time | Plan | Location | Travel / notes |
|---|---|---|---|
| 10:00 | Government Central Museum | Albert Hall Museum | Indo-Saracenic architecture; historic artifacts & art. |
| 12:30 | Pink City Artisan Bazaars | Johari & Bapu Bazaar | Walking exploration of local jewelry, textile, and spice lanes. |
| 14:00 | Midday Refreshment & Lunch | Local Heritage Cafe | Relaxed lunch and beverage break. |
| 15:30 | Afternoon Rest / Free Time | Hotel or Tea Lounge | Built-in relaxation buffer for {pace} pace. |
| 18:00 | Folk Heritage Experience & Feast | Chokhi Dhani Ethnic Resort | Traditional folk dancers, cultural performances, and Rajasthani dinner. |""")

        # Day 4+: Extended Regional Exploration
        if duration_days >= 4:
            for d in range(4, duration_days + 1):
                days_markdown.append(f"""### Day {d}
| Time | Plan | Location | Travel / notes |
|---|---|---|---|
| 10:00 | Sacred Mountain Valley | Galtaji Temple (Monkey Temple) | Ancient natural springs and historic temples set in mountain pass. |
| 13:00 | Garden Lunch | Local Courtyard Eatery | Leisurely meal with regional specialties. |
| 15:30 | Royal Marble Cenotaphs | Gaitor Ki Chhatriyan | Intricate Rajput stone memorials in peaceful foothills. |
| 18:00 | Farewell Sunset Dinner | Handi Restaurant | Authentic flavors and relaxed concluding evening. |""")

        days_section = "\n\n".join(days_markdown)

        return f"""### Trip overview
- **Destination:** {destination}, Rajasthan, India
- **Dates or duration:** {duration_days} Days
- **Budget and pace:** {budget.title()} Budget, {pace.title()} Pace
- **Assumptions or details to confirm:** Weather is pleasant; private cab or auto-rickshaw used for inter-venue transit{visited_note}.

{days_section}

### Why this plan fits
- **Pace:** Formulated for a {pace} schedule with generous 1.5-hour breaks and maximum 2-3 key stops per day.
- **Geography:** Grouped geographically to minimize zigzag travel across town.
- **Memory Invariant:** Respects past travels by omitting previously visited sites ({', '.join(visited) if visited else 'None'}).

### Please verify
- **Amber Palace Jeep Ride:** Walking up can be steep; local jeeps available at base.
- **Sunset Timings:** Check local sunset time for Nahargarh Fort to arrive 45 minutes prior.
- **Museum Admissions:** Verify student/senior ID requirements for ticket counters.

### Sources
- [Amber Fort Official Tourism Guide](https://tourism.rajasthan.gov.in/amer-fort.html) (Checked: 2026-10-15)
- [City Palace Jaipur](https://royaljaipur.in/city-palace) (Checked: 2026-10-20)
- [Hawa Mahal Portal](https://tourism.rajasthan.gov.in/hawa-mahal.html) (Checked: 2026-10-18)
"""


class LiveLLMClient:
    """
    Live LLM Client for Gemini API (Requirement 7: Real LLM).
    Uses standard library urllib (zero external package dependencies).
    Auto-discovers the best available model for the user's API key
    to prevent 404 Model Not Found errors across API versions.
    """
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        raw_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not raw_key:
            env_file = os.path.join(os.path.dirname(__file__), ".env")
            if os.path.isfile(env_file):
                try:
                    with open(env_file, "r", encoding="utf-8-sig") as f:
                        for line in f:
                            clean_line = line.strip()
                            if clean_line.startswith("GEMINI_API_KEY") and "=" in clean_line:
                                raw_key = clean_line.split("=", 1)[1].strip()
                                break
                except Exception:
                    pass

        # Thoroughly sanitize key (remove quotes, whitespace, linebreaks)
        self.api_key = raw_key.strip().strip("'\"").strip()
        self.model = model or "gemini-flash-lite-latest"
        self.api_version = "v1beta"
        self.available_models: List[str] = [self.model]
        self.discovery_error: Optional[str] = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _discover_and_set_model(self) -> None:
        """Queries Google ModelService.ListModels to auto-detect supported models for this key."""
        endpoints = [
            f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}",
            f"https://generativelanguage.googleapis.com/v1/models?key={self.api_key}"
        ]
        # Text-only model preferences prioritized by reliability and speed
        preferences = [
            "gemini-flash-lite-latest",
            "gemini-3.8-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro",
        ]

        def is_text_model(name: str) -> bool:
            lower = name.lower()
            banned = ["tts", "audio", "embedding", "aqa", "imagen", "image", "gemma"]
            return not any(b in lower for b in banned)

        def model_sort_key(m: str) -> int:
            for idx, pref in enumerate(preferences):
                if m == pref:
                    return idx
                if m.startswith(pref):
                    return idx + 10
            return 100

        for url in endpoints:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TravelPlannerAgent/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = data.get("models", [])
                    gen_models = []
                    for m in models:
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods:
                            name = m.get("name", "").replace("models/", "")
                            if is_text_model(name):
                                gen_models.append(name)

                    if gen_models:
                        gen_models.sort(key=model_sort_key)
                        self.available_models = gen_models
                        if "/v1/" in url:
                            self.api_version = "v1"
                        else:
                            self.api_version = "v1beta"

                        self.model = gen_models[0]
                        return
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                self.discovery_error = f"HTTP {e.code}: {err_body}"
            except Exception as e:
                self.discovery_error = str(e)

        # Fallback default if ListModels did not return
        self.model = "gemini-flash-lite-latest"

    def generate_response(self, prompt: str, tool_schemas: Optional[List[Dict[str, Any]]] = None) -> str:
        if not self.is_available():
            raise ValueError("GEMINI_API_KEY is not set.")

        def to_gemini_schema(schema: Any) -> Any:
            """Convert the registry's JSON Schema types to Gemini Schema enums."""
            if isinstance(schema, list):
                return [to_gemini_schema(item) for item in schema]
            if not isinstance(schema, dict):
                return schema
            converted = {}
            for key, value in schema.items():
                if key == "default":
                    continue
                if key == "type" and isinstance(value, str):
                    converted[key] = value.upper()
                else:
                    converted[key] = to_gemini_schema(value)
            return converted

        def is_text_model(name: str) -> bool:
            lower = name.lower()
            banned = ["tts", "audio", "embedding", "aqa", "imagen", "image", "gemma"]
            return not any(b in lower for b in banned)

        preferences = [
            "gemini-flash-lite-latest",
            "gemini-3.8-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]

        # Prioritize confirmed working fast models
        if self.available_models:
            raw_candidates = [self.model] + [m for m in self.available_models if m != self.model]
        else:
            raw_candidates = [self.model] + preferences

        seen = set()
        unique_candidates = [
            c for c in raw_candidates
            if is_text_model(c) and not (c in seen or seen.add(c))
        ][:4]  # Limit to top 4 best candidates to prevent slow fallback loops

        last_error = None
        for cand in unique_candidates:
            for api_ver in ["v1beta"]:
                endpoint = f"https://generativelanguage.googleapis.com/{api_ver}/models/{cand}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}
                }
                if tool_schemas:
                    declarations = []
                    for schema in tool_schemas:
                        declaration = dict(schema)
                        if "parameters" in declaration:
                            declaration["parameters"] = to_gemini_schema(declaration["parameters"])
                        declarations.append(declaration)
                    payload["tools"] = [{"functionDeclarations": declarations}]
                    payload["toolConfig"] = {
                        "functionCallingConfig": {"mode": "ANY"}
                    }
                body = json.dumps(payload).encode("utf-8")

                req = urllib.request.Request(
                    endpoint,
                    data=body,
                    headers={"Content-Type": "application/json"}
                )
                try:
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        candidates_list = data.get("candidates", [])
                        if candidates_list:
                            parts = candidates_list[0].get("content", {}).get("parts", [])
                            for part in parts:
                                function_call = part.get("functionCall")
                                if function_call:
                                    self.model = cand
                                    self.api_version = api_ver
                                    return json.dumps({
                                        "thought": "",
                                        "action": {
                                            "tool": function_call.get("name", ""),
                                            "args": function_call.get("args", {})
                                        },
                                        "is_final": function_call.get("name") == "finish_itinerary",
                                        "final_answer": function_call.get("args", {}).get("final_answer", "")
                                    })
                            text = next((part.get("text", "") for part in parts if part.get("text")), "")
                            if text:
                                self.model = cand
                                self.api_version = api_ver
                                return text
                        return ""
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8", errors="ignore")
                    last_error = RuntimeError(f"Gemini API Error ({e.code}): {err_body}")
                    # If model not found or overloaded, immediately try next candidate
                    continue
                except Exception as e:
                    last_error = e
                    continue

        if last_error:
            msg = str(last_error)
            if self.discovery_error:
                msg += f"\nInitial Model Discovery Notice: {self.discovery_error}"
            raise RuntimeError(msg)

        return ""


class OllamaLLMClient:
    """Local Llama client using Ollama's HTTP API; no cloud key is required."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.1:8b").strip()
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")

    def generate_response(self, prompt: str, tool_schemas: Optional[List[Dict[str, Any]]] = None) -> str:
        messages = [{"role": "user", "content": prompt}]
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": 4096, "num_predict": 1100, "temperature": 0.3},
        }
        if tool_schemas:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": schema["name"],
                        "description": schema.get("description", ""),
                        "parameters": schema.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
                for schema in tool_schemas
            ]
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama returned HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.base_url}. Start Ollama and make sure '{self.model}' is installed."
            ) from exc

        message = data.get("message", {})
        tool_calls = message.get("tool_calls", []) or []
        if tool_calls:
            call = tool_calls[0].get("function", {})
            args = call.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            name = call.get("name", "")
            return json.dumps({
                "thought": "",
                "action": {"tool": name, "args": args},
                "is_final": name == "finish_itinerary",
                "final_answer": args.get("final_answer", "") if isinstance(args, dict) else "",
            })
        return str(message.get("content", ""))


def get_active_llm_client() -> Any:
    """Returns the best available LLM client: Gemini Live if API key is present, Ollama if running, else MockLLMClient."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.isfile(env_file):
            try:
                with open(env_file, "r", encoding="utf-8-sig") as f:
                    for line in f:
                        clean_line = line.strip()
                        if clean_line.startswith("GEMINI_API_KEY") and "=" in clean_line:
                            gemini_key = clean_line.split("=", 1)[1].strip().strip("'\"").strip()
                            break
            except Exception:
                pass
    if gemini_key:
        try:
            live_client = LiveLLMClient(api_key=gemini_key)
            if live_client.is_available():
                return live_client
        except Exception:
            pass

    # Check if Ollama service is reachable
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        req = urllib.request.Request(f"{host}/api/tags", headers={"User-Agent": "TravelPlannerAgent/1.0"})
        with urllib.request.urlopen(req, timeout=1) as resp:
            if resp.status == 200:
                return OllamaLLMClient()
    except Exception:
        pass

    return MockLLMClient()


class ReActAgent:
    """
    Autonomous ReAct Agent orchestrating the full think -> act -> look loop.
    Enforces Safety Guardrails (HITL, Step Limit, Audit Logging),
    Persistent Memory, and Task Planning.
    """
    def __init__(self,
                 tool_registry: Optional[ToolRegistry] = None,
                 memory_store: Optional[PersistentMemoryStore] = None,
                 task_planner: Optional[TaskPlanner] = None,
                 audit_logger: Optional[AuditLogger] = None,
                 step_limiter: Optional[StepLimiter] = None,
                 hitl_manager: Optional[HITLManager] = None,
                 llm_client: Optional[Any] = None):

        self.tools = tool_registry or ToolRegistry()
        self.memory = memory_store or PersistentMemoryStore()
        self.planner = task_planner or TaskPlanner()
        self.audit = audit_logger or AuditLogger()
        self.limiter = step_limiter or StepLimiter(max_steps=8)
        self.hitl = hitl_manager or HITLManager()
        self.llm = llm_client or MockLLMClient()
        self.session_id = str(uuid.uuid4())[:8]

    def run(self, user_prompt: str) -> Dict[str, Any]:
        """
        Executes the ReAct loop:
        1. Pre-Action Planning: Formulates 5 milestones.
        2. Loop:
           - THINK: Formulate rationale based on history, plan, observations.
           - ACT: Select tool and validate arguments (or finish).
           - LOOK: Execute tool (gated by HITL) and receive observation.
        3. Enforce Step Limit and record full Audit Log.
        """
        self.session_id = str(uuid.uuid4())[:8]
        self.limiter.reset()

        # Step 1: Memory retrieval & Pre-Action Planning (Req 4 & 5)
        profile = self.memory.get_profile()
        milestones = self.planner.formulate_plan(user_prompt, profile)

        history: List[Dict[str, Any]] = []
        last_observation: Optional[Dict[str, Any]] = None
        final_answer = ""
        hitl_prompted = False
        hitl_approved_count = 0

        while self.limiter.can_proceed():
            step_idx = self.limiter.increment()
            current_ms = self.planner.get_current_milestone()
            ms_id = current_ms.id if current_ms else None

            # ----------------------------------------------------
            # 1. THINK: Analyze State, Milestone, and Prior Result
            # ----------------------------------------------------
            prompt_context = {
                "step_index": step_idx,
                "user_prompt": user_prompt,
                "visited_places": self.memory.get_visited_places(),
                "profile": profile.to_dict(),
                "extracted_params": self.planner.extracted_params,
                "plan": self.planner.format_plan_for_prompt(),
                "last_observation": last_observation,
                "history": history
            }

            if isinstance(self.llm, MockLLMClient):
                llm_decision = self.llm.generate_response(prompt_context, step_idx)
            else:
                # Live LLM parsing
                raw_response = self._invoke_live_llm(prompt_context)
                if step_idx >= self.limiter.max_steps:
                    # The final safety step deliberately asks for plain text,
                    # so it does not depend on Gemini returning another tool call.
                    llm_decision = {
                        "thought": "Final itinerary response.",
                        "action": None,
                        "is_final": True,
                        "final_answer": raw_response.strip() or (
                            "I gathered some trip information, but Gemini returned an empty final response. "
                            "Please try the request again."
                        )
                    }
                else:
                    llm_decision = self._parse_llm_json(raw_response)
                if llm_decision.get("_parse_error"):
                    # Check if the model directly outputted the final itinerary in Markdown
                    cleaned_raw = raw_response.strip()
                    lower_raw = cleaned_raw.lower()
                    is_itinerary_content = any(marker in lower_raw for marker in ("day 1", "trip overview", "### day", "why this plan fits")) or ("|" in cleaned_raw and "\n" in cleaned_raw)
                    if is_itinerary_content:
                        llm_decision = {
                            "thought": "Generated completed Markdown itinerary.",
                            "action": None,
                            "is_final": True,
                            "final_answer": cleaned_raw
                        }
                    else:
                        # Give the model one retry to return a tool call
                        retry_context = dict(prompt_context)
                        retry_context["format_retry"] = True
                        retry_raw = self._invoke_live_llm(retry_context)
                        llm_decision = self._parse_llm_json(retry_raw)
                        if llm_decision.get("_parse_error"):
                            # If it still returned prose/markdown, accept it as the final answer
                            llm_decision = {
                                "thought": "Final response produced.",
                                "action": None,
                                "is_final": True,
                                "final_answer": retry_raw.strip() or cleaned_raw
                            }

            thought = llm_decision.get("thought", "")
            action = llm_decision.get("action")
            is_final = llm_decision.get("is_final", False)

            # ----------------------------------------------------
            # 2. ACT: Tool Selection & HITL Safety Gating
            # ----------------------------------------------------
            if (action and action.get("tool") == "finish_itinerary"):
                is_final = True
            if is_final or action is None:
                action_args = action.get("args", {}) if action else {}
                final_answer = llm_decision.get("final_answer") or action_args.get("final_answer") or thought
                self.audit.log(
                    session_id=self.session_id,
                    step_index=step_idx,
                    milestone_id=ms_id,
                    thought=thought,
                    action=None,
                    observation=None,
                    hitl_status="NONE",
                    is_final=True
                )
                break

            tool_name = action.get("tool", "")
            tool_args = action.get("args", {})
            hitl_status = "NONE"

            # Requirement 6: Safety - Asks you first for destructive actions
            if self.tools.is_hitl_required(tool_name):
                hitl_prompted = True
                approved = self.hitl.request_approval(tool_name, tool_args)
                if approved:
                    hitl_status = "APPROVED"
                    hitl_approved_count += 1
                else:
                    hitl_status = "DENIED"

            # ----------------------------------------------------
            # 3. LOOK: Tool Execution & Observation Feedback
            # ----------------------------------------------------
            if hitl_status == "DENIED":
                observation = {
                    "status": "DENIED",
                    "error_code": "HITL_USER_DENIED",
                    "message": f"Action '{tool_name}' was rejected by the human supervisor."
                }
            else:
                observation = self.tools.execute(tool_name, **tool_args)

            # Advance milestone progress
            self.planner.advance_milestone()

            # Record step to Audit Log (Requirement 6)
            self.audit.log(
                session_id=self.session_id,
                step_index=step_idx,
                milestone_id=ms_id,
                thought=thought,
                action=action,
                observation=observation,
                hitl_status=hitl_status,
                is_final=False
            )

            # Save state for next Think phase
            last_observation = observation
            history.append({
                "step": step_idx,
                "thought": thought,
                "action": action,
                "observation": observation
            })

            # A failed place lookup should not trap a local model in repeated
            # retries. Finish from general knowledge and clearly flag details to verify.
            if isinstance(self.llm, OllamaLLMClient) and observation.get("status") == "ERROR":
                final_context = dict(prompt_context)
                final_context.update({
                    "step_index": self.limiter.max_steps,
                    "last_observation": observation,
                    "history": history,
                })
                final_answer = self._invoke_live_llm(final_context).strip()
                if final_answer:
                    break

        # Graceful halt if step limit reached
        if self.limiter.is_exceeded() and not final_answer:
            final_answer = (
                "⚠️ Step limit (8 steps) reached. Halting execution for safety. "
                "Partial progress has been saved to the audit log."
            )

        return {
            "session_id": self.session_id,
            "steps_taken": self.limiter.current_step,
            "milestones_completed": [m.to_dict() for m in self.planner.milestones if m.status == "COMPLETED"],
            "hitl_prompted": hitl_prompted,
            "hitl_approved": hitl_approved_count > 0,
            "final_answer": final_answer,
            "history": history
        }

    def _invoke_live_llm(self, context: Dict[str, Any]) -> str:
        """Constructs a compact ReAct prompt for live LLM to stay within token limits."""

        # Compact tool summary instead of full JSON schemas
        tool_names = self.tools.get_tool_names()
        tool_summary = (
            "1. search_places(destination, category?, budget?, interests?, exclude_names?) — Find attractions/dining/culture.\n"
            "2. get_travel_time(origin, destination, city?, mode?) — Distance & travel time between stops.\n"
            "3. check_venue_details(venue_name, city?) — Hours, tickets, ratings for a venue.\n"
            "4. save_itinerary(filename, content) — Save markdown itinerary to disk (needs approval)."
        )

        # Keep search results useful to Gemini without sending full records.
        obs_text = "None"
        if context['last_observation']:
            observation = context['last_observation']
            places = observation.get('places') if isinstance(observation, dict) else None
            if isinstance(places, list):
                compact_places = []
                for place in places[:8]:
                    if isinstance(place, dict):
                        compact_places.append({
                            key: place[key]
                            for key in ('name', 'category', 'tags', 'address', 'price_level',
                                        'typical_duration_mins', 'rating', 'source_url')
                            if key in place
                        })
                compact_observation = {
                    key: observation[key]
                    for key in ('status', 'destination', 'source_type', 'count')
                    if key in observation
                }
                compact_observation['places'] = compact_places
                obs_text = json.dumps(compact_observation, separators=(',', ':'), ensure_ascii=False)
            else:
                obs_text = json.dumps(observation, separators=(',', ':'), ensure_ascii=False)
            if len(obs_text) > 3500:
                obs_text = obs_text[:3500] + "... [summary truncated]"

        # Include recent arguments and compact results so Gemini can build on
        # earlier searches instead of repeating them.
        recent_history = context.get('history', [])[-7:]
        history_text = "None"
        if recent_history:
            history_lines = []
            for h in recent_history:
                action = h.get('action') or {}
                tool = action.get('tool', 'N/A')
                args = json.dumps(action.get('args', {}), separators=(',', ':'), ensure_ascii=False)
                if len(args) > 240:
                    args = args[:240] + "..."
                prior_observation = h.get('observation') or {}
                status = prior_observation.get('status', '?')
                prior_places = prior_observation.get('places') or []
                if isinstance(prior_places, list) and prior_places:
                    result_summary = [
                        {key: place[key] for key in ('name', 'category', 'tags') if key in place}
                        for place in prior_places[:8] if isinstance(place, dict)
                    ]
                    result_text = json.dumps(result_summary, ensure_ascii=False, separators=(',', ':'))
                else:
                    result_text = json.dumps(prior_observation, ensure_ascii=False, separators=(',', ':'))
                if len(result_text) > 900:
                    result_text = result_text[:900] + "..."
                history_lines.append(f"Step {h['step']}: {tool}({args}) -> {status}; results={result_text}")
            history_text = "; ".join(history_lines)

        # Extracted parameters for context
        params = context.get('extracted_params', {})
        duration_days = params.get('duration_days', 2)
        retry_instruction = ""
        if context.get('format_retry'):
            retry_instruction = (
                "\n\nRETRY: The previous response could not be used. Do not explain or narrate. "
                "Immediately call exactly one provided function, including finish_itinerary if done."
            )

        prompt = f"""You are a Travel Itinerary Planner Agent. Use the provided function tools to act; do not merely describe a planned tool call.

Task: {context.get('user_prompt', 'Plan a trip')}
Destination: {params.get('destination', 'Unknown')} | Duration: {params.get('duration_days', 2)} days | Pace: {params.get('pace', 'relaxed')} | Budget: {params.get('budget', 'moderate')}

Current Plan:
{context['plan']}

Memory — Exclude visited: {context['visited_places']}

Previous steps: {history_text}
Last observation: {obs_text}

Tools:
{tool_summary}

Call exactly one provided function for each step. Use search_places first when places are needed, then use other tools to verify details and travel times. The previous steps and last observation contain completed tool results: do not repeat a tool call with the same arguments; build on its results and move to the next useful action. If discovery results are sufficient, finish the itinerary instead of searching again. Do not write your private reasoning. When the itinerary is complete, call finish_itinerary with a polished Markdown itinerary containing a short Trip overview, exactly {duration_days} day sections, and a separate table under each day with these columns: Time | Plan | Location | Notes. End with Why this plan fits, Please verify, and Sources. Use readable, concise activity descriptions. Do not put the daily schedule in paragraphs or bullet lists.{retry_instruction}"""
        finish_tool_schema = {
            "name": "finish_itinerary",
            "description": f"Return the completed {duration_days}-day itinerary as Markdown. Include a short overview, exactly {duration_days} day sections with a separate table for each day using columns Time, Plan, Location, Notes, then Why this plan fits, Please verify, and Sources.",
            "parameters": {
                "type": "object",
                "properties": {"final_answer": {"type": "string", "description": "The completed itinerary in the required format."}},
                "required": ["final_answer"]
            }
        }
        # Reserve the last permitted loop step for producing an answer. Gemini
        # cannot spend the entire safety budget repeating discovery calls.
        final_step = context.get('step_index', 0) >= self.limiter.max_steps
        if final_step:
            prompt += (
                "\n\nThis is the final allowed step. Return the completed itinerary directly as Markdown now. "
                "Do not narrate your process and do not request another tool call. Use the trip request and "
                "collected search results above. Start with a short Trip overview, then provide exactly "
                f"{duration_days} day sections. Under every day use a Markdown table with these exact columns: "
                "Time | Plan | Location | Notes. Put one activity per row, with realistic breaks and travel time. "
                "Finish with Why this plan fits, Please verify, and Sources. Do not use paragraphs or bullets "
                f"for the daily schedule. The itinerary must cover exactly {duration_days} days."
            )
            return self.llm.generate_response(prompt)

        tool_schemas = self.tools.get_tools_schema() + [finish_tool_schema]
        return self.llm.generate_response(prompt, tool_schemas=tool_schemas)

    def _parse_llm_json(self, raw_text: str) -> Dict[str, Any]:
        """Extracts JSON block from LLM output with multiple fallback strategies."""
        try:
            cleaned = raw_text.strip()
            # Strip markdown code fences if present
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()

            # Remove trailing commas before } or ] (common LLM mistake)
            import re
            cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
            # Remove single-line comments (// ...)
            cleaned = re.sub(r'//[^\n]*', '', cleaned)

            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find any JSON object in the text
            try:
                import re
                match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_text, re.DOTALL)
                if match:
                    candidate = re.sub(r',\s*([}\]])', r'\1', match.group())
                    candidate = re.sub(r'//[^\n]*', '', candidate)
                    return json.loads(candidate)
            except Exception:
                pass

            return {
                "thought": "Failed to parse JSON response. Returning raw LLM output as final answer.",
                "action": None,
                "is_final": True,
                "final_answer": raw_text,
                "_parse_error": True
            }
        except Exception:
            return {
                "thought": "Failed to parse JSON response. Falling back to final answer.",
                "action": None,
                "is_final": True,
                "final_answer": raw_text,
                "_parse_error": True
            }

