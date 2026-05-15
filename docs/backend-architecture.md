# Builder Swarm — Level B Backend Architecture

## Goal
Provide a lightweight, deterministic live backend that makes the static demo feel dynamic without requiring external LLM API calls, accounts, or databases.

## Design Principles
1. **Zero-cost** — No paid APIs, no cloud services.
2. **Deterministic** — Judges get reproducible results.
3. **Looks live** — Streaming NDJSON with realistic delays simulates agent processing.
4. **Template-driven** — Content is sample Markdown parameterized by the competition brief.
5. **Same UX** — Existing HTML/CSS is reused; only JS and a small backend are added.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (live-demo.html + live-api-client.js)              │
│  - Form input for competition brief                         │
│  - Render timeline, agent cards, artifact tabs              │
│  - Stream NDJSON from /api/swarm/run                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ POST /api/swarm/run
                       │  Accepts: {competition, deadline,    │
                       │           rules, idea, concern}      │
                       │  Returns: NDJSON stream              │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Flask server (server.py)                                   │
│  - Loads agents.json, workflows.json, sample Markdown       │
│  - Extracts keywords from POST body                         │
│  - Iterates agents/workflow steps                           │
│  - Yields NDJSON events:                                    │
│    * system, stage_start, thought                           │
│    * artifact_start, artifact_chunk, artifact_done          │
│    * stage_done, done                                       │
│  - Personalizes samples by string-replacing keyword tokens  │
└─────────────────────────────────────────────────────────────┘
```

## Event Types (NDJSON Stream)

| Type | Fields | Purpose |
|------|--------|---------|
| `system` | `message`, `competition`, `total_steps` | Kickoff |
| `stage_start` | `step_index`, `step_name`, `agent_id`, `agent_name`, `agent_role`, `artifact` | Highlight active agent |
| `thought` | `text`, `agent_id` | Show agent is "thinking" |
| `artifact_start` | `artifact`, `agent_id` | Switch artifact tab |
| `artifact_chunk` | `artifact`, `chunk`, `agent_id` | Stream Markdown in real time |
| `artifact_done` | `artifact`, `full_text`, `agent_id` | Final artifact text |
| `stage_done` | `step_index`, `step_name`, `agent_id` | Mark stage complete |
| `done` | `message`, `artifacts` | Finalize |

## Content Personalization
The backend extracts keywords from the brief:
- `project_name` — derived from the idea field (first clause)
- `competition`, `deadline`, `idea`, `concern` — used verbatim
- `bonus_line` — inferred from rules text

These are substituted into the sample Markdown files before streaming, so changing the brief yields believably customized output without calling an LLM.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/swarm/run` | POST | NDJSON stream of the swarm simulation |
| `/api/agents` | GET | Agent definitions |
| `/api/workflows` | GET | Workflow definitions |
| `/api/samples/<filename>` | GET | Personalized Markdown sample |

## Files

- `server.py` — Flask app, streaming generator, keyword extraction, personalization
- `app/live-demo.html` — shell page for live mode (nearly identical to `index.html`)
- `app/js/live-api-client.js` — NDJSON fetcher, event handler, DOM renderer
- `docs/backend-architecture.md` — this document
- `requirements.txt` — `flask`, `flask-cors`

## Running Locally

```bash
cd BuilderSwarm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 server.py
```

Open:

```text
http://localhost:5173/app/live-demo.html
```

The static demo remains available at `http://localhost:5173/app/index.html` as a fallback.

## Why Not a Real LLM Backend?
- **Cost:** $0 for judges and community.
- **Latency:** No cold starts or rate limits during demos.
- **Reliability:** No API key drift, no model downtime, no prompt-versioning issues.
- **Extensibility:** The NDJSON contract and event types are designed so a real LLM backend can slot in later without changing the frontend.

## Future Extension Path
1. **Level C:** Replace template substitution with local model (Ollama / llama.cpp) calls using the same NDJSON contract.
2. **Level D:** Add async job queue, database, and user sessions.
3. **Level E:** External model APIs with streaming tokens into `artifact_chunk` events.
