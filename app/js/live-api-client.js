/**
 * Builder Swarm — Live API Client (Level B)
 *
 * Streams NDJSON from /api/swarm/run and progressively renders:
 *   - workflow timeline steps
 *   - agent cards with status
 *   - artifact tabs with streamed Markdown content
 *
 * Compatible with the existing app/styles.css.
 */

(function () {
  'use strict';

  const state = {
    agents: [],
    workflows: [],
    artifacts: [
      'project-brief.md',
      'mvp-scope.md',
      'research-plan.md',
      'build-plan.md',
      'repo-scaffold.md',
      'demo-script.md'
    ],
    artifactText: {},
    artifactOwners: {},
    selectedArtifact: 'project-brief.md',
    currentStep: -1,
    running: false,
  };

  const $ = (id) => document.getElementById(id);

  async function loadJson(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Could not load ${path}`);
    return res.json();
  }

  async function init() {
    const agentsRes = await loadJson('/api/agents');
    const workflowsRes = await loadJson('/api/workflows');
    state.agents = agentsRes.agents.slice(0, 6); // core agents only for demo
    state.workflows = workflowsRes.workflows;

    state.artifacts.forEach((f) => {
      state.artifactText[f] = '';
      state.artifactOwners[f] = '';
    });

    renderWorkflow();
    renderAgents();
    renderTabs();
    renderArtifact();

    $('runDemo').addEventListener('click', runLiveSwarm);
    $('copyArtifact').addEventListener('click', copyArtifact);
    $('downloadArtifact').addEventListener('click', downloadArtifact);
  }

  // ---------------------------------------------------------------------------
  // Render helpers (mirror static app.js where possible)
  // ---------------------------------------------------------------------------

  function renderWorkflow() {
    const workflow = state.workflows[0];
    $('workflow').innerHTML = workflow.steps.map((step, index) => {
      const cls =
        index < state.currentStep ? 'done' : index === state.currentStep ? 'active' : '';
      return `<div class="step ${cls}">${index + 1}. ${step}</div>`;
    }).join('');
  }

  function renderAgents() {
    $('agents').innerHTML = state.agents.map((agent, index) => {
      let cls = '';
      let status = '';
      if (index < state.currentStep) {
        cls = 'done';
        status = ' ✓ Done';
      } else if (index === state.currentStep) {
        cls = 'active';
        status = ' → Working…';
      }
      return `<article class="agent ${cls}" id="agent-${agent.id}">
        <strong>${agent.name}${status}</strong>
        <p>${agent.role}</p>
      </article>`;
    }).join('');
  }

  function titleFor(file) {
    return file
      .replace('.md', '')
      .split('-')
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join(' ');
  }

  function renderTabs() {
    $('tabs').innerHTML = state.artifacts
      .map((file) => {
        const active = file === state.selectedArtifact ? 'active' : '';
        const owner = state.artifactOwners[file]
          ? `<span style="font-size:10px;opacity:.7"> — ${state.artifactOwners[file]}</span>`
          : '';
        return `<button class="tab ${active}" data-file="${file}">${titleFor(file)}${owner}</button>`;
      })
      .join('');
    document.querySelectorAll('.tab').forEach((btn) => {
      btn.addEventListener('click', () => {
        state.selectedArtifact = btn.dataset.file;
        renderTabs();
        renderArtifact();
      });
    });
  }

  function renderArtifact() {
    const text = state.artifactText[state.selectedArtifact] || '';
    $('artifact').textContent = text || 'Waiting for swarm...';
    if (text) {
      // Auto-scroll to bottom when actively streaming
      $('artifact').scrollTop = $('artifact').scrollHeight;
    }
  }

  // ---------------------------------------------------------------------------
  // Live streaming engine
  // ---------------------------------------------------------------------------

  async function runLiveSwarm() {
    if (state.running) return;
    state.running = true;

    // Reset
    state.currentStep = -1;
    state.artifacts.forEach((f) => {
      state.artifactText[f] = '';
      state.artifactOwners[f] = '';
    });
    renderWorkflow();
    renderAgents();
    renderTabs();
    renderArtifact();

    $('runDemo').disabled = true;
    $('runDemo').textContent = 'Swarm running…';

    const payload = {
      competition: $('competition').value,
      deadline: $('deadline').value,
      rules: $('rules').value,
      idea: $('idea').value,
      concern: $('concern').value,
      api_key: $('apiKey') ? $('apiKey').value : '',
    };

    try {
      const res = await fetch('/api/swarm/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok || !res.body) {
        throw new Error(`Server returned ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const ev = JSON.parse(line);
            handleEvent(ev);
          } catch (err) {
            console.warn('Could not parse NDJSON line:', line);
          }
        }
      }

      // Drain remaining buffer
      if (buffer.trim()) {
        try {
          const ev = JSON.parse(buffer.trim());
          handleEvent(ev);
        } catch (err) {
          console.warn('Could not parse final NDJSON line:', buffer);
        }
      }
    } catch (err) {
      console.error(err);
      $('artifact').textContent = `Error: ${err.message}`;
    } finally {
      state.running = false;
      $('runDemo').disabled = false;
      $('runDemo').textContent = 'Run Builder Swarm Again';
      state.currentStep = state.workflows[0].steps.length;
      renderWorkflow();
      renderAgents();
      renderTabs();
    }
  }

  function handleEvent(ev) {
    switch (ev.type) {
      case 'system':
        $('artifact').textContent = `[System] ${ev.message}\n\n`;
        break;

      case 'stage_start':
        state.currentStep = ev.step_index;
        // If this agent owns an artifact, mark it
        if (ev.artifact) {
          state.artifactOwners[ev.artifact] = ev.agent_name;
        }
        renderWorkflow();
        renderAgents();
        renderTabs();
        break;

      case 'thought':
        // subtle: could append to a mini-log later; for now we ignore noise
        break;

      case 'artifact_start':
        if (ev.artifact) {
          state.selectedArtifact = ev.artifact;
          // clear prior content to show fresh streaming
          state.artifactText[ev.artifact] = '';
          renderTabs();
        }
        break;

      case 'artifact_chunk':
        if (ev.artifact) {
          state.artifactText[ev.artifact] += ev.chunk;
          if (state.selectedArtifact === ev.artifact) {
            renderArtifact();
          }
        }
        break;

      case 'artifact_done':
        if (ev.artifact) {
          state.artifactText[ev.artifact] = ev.full_text;
          if (state.selectedArtifact === ev.artifact) {
            renderArtifact();
          }
        }
        break;

      case 'stage_done':
        // workflow already progressed by next stage_start
        break;

      case 'done':
        $('artifact').textContent =
          (state.artifactText[state.selectedArtifact] || '') +
          '\n\n---\n✅ Launch packet complete.';
        break;
    }
  }

  // ---------------------------------------------------------------------------
  // Clipboard / download
  // ---------------------------------------------------------------------------

  async function copyArtifact() {
    const text = state.artifactText[state.selectedArtifact];
    if (!text) return;
    await navigator.clipboard.writeText(text);
    $('copyArtifact').textContent = 'Copied';
    setTimeout(() => ($('copyArtifact').textContent = 'Copy'), 1200);
  }

  function downloadArtifact() {
    const text = state.artifactText[state.selectedArtifact];
    if (!text) return;
    const blob = new Blob([text], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = state.selectedArtifact;
    a.click();
    URL.revokeObjectURL(url);
  }

  init().catch((err) => {
    console.error(err);
    $('artifact').textContent = `Error loading demo: ${err.message}`;
  });
})();
