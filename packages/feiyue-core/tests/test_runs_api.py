from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

from feiyue_core.workflow.runs_api import create_runs_api_handler


def _write_run_evidence(root, task_id="m13-api-demo"):
    run_dir = root / ".hermes" / "runs" / task_id
    run_dir.mkdir(parents=True)
    (run_dir / "run-evidence.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "status": "blocked",
                "policy_action": "escalate",
                "policy_reason": "high_risk_operation",
                "execution_performed": False,
                "retry_performed": False,
                "promotion_status": None,
                "promotion_side_effect_performed": None,
                "approval_exists": False,
                "approval_id": None,
                "approval_approver": None,
                "approval_action": None,
                "approval_applies": False,
                "safe_to_retry": False,
                "next_safe_action": "request_human_approval",
                "report_paths": {"execution_report": "execution-report.md", "execution_json": "execution-report.json"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_dir


@contextmanager
def _api_server(root):
    server = HTTPServer(("127.0.0.1", 0), create_runs_api_handler(root))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get_json(url):
    with urlopen(url, timeout=5) as response:
        assert response.headers["content-type"] == "application/json"
        return json.loads(response.read().decode("utf-8"))


def _get_text(url):
    with urlopen(url, timeout=5) as response:
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"
        return response.read().decode("utf-8")


def _get_html(url):
    with urlopen(url, timeout=5) as response:
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        return response.read().decode("utf-8")


def test_runs_api_dashboard_renders_human_readable_html(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m13-api-demo")

    with _api_server(tmp_path) as base_url:
        html = _get_html(f"{base_url}/dashboard")

    assert "Feiyue Run Dashboard" in html
    assert "Total Runs" in html
    assert "Approval Required" in html
    assert "m13-api-demo" in html
    assert "request_human_approval" in html
    assert 'href="/dashboard/runs/m13-api-demo"' in html
    assert "<pre>" not in html
    assert "JSON.stringify" not in html


def test_runs_api_dashboard_run_detail_renders_human_readable_evidence(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m13-api-demo")

    with _api_server(tmp_path) as base_url:
        html = _get_html(f"{base_url}/dashboard/runs/m13-api-demo")

    assert "Feiyue Run Detail" in html
    assert "m13-api-demo" in html
    assert "Policy Decision" in html
    assert "Action Evidence" in html
    assert "Approval Evidence" in html
    assert "request_human_approval" in html
    assert 'href="/runs/m13-api-demo"' in html
    assert 'href="/runs/m13-api-demo/handoff"' in html
    assert "<pre>" not in html
    assert "JSON.stringify" not in html


def test_runs_api_dashboard_run_detail_missing_run_returns_json_404(tmp_path) -> None:
    with _api_server(tmp_path) as base_url:
        try:
            _get_html(f"{base_url}/dashboard/runs/missing-task")
        except HTTPError as exc:
            assert exc.code == 404
            payload = json.loads(exc.read().decode("utf-8"))
        else:
            raise AssertionError("Expected 404")

    assert payload["error"] == "run_evidence_not_found"
    assert payload["task_id"] == "missing-task"


def test_runs_api_get_runs_returns_catalog_summary(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m13-api-demo")

    with _api_server(tmp_path) as base_url:
        payload = _get_json(f"{base_url}/runs")

    assert payload["total_runs"] == 1
    assert payload["safe_to_retry_count"] == 0
    assert payload["next_action_counts"] == {"request_human_approval": 1}
    assert payload["runs"][0]["task_id"] == "m13-api-demo"
    assert payload["runs"][0]["approval_exists"] is False


def test_runs_api_get_run_returns_evidence_json(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m13-api-demo")

    with _api_server(tmp_path) as base_url:
        payload = _get_json(f"{base_url}/runs/m13-api-demo")

    assert payload["task_id"] == "m13-api-demo"
    assert payload["policy_reason"] == "high_risk_operation"
    assert payload["next_safe_action"] == "request_human_approval"


def test_runs_api_get_handoff_returns_markdown(tmp_path) -> None:
    _write_run_evidence(tmp_path, "m13-api-demo")

    with _api_server(tmp_path) as base_url:
        markdown = _get_text(f"{base_url}/runs/m13-api-demo/handoff")

    assert "# Fallback Handoff Summary" in markdown
    assert "- task_id: m13-api-demo" in markdown
    assert "## Approval Evidence" in markdown


def test_runs_api_missing_run_returns_json_404(tmp_path) -> None:
    with _api_server(tmp_path) as base_url:
        try:
            _get_json(f"{base_url}/runs/missing-task")
        except HTTPError as exc:
            assert exc.code == 404
            payload = json.loads(exc.read().decode("utf-8"))
        else:
            raise AssertionError("Expected 404")

    assert payload["error"] == "run_evidence_not_found"
    assert payload["task_id"] == "missing-task"


def test_runs_api_rejects_non_get_methods(tmp_path) -> None:
    with _api_server(tmp_path) as base_url:
        try:
            urlopen(f"{base_url}/runs", data=b"{}", timeout=5)
        except HTTPError as exc:
            assert exc.code == 405
        else:
            raise AssertionError("Expected 405")
