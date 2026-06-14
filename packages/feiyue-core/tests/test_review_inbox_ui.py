from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import HTTPServer
from urllib.request import urlopen

from feiyue_core.workflow.runs_api import create_runs_api_handler, render_review_inbox_dashboard
from feiyue_core.workflow.runs_export import export_static_runs_report


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def _get_html(url):
    with urlopen(url, timeout=5) as response:
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        return response.read().decode("utf-8")


def _write_review_fixture(root):
    _write_json(
        root / ".hermes" / "routing-proposals" / "route-ui" / "proposal.json",
        {"proposal_id": "route-ui", "requires_human_approval": True, "secret": "SHOULD_NOT_LEAK"},
    )
    _write_json(
        root / ".hermes" / "asset-proposals" / "asset-ui" / "proposal.json",
        {"proposal_id": "asset-ui", "status": "review_required", "token": "SHOULD_NOT_LEAK"},
    )


def test_review_inbox_api_route_returns_read_only_items_without_mutation(tmp_path) -> None:
    _write_review_fixture(tmp_path)
    before = {path.relative_to(tmp_path).as_posix(): path.stat().st_mtime_ns for path in tmp_path.rglob("*") if path.is_file()}

    with _api_server(tmp_path) as base_url:
        payload = _get_json(f"{base_url}/review-inbox")

    after = {path.relative_to(tmp_path).as_posix(): path.stat().st_mtime_ns for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before
    assert payload["mutates_state"] is False
    assert {item["item_type"] for item in payload["items"]} == {"asset_proposal", "routing_proposal"}
    assert {item["recommended_action"] for item in payload["items"]} == {
        "review_asset_proposal",
        "review_and_create_routing_proposal_approval",
    }
    assert [item["mutates_state"] for item in payload["items"]] == [False, False]
    assert all(item["evidence_path"].startswith(".hermes/") for item in payload["items"])
    assert str(tmp_path) not in json.dumps(payload, sort_keys=True)


def test_review_inbox_dashboard_renders_items_and_no_approval_controls(tmp_path) -> None:
    _write_review_fixture(tmp_path)

    with _api_server(tmp_path) as base_url:
        html = _get_html(f"{base_url}/dashboard/review-inbox")

    assert "Feiyue Review Inbox" in html
    assert "routing_proposal" in html
    assert "asset_proposal" in html
    assert "review_and_create_routing_proposal_approval" in html
    assert "review_asset_proposal" in html
    assert "mutates_state" in html
    assert "false" in html
    assert "SHOULD_NOT_LEAK" not in html
    assert str(tmp_path) not in html
    lower = html.lower()
    assert "<form" not in lower
    assert "method=\"post\"" not in lower
    assert "method='post'" not in lower
    assert "<button" not in lower
    assert "approve" not in lower
    assert "<pre>" not in html
    assert "JSON.stringify" not in html


def test_review_inbox_static_export_writes_offline_read_only_page(tmp_path) -> None:
    _write_review_fixture(tmp_path)

    result = export_static_runs_report(tmp_path, tmp_path / "report")

    assert result.review_inbox_index_path == tmp_path / "report" / "review-inbox" / "index.html"
    review_path = result.review_inbox_index_path
    assert review_path is not None
    assert review_path.exists()
    html = review_path.read_text(encoding="utf-8")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert "Offline read-only review surface" in html
    assert "Feiyue Review Inbox" in html
    assert "routing_proposal" in html
    assert "SHOULD_NOT_LEAK" not in html
    assert 'href="../index.html"' in html
    assert 'href="#review-json-unavailable-offline"' in html
    assert any(file["path"] == "review-inbox/index.html" for file in manifest["files"])
    assert "<form" not in html.lower()
    assert "<button" not in html.lower()


def test_render_review_inbox_dashboard_empty_state_is_read_only(tmp_path) -> None:
    html = render_review_inbox_dashboard(tmp_path)

    assert "No review inbox items found." in html
    assert "Read-only review surface" in html
    assert "mutates_state" in html
    assert "false" in html
    assert "<form" not in html.lower()
    assert "<button" not in html.lower()
