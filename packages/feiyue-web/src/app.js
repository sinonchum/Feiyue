const endpoints = {
  overview: '/api/overview',
  runs: '/runs',
  reviewInbox: '/review-inbox',
  assets: '/assets',
  routing: '/api/routing',
  capabilities: '/api/capabilities',
  frontendDogfood: '/api/frontend-dogfood',
};

const state = {
  overview: null,
  runs: null,
  reviewInbox: null,
  assets: null,
  routing: null,
  capabilities: null,
  frontendDogfood: null,
};

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

async function getJson(path) {
  const response = await fetch(path, { headers: { accept: 'application/json' } });
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
  return response.json();
}

function renderOverview(payload) {
  setText('runs-count', String(payload?.runs?.total_runs ?? 0));
  setText('review-count', String(payload?.review_inbox?.total_items ?? 0));
  setText('asset-count', String(payload?.assets?.total_assets ?? 0));
  setText('worker-route', payload?.routing?.worker_primary || 'unassigned');
}

function renderRuns(payload) {
  const items = payload?.runs || payload?.items || [];
  const target = document.getElementById('runs-list');
  if (!target) return;
  if (!items.length) {
    target.className = 'list empty';
    target.textContent = 'No run evidence returned yet.';
    return;
  }
  target.className = 'list';
  target.innerHTML = items.slice(0, 8).map((item) => `
    <article class="list-item">
      <strong>${escapeHtml(item.task_id || item.run_id || item.id || 'unknown run')}</strong>
      <span>${escapeHtml(item.status || item.policy_action || 'status unavailable')}</span>
    </article>
  `).join('');
}

function renderReviewInbox(payload) {
  const items = payload?.items || [];
  const target = document.getElementById('review-list');
  if (!target) return;
  if (!items.length) {
    target.className = 'list empty';
    target.textContent = 'No pending review items.';
    return;
  }
  target.className = 'list';
  target.innerHTML = items.slice(0, 8).map((item) => `
    <article class="list-item">
      <strong>${escapeHtml(item.item_type || 'review item')} / ${escapeHtml(item.status || 'unknown')}</strong>
      <span>${escapeHtml(item.recommended_action || 'review')} · ${escapeHtml(item.evidence_path || '')}</span>
    </article>
  `).join('');
}

function renderRouting(payload) {
  const routes = payload?.routes || {};
  const lines = [
    `status = ${payload?.status || 'unknown'}`,
    `worker.primary = ${payload?.worker_primary || 'unassigned'}`,
    `mutates_state = ${String(payload?.mutates_state === true)}`,
  ];
  for (const [role, route] of Object.entries(routes)) {
    lines.push(`${role}.primary = ${route?.primary || 'unassigned'}`);
  }
  setText('routing-summary', lines.join('\n'));
}

function renderCapabilities(payload) {
  const lines = [
    `history_status = ${payload?.history_status || 'unknown'}`,
    `feedback_status = ${payload?.feedback_status || 'unknown'}`,
    `mutates_state = ${String(payload?.mutates_state === true)}`,
  ];
  const history = payload?.capability_history;
  const feedback = payload?.capability_feedback;
  if (history?.profile_id) lines.push(`profile_id = ${history.profile_id}`);
  if (history?.total_runs !== undefined) lines.push(`history.total_runs = ${history.total_runs}`);
  if (feedback?.metrics?.verification_rate !== undefined) lines.push(`feedback.verification_rate = ${feedback.metrics.verification_rate}`);
  setText('capability-summary', lines.join('\n'));
}

function renderFrontendDogfood(payload) {
  const runs = payload?.runs || [];
  const lines = [
    `status = ${payload?.status || 'unknown'}`,
    `runs = ${runs.length}`,
    `mutates_state = ${String(payload?.mutates_state === true)}`,
  ];
  for (const run of runs.slice(0, 6)) {
    lines.push(`${run.run_id}: ${run.status}`);
  }
  setText('dogfood-summary', lines.join('\n'));
}

function renderOfflineState(error) {
  setText('runs-count', 'offline');
  setText('review-count', 'offline');
  setText('asset-count', 'offline');
  setText('worker-route', 'offline');
  const message = `API unavailable in static mode: ${error.message}`;
  for (const id of ['runs-list', 'review-list']) {
    const target = document.getElementById(id);
    if (target) {
      target.className = 'list empty';
      target.textContent = message;
    }
  }
  setText('routing-summary', message);
  setText('capability-summary', message);
  setText('dogfood-summary', message);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function boot() {
  try {
    const [overview, runs, reviewInbox, assets, routing, capabilities, frontendDogfood] = await Promise.all([
      getJson(endpoints.overview),
      getJson(endpoints.runs),
      getJson(endpoints.reviewInbox),
      getJson(endpoints.assets),
      getJson(endpoints.routing),
      getJson(endpoints.capabilities),
      getJson(endpoints.frontendDogfood),
    ]);
    state.overview = overview;
    state.runs = runs;
    state.reviewInbox = reviewInbox;
    state.assets = assets;
    state.routing = routing;
    state.capabilities = capabilities;
    state.frontendDogfood = frontendDogfood;
    renderOverview(overview);
    renderRuns(runs);
    renderReviewInbox(reviewInbox);
    renderRouting(routing);
    renderCapabilities(capabilities);
    renderFrontendDogfood(frontendDogfood);
  } catch (error) {
    renderOfflineState(error);
  }
}

boot();
