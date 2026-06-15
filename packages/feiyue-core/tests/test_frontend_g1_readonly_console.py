from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from feiyue_core.workflow.runs_api import create_runs_api_handler, read_operator_console_overview


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


def _get_text(url):
    with urlopen(url, timeout=5) as response:
        return response.headers["content-type"], response.read().decode("utf-8")


def _write_g1_fixture(root):
    (root / ".hermes" / "model-routing.yaml").parent.mkdir(parents=True, exist_ok=True)
    (root / ".hermes" / "model-routing.yaml").write_text(
        "routes:\n"
        "  worker:\n"
        "    primary: local-qwen25-coder\n"
        "  curator:\n"
        "    primary: default\n",
        encoding="utf-8",
    )
    _write_json(
        root / ".hermes" / "capability-history" / "latest.json",
        {"profile_id": "local-qwen25-coder", "total_runs": 7, "secret": "SHOULD_NOT_LEAK_IN_OVERVIEW"},
    )
    _write_json(
        root / ".hermes" / "capability-feedback" / "latest.json",
        {"metrics": {"verification_rate": 1.0}},
    )
    _write_json(
        root / ".hermes" / "frontend-dogfood" / "g1-readonly-console" / "evidence.json",
        {
            "run_id": "g1-readonly-console",
            "status": "verified",
            "task_type": "feiyue_frontend_g1_readonly_console",
            "provider_call_count": 0,
            "global_hermes_config_mutated": False,
            "production_mutated": False,
            "secret": "SHOULD_NOT_LEAK_IN_DOGFOOD_SUMMARY",
        },
    )


def test_g1_overview_api_is_read_only_summary_without_raw_secret_leak(tmp_path) -> None:
    _write_g1_fixture(tmp_path)
    before = {path.relative_to(tmp_path).as_posix(): path.stat().st_mtime_ns for path in tmp_path.rglob("*") if path.is_file()}

    overview = read_operator_console_overview(tmp_path)

    after = {path.relative_to(tmp_path).as_posix(): path.stat().st_mtime_ns for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before
    assert overview["surface"] == "feiyue_operator_console_g1"
    assert overview["mode"] == "read_only"
    assert overview["mutates_state"] is False
    assert overview["write_endpoints_added"] == 0
    assert overview["provider_call_count"] == 0
    assert overview["routing"]["worker_primary"] == "local-qwen25-coder"
    assert overview["capabilities"]["history_status"] == "found"
    assert overview["frontend_dogfood"]["total_runs"] == 1
    assert "SHOULD_NOT_LEAK" not in json.dumps(overview, sort_keys=True)


def test_g1_api_routes_and_app_static_shell_are_served(tmp_path) -> None:
    _write_g1_fixture(tmp_path)

    with _api_server(tmp_path) as base_url:
        app_content_type, html = _get_text(f"{base_url}/app")
        css_content_type, css = _get_text(f"{base_url}/app/styles.css")
        js_content_type, js = _get_text(f"{base_url}/app/app.js")
        overview = _get_json(f"{base_url}/api/overview")
        routing = _get_json(f"{base_url}/api/routing")
        capabilities = _get_json(f"{base_url}/api/capabilities")
        dogfood = _get_json(f"{base_url}/api/frontend-dogfood")

    assert app_content_type == "text/html; charset=utf-8"
    assert css_content_type == "text/css; charset=utf-8"
    assert js_content_type == "text/javascript; charset=utf-8"
    assert "Feiyue Operator Console" in html
    assert 'href="/app/styles.css"' in html
    assert 'src="/app/app.js"' in html
    assert "GET /api/overview" in html
    assert "localStorage" not in js
    assert "sessionStorage" not in js
    assert "<form" not in html.lower()
    assert "method=\"post\"" not in html.lower()
    assert "#0b0f14" in css
    assert overview["routing"]["worker_primary"] == "local-qwen25-coder"
    assert routing["routes"]["worker"]["primary"] == "local-qwen25-coder"
    assert capabilities["history_status"] == "found"
    assert dogfood["runs"][0]["run_id"] == "g1-readonly-console"
    assert "SHOULD_NOT_LEAK" not in json.dumps(dogfood, sort_keys=True)


def test_g1_write_methods_remain_blocked(tmp_path) -> None:
    with _api_server(tmp_path) as base_url:
        request = Request(f"{base_url}/api/overview", method="POST")
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            assert exc.code == 405
            payload = json.loads(exc.read().decode("utf-8"))
        else:  # pragma: no cover - defensive
            raise AssertionError("POST unexpectedly succeeded")

    assert payload == {"error": "method_not_allowed", "method": "POST"}
