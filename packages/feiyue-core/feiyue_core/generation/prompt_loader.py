from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from feiyue_core.schemas import TaskSpec
from feiyue_core.schemas.common import FeiyueModel


class PromptTemplateError(FileNotFoundError):
    pass


class PromptArtifact(FeiyueModel):
    name: str
    version: str
    template: str
    template_hash: str
    rendered_prompt: str | None = None
    rendered_hash: str | None = None


class PromptTemplateLoader:
    def __init__(self, template_dir: Path | None = None) -> None:
        self.template_dir = template_dir or Path(__file__).with_name("prompts")

    def load(self, name: str) -> PromptArtifact:
        path = self.template_dir / f"{name}.md"
        if not path.exists():
            raise PromptTemplateError(f"prompt template {name!r} not found at {path}")
        template = path.read_text(encoding="utf-8")
        version = self._extract_version(template)
        return PromptArtifact(
            name=name,
            version=version,
            template=template,
            template_hash=self._hash(template),
        )

    def render_student_candidate_prompt(self, *, task: TaskSpec, output_schema: dict[str, Any]) -> PromptArtifact:
        artifact = self.load("student_candidate_generation")
        target_files = task.metadata.get("target_files", [])
        constraints = task.metadata.get("constraints", [])
        rendered = artifact.template.format(
            task_id=task.id,
            task_title=task.title,
            task_type=task.type.value,
            task_goal=task.goal,
            acceptance_criteria=self._bullets(task.acceptance_criteria),
            target_files=self._bullets(target_files),
            constraints=self._bullets(constraints),
            output_schema=json.dumps(output_schema, ensure_ascii=False, sort_keys=True, indent=2),
        )
        return PromptArtifact(
            name=artifact.name,
            version=artifact.version,
            template=artifact.template,
            template_hash=artifact.template_hash,
            rendered_prompt=rendered,
            rendered_hash=self._hash(rendered),
        )

    @staticmethod
    def _extract_version(template: str) -> str:
        for line in template.splitlines():
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()
        return "unversioned"

    @staticmethod
    def _hash(text: str) -> str:
        return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _bullets(values: object) -> str:
        if not isinstance(values, list) or not values:
            return "- none"
        return "\n".join(f"- {value}" for value in values)
