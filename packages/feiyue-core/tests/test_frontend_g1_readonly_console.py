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


def _post_json(url, payload):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        assert response.headers["content-type"] == "application/json"
        return response.status, json.loads(response.read().decode("utf-8"))


def _get_text(url):
    with urlopen(url, timeout=5) as response:
        return response.headers["content-type"], response.read().decode("utf-8")


def _write_g3_fixture(root):
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
    _write_json(
        root / ".hermes" / "routing-proposals" / "route-ui" / "proposal.json",
        {"proposal_id": "route-ui", "requires_human_approval": True, "secret": "SHOULD_NOT_LEAK_IN_INTENT"},
    )


def test_g3_overview_api_reports_hermes_dry_run_mode_without_raw_secret_leak(tmp_path) -> None:
    _write_g3_fixture(tmp_path)
    before = {path.relative_to(tmp_path).as_posix(): path.stat().st_mtime_ns for path in tmp_path.rglob("*") if path.is_file()}

    overview = read_operator_console_overview(tmp_path)

    after = {path.relative_to(tmp_path).as_posix(): path.stat().st_mtime_ns for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before
    assert overview["surface"] == "feiyue_operator_console_g9"
    assert overview["mode"] == "audit_export_enabled"
    assert overview["mutates_state"] is False
    assert overview["write_endpoints_added"] == 6
    assert overview["provider_call_count"] == 0
    assert overview["hermes_started"] is False
    assert overview["routing"]["worker_primary"] == "local-qwen25-coder"
    assert overview["capabilities"]["history_status"] == "found"
    assert overview["frontend_dogfood"]["total_runs"] == 1
    assert overview["review_intents"] == {"total_drafts": 0, "draft_only": True}
    assert overview["hermes_sessions"] == {"total_drafts": 0, "dry_run_only": True}
    assert overview["approval_gate"] == {"total_approvals": 0, "dry_run_only": True}
    assert overview["verifier_report"]["total_approvals"] == 0
    assert overview["verifier_report"]["total_anomalies"] == 0
    assert overview["verifier_report"]["all_boundary_preserved"] is True
    assert overview["templates"]["from_review_inbox"] is True
    assert overview["templates"]["review_item_count"] >= 0
    assert overview["execution_output"]["total_outputs"] >= 0
    assert overview["execution_output"]["dry_run_only_executions"] is True
    assert overview["execution_output"]["provider_call_count"] == 0
    assert overview["audit_trail"] == {"total_entries": 0, "sources": {}, "mutates_state": False}
    assert "SHOULD_NOT_LEAK" not in json.dumps(overview, sort_keys=True)


def test_g4_api_routes_and_app_shell_are_served(tmp_path) -> None:
    _write_g3_fixture(tmp_path)

    with _api_server(tmp_path) as base_url:
        app_content_type, html = _get_text(f"{base_url}/app")
        css_content_type, css = _get_text(f"{base_url}/app/styles.css")
        js_content_type, js = _get_text(f"{base_url}/app/app.js")
        overview = _get_json(f"{base_url}/api/overview")
        routing = _get_json(f"{base_url}/api/routing")
        capabilities = _get_json(f"{base_url}/api/capabilities")
        dogfood = _get_json(f"{base_url}/api/frontend-dogfood")
        intents = _get_json(f"{base_url}/api/review-intents")
        sessions = _get_json(f"{base_url}/api/hermes-session-drafts")
        approvals = _get_json(f"{base_url}/api/approval-gate")
        verifier = _get_json(f"{base_url}/api/verifier-report")

    assert app_content_type == "text/html; charset=utf-8"
    assert css_content_type == "text/css; charset=utf-8"
    assert js_content_type == "text/javascript; charset=utf-8"
    assert "Feiyue Operator Console" in html
    assert "Review Intent Drafts" in html
    assert "Session Draft Events" in html
    assert "Dry-Run Approvals" in html
    assert "Verifier Evidence Dashboard" in html
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
    assert intents["drafts"] == []
    assert intents["write_endpoints_added"] == 1
    assert sessions["drafts"] == []
    assert sessions["hermes_started"] is False
    assert approvals["approvals"] == []
    assert approvals["dry_run_only"] is True
    assert approvals["hermes_started"] is False
    assert verifier["total_approvals"] == 0
    assert "SHOULD_NOT_LEAK" not in json.dumps(dogfood, sort_keys=True)


def test_g2_review_intent_post_creates_draft_only_artifact(tmp_path) -> None:
    _write_g3_fixture(tmp_path)
    request_payload = {
        "item_type": "routing_proposal",
        "item_id": "route-ui",
        "recommended_action": "review_and_create_routing_proposal_approval",
        "evidence_path": ".hermes/routing-proposals/route-ui/proposal.json",
        "created_by": "test-operator",
        "reason": "g2_test_intent_draft",
    }

    with _api_server(tmp_path) as base_url:
        status, created = _post_json(f"{base_url}/api/review-intents", request_payload)
        listed = _get_json(f"{base_url}/api/review-intents")

    assert status == 201
    assert created["draft_only"] is True
    assert created["mutation_scope"] == "project_local_review_intent_draft_only"
    assert created["provider_call_count"] == 0
    assert created["global_hermes_config_mutated"] is False
    assert created["production_mutated"] is False
    assert created["draft"]["intent_kind"] == "routing_approval_draft"
    assert created["draft"]["writes_approval"] is False
    assert created["draft"]["applies_routing"] is False
    assert created["draft"]["starts_hermes_session"] is False
    draft_path = tmp_path / created["path"]
    assert draft_path.exists()
    assert listed["drafts"][0]["intent_id"] == created["draft"]["intent_id"]
    assert "SHOULD_NOT_LEAK" not in json.dumps(created, sort_keys=True)


def test_g2_rejects_intent_for_non_matching_review_item(tmp_path) -> None:
    _write_g3_fixture(tmp_path)
    request_payload = {
        "item_type": "routing_proposal",
        "item_id": "route-ui",
        "recommended_action": "apply_approved_routing_proposal",
        "evidence_path": ".hermes/routing-proposals/route-ui/proposal.json",
        "created_by": "test-operator",
        "reason": "mismatched_action",
    }

    with _api_server(tmp_path) as base_url:
        request = Request(
            f"{base_url}/api/review-intents",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            assert exc.code == 404
            payload = json.loads(exc.read().decode("utf-8"))
        else:  # pragma: no cover - defensive
            raise AssertionError("POST unexpectedly succeeded")

    assert payload["error"] == "review_intent_draft_rejected"
    assert not list((tmp_path / ".hermes" / "review-intent-drafts").glob("*/intent.json"))


def test_g3_hermes_session_post_creates_provider_free_draft_and_events(tmp_path) -> None:
    _write_g3_fixture(tmp_path)
    request_payload = {
        "goal": "Inspect evidence and plan next UI slice; dry-run only.",
        "profile": "dry-run",
        "toolsets": ["none"],
        "created_by": "test-operator",
        "reason": "g3_test_provider_free_dry_run",
        "dry_run_only": True,
        "provider_call_budget": 0,
    }

    with _api_server(tmp_path) as base_url:
        status, created = _post_json(f"{base_url}/api/hermes-session-drafts", request_payload)
        listed = _get_json(f"{base_url}/api/hermes-session-drafts")
        events = _get_json(f"{base_url}/api/hermes-session-events/{created['draft']['draft_id']}")

    assert status == 201
    assert created["dry_run_only"] is True
    assert created["provider_call_count"] == 0
    assert created["hermes_started"] is False
    assert created["global_hermes_config_mutated"] is False
    assert created["production_mutated"] is False
    assert created["draft"]["status"] == "blocked_until_exact_approval"
    assert created["draft"]["approval_required"] is True
    assert created["draft"]["provider_call_budget"] == 0
    assert created["draft"]["tool_call_count"] == 0
    assert (tmp_path / created["draft_path"]).exists()
    assert (tmp_path / created["events_path"]).exists()
    assert listed["drafts"][0]["draft_id"] == created["draft"]["draft_id"]
    assert [event["event_type"] for event in events] == [
        "session_draft_created",
        "policy_checked",
        "approval_required",
        "blocked_until_exact_approval",
    ]
    assert all(event["provider_call_count"] == 0 for event in events)


def test_g3_rejects_real_hermes_session_escalation(tmp_path) -> None:
    with _api_server(tmp_path) as base_url:
        request = Request(
            f"{base_url}/api/hermes-session-drafts",
            data=json.dumps(
                {
                    "goal": "Start a real session",
                    "profile": "dry-run",
                    "toolsets": ["none"],
                    "dry_run_only": False,
                    "provider_call_budget": 1,
                }
            ).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            assert exc.code == 400
            payload = json.loads(exc.read().decode("utf-8"))
        else:  # pragma: no cover - defensive
            raise AssertionError("POST unexpectedly succeeded")

    assert payload["error"] == "invalid_hermes_session_draft"
    assert not list((tmp_path / ".hermes" / "hermes-session-drafts").glob("*/draft.json"))


def test_g4_approve_dry_run_creates_exact_approval_and_updates_draft(tmp_path) -> None:
    _write_g3_fixture(tmp_path)
    root = tmp_path

    # Use an inline server for both create and approve
    with _api_server(root) as base_url:
        # Create draft
        status, created = _post_json(
            f"{base_url}/api/hermes-session-drafts",
            {
                "goal": "G-4 dogfood: test approval gate after session draft.",
                "profile": "dry-run",
                "toolsets": ["none"],
                "created_by": "test-operator",
                "reason": "g4_test_session_draft",
                "dry_run_only": True,
                "provider_call_budget": 0,
            },
        )
        assert status == 201
        draft_id = created["draft"]["draft_id"]

        # 2. Approve it
        status, approved = _post_json(
            f"{base_url}/api/hermes-session-drafts/{draft_id}/approve-dry-run",
            {
                "approved_by": "test-verifier",
                "reason": "g4_test_dry_run_approval",
                "dry_run_only_verified": True,
                "provider_call_budget_verified": 0,
                "no_hermes_start_verified": True,
                "no_production_mutation_verified": True,
                "no_global_config_mutation_verified": True,
            },
        )
        assert status == 201

        # 3. Read back
        approval = _get_json(f"{base_url}/api/approval-gate/{draft_id}")
        draft = _get_json(f"{base_url}/api/hermes-session-drafts/{draft_id}")

    # Assert approval
    assert approved["approval"]["draft_id"] == draft_id
    assert approved["approval"]["status"] == "approved_dry_run"
    assert approved["approval"]["approved_by"] == "test-verifier"
    assert approved["dry_run_only"] is True
    assert approved["provider_call_count"] == 0
    assert approved["hermes_started"] is False
    assert approved["global_hermes_config_mutated"] is False
    assert approved["production_mutated"] is False

    # Assert approval artifacts
    gate_dir = root / ".hermes" / "approval-gate" / draft_id
    assert (gate_dir / "approval.json").exists()
    assert (gate_dir / "verifier-evidence.json").exists()
    assert (gate_dir / "events.json").exists()

    # Assert draft status updated
    assert draft["status"] == "approved_dry_run"
    assert draft["approval_required"] is True
    assert draft["hermes_started"] is False

    # Assert approval API lists it
    assert approval["approval_id"] == draft_id
    assert approval["status"] == "approved_dry_run"


def test_g4_rejects_approval_for_nonexistent_draft(tmp_path) -> None:
    with _api_server(tmp_path) as base_url:
        request = Request(
            f"{base_url}/api/hermes-session-drafts/fake-id-12345/approve-dry-run",
            data=json.dumps({
                "approved_by": "test",
                "reason": "test",
                "dry_run_only_verified": True,
                "provider_call_budget_verified": 0,
                "no_hermes_start_verified": True,
                "no_production_mutation_verified": True,
                "no_global_config_mutation_verified": True,
            }).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            assert exc.code == 404
            payload = json.loads(exc.read().decode("utf-8"))
        else:  # pragma: no cover - defensive
            raise AssertionError("POST unexpectedly succeeded")

    assert payload["error"] == "dry_run_approval_rejected"


def test_g4_rejects_approval_escalation_with_provider_budget(tmp_path) -> None:
    _write_g3_fixture(tmp_path)
    root = tmp_path
    draft_id = None

    with _api_server(root) as base_url:
        # Create draft
        status, created = _post_json(
            f"{base_url}/api/hermes-session-drafts",
            {
                "goal": "G-4 escalation test",
                "profile": "dry-run",
                "toolsets": ["none"],
                "created_by": "test",
                "reason": "escalation_test",
                "dry_run_only": True,
                "provider_call_budget": 0,
            },
        )
        assert status == 201
        draft_id = created["draft"]["draft_id"]

        # Try to approve with dry_run_only_verified=False
        import urllib.error
        req = Request(
            f"{base_url}/api/hermes-session-drafts/{draft_id}/approve-dry-run",
            data=json.dumps({
                "approved_by": "test",
                "reason": "attempted_escalation",
                "dry_run_only_verified": False,
                "provider_call_budget_verified": 0,
                "no_hermes_start_verified": True,
                "no_production_mutation_verified": True,
                "no_global_config_mutation_verified": True,
            }).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            payload = json.loads(exc.read().decode("utf-8"))
        else:
            raise AssertionError("POST unexpectedly succeeded")

    assert payload["error"] == "invalid_dry_run_approval"


def test_g3_other_write_methods_remain_blocked(tmp_path) -> None:
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
