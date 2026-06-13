from pathlib import Path

import pytest
from pydantic import ValidationError

from feiyue_core.workflow.model_routing_table import (
    MODEL_ROUTING_FILENAME,
    REQUIRED_MODEL_ROUTING_ROLES,
    ModelRoutingTable,
    ModelRoutingTableInitializer,
    ModelRoutingTableLoader,
    RoleRoute,
)


def test_role_route_rejects_blank_configured_model_names() -> None:
    with pytest.raises(ValidationError):
        RoleRoute(primary="   ")

    with pytest.raises(ValidationError):
        RoleRoute(primary="claude", fallback="\t")


def test_model_routing_table_requires_default_roles() -> None:
    routes = {
        role: RoleRoute(primary=f"{role}-model")
        for role in REQUIRED_MODEL_ROUTING_ROLES
        if role != "curator"
    }

    with pytest.raises(ValidationError, match="curator"):
        ModelRoutingTable(routes=routes)


def test_parse_yaml_like_text_and_json_fallback_are_provider_free() -> None:
    yaml_text = """
routes:
  worker:
    primary: claude-sonnet
    fallback: codex
    reviewer: gemini-3.1-pro
  creative_expansion:
    primary: claude-opus
  prd:
    primary: claude-sonnet
  spec:
    primary: claude-sonnet
  teacher_debug:
    primary: claude-opus
    teacher: teacher-profile
  curator:
    primary: curator-profile
"""

    table = ModelRoutingTable.parse_yaml(yaml_text)

    assert table.routes["worker"] == RoleRoute(
        primary="claude-sonnet",
        fallback="codex",
        reviewer="gemini-3.1-pro",
    )
    assert table.routes["teacher_debug"].teacher == "teacher-profile"

    json_text = """
{
  "routes": {
    "creative_expansion": {"primary": "claude-opus"},
    "prd": {"primary": "claude-sonnet"},
    "spec": {"primary": "claude-sonnet"},
    "worker": {"primary": "codex"},
    "teacher_debug": {"primary": "claude-opus"},
    "curator": {"primary": "claude-sonnet"}
  }
}
"""

    assert ModelRoutingTable.parse_yaml(json_text).routes["worker"].primary == "codex"


def test_render_yaml_is_deterministic_and_uses_stable_required_role_order() -> None:
    table = ModelRoutingTable(
        routes={
            "worker": RoleRoute(primary="worker-model", fallback="worker-fallback"),
            "curator": RoleRoute(primary="curator-model"),
            "teacher_debug": RoleRoute(primary="teacher-model", teacher="debug-teacher"),
            "spec": RoleRoute(primary="spec-model", reviewer="spec-reviewer"),
            "prd": RoleRoute(primary="prd-model"),
            "creative_expansion": RoleRoute(primary="creative-model"),
            "extra_role": RoleRoute(primary="extra-model"),
        }
    )

    assert table.render_yaml() == (
        "routes:\n"
        "  creative_expansion:\n"
        "    primary: creative-model\n"
        "  prd:\n"
        "    primary: prd-model\n"
        "  spec:\n"
        "    primary: spec-model\n"
        "    reviewer: spec-reviewer\n"
        "  worker:\n"
        "    primary: worker-model\n"
        "    fallback: worker-fallback\n"
        "  teacher_debug:\n"
        "    primary: teacher-model\n"
        "    teacher: debug-teacher\n"
        "  curator:\n"
        "    primary: curator-model\n"
        "  extra_role:\n"
        "    primary: extra-model\n"
    )


def test_loader_reads_project_local_model_routing_table(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    hermes_dir = project_root / ".hermes"
    hermes_dir.mkdir(parents=True)
    (hermes_dir / MODEL_ROUTING_FILENAME).write_text(
        ModelRoutingTable.default().render_yaml(),
        encoding="utf-8",
    )

    loaded = ModelRoutingTableLoader(project_root).load()

    assert list(loaded.routes) == list(REQUIRED_MODEL_ROUTING_ROLES)
    assert loaded.routes["worker"].primary != ""


def test_initializer_creates_default_file_without_overwriting_unless_requested(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    initializer = ModelRoutingTableInitializer(project_root)

    created_path = initializer.initialize()

    assert created_path == project_root / ".hermes" / MODEL_ROUTING_FILENAME
    assert created_path.is_file()
    assert ModelRoutingTableLoader(project_root).load() == ModelRoutingTable.default()

    created_path.write_text("custom: true\n", encoding="utf-8")
    initializer.initialize()
    assert created_path.read_text(encoding="utf-8") == "custom: true\n"

    initializer.initialize(overwrite=True)
    assert created_path.read_text(encoding="utf-8") == ModelRoutingTable.default().render_yaml()
