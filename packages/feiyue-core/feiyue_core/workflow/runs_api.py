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


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


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
                if path in ("/", "/dashboard"):
                    self._send_text(200, render_runs_dashboard(root), content_type="text/html; charset=utf-8")
                    return
                if path == "/dashboard/assets":
                    self._send_text(200, render_assets_dashboard(root), content_type="text/html; charset=utf-8")
                    return
                if path == "/assets":
                    self._send_json(200, AssetCatalog(root).summary().model_dump(mode="json"))
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

        def _send_text(self, status: int, body_text: str, *, content_type: str) -> None:
            body = body_text.encode("utf-8")
            self.send_response(status)
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
