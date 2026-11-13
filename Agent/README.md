# Roava — Travel Itinerary Planner

An autonomous AI agent designed following core agentic workflow principles (ReAct loop, grounded tools, self-correction, persistent memory, task planning, and human-in-the-loop safety). The live model runs locally through Ollama using Llama; no Gemini API key is needed.

Built according to the product specifications in [travel-itinerary-planner-prd.md](file:///c:/Users/reach/Downloads/Agent/travel-itinerary-planner-prd.md).

---

## 📚 Project Architecture & Documentation

| Document / Script | Description |
|---|---|
| 📖 [travel-planner-agent-execution.md](file:///c:/Users/reach/Downloads/Agent/travel-planner-agent-execution.md) | **Core Execution Blueprint**: Comprehensive technical guide detailing the 7 architectural components, Mermaid workflows, ReAct state-machine, tool JSON schemas, error recovery matrix, memory structure, safety guardrails, and test designs. |
| 📋 [travel-itinerary-planner-prd.md](file:///c:/Users/reach/Downloads/Agent/travel-itinerary-planner-prd.md) | **Product Requirements Document**: User stories, functional/non-functional requirements, and PRD Section 11 response table layout. |
| 🐍 [travel_agent.py](file:///c:/Users/reach/Downloads/Agent/travel_agent.py) | **Agent Core Implementation**: ReAct loop engine, dual LLM adapter (Mock & Live Gemini), self-correction, and PRD Section 11 output formatter. |
| 🛠️ [tools.py](file:///c:/Users/reach/Downloads/Agent/tools.py) | **Grounded Tools**: 4 registered tools (`search_places`, `get_travel_time`, `check_venue_details`, `save_itinerary`) with structured error recovery. |
| 🧠 [memory.py](file:///c:/Users/reach/Downloads/Agent/memory.py) | **Cross-Session Memory Store**: Manages `traveler_memory.json` to persist pace, preferences, and visited site exclusions. |
| 🗺️ [planner.py](file:///c:/Users/reach/Downloads/Agent/planner.py) | **Task Planner**: Pre-action roadmap generating 5 sequential milestones before tool invocation. |
| 🛡️ [safety.py](file:///c:/Users/reach/Downloads/Agent/safety.py) | **Safety Invariants**: Human-in-the-Loop (HITL) gate, step limiter (`max_steps=8`), and audit logger (`agent_audit.jsonl`). |
| 📦 [models.py](file:///c:/Users/reach/Downloads/Agent/models.py) | **Data Models & Loader**: Strongly-typed dataclasses for places, transit calculations, itinerary items, and multi-city datasets. |
| 🧪 [test_agent.py](file:///c:/Users/reach/Downloads/Agent/test_agent.py) | **Zero-Dependency Test Suite**: 10 unit tests using Python's standard `unittest` framework testing all 7 requirements. |
| 💻 [cli.py](file:///c:/Users/reach/Downloads/Agent/cli.py) | **Interactive REPL**: Terminal interface supporting offline simulated mode, live Gemini API integration, and audit inspection. |
| 🌐 [web_app.py](file:///c:/Users/reach/Downloads/Agent/web_app.py) | **Local Web App**: Browser interface for planning trips; serves on `127.0.0.1:8001` and talks to the local Ollama service. |
| 📍 [data/jaipur_places.json](file:///c:/Users/reach/Downloads/Agent/data/jaipur_places.json) | **Curated Grounded Dataset**: 13 verified Jaipur venues with coordinates, operating hours, prices, ratings, and official sources. |

---

## 7 Core Requirements Coverage

| # | Requirement | Implementation in Codebase |
|---|---|---|
| **1️⃣** | **A Loop: think → act → look** *(📘 L1, L3)* | `ReActAgent.run()` implements explicit thought extraction, tool action execution, and observation feedback in a continuous cycle. |
| **2️⃣** | **2–4 Tools, Clearly Described** *(📘 L2)* | `ToolRegistry` defines 4 grounded tools: `search_places`, `get_travel_time`, `check_venue_details`, and `save_itinerary`. |
| **3️⃣** | **Fixing Errors When a Tool Fails** *(📘 L2)* | Structured error returns on `NO_RESULTS`, invalid categories, or venue not found. Agent reads error observation in the **Think** step and self-corrects. |
| **4️⃣** | **Memory Between Tasks** *(📘 L4)* | `PersistentMemoryStore` loads and saves traveler profile, pace preferences, and previously visited sites (`Jantar Mantar`) across sessions. |
| **5️⃣** | **A Plan Before It Acts** *(📘 L5)* | `TaskPlanner.formulate_plan()` decomposes the trip request into a 5-step milestone roadmap before tool execution begins. |
| **6️⃣** | **Safety: Asks You First, Step Limit, Log** *(📘 L7)* | • **Asks You First**: HITL callback prompts for human approval before disk writes.<br/>• **Step Limit**: Hard cap (`max_steps = 8`) halts runaway loops.<br/>• **Log**: Appends every thought, action, input, and observation to `agent_audit.jsonl`. |
| **7️⃣** | **Tests: Fake LLM First, Then Real** | • **Test Suite 1 (Fake LLM)**: Scripted deterministic mock LLM validating loop transitions, error fixes, memory exclusion, and HITL safety.<br/>• **Test Suite 2 (Real LLM)**: Live integration with Gemini/OpenAI API. |

---

## 🚀 Quickstart & Execution

### 1. Run Unit Tests (Fake LLM First, No API Key Required)
```bash
python -m unittest test_agent.py -v
```

### 2. Run the Interactive CLI
```bash
python cli.py
```
- Select `[1]` to run the deterministic offline demonstration.
- Select `[2]` to enter an API key and chat with a live model.

### 3. Run with Local Llama through Ollama
```bash
# Install Ollama from https://ollama.com/download/windows, then open PowerShell
ollama pull llama3.1:8b
```
Ollama runs its local API in the background. `llama3.1:8b` is the default model; the first pull downloads the model (about 4.9 GB). See the [official Ollama model page](https://ollama.com/library/llama3.1) for model details.

### 4. Run the Local Browser Interface
```powershell
cd C:\Users\reach\Downloads\Agent
python web_app.py
```
Make sure Ollama is running and the `llama3.1:8b` model is installed. Then open `http://127.0.0.1:8001` in your browser. Keep both Ollama and the Roava server running while using the page; press `Ctrl+C` in the Roava server terminal to stop it. For a different model or Ollama host, set `OLLAMA_MODEL` or `OLLAMA_HOST` in `.env`.

### 5. Inspect Audit Logs & Memory
```bash
# View execution audit records
type agent_audit.jsonl

# View persisted traveler profile
type traveler_memory.json
```

