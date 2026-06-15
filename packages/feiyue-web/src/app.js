const endpoints = {
  runs: '/runs',
  reviewInbox: '/review-inbox',
  assets: '/assets',
};

const state = {
  runs: null,
  reviewInbox: null,
  assets: null,
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

function renderRuns(payload) {
  const items = payload?.runs || payload?.items || [];
  setText('runs-count', String(items.length ?? 0));
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
  setText('review-count', String(items.length));
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

function renderAssets(payload) {
  const total = payload?.total_assets ?? payload?.assets?.length ?? payload?.items?.length ?? 0;
  setText('asset-count', String(total));
}

function renderOfflineState(error) {
  setText('runs-count', 'offline');
  setText('review-count', 'offline');
  setText('asset-count', 'offline');
  const message = `API unavailable in static mode: ${error.message}`;
  for (const id of ['runs-list', 'review-list']) {
    const target = document.getElementById(id);
    if (target) {
      target.className = 'list empty';
      target.textContent = message;
    }
  }
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
    const [runs, reviewInbox, assets] = await Promise.all([
      getJson(endpoints.runs),
      getJson(endpoints.reviewInbox),
      getJson(endpoints.assets),
    ]);
    state.runs = runs;
    state.reviewInbox = reviewInbox;
    state.assets = assets;
    renderRuns(runs);
    renderReviewInbox(reviewInbox);
    renderAssets(assets);
  } catch (error) {
    renderOfflineState(error);
  }
}

boot();
