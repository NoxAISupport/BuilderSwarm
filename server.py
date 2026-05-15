#!/usr/bin/env python3
"""
Builder Swarm — Level B Live Backend
A lightweight Flask server that streams pre-structured agent outputs
with realistic delays to simulate a live multi-agent workflow.

Run:
    python3 server.py
Open:
    http://localhost:5173/app/live-demo.html
"""

import os
import re
import json
import time
from pathlib import Path
from flask import Flask, request, Response, send_from_directory
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "app"
SAMPLES_DIR = BASE_DIR / "samples"
DATA_DIR = BASE_DIR / "data"

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_samples():
    """Load all sample Markdown files into memory."""
    samples = {}
    for path in SAMPLES_DIR.glob("*.md"):
        samples[path.name] = path.read_text(encoding="utf-8")
    return samples


def load_agents():
    """Load agent definitions from data/agents.json."""
    return json.loads((DATA_DIR / "agents.json").read_text(encoding="utf-8"))


def load_workflows():
    """Load workflow definitions from data/workflows.json."""
    return json.loads((DATA_DIR / "workflows.json").read_text(encoding="utf-8"))


SAMPLES = load_samples()
AGENTS = load_agents()
WORKFLOWS = load_workflows()

# Mapping from agent artifact filename -> sample filename
ARTIFACT_MAP = {
    "project-brief.md": "project-brief.md",
    "mvp-scope.md": "mvp-scope.md",
    "research-plan.md": "research-plan.md",
    "build-plan.md": "build-plan.md",
    "repo-scaffold.md": "repo-scaffold.md",
    "demo-script.md": "demo-script.md",
}


def extract_keywords(payload: dict) -> dict:
    """Extract / normalize keywords from the competition brief."""
    idea = payload.get("idea", "").strip()
    competition = payload.get("competition", "").strip()
    deadline = payload.get("deadline", "").strip()
    concern = payload.get("concern", "").strip()
    rules = payload.get("rules", "").strip()

    # Derive a short project name from the idea
    project_name = "Project"
    if ":" in idea:
        project_name = idea.split(":", 1)[0].strip()
    elif idea:
        words = idea.split()[:3]
        project_name = " ".join(words)

    # Sentiment for concern
    concern_adj = "manageable" if "easy" in concern.lower() else "critical"
    if not concern:
        concern_adj = "unknown"

    # Rule keywords
    has_open_source = "open source" in rules.lower() or "open-source" in rules.lower()
    has_community = "community" in rules.lower() or "team" in rules.lower()
    bonus_line = ""
    if has_open_source and has_community:
        bonus_line = "Strong open-source + community alignment detected."
    elif has_open_source:
        bonus_line = "Open-source bonus criteria are present."
    elif has_community:
        bonus_line = "Community bonus criteria are present."
    else:
        bonus_line = "No specific bonus criteria extracted."

    return {
        "project_name": project_name,
        "competition": competition or "SSTB Agentic AI Competition",
        "deadline": deadline or "May 29, 2026",
        "idea": idea,
        "concern": concern,
        "concern_adj": concern_adj,
        "rules": rules,
        "bonus_line": bonus_line,
    }


def personalize(text: str, kw: dict) -> str:
    """Replace template tokens inside sample Markdown with keywords."""
    replacements = {
        "Builder Swarm": kw["project_name"],
        "SSTB Agentic AI Competition": kw["competition"],
        "May 29, 2026": kw["deadline"],
        'an open-source agentic project launcher for competitions, hackathons, and community builders.': kw["idea"],
        "It has to be easy to use and innovative.": kw["concern"],
    }
    for old, new in replacements.items():
        if new and old != new:
            text = text.replace(old, new)
    return text


def chunks_of(text: str, size: int = 80):
    """Yield text in small chunks for streaming."""
    for i in range(0, len(text), size):
        yield text[i : i + size]


# ---------------------------------------------------------------------------
# Streaming generator
# ---------------------------------------------------------------------------

def run_swarm_stream(payload: dict):
    """Generate NDJSON events for the swarm simulation."""
    kw = extract_keywords(payload)
    workflow = WORKFLOWS[0]
    steps = workflow["steps"]

    # Filter to agents that actually have mapped artifacts (6 core agents)
    agents = [a for a in AGENTS[:6]]

    event = lambda **kwargs: json.dumps(kwargs) + "\n"

    # ---- Kickoff -----------------------------------------------------------
    yield event(
        type="system",
        message=f"Swarm initialized for '{kw['project_name']}'",
        competition=kw["competition"],
        total_steps=len(steps),
    )
    time.sleep(0.15)

    for idx, (step_name, agent) in enumerate(zip(steps, agents)):
        artifact_file = agent.get("artifact", "")
        sample_name = ARTIFACT_MAP.get(artifact_file)

        # -- stage start
        yield event(
            type="stage_start",
            step_index=idx,
            step_name=step_name,
            agent_id=agent["id"],
            agent_name=agent["name"],
            agent_role=agent["role"],
            artifact=artifact_file,
        )
        time.sleep(0.2)

        # -- a few thinking thoughts
        thoughts = [
            f"{agent['name']} analyzing brief...",
            f"{agent['name']} evaluating constraints...",
            f"{agent['name']} drafting {artifact_file}...",
        ]
        for t in thoughts:
            yield event(type="thought", text=t, agent_id=agent["id"])
            time.sleep(0.35)

        # -- load + personalize sample text
        raw = SAMPLES.get(sample_name, f"# {artifact_file}\n\n(No sample found.)")
        personalized = personalize(raw, kw)

        # -- stream artifact in chunks
        yield event(
            type="artifact_start",
            artifact=artifact_file,
            agent_id=agent["id"],
        )
        for chunk in chunks_of(personalized, 120):
            yield event(
                type="artifact_chunk",
                artifact=artifact_file,
                chunk=chunk,
                agent_id=agent["id"],
            )
            time.sleep(0.04)

        yield event(
            type="artifact_done",
            artifact=artifact_file,
            full_text=personalized,
            agent_id=agent["id"],
        )
        time.sleep(0.2)

        # -- stage done
        yield event(
            type="stage_done",
            step_index=idx,
            step_name=step_name,
            agent_id=agent["id"],
        )
        time.sleep(0.25)

    # ---- Completion --------------------------------------------------------
    yield event(
        type="done",
        message="Launch packet ready.",
        artifacts=list(ARTIFACT_MAP.keys()),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/swarm/run", methods=["POST"])
def api_swarm_run():
    """POST /api/swarm/run

    Accepts JSON body with keys:
        competition, deadline, rules, idea, concern

    Returns NDJSON stream of agent events.
    """
    payload = request.get_json(force=True, silent=True) or {}
    return Response(
        run_swarm_stream(payload),
        mimetype="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"},
    )


@app.route("/api/agents")
def api_agents():
    """Return agent definitions."""
    return {"agents": AGENTS}


@app.route("/api/workflows")
def api_workflows():
    """Return workflow definitions."""
    return {"workflows": WORKFLOWS}


@app.route("/api/samples/<path:filename>")
def api_samples(filename):
    """Serve a personalized sample Markdown file."""
    kw = extract_keywords(request.args.to_dict())
    raw = SAMPLES.get(filename, "")
    if not raw:
        return {"error": "Not found"}, 404
    return Response(personalize(raw, kw), mimetype="text/markdown")


# ---------------------------------------------------------------------------
# Static file serving (optional — can also use python3 -m http.server)
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(str(APP_DIR), "live-demo.html")

@app.route("/<path:path>")
def static_files(path):
    """Serve static files from the app/ directory or root directory."""
    # Files under app/ (HTML, CSS, JS)
    app_file = APP_DIR / path
    if app_file.is_file():
        return send_from_directory(str(APP_DIR), path)
    # Root-level files (README, LICENSE, etc.)
    root_file = BASE_DIR / path
    if root_file.is_file():
        return send_from_directory(str(BASE_DIR), path)
    # Fallback to live-demo.html for SPA-like behavior
    return send_from_directory(str(APP_DIR), "live-demo.html")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Builder Swarm — Level B Live Backend")
    print(f"Serving from {BASE_DIR}")
    print("Open: http://localhost:5173/app/live-demo.html")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5173, threaded=True)
