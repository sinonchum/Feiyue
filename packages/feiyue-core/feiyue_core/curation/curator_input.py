from __future__ import annotations

from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow import (
    BugDossier,
    LessonPacket,
    ModelRoutingTable,
    RegressionCheck,
    TaskContract,
)

DEFAULT_MAX_TEACHER_GUIDANCE_CHARS = 2000
DEFAULT_MAX_VERIFIER_EVIDENCE_CHARS = 2000


class CuratorInput(FeiyueModel):
    """Provider-free bundle of task context prepared for curator review."""

    input_id: str
    task_contract_markdown: str
    bug_dossier_markdown: str | None = None
    teacher_guidance: str | None = None
    verifier_evidence_summary: str | None = None
    lesson_packet_markdown: str | None = None
    regression_check_id: str | None = None
    routing_role: str | None = None
    routing_primary: str | None = None
    source_task_id: str

    @classmethod
    def from_assets(
        cls,
        *,
        input_id: str,
        task_contract: TaskContract,
        bug_dossier: BugDossier | None = None,
        teacher_guidance: str | None = None,
        verifier_evidence_summary: str | None = None,
        lesson_packet: LessonPacket | None = None,
        regression_check: RegressionCheck | None = None,
        routing_table: ModelRoutingTable | None = None,
        routing_role: str | None = None,
        max_teacher_guidance_chars: int = DEFAULT_MAX_TEACHER_GUIDANCE_CHARS,
        max_verifier_evidence_chars: int = DEFAULT_MAX_VERIFIER_EVIDENCE_CHARS,
    ) -> "CuratorInput":
        """Bundle workflow assets into a deterministic curator input model.

        Text supplied by teacher/verifier channels is bounded before storage so the
        rendered bundle is safe to pass through provider-specific prompts later.
        This helper only uses local renderers and never performs network calls.
        """

        routing_primary = None
        if routing_table is not None and routing_role is not None:
            route = routing_table.routes.get(routing_role)
            if route is not None:
                routing_primary = route.primary

        return cls(
            input_id=input_id,
            task_contract_markdown=task_contract.render_markdown(),
            bug_dossier_markdown=(
                bug_dossier.render_markdown() if bug_dossier is not None else None
            ),
            teacher_guidance=_truncate_optional_text(
                teacher_guidance,
                max_teacher_guidance_chars,
                parameter_name="max_teacher_guidance_chars",
            ),
            verifier_evidence_summary=_truncate_optional_text(
                verifier_evidence_summary,
                max_verifier_evidence_chars,
                parameter_name="max_verifier_evidence_chars",
            ),
            lesson_packet_markdown=(
                lesson_packet.render_markdown() if lesson_packet is not None else None
            ),
            regression_check_id=(
                regression_check.check_id if regression_check is not None else None
            ),
            routing_role=routing_role,
            routing_primary=routing_primary,
            source_task_id=task_contract.task_id,
        )

    def render_markdown(self) -> str:
        """Render deterministic Markdown with all expected curator sections."""

        sections = [
            f"# Curator Input: {self.input_id}",
            f"## Source Task\n{self.source_task_id}",
            "## Task Contract\n" + self.task_contract_markdown.strip(),
            "## Bug Dossier\n" + _optional_block(self.bug_dossier_markdown),
            "## Teacher Guidance\n" + _optional_block(self.teacher_guidance),
            "## Verifier Evidence Summary\n"
            + _optional_block(self.verifier_evidence_summary),
            "## Lesson Packet\n" + _optional_block(self.lesson_packet_markdown),
            "## Regression Check\n" + self._render_regression_check(),
            "## Routing Context\n" + self._render_routing_context(),
        ]
        return "\n\n".join(sections) + "\n"

    def _render_regression_check(self) -> str:
        if self.regression_check_id is None:
            return "- None"
        return f"- ID: {self.regression_check_id}"

    def _render_routing_context(self) -> str:
        if self.routing_role is None and self.routing_primary is None:
            return "- None"
        return "\n".join(
            [
                f"- Role: {_render_optional_scalar(self.routing_role)}",
                f"- Primary: {_render_optional_scalar(self.routing_primary)}",
            ]
        )


def _optional_block(value: str | None) -> str:
    if value is None:
        return "- None"
    return value.strip()


def _render_optional_scalar(value: str | None) -> str:
    if value is None:
        return "None"
    return value


def _truncate_optional_text(
    value: str | None, max_chars: int, *, parameter_name: str
) -> str | None:
    if value is None:
        return None
    return _truncate_text(value, max_chars, parameter_name=parameter_name)


def _truncate_text(value: str, max_chars: int, *, parameter_name: str) -> str:
    if max_chars < 0:
        raise ValueError(f"{parameter_name} must be non-negative")
    if len(value) <= max_chars:
        return value
    omitted = len(value) - max_chars
    return f"{value[:max_chars]}... [truncated {omitted} chars]"
