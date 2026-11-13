# Deploy Roava to Render

This project serves its HTML, CSS, JavaScript, and API from one Python web service. Deploy the repository root as a Render Web Service using the included render.yaml.

## Before you deploy

1. Keep .env, traveler_memory.json, and agent_audit.jsonl out of Git. The repository .gitignore already lists these paths; confirm they are not staged or committed.
2. Push the project contents (including data/, static/, all imported Python modules, requirements.txt, and render.yaml) to a GitHub repository.
3. In Render, choose New > Blueprint, connect that repository, and select the branch to deploy.
4. During setup, provide GEMINI_API_KEY as a secret environment value. Never add the real key to this repository.
5. Deploy and open the onrender.com URL. The first request after the free service sleeps may take about a minute.

## Configuration

The included Blueprint sets:

- Build command: pip install -r requirements.txt
- Start command: python web_app.py
- HOST=0.0.0.0
- A free web-service plan

Render supplies PORT at runtime. For local development, the app keeps its 127.0.0.1:8001 default.

## Public-site behavior

- The website uses temporary default memory for each planning request. It does not persist a visitor's profile or mix requests through traveler_memory.json.
- The web version rejects server-side save_itinerary actions. Visitors can use the browser's download button for their own itinerary.
- Gemini requests use the key configured in Render. If there is no Gemini key, the app may use a reachable Ollama service or its offline mock, depending on what is available.
- Render free services have an ephemeral filesystem. Do not rely on local files for persistent visitor data. Move any future user accounts or durable history to a database.
- This is a hobby/demo deployment configuration. Free instances can sleep when idle, and AI provider usage may have separate limits or charges.

## Verify after deployment

1. Open the site root and confirm the page loads.
2. Open /api/health and confirm which provider the app reports.
3. Submit a short itinerary request and review the result, especially venue hours, prices, and route estimates.
4. Check Render logs if the page, health route, or planning request fails.
