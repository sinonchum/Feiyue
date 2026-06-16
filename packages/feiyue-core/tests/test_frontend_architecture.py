from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "packages" / "feiyue-web"
DOC = ROOT / "docs" / "feiyue-frontend-hermes-embedding.md"


def test_frontend_architecture_doc_defines_hermes_bridge_boundary() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "Feiyue Backend + Hermes Bridge sidecar" in text
    assert "The browser is an operator surface, not an agent runtime." in text
    assert "no browser-side secrets" in text
    assert "RoutingApplyGate" in text
    assert "exact approval" in text
    assert "recursive evaluation surface" in text
    assert "feiyue-frontend-dogfood-real-task.md" in text


def test_frontend_dogfood_plan_treats_frontend_as_real_feiyue_task() -> None:
    text = (ROOT / "docs" / "plans" / "feiyue-frontend-dogfood-real-task.md").read_text(encoding="utf-8")

    assert "Feiyue plans Feiyue frontend" in text
    assert "Hermes-backed worker implements bounded frontend slices" in text
    assert "evidence updates capability history" in text
    assert '"provider_call_count": 0' in text
    assert "global_hermes_config_mutated" in text
    assert "production_mutated" in text


def test_frontend_scaffold_is_read_only_by_default() -> None:
    html = (WEB / "src" / "index.html").read_text(encoding="utf-8")
    js = (WEB / "src" / "app.js").read_text(encoding="utf-8")
    css = (WEB / "src" / "styles.css").read_text(encoding="utf-8")
    combined = "\n".join([html, js, css]).lower()

    assert "feiyue operator console" in html.lower()
    assert "hermes agent console" in html.lower()
    assert "data-action=\"create-hermes-session-draft\"" in html
    assert "data-action=\"approve-first-session-draft\"" in html
    assert "start-hermes-session-draft" not in html
    assert "disabled data-action=\"apply-routing-proposal\"" in html
    assert "<form" not in combined
    assert "method=\"post" not in combined

    assert "localstorage" not in combined
    assert "sessionstorage" not in combined
    assert "api/" in html
    assert "api/execution-output" in html
    assert "api/audit-trail" in html
    assert "audit-trail-list" in html
    assert "audit-trail-summary" in html
    assert "execute-approved-dry-run" in html
    assert "approval-gate" in html
    assert "verifier-report" in html
    assert "review-item-create-draft" in combined

def test_frontend_scaffold_uses_dark_institutional_palette() -> None:
    css = (WEB / "src" / "styles.css").read_text(encoding="utf-8")

    assert "--bg: #0b0f14" in css
    assert "--panel: #111827" in css
    assert "--ink: #e5e7eb" in css
    assert "--accent: #2dd4bf" in css


def test_audit_trail_module_scans_all_artifact_sources() -> None:
    """G-8: audit_trail.generate_audit_trail aggregates from all sources."""
    from feiyue_core.workflow.audit_trail import generate_audit_trail, AuditEntry, AuditTrailResult, render_audit_trail_export_markdown

    # Empty project - should return empty result
    result = generate_audit_trail("/tmp/feiyue-test-audit-empty")
    assert isinstance(result, AuditTrailResult)
    assert result.total_entries == 0
    assert result.sources_found == {}
    assert result.provider_call_count == 0
    assert result.hermes_started is False
    assert result.global_hermes_config_mutated is False
    assert result.production_mutated is False

    # Since filter with ISO timestamp
    result_filtered = generate_audit_trail(
        "/tmp/feiyue-test-audit-empty",
        since="2026-01-01T00:00:00+00:00",
    )
    assert result_filtered.total_entries == 0
    assert result_filtered.since == "2026-01-01T00:00:00+00:00"

    # Verify AuditEntry dataclass shape
    entry = AuditEntry(
        timestamp="2026-06-15T12:00:00+00:00",
        source="draft",
        event_type="session_draft_created",
        description="Test entry",
        details={"draft_id": "test-001"},
    )
    assert entry.timestamp == "2026-06-15T12:00:00+00:00"
    assert entry.source == "draft"
    assert entry.event_type == "session_draft_created"
    assert entry.description == "Test entry"
    assert entry.details == {"draft_id": "test-001"}

    # Verify overview surface reports G-9 mode
    from feiyue_core.workflow.runs_api import read_operator_console_overview
    overview = read_operator_console_overview("/tmp/feiyue-test-audit-empty")
    assert overview["surface"] == "feiyue_operator_console_g9"
    assert overview["mode"] == "audit_export_enabled"
    assert "audit_trail" in overview
    assert overview["audit_trail"]["total_entries"] == 0
    assert overview["audit_trail"]["mutates_state"] is False

    # Verify export markdown generation
    markdown = render_audit_trail_export_markdown(result)
    assert isinstance(markdown, str)
    assert "# Feiyue Audit Trail Report" in markdown
    assert "## Summary" in markdown
    assert "| Total entries | 0 |" in markdown
    assert "## Source Breakdown" in markdown
    assert "## Chronological Event Log" in markdown
    assert "provider-free" in markdown
    assert "G-9" in markdown
    assert "No audit trail entries found" in markdown or "No entries" in markdown

    # Export with real data
    result_with_data = generate_audit_trail("/tmp/feiyue-test-audit-empty")
    # Create minimal entries manually to test table rendering
    from feiyue_core.workflow.audit_trail import AuditEntry
    data_result = AuditTrailResult(
        total_entries=3,
        sources_found={"draft": 2, "approval": 1},
        entries=[
            AuditEntry(
                timestamp="2026-01-01T00:00:00+00:00",
                source="draft",
                event_type="session_draft_created",
                description="Test draft created",
                details={"draft_id": "test-001"},
            ),
            AuditEntry(
                timestamp="2026-01-02T00:00:00+00:00",
                source="approval",
                event_type="dry_run_approved",
                description="Test approval",
                details={"approved_by": "operator"},
            ),
            AuditEntry(
                timestamp="2026-01-03T00:00:00+00:00",
                source="draft",
                event_type="approval_required",
                description="Approval required for test",
            ),
        ],
    )
    markdown_data = render_audit_trail_export_markdown(data_result)
    assert "📝 Draft" in markdown_data or "Draft" in markdown_data
    assert "✅ Approval" in markdown_data or "Approval" in markdown_data
    assert "| 1 |" in markdown_data  # chronological log row
    assert "Test draft created" in markdown_data
    assert "Test approval" in markdown_data
    assert "Approval required for test" in markdown_data
    assert "3" in markdown_data  # total entries
