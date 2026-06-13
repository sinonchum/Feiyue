from __future__ import annotations

import json

from feiyue_core.workflow.asset_catalog import AssetCatalog


def test_asset_catalog_empty_hermes_returns_zero_counts(tmp_path) -> None:
    (tmp_path / ".hermes").mkdir()

    summary = AssetCatalog(tmp_path).summary().model_dump(mode="json")

    assert summary["total_assets"] == 0
    assert summary["counts"] == {
        "lessons": 0,
        "evals": 0,
        "model_routing": 0,
        "capability_profiles": 0,
        "creative_proposals": 0,
        "asset_proposals": 0,
    }
    assert summary["categories"]["lessons"] == []
    assert summary["categories"]["evals"] == []


def test_asset_catalog_discovers_known_assets_with_relative_sanitized_metadata(tmp_path) -> None:
    hermes = tmp_path / ".hermes"
    (hermes / "lessons").mkdir(parents=True)
    (hermes / "evals").mkdir()
    (hermes / "capability-profiles").mkdir()
    (hermes / "creative-proposals").mkdir()
    (hermes / "asset-proposals").mkdir()

    (hermes / "lessons" / "lesson-123.md").write_text(
        "# Lesson Packet: lesson-123\n\nsecret_token=SHOULD_NOT_LEAK\n", encoding="utf-8"
    )
    (hermes / "evals" / "regression-checks.sh").write_text(
        "#!/usr/bin/env bash\n# API_KEY=SHOULD_NOT_LEAK\n", encoding="utf-8"
    )
    (hermes / "model-routing.yaml").write_text(
        "schema_version: feiyue.model_routing.v1\n# password: SHOULD_NOT_LEAK\n", encoding="utf-8"
    )
    (hermes / "capability-profiles" / "agent.json").write_text(
        json.dumps({"id": "agent-safe", "title": "Agent Capability", "secret": "SHOULD_NOT_LEAK"}),
        encoding="utf-8",
    )
    (hermes / "creative-proposals" / "variant.md").write_text(
        "# Creative Proposal Alpha\n\nBearer SHOULD_NOT_LEAK\n", encoding="utf-8"
    )
    (hermes / "asset-proposals" / "proposal.json").write_text(
        json.dumps({"proposal_id": "asset-9", "name": "Asset Proposal Nine", "token": "SHOULD_NOT_LEAK"}),
        encoding="utf-8",
    )

    summary = AssetCatalog(tmp_path).summary().model_dump(mode="json")
    rendered = json.dumps(summary, sort_keys=True)

    assert summary["total_assets"] == 6
    assert summary["counts"] == {
        "lessons": 1,
        "evals": 1,
        "model_routing": 1,
        "capability_profiles": 1,
        "creative_proposals": 1,
        "asset_proposals": 1,
    }
    assert summary["categories"]["lessons"] == [
        {"id": "lesson-123", "path": ".hermes/lessons/lesson-123.md", "title": "Lesson Packet: lesson-123"}
    ]
    assert summary["categories"]["model_routing"][0]["path"] == ".hermes/model-routing.yaml"
    assert summary["categories"]["capability_profiles"][0] == {
        "id": "agent-safe",
        "path": ".hermes/capability-profiles/agent.json",
        "title": "Agent Capability",
    }
    assert summary["categories"]["asset_proposals"][0]["id"] == "asset-9"
    assert "SHOULD_NOT_LEAK" not in rendered
    assert str(tmp_path) not in rendered
