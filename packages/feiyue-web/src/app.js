const endpoints = {
  overview: '/api/overview',
  runs: '/runs',
  reviewInbox: '/review-inbox',
  assets: '/assets',
  routing: '/api/routing',
  capabilities: '/api/capabilities',
  frontendDogfood: '/api/frontend-dogfood',
  reviewIntents: '/api/review-intents',
  hermesSessionDrafts: '/api/hermes-session-drafts',
  approvalGate: '/api/approval-gate',
  verifierReport: '/api/verifier-report',
  executionOutput: '/api/execution-output',
  auditTrail: '/api/audit-trail',
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
  hermesSessionDrafts: null,
  approvalGate: null,
  verifierReport: null,
  executionOutput: null,
  auditTrail: null,
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
      <button class="ghost-button review-item-create-draft" type="button" data-item-id="${escapeHtml(item.item_id)}">Create draft</button>
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

function renderHermesSessions(payload, events = []) {
  const drafts = payload?.drafts || [];
  const approveButton = document.getElementById('approve-first-session-draft');
  const executeButton = document.getElementById('execute-approved-dry-run');
  const firstBlockedIndex = drafts.findIndex((d) => d.status === 'blocked_until_exact_approval');
  const firstApprovedIndex = drafts.findIndex((d) => d.status === 'approved_dry_run');
  if (approveButton) approveButton.disabled = firstBlockedIndex === -1;
  if (executeButton) executeButton.disabled = firstApprovedIndex === -1;
  const lines = [
    `drafts = ${drafts.length}`,
    `dry_run_only = true`,
    `provider_call_count = ${payload?.provider_call_count ?? 0}`,
    `hermes_started = ${String(payload?.hermes_started === true)}`,
    `global_hermes_config_mutated = ${String(payload?.global_hermes_config_mutated === true)}`,
    `production_mutated = ${String(payload?.production_mutated === true)}`,
  ];
  for (const draft of drafts.slice(0, 4)) {
    lines.push(`${draft.draft_id}: ${draft.status} / ${draft.profile}`);
  }
  for (const event of events.slice(0, 6)) {
    lines.push(`${event.sequence}. ${event.event_type}: ${event.message}`);
  }
  setText('session-summary', lines.join('\n'));
}

function renderApprovals(payload) {
  const approvals = payload?.approvals || [];
  const target = document.getElementById('approval-list');
  const lines = [
    `approvals = ${approvals.length}`,
    `dry_run_only = ${String(payload?.dry_run_only === true)}`,
    `provider_call_count = ${payload?.provider_call_count ?? 0}`,
    `hermes_started = ${String(payload?.hermes_started === true)}`,
    `global_hermes_config_mutated = ${String(payload?.global_hermes_config_mutated === true)}`,
    `production_mutated = ${String(payload?.production_mutated === true)}`,
  ];
  for (const approval of approvals.slice(0, 6)) {
    lines.push(`${approval.approval_id}: ${approval.status} / by ${approval.approved_by}`);
  }
  setText('approval-summary', lines.join('\n'));
  if (!target) return;
  if (!approvals.length) {
    target.className = 'list empty';
    target.textContent = 'No dry-run approvals yet. Create a session draft first, then approve it.';
    return;
  }
  target.className = 'list';
  target.innerHTML = approvals.slice(0, 8).map((a) => `
    <article class="list-item">
      <strong>${escapeHtml(a.approval_id)}</strong>
      <span>${escapeHtml(a.status)} · by ${escapeHtml(a.approved_by)}</span>
    </article>
  `).join('');
}

function renderExecutionOutput(payload) {
  const outputs = payload?.outputs || [];
  const lines = [
    `outputs = ${outputs.length}`,
    `provider_call_count = ${payload?.provider_call_count ?? 0}`,
    `hermes_started = ${String(payload?.hermes_started === true)}`,
    `global_hermes_config_mutated = ${String(payload?.global_hermes_config_mutated === true)}`,
    `production_mutated = ${String(payload?.production_mutated === true)}`,
  ];
  for (const out of outputs.slice(0, 4)) {
    const events = out.events ? out.events.map((e) => e.event_type).join(', ') : '';
    lines.push(`${out.session_draft_id}: ${out.event_count} events · executed by ${escapeHtml(out.executed_by)}`);
  }
  setText('execution-output-summary', lines.join('\n'));
  const target = document.getElementById('execution-output-list');
  if (!target) return;
  if (!outputs.length) {
    target.className = 'list empty';
    target.textContent = 'No execution outputs yet. Create a session draft, approve it, then execute it.';
    return;
  }
  target.className = 'list';
  target.innerHTML = outputs.slice(0, 8).map((out) => {
    const eventList = (out.events || []).slice(0, 5).map((e) =>
      `${e.sequence}. ${e.event_type}: ${escapeHtml(e.message)}`
    ).join('\n');
    return `<article class="list-item">
      <strong>${escapeHtml(out.session_draft_id)}</strong>
      <span>${out.event_count} events · by ${escapeHtml(out.executed_by)} · ${escapeHtml(out.executed_at)}</span>
      <pre class="code-block code-block--inline">${eventList}</pre>
    </article>`;
  }).join('');
}

function renderAuditTrail(payload) {
  const entries = payload?.entries || [];
  const target = document.getElementById('audit-trail-list');
  setText('audit-trail-summary', [
    `entries = ${payload?.total_entries ?? 0}`,
    `since = ${payload?.since || 'all'}`,
    `sources = ${Object.entries(payload?.sources_found || {}).map(([k, v]) => `${k}:${v}`).join(', ')}`,
    `provider_call_count = ${payload?.provider_call_count ?? 0}`,
    `hermes_started = ${String(payload?.hermes_started === true)}`,
    `production_mutated = ${String(payload?.production_mutated === true)}`,
  ].join('\n'));
  if (!target) return;
  if (!entries.length) {
    target.className = 'list empty';
    target.textContent = 'No audit trail entries yet. Create session drafts, approvals, or executions to populate the trail.';
    return;
  }
  target.className = 'list';
  // Show last 50 entries, most recent first
  target.innerHTML = entries.slice(-50).reverse().map((e) => {
    const details = e.details || {};
    const extra = Object.entries(details).slice(0, 4)
      .filter(([k]) => !['sequence', 'redacted', 'message'].includes(k))
      .map(([k, v]) => `${k}=${escapeHtml(String(v)).slice(0, 60)}`)
      .join(' · ');
    return `<article class="list-item audit-entry audit-entry--${escapeHtml(e.source)}">
      <div class="audit-entry__header">
        <strong>${escapeHtml(e.event_type)}</strong>
        <span class="audit-entry__source">${escapeHtml(e.source)}</span>
        <time class="audit-entry__time">${escapeHtml(e.timestamp)}</time>
      </div>
      <p class="audit-entry__desc">${escapeHtml(e.description).slice(0, 200)}</p>
      ${extra ? `<pre class="code-block code-block--inline">${extra}</pre>` : ''}
    </article>`;
  }).join('');
}

function renderVerifier(payload) {
  const reports = payload?.reports || [];
  const target = document.getElementById('verifier-list');
  setText('verifier-summary', [
    `approvals = ${payload?.total_approvals ?? 0}`,
    `checks_passed = ${payload?.total_verification_checks_passed ?? 0}`,
    `anomalies = ${payload?.total_anomalies ?? 0}`,
    `all_boundary_preserved = ${String(payload?.all_boundary_preserved === true)}`,
    `all_provider_calls_zero = ${String(payload?.all_provider_calls_zero === true)}`,
    `all_hermes_not_started = ${String(payload?.all_hermes_not_started === true)}`,
    `dry_run_only = ${String(payload?.dry_run_only === true)}`,
  ].join('\n'));
  if (!target) return;
  if (!reports.length) {
    target.className = 'list empty';
    target.textContent = 'No verifier data yet. Create a session draft and approve it first.';
    return;
  }
  target.className = 'list';
  target.innerHTML = reports.slice(0, 8).map((r) => {
    const anomalies = r.anomalies?.length ? `⚠ ${escapeHtml(r.anomalies.join(', '))}` : '✓ no anomalies';
    return `<article class="list-item">
      <strong>${escapeHtml(r.draft_id)}</strong>
      <span>${escapeHtml(r.status)} · ${r.verification_checks ? Object.values(r.verification_checks).filter(Boolean).length : 0}/${r.verification_checks ? Object.keys(r.verification_checks).length : 0} checks · ${anomalies}</span>
    </article>`;
  }).join('');
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

async function createHermesSessionDraft() {
  const result = await postJson(endpoints.hermesSessionDrafts, {
    goal: 'Inspect Feiyue evidence and prepare next operator-console improvement; dry-run only.',
    profile: 'dry-run',
    toolsets: ['none'],
    created_by: 'feiyue-operator-console',
    reason: 'g3_operator_requested_provider_free_session_draft',
    dry_run_only: true,
    provider_call_budget: 0,
  });
  const updated = await getJson(endpoints.hermesSessionDrafts);
  const events = await getJson(`/api/hermes-session-events/${result.draft.draft_id}`);
  state.hermesSessionDrafts = updated;
  renderHermesSessions(updated, events);
}

async function approveFirstSessionDraft() {
  const drafts = state.hermesSessionDrafts?.drafts || [];
  const firstBlocked = drafts.find((d) => d.status === 'blocked_until_exact_approval');
  if (!firstBlocked) return;
  const result = await postJson(`/api/hermes-session-drafts/${firstBlocked.draft_id}/approve-dry-run`, {
    approved_by: 'feiyue-operator-console',
    reason: 'g4_operator_approved_dry_run_execution',
    dry_run_only_verified: true,
    provider_call_budget_verified: 0,
    no_hermes_start_verified: true,
    no_production_mutation_verified: true,
    no_global_config_mutation_verified: true,
  });
  const [updatedSessions, updatedApprovals] = await Promise.all([
    getJson(endpoints.hermesSessionDrafts),
    getJson(endpoints.approvalGate),
  ]);
  state.hermesSessionDrafts = updatedSessions;
  state.approvalGate = updatedApprovals;
  renderHermesSessions(updatedSessions, []);
  renderApprovals(updatedApprovals);
  setText('session-summary', `${document.getElementById('session-summary')?.textContent || ''}\napproved = ${result.approval.approval_id}`);
}

async function createDraftFromReviewItem(itemId) {
  const result = await postJson(`/api/hermes-session-drafts/from-review-item/${itemId}`, {});
  const updated = await getJson(endpoints.hermesSessionDrafts);
  state.hermesSessionDrafts = updated;
  renderHermesSessions(updated, []);
  setText('session-summary', `${document.getElementById('session-summary')?.textContent || ''}\ncreated from review: ${result.draft.draft_id}`);
}

async function executeFirstApprovedDraft() {
  const drafts = state.hermesSessionDrafts?.drafts || [];
  const firstApproved = drafts.find((d) => d.status === 'approved_dry_run');
  if (!firstApproved) return;
  const result = await postJson(`/api/hermes-session-drafts/${firstApproved.draft_id}/execute-approved`, {
    executed_by: 'feiyue-operator-console',
    reason: 'g7_operator_executed_approved_dry_run',
  });
  const [updatedSessions, updatedExecution] = await Promise.all([
    getJson(endpoints.hermesSessionDrafts),
    getJson(endpoints.executionOutput),
  ]);
  state.hermesSessionDrafts = updatedSessions;
  state.executionOutput = updatedExecution;
  renderHermesSessions(updatedSessions, result.events || result.execution?.events || []);
  renderExecutionOutput(updatedExecution);
  setText('session-summary', `${document.getElementById('session-summary')?.textContent || ''}\nexecuted = ${result.session_draft_id} · ${result.event_count} events`);
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

function wireReviewCreateDraftButtons() {
  document.addEventListener('click', async (event) => {
    const button = event.target.closest('.review-item-create-draft');
    if (!button) return;
    button.disabled = true;
    const itemId = button.getAttribute('data-item-id');
    try {
      await createDraftFromReviewItem(itemId);
    } catch (error) {
      setText('session-summary', `draft from review item failed: ${error.message}`);
    } finally {
      button.disabled = false;
    }
  });
}

function wireHermesSessionDraftButton() {
  const button = document.getElementById('create-hermes-session-draft');
  if (!button) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await createHermesSessionDraft();
    } catch (error) {
      setText('session-summary', `session draft failed: ${error.message}`);
    } finally {
      button.disabled = false;
    }
  });
}

function wireApproveDraftButton() {
  const button = document.getElementById('approve-first-session-draft');
  if (!button) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await approveFirstSessionDraft();
    } catch (error) {
      setText('approval-summary', `approval failed: ${error.message}`);
    } finally {
      button.disabled = false;
    }
  });
}

function wireExecuteApprovedButton() {
  const button = document.getElementById('execute-approved-dry-run');
  if (!button) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await executeFirstApprovedDraft();
    } catch (error) {
      setText('execution-output-summary', `execution failed: ${error.message}`);
    } finally {
      button.disabled = false;
    }
  });
}

function renderOfflineState(error) {
  setText('runs-count', 'offline');
  setText('review-count', 'offline');
  setText('asset-count', 'offline');
  setText('worker-route', 'offline');
  const message = `API unavailable in static mode: ${error.message}`;
  for (const id of ['runs-list', 'review-list', 'approval-list', 'verifier-list', 'execution-output-list', 'audit-trail-list']) {
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
  setText('session-summary', message);
  setText('approval-summary', message);
  setText('verifier-summary', message);
  setText('execution-output-summary', message);
  setText('audit-trail-summary', message);
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
  wireReviewCreateDraftButtons();
  wireHermesSessionDraftButton();
  wireApproveDraftButton();
  wireExecuteApprovedButton();
  try {
    const [overview, runs, reviewInbox, assets, routing, capabilities, frontendDogfood, reviewIntents, hermesSessionDrafts, approvalGate, verifierReport, executionOutput, auditTrail] = await Promise.all([
      getJson(endpoints.overview),
      getJson(endpoints.runs),
      getJson(endpoints.reviewInbox),
      getJson(endpoints.assets),
      getJson(endpoints.routing),
      getJson(endpoints.capabilities),
      getJson(endpoints.frontendDogfood),
      getJson(endpoints.reviewIntents),
      getJson(endpoints.hermesSessionDrafts),
      getJson(endpoints.approvalGate),
      getJson(endpoints.verifierReport),
      getJson(endpoints.executionOutput),
      getJson(endpoints.auditTrail),
    ]);
    state.overview = overview;
    state.runs = runs;
    state.reviewInbox = reviewInbox;
    state.assets = assets;
    state.routing = routing;
    state.capabilities = capabilities;
    state.frontendDogfood = frontendDogfood;
    state.reviewIntents = reviewIntents;
    state.hermesSessionDrafts = hermesSessionDrafts;
    state.approvalGate = approvalGate;
    state.verifierReport = verifierReport;
    state.executionOutput = executionOutput;
    state.auditTrail = auditTrail;
    renderOverview(overview);
    renderRuns(runs);
    renderReviewInbox(reviewInbox);
    renderRouting(routing);
    renderCapabilities(capabilities);
    renderFrontendDogfood(frontendDogfood);
    renderReviewIntents(reviewIntents);
    renderHermesSessions(hermesSessionDrafts);
    renderApprovals(approvalGate);
    renderVerifier(verifierReport);
    renderExecutionOutput(executionOutput);
    renderAuditTrail(auditTrail);
  } catch (error) {
    renderOfflineState(error);
  }
}

boot();
