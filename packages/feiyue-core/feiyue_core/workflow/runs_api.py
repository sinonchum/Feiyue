from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlparse

from feiyue_core.workflow.asset_catalog import AssetCatalog
from feiyue_core.workflow.execution import RunCatalog, RunEvidenceLoader, RunEvidenceNotFoundError
from feiyue_core.workflow.review_inbox import ReviewInbox
from feiyue_core.workflow.review_intents import (
    ReviewIntentDraftError,
    ReviewIntentDraftRequest,
    create_review_intent_draft,
    list_review_intent_drafts,
)


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _frontend_source_root() -> Path:
    return _repo_root() / "packages" / "feiyue-web" / "src"


def _read_json_file(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": "invalid_json", "path": path.name}


def _read_model_routing(project_root: str | Path) -> dict[str, object]:
    """Read the project-local model routing table without requiring PyYAML."""

    root = Path(project_root)
    path = root / ".hermes" / "model-routing.yaml"
    routes: dict[str, dict[str, str]] = {}
    current_role: str | None = None
    if path.exists():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.rstrip()
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
                current_role = line.strip().removesuffix(":")
                routes.setdefault(current_role, {})
                continue
            if line.startswith("    ") and current_role and ":" in line:
                key, value = line.strip().split(":", 1)
                routes[current_role][key.strip()] = value.strip().strip('"\'')
    return {
        "status": "found" if path.exists() else "missing",
        "path": ".hermes/model-routing.yaml",
        "mutates_state": False,
        "routes": routes,
        "worker_primary": routes.get("worker", {}).get("primary"),
    }


def _read_capabilities(project_root: str | Path) -> dict[str, object]:
    root = Path(project_root)
    history = _read_json_file(root / ".hermes" / "capability-history" / "latest.json")
    feedback = _read_json_file(root / ".hermes" / "capability-feedback" / "latest.json")
    return {
        "mutates_state": False,
        "capability_history": history,
        "capability_feedback": feedback,
        "history_status": "found" if history is not None else "missing",
        "feedback_status": "found" if feedback is not None else "missing",
    }


def _read_frontend_dogfood(project_root: str | Path) -> dict[str, object]:
    root = Path(project_root)
    dogfood_root = root / ".hermes" / "frontend-dogfood"
    runs = []
    if dogfood_root.exists():
        for evidence_path in sorted(dogfood_root.glob("*/evidence.json")):
            payload = _read_json_file(evidence_path)
            if isinstance(payload, dict):
                runs.append(
                    {
                        "run_id": payload.get("run_id") or evidence_path.parent.name,
                        "status": payload.get("status", "unknown"),
                        "task_type": payload.get("task_type"),
                        "evidence_path": evidence_path.relative_to(root).as_posix(),
                        "provider_call_count": payload.get("provider_call_count"),
                        "global_hermes_config_mutated": payload.get("global_hermes_config_mutated"),
                        "production_mutated": payload.get("production_mutated"),
                    }
                )
    return {
        "mutates_state": False,
        "status": "found" if runs else "empty",
        "runs": runs,
    }


def read_operator_console_overview(project_root: str | Path) -> dict[str, object]:
    run_summary = RunCatalog(project_root).summary().model_dump(mode="json")
    review_summary = ReviewInbox(project_root).summary().model_dump(mode="json")
    asset_summary = AssetCatalog(project_root).summary().model_dump(mode="json")
    routing = _read_model_routing(project_root)
    capabilities = _read_capabilities(project_root)
    dogfood = _read_frontend_dogfood(project_root)
    intents = list_review_intent_drafts(project_root).model_dump(mode="json")
    return {
        "surface": "feiyue_operator_console_g2",
        "mode": "review_intent_drafts",
        "mutates_state": False,
        "write_endpoints_added": 1,
        "provider_call_count": 0,
        "runs": {"total_runs": run_summary.get("total_runs", 0)},
        "review_inbox": {"total_items": len(review_summary.get("items", []))},
        "assets": {"total_assets": asset_summary.get("total_assets", 0)},
        "routing": {"worker_primary": routing.get("worker_primary"), "status": routing.get("status")},
        "capabilities": {
            "history_status": capabilities["history_status"],
            "feedback_status": capabilities["feedback_status"],
        },
        "frontend_dogfood": {"total_runs": len(dogfood["runs"]), "status": dogfood["status"]},
        "review_intents": {"total_drafts": len(intents.get("drafts", [])), "draft_only": True},
    }


def render_operator_console_app() -> str:
    path = _frontend_source_root() / "index.html"
    html_text = path.read_text(encoding="utf-8")
    return html_text.replace('href="./styles.css"', 'href="/app/styles.css"').replace(
        'src="./app.js"', 'src="/app/app.js"'
    )


def render_runs_dashboard(project_root: str | Path) -> str:
    """Render a human-readable, read-only dashboard for persisted run evidence."""

    summary = RunCatalog(project_root).summary()
    approval_required = summary.next_action_counts.get("request_human_approval", 0)
    rows = []
    for run in summary.runs:
        risk_class = "needs-approval" if run.next_safe_action == "request_human_approval" else "normal"
        rows.append(
            """
            <tr class="{risk_class}">
              <td><a href="/dashboard/runs/{task_id}">{task_id}</a></td>
              <td>{status}</td>
              <td>{policy_action}</td>
              <td>{next_safe_action}</td>
              <td>{safe_to_retry}</td>
              <td>{approval_state}</td>
              <td><a href="/runs/{task_id}/handoff">handoff</a></td>
            </tr>
            """.format(
                risk_class=risk_class,
                task_id=_esc(run.task_id),
                status=_esc(run.status),
                policy_action=_esc(run.policy_action),
                next_safe_action=_esc(run.next_safe_action),
                safe_to_retry="yes" if run.safe_to_retry else "no",
                approval_state="exists" if run.approval_exists else "missing",
            )
        )

    next_action_items = "".join(
        f"<li><span>{_esc(action)}</span><strong>{count}</strong></li>"
        for action, count in sorted(summary.next_action_counts.items())
    ) or "<li><span>none</span><strong>0</strong></li>"

    run_rows = "".join(rows) or '<tr><td colspan="7" class="empty">No run evidence found.</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Feiyue Run Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #111827;
      --muted: #4b5563;
      --line: #d1d5db;
      --panel: #ffffff;
      --surface: #f8fafc;
      --accent: #0f766e;
      --risk: #991b1b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--surface);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 40px 24px; }}
    header {{ border-bottom: 1px solid var(--line); padding-bottom: 24px; margin-bottom: 24px; }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: .14em; font-size: 11px; color: var(--accent); font-weight: 700; }}
    h1 {{ margin: 8px 0 8px; font-size: 34px; letter-spacing: -.03em; }}
    p {{ color: var(--muted); margin: 0; line-height: 1.6; }}
    nav {{ display:flex; gap:16px; margin-top:18px; flex-wrap:wrap; }}
    .cards {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 24px 0; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 18px; }}
    .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }}
    .value {{ display: block; margin-top: 10px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 30px; font-weight: 700; }}
    section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 4px; margin-top: 16px; }}
    h2 {{ font-size: 15px; margin: 0; padding: 16px 18px; border-bottom: 1px solid var(--line); }}
    ul {{ margin: 0; padding: 0; list-style: none; }}
    li {{ display: flex; justify-content: space-between; gap: 20px; padding: 12px 18px; border-top: 1px solid #eef2f7; }}
    li:first-child {{ border-top: 0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 12px 14px; border-top: 1px solid #eef2f7; text-align: left; font-size: 13px; vertical-align: top; }}
    th {{ color: var(--muted); text-transform: uppercase; letter-spacing: .10em; font-size: 11px; font-weight: 700; }}
    a {{ color: var(--accent); text-decoration: none; font-weight: 700; }}
    a:hover {{ text-decoration: underline; }}
    .needs-approval td:nth-child(4), .needs-approval td:nth-child(6) {{ color: var(--risk); font-weight: 700; }}
    .empty {{ color: var(--muted); text-align: center; padding: 28px; }}
    @media (max-width: 760px) {{ .cards {{ grid-template-columns: 1fr; }} main {{ padding: 24px 12px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">Read-only evidence surface</div>
      <h1>Feiyue Run Dashboard</h1>
      <p>Human-readable inspection for persisted run evidence. This page does not execute work, retry tasks, call providers, or mutate Hermes configuration.</p>
      <nav><a href="/dashboard/review-inbox">Review inbox</a><a href="/dashboard/assets">Asset catalog</a><a href="/runs">Run JSON</a></nav>
    </header>
    <div class="cards" aria-label="Run summary">
      <div class="card"><span class="label">Total Runs</span><span class="value">{summary.total_runs}</span></div>
      <div class="card"><span class="label">Safe To Retry</span><span class="value">{summary.safe_to_retry_count}</span></div>
      <div class="card"><span class="label">Approval Required</span><span class="value">{approval_required}</span></div>
    </div>
    <section>
      <h2>Next Safe Action Distribution</h2>
      <ul>{next_action_items}</ul>
    </section>
    <section>
      <h2>Run Evidence</h2>
      <table>
        <thead>
          <tr>
            <th>Task</th>
            <th>Status</th>
            <th>Policy</th>
            <th>Next Safe Action</th>
            <th>Retry</th>
            <th>Approval</th>
            <th>Handoff</th>
          </tr>
        </thead>
        <tbody>{run_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""


def render_assets_dashboard(project_root: str | Path) -> str:
    """Render a human-readable, read-only dashboard for local Hermes assets."""

    summary = AssetCatalog(project_root).summary()
    sections = []
    for category, items in summary.categories.items():
        rows = []
        for item in items:
            rows.append(
                """
                <tr>
                  <td>{id}</td>
                  <td>{path}</td>
                  <td>{title}</td>
                </tr>
                """.format(
                    id=_esc(item.id),
                    path=_esc(item.path),
                    title=_esc(item.title or ""),
                )
            )
        body = "".join(rows) or '<tr><td colspan="3" class="empty">No assets found.</td></tr>'
        sections.append(
            f"""
            <section>
              <h2>{_esc(category)} <span>{summary.counts.get(category, 0)}</span></h2>
              <table>
                <thead><tr><th>ID</th><th>Relative Path</th><th>Title</th></tr></thead>
                <tbody>{body}</tbody>
              </table>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Feiyue Asset Catalog</title>
  <style>
    :root {{ --ink:#111827; --muted:#4b5563; --line:#d1d5db; --panel:#fff; --surface:#f8fafc; --accent:#0f766e; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--surface); color:var(--ink); font-family:ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width:1080px; margin:0 auto; padding:40px 24px; }}
    header {{ border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:24px; }}
    .eyebrow {{ text-transform:uppercase; letter-spacing:.14em; font-size:11px; color:var(--accent); font-weight:700; }}
    h1 {{ margin:8px 0; font-size:34px; letter-spacing:-.03em; }}
    p {{ color:var(--muted); margin:0; line-height:1.6; }}
    nav {{ display:flex; gap:16px; margin-top:18px; flex-wrap:wrap; }}
    a {{ color:var(--accent); text-decoration:none; font-weight:700; }}
    a:hover {{ text-decoration:underline; }}
    .cards {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px; margin:24px 0; }}
    .card, section {{ background:var(--panel); border:1px solid var(--line); border-radius:4px; }}
    .card {{ padding:18px; }}
    .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.12em; }}
    .value {{ display:block; margin-top:10px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:30px; font-weight:700; }}
    section {{ margin-top:16px; overflow:hidden; }}
    h2 {{ display:flex; justify-content:space-between; gap:12px; font-size:15px; margin:0; padding:16px 18px; border-bottom:1px solid var(--line); }}
    h2 span {{ color:var(--muted); font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ padding:12px 14px; border-top:1px solid #eef2f7; text-align:left; font-size:13px; vertical-align:top; overflow-wrap:anywhere; }}
    th {{ color:var(--muted); text-transform:uppercase; letter-spacing:.10em; font-size:11px; font-weight:700; }}
    .empty {{ color:var(--muted); text-align:center; padding:24px; }}
    @media (max-width:760px) {{ .cards {{ grid-template-columns:1fr; }} main {{ padding:24px 12px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">Read-only asset surface</div>
      <h1>Feiyue Asset Catalog</h1>
      <p>Safe summary of project-local Hermes workflow assets. This page exposes only IDs, relative paths, and parseable titles; it does not show raw asset contents, call providers, or mutate state.</p>
      <nav><a href="/dashboard">Run dashboard</a><a href="/assets">Asset JSON</a></nav>
    </header>
    <div class="cards" aria-label="Asset summary">
      <div class="card"><span class="label">Total Assets</span><span class="value">{summary.total_assets}</span></div>
      <div class="card"><span class="label">Categories</span><span class="value">{len(summary.categories)}</span></div>
    </div>
    {''.join(sections)}
  </main>
</body>
</html>"""


def render_review_inbox_dashboard(project_root: str | Path) -> str:
    """Render pending local review items as a read-only human-inspection page."""

    summary = ReviewInbox(project_root).summary()
    rows = []
    for item in summary.items:
        rows.append(
            """
            <tr>
              <td>{item_type}</td>
              <td>{item_id}</td>
              <td>{status}</td>
              <td>{recommended_action}</td>
              <td>{evidence_path}</td>
              <td>{mutates_state}</td>
              <td><button type="button" disabled aria-disabled="true" data-action="{recommended_action}" data-item-id="{item_id}">Approval-gated</button></td>
            </tr>
            """.format(
                item_type=_esc(item.item_type),
                item_id=_esc(item.item_id),
                status=_esc(item.status),
                recommended_action=_esc(item.recommended_action),
                evidence_path=_esc(item.evidence_path),
                mutates_state="true" if item.mutates_state else "false",
            )
        )

    body = "".join(rows) or '<tr><td colspan="7" class="empty">No review inbox items found.</td></tr>'
    type_counts: dict[str, int] = {}
    for item in summary.items:
        type_counts[item.item_type] = type_counts.get(item.item_type, 0) + 1
    type_items = "".join(
        f"<li><span>{_esc(item_type)}</span><strong>{count}</strong></li>" for item_type, count in sorted(type_counts.items())
    ) or "<li><span>none</span><strong>0</strong></li>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Feiyue Review Inbox</title>
  <style>
    :root {{ --ink:#111827; --muted:#4b5563; --line:#d1d5db; --panel:#fff; --surface:#f8fafc; --accent:#0f766e; --risk:#991b1b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--surface); color:var(--ink); font-family:ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width:1180px; margin:0 auto; padding:40px 24px; }}
    header {{ border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:24px; }}
    .eyebrow {{ text-transform:uppercase; letter-spacing:.14em; font-size:11px; color:var(--accent); font-weight:700; }}
    h1 {{ margin:8px 0; font-size:34px; letter-spacing:-.03em; }}
    p {{ color:var(--muted); margin:0; line-height:1.6; }}
    nav {{ display:flex; gap:16px; margin-top:18px; flex-wrap:wrap; }}
    a {{ color:var(--accent); text-decoration:none; font-weight:700; }}
    a:hover {{ text-decoration:underline; }}
    .cards {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; margin:24px 0; }}
    .card, section {{ background:var(--panel); border:1px solid var(--line); border-radius:4px; }}
    .card {{ padding:18px; }}
    .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.12em; }}
    .value {{ display:block; margin-top:10px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:30px; font-weight:700; }}
    section {{ margin-top:16px; overflow:hidden; }}
    h2 {{ font-size:15px; margin:0; padding:16px 18px; border-bottom:1px solid var(--line); }}
    ul {{ margin:0; padding:0; list-style:none; }}
    li {{ display:flex; justify-content:space-between; gap:20px; padding:12px 18px; border-top:1px solid #eef2f7; }}
    li:first-child {{ border-top:0; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ padding:12px 14px; border-top:1px solid #eef2f7; text-align:left; font-size:13px; vertical-align:top; overflow-wrap:anywhere; }}
    th {{ color:var(--muted); text-transform:uppercase; letter-spacing:.10em; font-size:11px; font-weight:700; }}
    .safe {{ color:var(--accent); }}
    button[disabled] {{ border:1px solid var(--line); border-radius:4px; background:#f3f4f6; color:var(--muted); padding:6px 10px; font:inherit; cursor:not-allowed; }}
    .empty {{ color:var(--muted); text-align:center; padding:24px; }}
    @media (max-width:760px) {{ .cards {{ grid-template-columns:1fr; }} main {{ padding:24px 12px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">Read-only review surface</div>
      <h1>Feiyue Review Inbox</h1>
      <p>Pending project-local review evidence for human inspection only. Approval-gated write actions are intentionally disabled in this skeleton. This page lists item metadata and relative evidence paths; it does not create approvals, run promotions, apply changes, call providers, or mutate state.</p>
      <nav><a href="/dashboard">Run dashboard</a><a href="/dashboard/assets">Asset catalog</a><a href="/review-inbox">Review JSON</a></nav>
    </header>
    <div class="cards" aria-label="Review inbox summary">
      <div class="card"><span class="label">Total Items</span><span class="value">{len(summary.items)}</span></div>
      <div class="card"><span class="label">Item Types</span><span class="value">{len(type_counts)}</span></div>
      <div class="card"><span class="label">mutates_state</span><span class="value safe">{'true' if summary.mutates_state else 'false'}</span></div>
    </div>
    <section>
      <h2>Item Type Distribution</h2>
      <ul>{type_items}</ul>
    </section>
    <section>
      <h2>Review Items</h2>
      <table>
        <thead>
          <tr>
            <th>item_type</th>
            <th>item_id</th>
            <th>status</th>
            <th>recommended_action</th>
            <th>evidence_path</th>
            <th>mutates_state</th>
            <th>disabled_action</th>
          </tr>
        </thead>
        <tbody>{body}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""


def _detail_item(label: str, value: object) -> str:
    return f"<li><span>{_esc(label)}</span><strong>{_esc(value)}</strong></li>"


def render_run_detail(project_root: str | Path, task_id: str) -> str:
    """Render one run evidence record as a human-readable read-only HTML page."""

    evidence = RunEvidenceLoader(project_root).load(task_id)
    policy_items = "".join(
        [
            _detail_item("Policy Action", evidence.policy_action),
            _detail_item("Policy Reason", evidence.policy_reason),
            _detail_item("Next Safe Action", evidence.next_safe_action),
            _detail_item("Safe To Retry", "yes" if evidence.safe_to_retry else "no"),
        ]
    )
    action_items = "".join(
        [
            _detail_item("Execution Performed", evidence.execution_performed),
            _detail_item("Retry Performed", evidence.retry_performed),
            _detail_item("Promotion Status", evidence.promotion_status),
            _detail_item("Promotion Side Effect Performed", evidence.promotion_side_effect_performed),
        ]
    )
    approval_items = "".join(
        [
            _detail_item("Approval Exists", evidence.approval_exists),
            _detail_item("Approval ID", evidence.approval_id),
            _detail_item("Approver", evidence.approval_approver),
            _detail_item("Approved Action", evidence.approval_action),
            _detail_item("Approval Applies", evidence.approval_applies),
        ]
    )
    report_items = "".join(
        _detail_item(label, path) for label, path in sorted(evidence.report_paths.items())
    ) or _detail_item("Reports", "none")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Feiyue Run Detail</title>
  <style>
    :root {{ --ink:#111827; --muted:#4b5563; --line:#d1d5db; --panel:#fff; --surface:#f8fafc; --accent:#0f766e; --risk:#991b1b; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; background:var(--surface); color:var(--ink); font-family:ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width:960px; margin:0 auto; padding:40px 24px; }}
    header {{ border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:24px; }}
    .eyebrow {{ text-transform:uppercase; letter-spacing:.14em; font-size:11px; color:var(--accent); font-weight:700; }}
    h1 {{ margin:8px 0; font-size:32px; letter-spacing:-.03em; }}
    p {{ color:var(--muted); line-height:1.6; margin:0; }}
    nav {{ display:flex; gap:16px; margin-top:18px; flex-wrap:wrap; }}
    a {{ color:var(--accent); text-decoration:none; font-weight:700; }}
    a:hover {{ text-decoration:underline; }}
    .summary {{ display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap:12px; margin:24px 0; }}
    .card, section {{ background:var(--panel); border:1px solid var(--line); border-radius:4px; }}
    .card {{ padding:18px; }}
    .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.12em; }}
    .value {{ display:block; margin-top:10px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:20px; font-weight:700; overflow-wrap:anywhere; }}
    section {{ margin-top:16px; }}
    h2 {{ font-size:15px; margin:0; padding:16px 18px; border-bottom:1px solid var(--line); }}
    ul {{ margin:0; padding:0; list-style:none; }}
    li {{ display:flex; justify-content:space-between; gap:20px; padding:12px 18px; border-top:1px solid #eef2f7; }}
    li:first-child {{ border-top:0; }}
    li span {{ color:var(--muted); }}
    li strong {{ text-align:right; overflow-wrap:anywhere; }}
    .attention {{ color:var(--risk); }}
    @media (max-width:760px) {{ .summary {{ grid-template-columns:1fr; }} main {{ padding:24px 12px; }} li {{ display:block; }} li strong {{ display:block; text-align:left; margin-top:6px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">Read-only run evidence</div>
      <h1>Feiyue Run Detail</h1>
      <p>Task <strong>{_esc(evidence.task_id)}</strong> is rendered for human inspection only. This view does not execute, retry, promote, approve, or mutate state.</p>
      <nav>
        <a href="/dashboard">Back to dashboard</a>
        <a href="/runs/{_esc(evidence.task_id)}">Evidence JSON</a>
        <a href="/runs/{_esc(evidence.task_id)}/handoff">Handoff Markdown</a>
      </nav>
    </header>
    <div class="summary">
      <div class="card"><span class="label">Status</span><span class="value">{_esc(evidence.status)}</span></div>
      <div class="card"><span class="label">Next Safe Action</span><span class="value attention">{_esc(evidence.next_safe_action)}</span></div>
      <div class="card"><span class="label">Approval</span><span class="value">{_esc('exists' if evidence.approval_exists else 'missing')}</span></div>
    </div>
    <section><h2>Policy Decision</h2><ul>{policy_items}</ul></section>
    <section><h2>Action Evidence</h2><ul>{action_items}</ul></section>
    <section><h2>Approval Evidence</h2><ul>{approval_items}</ul></section>
    <section><h2>Report Paths</h2><ul>{report_items}</ul></section>
  </main>
</body>
</html>"""


def create_runs_api_handler(project_root: str | Path) -> type[BaseHTTPRequestHandler]:
    """Create a read-only HTTP handler for persisted Feiyue run evidence."""

    root = Path(project_root)

    class RunsApiHandler(BaseHTTPRequestHandler):
        server_version = "FeiyueRunsAPI/0.1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            path = unquote(urlparse(self.path).path).rstrip("/") or "/"
            try:
                if path == "/app":
                    self._send_text(200, render_operator_console_app(), content_type="text/html; charset=utf-8")
                    return
                if path == "/app/app.js":
                    self._send_static_file(_frontend_source_root() / "app.js", "text/javascript; charset=utf-8")
                    return
                if path == "/app/styles.css":
                    self._send_static_file(_frontend_source_root() / "styles.css", "text/css; charset=utf-8")
                    return
                if path == "/api/overview":
                    self._send_json(200, read_operator_console_overview(root))
                    return
                if path == "/api/routing":
                    self._send_json(200, _read_model_routing(root))
                    return
                if path == "/api/capabilities":
                    self._send_json(200, _read_capabilities(root))
                    return
                if path == "/api/frontend-dogfood":
                    self._send_json(200, _read_frontend_dogfood(root))
                    return
                if path == "/api/review-intents":
                    self._send_json(200, list_review_intent_drafts(root).model_dump(mode="json"))
                    return
                if path in ("/", "/dashboard"):
                    self._send_text(200, render_runs_dashboard(root), content_type="text/html; charset=utf-8")
                    return
                if path == "/dashboard/assets":
                    self._send_text(200, render_assets_dashboard(root), content_type="text/html; charset=utf-8")
                    return
                if path == "/dashboard/review-inbox":
                    self._send_text(200, render_review_inbox_dashboard(root), content_type="text/html; charset=utf-8")
                    return
                if path == "/assets":
                    self._send_json(200, AssetCatalog(root).summary().model_dump(mode="json"))
                    return
                if path == "/review-inbox":
                    self._send_json(200, ReviewInbox(root).summary().model_dump(mode="json"))
                    return
                if path.startswith("/dashboard/runs/"):
                    parts = [part for part in path.split("/") if part]
                    if len(parts) == 3:
                        self._send_text(200, render_run_detail(root, parts[2]), content_type="text/html; charset=utf-8")
                        return
                if path == "/runs":
                    self._send_json(200, RunCatalog(root).summary().model_dump(mode="json"))
                    return
                if path.startswith("/runs/"):
                    parts = [part for part in path.split("/") if part]
                    if len(parts) == 2:
                        evidence = RunEvidenceLoader(root).load(parts[1])
                        self._send_json(200, evidence.model_dump(mode="json"))
                        return
                    if len(parts) == 3 and parts[2] == "handoff":
                        markdown = RunEvidenceLoader(root).render_handoff_summary(parts[1])
                        self._send_text(200, markdown, content_type="text/markdown; charset=utf-8")
                        return
                self._send_json(404, {"error": "not_found", "path": path})
            except RunEvidenceNotFoundError as exc:
                self._send_json(
                    404,
                    {
                        "error": "run_evidence_not_found",
                        "task_id": exc.task_id,
                        "path": str(exc.path),
                    },
                )

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            path = unquote(urlparse(self.path).path).rstrip("/") or "/"
            if path == "/api/review-intents":
                try:
                    payload = self._read_json_body()
                    request = ReviewIntentDraftRequest.model_validate(payload)
                    result = create_review_intent_draft(root, request)
                    self._send_json(201, result.model_dump(mode="json"))
                except ReviewIntentDraftError as exc:
                    self._send_json(exc.status_code, {"error": "review_intent_draft_rejected", "message": str(exc)})
                except ValueError as exc:
                    self._send_json(400, {"error": "invalid_review_intent_draft", "message": str(exc)})
                return
            self._send_json(405, {"error": "method_not_allowed", "method": "POST"})

        def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
            self._send_json(405, {"error": "method_not_allowed", "method": "PUT"})

        def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler API
            self._send_json(405, {"error": "method_not_allowed", "method": "PATCH"})

        def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API
            self._send_json(405, {"error": "method_not_allowed", "method": "DELETE"})

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, status: int, payload: object) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> object:
            length = int(self.headers.get("content-length", "0") or "0")
            if length <= 0:
                raise ValueError("request body is required")
            if length > 16384:
                raise ValueError("request body is too large for an intent draft")
            content_type = self.headers.get("content-type", "")
            if "application/json" not in content_type:
                raise ValueError("content-type must be application/json")
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def _send_text(self, status: int, body_text: str, *, content_type: str) -> None:
            body = body_text.encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_static_file(self, path: Path, content_type: str) -> None:
            if not path.exists() or not path.is_file():
                self._send_json(404, {"error": "static_asset_not_found", "path": path.name})
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return RunsApiHandler


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feiyue-runs-api",
        description="Serve a read-only local API over Feiyue run evidence.",
    )
    parser.add_argument("--root", default=".", help="Project root containing .hermes/runs")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", default=8765, type=int, help="Bind port")
    args = parser.parse_args(list(argv) if argv is not None else None)

    server = HTTPServer((args.host, args.port), create_runs_api_handler(args.root))
    print(f"Serving Feiyue runs API on http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
