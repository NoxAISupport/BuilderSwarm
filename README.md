# Builder Swarm

**Builder Swarm** is an open-source agentic project launcher for competitions, hackathons, and community builders.

Give it a competition brief, deadline, rough idea, current assets, and biggest concern. Builder Swarm coordinates specialist AI-agent roles to produce a practical launch packet: project brief, MVP scope, research plan, build plan, repo scaffold, demo script, AI usage log, and submission checklist.

## Why

A lot of builders have ideas but lose momentum between “interesting concept” and “submitted project.” Builder Swarm reduces blank-page paralysis by turning rough project inputs into an executable plan and open-source-ready package.

## SSTB Competition Fit

- **Agentic:** uses a visible multi-agent workflow: rule parser, validator, researcher, planner, builder, and submission coach.
- **Community-oriented:** helps other builders ship competition projects faster.
- **Open-source friendly:** templates, prompts, rubrics, and packet formats can be extended by the community.
- **Easy to demo:** input one rough competition idea; output a complete project launch packet.

## Run the Demo Locally

### Static Demo (no backend)

```bash
git clone https://github.com/NoxAISupport/BuilderSwarm.git
cd BuilderSwarm
python3 -m http.server 5173
```

Open: `http://localhost:5173/app/index.html`

> Make sure the server is started **inside** the `BuilderSwarm` folder, or you will get a 404.

### Live Backend Demo

**macOS / Linux:**

```bash
git clone https://github.com/NoxAISupport/BuilderSwarm.git
cd BuilderSwarm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 server.py
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/NoxAISupport/BuilderSwarm.git
cd BuilderSwarm
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python server.py
```

**Windows (Command Prompt):**

```cmd
git clone https://github.com/NoxAISupport/BuilderSwarm.git
cd BuilderSwarm
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python server.py
```

Open: `http://localhost:5173/app/live-demo.html`

> **Demo mode:** No API key needed — runs offline with template-based keyword substitution.  
> **LLM mode:** Paste your OpenAI API key in the UI for real AI-generated artifacts (requires internet + credits).

## Current MVP

The current MVP is a static demo console. It shows:

- Competition brief form
- Visible swarm workflow
- Agent cards
- Generated artifact tabs
- Copy/download Markdown controls
- Sample SSTB launch packet

## Important MVP Note

This first version uses curated sample Markdown outputs to make the workflow reliable for demo and review. A later version can replace the samples with live model calls while keeping the same artifact structure.

## Project Structure

```text
BuilderSwarm/
  app/        Static demo console
  data/       Agent and workflow definitions
  samples/    Sample generated launch-packet artifacts
  docs/       Architecture, AI usage log, workflow docs
  outputs/    Generated launch packs
```

## Open Source Extension Ideas

Community members can add:

- New competition templates
- New agent roles
- Better judging rubrics
- Sample launch packets
- Export formats
- Live AI backend adapters
