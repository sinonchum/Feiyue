"""Provider-free project knowledge layer.

This module manages the project-local `.hermes/` knowledge files that are
shared with workers as deterministic Markdown context. It intentionally uses
only local filesystem access and has no provider or network dependencies.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

KNOWLEDGE_FILENAMES: tuple[str, ...] = (
    "project-memory.md",
    "rules.md",
    "design-laws.md",
    "architecture.md",
)

_FIELD_BY_FILENAME: dict[str, str] = {
    "project-memory.md": "project_memory",
    "rules.md": "rules",
    "design-laws.md": "design_laws",
    "architecture.md": "architecture",
}

_SECTION_BY_FIELD: tuple[tuple[str, str], ...] = (
    ("project_memory", "Project Memory"),
    ("rules", "Rules"),
    ("design_laws", "Design Laws"),
    ("architecture", "Architecture"),
)

_DEFAULT_CONTENT: dict[str, str] = {
    "project-memory.md": "# Project Memory\n\nCapture stable project facts, decisions, and lessons learned here.\n",
    "rules.md": "# Rules\n\nCapture project-specific operating rules and constraints here.\n",
    "design-laws.md": "# Design Laws\n\nCapture durable product, UX, and design principles here.\n",
    "architecture.md": "# Architecture\n\nCapture system structure, boundaries, and important technical decisions here.\n",
}

KnowledgeField = Literal["project_memory", "rules", "design_laws", "architecture"]


class ProjectKnowledge(BaseModel):
    """Typed, dict-like model for project-local knowledge files."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    project_memory: str | None = None
    rules: str | None = None
    design_laws: str | None = None
    architecture: str | None = None
    missing_files: list[str] = Field(default_factory=list)

    def __getitem__(self, key: KnowledgeField | str) -> str | list[str] | None:
        if key not in type(self).model_fields:
            raise KeyError(key)
        return getattr(self, key)

    def keys(self) -> Iterator[str]:
        return iter(type(self).model_fields)

    def items(self) -> Iterator[tuple[str, Any]]:
        for key in self.keys():
            yield key, getattr(self, key)

    def values(self) -> Iterator[Any]:
        for key in self.keys():
            yield getattr(self, key)


class ProjectKnowledgeInitializer:
    """Create the `.hermes/` project knowledge directory and seed files."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.knowledge_dir = self.project_root / ".hermes"

    def initialize(self, *, overwrite: bool = False) -> list[Path]:
        """Create knowledge files, preserving existing files unless requested.

        Returns paths in deterministic knowledge-file order.
        """

        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for filename in KNOWLEDGE_FILENAMES:
            path = self.knowledge_dir / filename
            if overwrite or not path.exists():
                path.write_text(_DEFAULT_CONTENT[filename], encoding="utf-8")
            paths.append(path)
        return paths


class ProjectKnowledgeLoader:
    """Load project-local `.hermes/` knowledge files."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.knowledge_dir = self.project_root / ".hermes"

    def load(self) -> ProjectKnowledge:
        data: dict[str, str | None] = {}
        missing_files: list[str] = []

        for filename in KNOWLEDGE_FILENAMES:
            field_name = _FIELD_BY_FILENAME[filename]
            path = self.knowledge_dir / filename
            if path.is_file():
                data[field_name] = path.read_text(encoding="utf-8")
            else:
                data[field_name] = None
                missing_files.append(filename)

        return ProjectKnowledge(**data, missing_files=missing_files)


def build_worker_context(project_root: str | Path) -> str:
    """Build deterministic Markdown context for worker prompts."""

    knowledge = ProjectKnowledgeLoader(project_root).load()
    parts = ["# Project Knowledge Context"]

    for field_name, section_title in _SECTION_BY_FIELD:
        value = getattr(knowledge, field_name)
        rendered_value = value.rstrip() if value else "- None"
        parts.append(f"## {section_title}\n\n{rendered_value}")

    return "\n\n".join(parts) + "\n"
