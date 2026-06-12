from pathlib import Path

from feiyue_core.workflow.project_knowledge import (
    KNOWLEDGE_FILENAMES,
    ProjectKnowledgeInitializer,
    ProjectKnowledgeLoader,
    build_worker_context,
)


def test_initializer_creates_project_knowledge_files_without_provider_dependency(tmp_path: Path) -> None:
    project_root = tmp_path / "project"

    created = ProjectKnowledgeInitializer(project_root).initialize()

    hermes_dir = project_root / ".hermes"
    assert hermes_dir.is_dir()
    assert [path.name for path in created] == list(KNOWLEDGE_FILENAMES)
    for filename in KNOWLEDGE_FILENAMES:
        file_path = hermes_dir / filename
        assert file_path.is_file()
        assert file_path.read_text(encoding="utf-8") != ""


def test_initializer_does_not_overwrite_existing_files_by_default(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    hermes_dir = project_root / ".hermes"
    hermes_dir.mkdir(parents=True)
    existing = hermes_dir / "rules.md"
    existing.write_text("custom rules\n", encoding="utf-8")

    ProjectKnowledgeInitializer(project_root).initialize()

    assert existing.read_text(encoding="utf-8") == "custom rules\n"


def test_initializer_overwrites_existing_files_when_requested(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    hermes_dir = project_root / ".hermes"
    hermes_dir.mkdir(parents=True)
    existing = hermes_dir / "rules.md"
    existing.write_text("custom rules\n", encoding="utf-8")

    ProjectKnowledgeInitializer(project_root).initialize(overwrite=True)

    assert existing.read_text(encoding="utf-8") != "custom rules\n"
    assert existing.read_text(encoding="utf-8") != ""


def test_loader_returns_typed_dict_like_model_and_deterministic_missing_diagnostics(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    hermes_dir = project_root / ".hermes"
    hermes_dir.mkdir(parents=True)
    (hermes_dir / "rules.md").write_text("Use deterministic output.\n", encoding="utf-8")
    (hermes_dir / "architecture.md").write_text("Layered core package.\n", encoding="utf-8")

    knowledge = ProjectKnowledgeLoader(project_root).load()

    assert knowledge.rules == "Use deterministic output.\n"
    assert knowledge["rules"] == "Use deterministic output.\n"
    assert knowledge.architecture == "Layered core package.\n"
    assert knowledge.project_memory is None
    assert knowledge.design_laws is None
    assert knowledge.missing_files == ["project-memory.md", "design-laws.md"]


def test_build_worker_context_renders_deterministic_markdown_and_none_for_missing(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    hermes_dir = project_root / ".hermes"
    hermes_dir.mkdir(parents=True)
    (hermes_dir / "project-memory.md").write_text("Remember constraints.\n", encoding="utf-8")
    (hermes_dir / "rules.md").write_text("No network calls.\n", encoding="utf-8")

    context = build_worker_context(project_root)

    assert context == (
        "# Project Knowledge Context\n\n"
        "## Project Memory\n\n"
        "Remember constraints.\n\n"
        "## Rules\n\n"
        "No network calls.\n\n"
        "## Design Laws\n\n"
        "- None\n\n"
        "## Architecture\n\n"
        "- None\n"
    )
