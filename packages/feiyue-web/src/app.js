const endpoints = {
  overview: '/api/overview',
  runs: '/runs',
  reviewInbox: '/review-inbox',
  assets: '/assets',
  routing: '/api/routing',
  capabilities: '/api/capabilities',
  frontendDogfood: '/api/frontend-dogfood',
  reviewIntents: '/api/review-intents',
};

const state = {
  overview: null,
  runs: null,
  reviewInbox: null,
  assets: null,
  routing: null,
  capabilities: null,
  frontendDogfood: null,
  reviewIntents: null,
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

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { accept: 'application/json', 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body?.message || `${path} returned ${response.status}`);
  return body;
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
  const button = document.getElementById('create-intent-draft');
  if (button) button.disabled = items.length === 0;
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

function renderReviewIntents(payload) {
  const drafts = payload?.drafts || [];
  const lines = [
    `drafts = ${drafts.length}`,
    `draft_only = true`,
    `provider_call_count = ${payload?.provider_call_count ?? 0}`,
    `global_hermes_config_mutated = ${String(payload?.global_hermes_config_mutated === true)}`,
    `production_mutated = ${String(payload?.production_mutated === true)}`,
  ];
  for (const draft of drafts.slice(0, 6)) {
    lines.push(`${draft.intent_id}: ${draft.intent_kind} / ${draft.status}`);
  }
  setText('intent-summary', lines.join('\n'));
}

async function createIntentDraftForFirstReviewItem() {
  const item = state.reviewInbox?.items?.[0];
  if (!item) return;
  const payload = {
    item_type: item.item_type,
    item_id: item.item_id,
    recommended_action: item.recommended_action,
    evidence_path: item.evidence_path,
    created_by: 'feiyue-operator-console',
    reason: 'g2_operator_requested_review_intent_draft',
  };
  const result = await postJson(endpoints.reviewIntents, payload);
  const updated = await getJson(endpoints.reviewIntents);
  state.reviewIntents = updated;
  renderReviewIntents(updated);
  setText('intent-summary', `${document.getElementById('intent-summary')?.textContent || ''}\ncreated = ${result.draft.intent_id}`);
}

function wireIntentDraftButton() {
  const button = document.getElementById('create-intent-draft');
  if (!button) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await createIntentDraftForFirstReviewItem();
    } catch (error) {
      setText('intent-summary', `intent draft failed: ${error.message}`);
    } finally {
      button.disabled = !(state.reviewInbox?.items?.length > 0);
    }
  });
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
  setText('intent-summary', message);
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
  wireIntentDraftButton();
  try {
    const [overview, runs, reviewInbox, assets, routing, capabilities, frontendDogfood, reviewIntents] = await Promise.all([
      getJson(endpoints.overview),
      getJson(endpoints.runs),
      getJson(endpoints.reviewInbox),
      getJson(endpoints.assets),
      getJson(endpoints.routing),
      getJson(endpoints.capabilities),
      getJson(endpoints.frontendDogfood),
      getJson(endpoints.reviewIntents),
    ]);
    state.overview = overview;
    state.runs = runs;
    state.reviewInbox = reviewInbox;
    state.assets = assets;
    state.routing = routing;
    state.capabilities = capabilities;
    state.frontendDogfood = frontendDogfood;
    state.reviewIntents = reviewIntents;
    renderOverview(overview);
    renderRuns(runs);
    renderReviewInbox(reviewInbox);
    renderRouting(routing);
    renderCapabilities(capabilities);
    renderFrontendDogfood(frontendDogfood);
    renderReviewIntents(reviewIntents);
  } catch (error) {
    renderOfflineState(error);
  }
}

boot();
