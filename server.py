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

# Optional OpenAI import — graceful fallback if not installed
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

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

# ---------------------------------------------------------------------------
# LLM-powered generation (user-provided API key)
# ---------------------------------------------------------------------------

AGENT_PROMPTS = {
    "project-brief.md": """You are a Competition Rule Parser.
Given a competition brief, extract and structure:
- Competition name and deadline
- Key rules and constraints
- Judging criteria
- Bonus opportunities

Output ONLY a clean Markdown document titled "Project Brief".
""",
    "mvp-scope.md": """You are an Idea Validator.
Given a competition idea, pressure-test it and recommend:
- The strongest MVP cutline (what MUST be built)
- What to defer or cut
- Weak assumptions to validate
- Differentiation angle

Output ONLY a clean Markdown document titled "MVP Scope".
""",
    "research-plan.md": """You are a Market Researcher.
Given a project idea, create a research plan covering:
- Competitors and substitutes
- Community language and positioning
- Evidence to verify before building
- Risks and mitigations

Output ONLY a clean Markdown document titled "Research Plan".
""",
    "build-plan.md": """You are a Project Manager.
Given a validated scope, create a build plan with:
- Milestones and deadlines
- Task breakdown
- Risk register
- Definition of done for each phase

Output ONLY a clean Markdown document titled "Build Plan".
""",
    "repo-scaffold.md": """You are a Builder Agent.
Given a project plan, create a repo scaffold with:
- Recommended folder structure
- Key files and templates
- Implementation notes
- First-build checklist

Output ONLY a clean Markdown document titled "Repo Scaffold".
""",
    "demo-script.md": """You are a Pitch Agent.
Given a project, write a demo script with:
- Opening hook
- Walkthrough script (2-3 minutes)
- Key talking points
- Closing call-to-action

Output ONLY a clean Markdown document titled "Demo Script".
""",
}


def build_agent_prompt(agent, kw, artifact_file):
    """Build a prompt for a specific agent given the user's brief."""
    system_prompt = AGENT_PROMPTS.get(artifact_file, "You are a helpful AI assistant. Output Markdown only.")
    user_prompt = f"""## Competition Brief

- **Competition:** {kw['competition']}
- **Deadline:** {kw['deadline']}
- **Rules:** {kw['rules']}
- **Idea:** {kw['idea']}
- **Biggest Concern:** {kw['concern']}

## Your Role
{agent['role']}

## Task
Produce the artifact: {artifact_file}
"""
    return system_prompt, user_prompt


def run_swarm_stream_llm(payload: dict):
    """Generate NDJSON events using a real LLM via user-provided API key."""
    api_key = payload.get("api_key", "").strip()
    if not api_key:
        yield json.dumps({"type": "error", "message": "No API key provided."}) + "\n"
        return

    if not HAS_OPENAI:
        yield json.dumps({"type": "error", "message": "OpenAI package not installed. Run: pip install openai"}) + "\n"
        return

    kw = extract_keywords(payload)
    workflow = WORKFLOWS[0]
    steps = workflow["steps"]
    agents = [a for a in AGENTS[:6]]

    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        yield json.dumps({"type": "error", "message": f"Invalid API key or connection error: {e}"}) + "\n"
        return

    event = lambda **kwargs: json.dumps(kwargs) + "\n"

    yield event(
        type="system",
        message=f"Swarm initialized for '{kw['project_name']}' (LLM mode)",
        competition=kw["competition"],
        total_steps=len(steps),
    )
    time.sleep(0.15)

    for idx, (step_name, agent) in enumerate(zip(steps, agents)):
        artifact_file = agent.get("artifact", "")

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

        # Thinking thoughts
        for t in [
            f"{agent['name']} analyzing brief...",
            f"{agent['name']} evaluating constraints...",
            f"{agent['name']} drafting {artifact_file}...",
        ]:
            yield event(type="thought", text=t, agent_id=agent["id"])
            time.sleep(0.2)

        yield event(type="artifact_start", artifact=artifact_file, agent_id=agent["id"])

        # Call LLM
        system_prompt, user_prompt = build_agent_prompt(agent, kw, artifact_file)
        full_text = ""
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            full_text = response.choices[0].message.content
        except Exception as e:
            full_text = f"# Error generating {artifact_file}\n\n{e}"

        # Stream chunks
        for chunk in chunks_of(full_text, 120):
            yield event(type="artifact_chunk", artifact=artifact_file, chunk=chunk, agent_id=agent["id"])
            time.sleep(0.03)

        yield event(type="artifact_done", artifact=artifact_file, full_text=full_text, agent_id=agent["id"])
        time.sleep(0.2)

        yield event(
            type="stage_done", step_index=idx, step_name=step_name, agent_id=agent["id"]
        )
        time.sleep(0.25)

    yield event(type="done", message="Launch packet ready.", artifacts=list(ARTIFACT_MAP.keys()))


# ---------------------------------------------------------------------------
# Streaming generator (legacy / no API key)
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
        competition, deadline, rules, idea, concern, api_key (optional)

    If api_key is provided, uses real LLM generation (gpt-4o-mini).
    Otherwise falls back to keyword-substituted sample content.

    Returns NDJSON stream of agent events.
    """
    payload = request.get_json(force=True, silent=True) or {}
    if payload.get("api_key", "").strip():
        return Response(
            run_swarm_stream_llm(payload),
            mimetype="application/x-ndjson",
            headers={"X-Accel-Buffering": "no"},
        )
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
