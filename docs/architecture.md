# Architecture

## Current MVP
Builder Swarm currently uses a static web demo:
- `app/index.html` — app shell
- `app/styles.css` — visual design
- `app/app.js` — workflow simulation, artifact tabs, copy/download controls
- `data/agents.json` — agent definitions
- `data/workflows.json` — workflow definitions
- `samples/*.md` — sample launch packet artifacts

## Why Static First
The SSTB competition does not require a production SaaS. A static demo is reliable, open-source friendly, and easy for judges/community members to run.

## Future AI Backend
A later version can replace sample artifacts with live model calls:
1. Parse competition brief.
2. Run each agent prompt in sequence.
3. Store each agent artifact as Markdown.
4. Synthesize final launch packet.
5. Export as folder/ZIP/GitHub issue set.
