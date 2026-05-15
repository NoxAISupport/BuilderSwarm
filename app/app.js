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
  selectedArtifact: 'project-brief.md',
  currentStep: -1
};

const $ = (id) => document.getElementById(id);

async function loadJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Could not load ${path}`);
  return res.json();
}

async function loadText(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Could not load ${path}`);
  return res.text();
}

async function init() {
  state.agents = await loadJson('../data/agents.json');
  state.workflows = await loadJson('../data/workflows.json');
  for (const file of state.artifacts) {
    state.artifactText[file] = await loadText(`../samples/${file}`);
  }
  renderWorkflow();
  renderAgents();
  renderTabs();
  renderArtifact();
  $('runDemo').addEventListener('click', runDemo);
  $('copyArtifact').addEventListener('click', copyArtifact);
  $('downloadArtifact').addEventListener('click', downloadArtifact);
}

function renderWorkflow() {
  const workflow = state.workflows[0];
  $('workflow').innerHTML = workflow.steps.map((step, index) => {
    const cls = index < state.currentStep ? 'done' : index === state.currentStep ? 'active' : '';
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
    return `<article class="agent ${cls}"><strong>${agent.name}${status}</strong><p>${agent.role}</p></article>`;
  }).join('');
}

function titleFor(file) {
  return file.replace('.md', '').split('-').map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
}

function renderTabs() {
  $('tabs').innerHTML = state.artifacts.map(file => {
    const active = file === state.selectedArtifact ? 'active' : '';
    return `<button class="tab ${active}" data-file="${file}">${titleFor(file)}</button>`;
  }).join('');
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      state.selectedArtifact = btn.dataset.file;
      renderTabs();
      renderArtifact();
    });
  });
}

function renderArtifact() {
  $('artifact').textContent = state.artifactText[state.selectedArtifact] || 'No artifact loaded.';
}

async function runDemo() {
  $('runDemo').disabled = true;
  $('runDemo').textContent = 'Swarm running…';
  for (let i = 0; i < state.workflows[0].steps.length; i++) {
    state.currentStep = i;
    renderWorkflow();
    renderAgents();
    await new Promise(resolve => setTimeout(resolve, 450));
  }
  state.currentStep = state.workflows[0].steps.length;
  renderWorkflow();
  renderAgents();
  $('runDemo').disabled = false;
  $('runDemo').textContent = 'Run Builder Swarm Again';
}

async function copyArtifact() {
  await navigator.clipboard.writeText(state.artifactText[state.selectedArtifact]);
  $('copyArtifact').textContent = 'Copied';
  setTimeout(() => $('copyArtifact').textContent = 'Copy', 1200);
}

function downloadArtifact() {
  const blob = new Blob([state.artifactText[state.selectedArtifact]], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = state.selectedArtifact;
  a.click();
  URL.revokeObjectURL(url);
}

init().catch(err => {
  console.error(err);
  $('artifact').textContent = `Error loading demo: ${err.message}`;
});
