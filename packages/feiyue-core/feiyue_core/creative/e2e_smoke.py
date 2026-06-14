"""Provider-free creative-to-execution end-to-end smoke.

This module stitches the existing provider-free creative schemas to the workflow
contract/report types without calling providers, mutating global Hermes config, or
attempting promotion. It writes project-local curator-ready evidence under
``.hermes/creative-e2e/<run_id>/``.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from feiyue_core.creative.brief import CreativeBrief
from feiyue_core.creative.critique import CreativeCritique, CreativeCritiqueRecommendation
from feiyue_core.creative.selection import UserSelectionFeedback, UserSelectionStatus
from feiyue_core.creative.variant import CreativeVariant, CreativeVariantType
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.execution import WorkflowExecutionReport, WorkflowExecutionStatus
from feiyue_core.workflow.task_contract import TaskContract, build_task_contract

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class CreativeE2ESmokeEvidence(FeiyueModel):
    """Curator-ready evidence for one provider-free creative E2E smoke run."""

    run_id: str
    seed: str
    selected_variant_id: str
    task_contract_id: str
    workflow_status: str
    verifier_passed: bool
    dry_run_only: bool = True
    promotion_attempted: bool = False
    curator_proposal_ready: bool
    global_hermes_config_mutated: bool = False
    provider_call_count: int = Field(default=0, ge=0)
    created_at: str
    creative_brief: CreativeBrief
    variants: list[CreativeVariant]
    critiques: list[CreativeCritique]
    selection_feedback: UserSelectionFeedback
    prd_markdown: str
    spec_markdown: str
    task_contract: TaskContract
    workflow_report: WorkflowExecutionReport
    evidence_path: Path
    report_path: Path | None = None

    @field_validator("run_id", "seed", "selected_variant_id", "task_contract_id", "workflow_status", "created_at")
    @classmethod
    def _required_text(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("evidence text fields must not be empty")
        return normalized


class CreativeE2ESmokeRunner:
    """Deterministic provider-free creative-to-execution smoke runner."""

    def __init__(self, *, project_root: str | Path) -> None:
        self.project_root = Path(project_root)

    def run(self, *, run_id: str, seed: str, write_report: bool = False) -> CreativeE2ESmokeEvidence:
        run_id = _validate_run_id(run_id)
        seed = _validate_seed(seed)
        run_dir = self.project_root / ".hermes" / "creative-e2e" / run_id
        evidence_path = run_dir / "evidence.json"
        report_path = run_dir / "report.md" if write_report else None

        brief = _build_brief(run_id=run_id, seed=seed)
        variants = _build_variants(brief)
        critiques = _build_critiques(variants)
        selected = _select_variant(variants=variants, critiques=critiques)
        selection_feedback = UserSelectionFeedback(
            feedback_id=f"selection-{run_id}",
            brief_id=brief.brief_id,
            selected_variant_id=selected.variant_id,
            status=UserSelectionStatus.ACCEPTED,
            rationale="Provider-free deterministic selector chose the first pursue-ready variant with no constraint violations.",
            violated_design_laws=[],
            useful_aspects=["Maps a human seed into a bounded task contract", "Keeps execution dry-run only"],
            source_ids=[selected.variant_id, brief.brief_id],
        )
        prd_markdown = _render_prd(brief=brief, selected=selected, selection=selection_feedback)
        spec_markdown = _render_spec(brief=brief, selected=selected)
        contract = _build_task_contract(run_id=run_id, seed=seed, selected=selected)
        workflow_report = WorkflowExecutionReport(
            task_id=contract.task_id,
            status=WorkflowExecutionStatus.VERIFIED,
            changed_files=[],
            verification_passed=True,
            promotion_ready=False,
            source_repo_clean=True,
            sandbox_removed=True,
            verification_command="provider-free dry-run verifier: validate creative evidence and task contract only",
            execution_performed=False,
            retry_performed=False,
            attempt_count=1,
        )
        evidence = CreativeE2ESmokeEvidence(
            run_id=run_id,
            seed=seed,
            selected_variant_id=selected.variant_id,
            task_contract_id=contract.task_id,
            workflow_status=workflow_report.status.value,
            verifier_passed=workflow_report.verification_passed,
            dry_run_only=True,
            promotion_attempted=False,
            curator_proposal_ready=True,
            global_hermes_config_mutated=False,
            provider_call_count=0,
            created_at=datetime.now(UTC).isoformat(),
            creative_brief=brief,
            variants=variants,
            critiques=critiques,
            selection_feedback=selection_feedback,
            prd_markdown=prd_markdown,
            spec_markdown=spec_markdown,
            task_contract=contract,
            workflow_report=workflow_report,
            evidence_path=evidence_path,
            report_path=report_path,
        )
        _verify_evidence(evidence)
        run_dir.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(evidence.model_dump_json(indent=2), encoding="utf-8")
        if report_path is not None:
            report_path.write_text(_render_report(evidence), encoding="utf-8")
        return evidence


def run_creative_e2e_smoke(
    *,
    project_root: str | Path,
    run_id: str,
    seed: str,
    write_report: bool = False,
) -> CreativeE2ESmokeEvidence:
    """Run the provider-free creative E2E smoke and persist evidence."""

    return CreativeE2ESmokeRunner(project_root=project_root).run(
        run_id=run_id,
        seed=seed,
        write_report=write_report,
    )


def _validate_run_id(run_id: str) -> str:
    normalized = str(run_id).strip()
    if not normalized or not _RUN_ID_RE.fullmatch(normalized) or normalized in {".", ".."}:
        raise ValueError("run_id must be a non-empty safe slug containing only letters, numbers, dot, underscore, or dash")
    return normalized


def _validate_seed(seed: str) -> str:
    normalized = str(seed).strip()
    if not normalized:
        raise ValueError("seed must not be empty")
    return normalized


def _build_brief(*, run_id: str, seed: str) -> CreativeBrief:
    return CreativeBrief.from_project_knowledge(
        brief_id=f"brief-{run_id}",
        human_seed=seed,
        context=["Wave5-5 provider-free creative-to-execution smoke", "Project-local evidence only"],
        design_laws=["No live providers by default", "No global Hermes mutation", "No production side effects"],
        non_goals=["Production promotion", "Provider/profile subprocess execution"],
        constraints=["Persist under .hermes/creative-e2e/<run_id>/", "Emit curator-ready evidence"],
        target_users=["Curators", "Feiyue operators"],
        desired_outcomes=["A selected creative variant", "A rendered PRD/spec/task contract", "A verified dry-run workflow report"],
        source_ids=[f"seed:{run_id}"],
    )


def _build_variants(brief: CreativeBrief) -> list[CreativeVariant]:
    return [
        CreativeVariant(
            variant_id=f"{brief.brief_id}-high-impact",
            brief_id=brief.brief_id,
            variant_type=CreativeVariantType.HIGH_IMPACT,
            pitch="Turn the seed into a small deterministic product slice with evidence that a curator can review.",
            rationale="High impact comes from exercising the full creative-to-contract path while keeping execution fake and local.",
            risks=["May look like real execution if dry-run markers are omitted"],
            non_goals=brief.non_goals,
            verification_idea="Validate required evidence flags, selected variant linkage, and workflow report status.",
            required_capability_level="provider_free_workflow_contract",
            source_ids=[brief.brief_id, *brief.source_ids],
        ),
        CreativeVariant(
            variant_id=f"{brief.brief_id}-low-cost",
            brief_id=brief.brief_id,
            variant_type=CreativeVariantType.LOW_COST,
            pitch="Render only the selected contract and skip rich PRD/spec context.",
            rationale="Lower implementation cost but weaker curator evidence.",
            risks=["Curator may lack enough context to reuse the asset"],
            non_goals=brief.non_goals,
            verification_idea="Check evidence file presence only.",
            required_capability_level="schema_rendering",
            source_ids=[brief.brief_id, *brief.source_ids],
        ),
    ]


def _build_critiques(variants: list[CreativeVariant]) -> list[CreativeCritique]:
    critiques: list[CreativeCritique] = []
    for variant in variants:
        pursue = variant.variant_type == CreativeVariantType.HIGH_IMPACT
        critiques.append(
            CreativeCritique(
                critique_id=f"critique-{variant.variant_id}",
                variant_id=variant.variant_id,
                constraint_violations=[] if pursue else ["Less complete curator evidence"],
                risk_assessment="Dry-run markers and zero provider-call evidence make the path safe by default." if pursue else "Safe but less useful for Wave5-5 acceptance.",
                feasibility_notes="Uses existing creative schemas plus TaskContract and WorkflowExecutionReport types.",
                verification_cost="deterministic in-process validation",
                recommendation=CreativeCritiqueRecommendation.PURSUE if pursue else CreativeCritiqueRecommendation.REVISE,
                source_ids=[variant.variant_id],
            )
        )
    return critiques


def _select_variant(*, variants: list[CreativeVariant], critiques: list[CreativeCritique]) -> CreativeVariant:
    critique_by_variant = {critique.variant_id: critique for critique in critiques}
    for variant in variants:
        critique = critique_by_variant[variant.variant_id]
        if critique.recommendation == CreativeCritiqueRecommendation.PURSUE and not critique.constraint_violations:
            return variant
    return variants[0]


def _build_task_contract(*, run_id: str, seed: str, selected: CreativeVariant) -> TaskContract:
    return build_task_contract(
        task_id=f"creative-e2e-{run_id}",
        title="Provider-free creative-to-execution smoke",
        scope=f"Convert the human seed into a curator-ready dry-run evidence bundle: {seed}",
        files_to_modify=[f".hermes/creative-e2e/{run_id}/evidence.json", f".hermes/creative-e2e/{run_id}/report.md"],
        files_not_to_touch=["~/.hermes/**", "production branches", "provider credentials"],
        context=[selected.pitch, selected.rationale],
        requirements=[
            "No live providers by default",
            "No global Hermes configuration mutation",
            "No production side effects or promotion attempts",
            "Evidence must include selected variant, task contract, workflow status, verifier result, and safety flags",
        ],
        acceptance_criteria=[
            "workflow_status is verified",
            "verifier_passed is true",
            "dry_run_only is true",
            "promotion_attempted is false",
            "curator_proposal_ready is true",
            "global_hermes_config_mutated is false",
        ],
        verification_commands=["python -m pytest tests/test_creative_e2e_smoke.py -q"],
        escalation_rule="Stop and request explicit human authorization before any provider/profile call or promotion.",
    )


def _render_prd(*, brief: CreativeBrief, selected: CreativeVariant, selection: UserSelectionFeedback) -> str:
    return "\n".join(
        [
            f"# PRD: {brief.brief_id}",
            "",
            f"Seed: {brief.human_seed}",
            f"Selected variant: {selected.variant_id}",
            f"Selection status: {selection.status.value}",
            "Goal: produce a project-local, provider-free evidence bundle for curator review.",
            "Non-goals: live providers, global Hermes mutation, production promotion.",
            "",
        ]
    )


def _render_spec(*, brief: CreativeBrief, selected: CreativeVariant) -> str:
    return "\n".join(
        [
            f"# Spec: {selected.variant_id}",
            "",
            "Inputs:",
            f"- run_id-derived brief: {brief.brief_id}",
            f"- human seed: {brief.human_seed}",
            "Outputs:",
            "- evidence.json",
            "- optional report.md",
            "Verifier: deterministic schema and safety flag checks only.",
            "",
        ]
    )


def _verify_evidence(evidence: CreativeE2ESmokeEvidence) -> None:
    checks: dict[str, Any] = {
        "workflow_status": evidence.workflow_status == WorkflowExecutionStatus.VERIFIED.value,
        "verifier_passed": evidence.verifier_passed is True,
        "dry_run_only": evidence.dry_run_only is True,
        "promotion_attempted": evidence.promotion_attempted is False,
        "curator_proposal_ready": evidence.curator_proposal_ready is True,
        "global_hermes_config_mutated": evidence.global_hermes_config_mutated is False,
        "provider_call_count": evidence.provider_call_count == 0,
        "selected_variant_linked": any(variant.variant_id == evidence.selected_variant_id for variant in evidence.variants),
        "task_contract_linked": evidence.task_contract.task_id == evidence.task_contract_id,
        "workflow_contract_linked": evidence.workflow_report.task_id == evidence.task_contract_id,
        "workflow_execution_not_performed": evidence.workflow_report.execution_performed is False,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"creative E2E smoke evidence failed verification: {', '.join(failed)}")


def _render_report(evidence: CreativeE2ESmokeEvidence) -> str:
    lines = [
        f"# Creative-to-Execution E2E Smoke: {evidence.run_id}",
        "",
        "## Summary",
        f"- seed: {evidence.seed}",
        f"- selected_variant_id: {evidence.selected_variant_id}",
        f"- task_contract_id: {evidence.task_contract_id}",
        f"- workflow_status: {evidence.workflow_status}",
        f"- verifier_passed: {_bool(evidence.verifier_passed)}",
        f"- dry_run_only: {_bool(evidence.dry_run_only)}",
        f"- promotion_attempted: {_bool(evidence.promotion_attempted)}",
        f"- curator_proposal_ready: {_bool(evidence.curator_proposal_ready)}",
        f"- global_hermes_config_mutated: {_bool(evidence.global_hermes_config_mutated)}",
        f"- provider_call_count: {evidence.provider_call_count}",
        "",
        "## Selected Variant",
        evidence.variants[0].render_markdown(),
        "## Task Contract",
        evidence.task_contract.render_markdown(),
        "## Workflow Evidence",
        "```json",
        json.dumps(evidence.workflow_report.model_dump(mode="json"), indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def _bool(value: bool) -> str:
    return "true" if value else "false"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run provider-free creative-to-execution E2E smoke.")
    parser.add_argument("--root", default=".", help="Project root where .hermes/creative-e2e evidence is written")
    parser.add_argument("--run-id", required=True, help="Safe run id slug for evidence path")
    parser.add_argument("--seed", required=True, help="Human creative seed")
    parser.add_argument("--write-report", action="store_true", help="Write report.md next to evidence.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence = run_creative_e2e_smoke(
        project_root=args.root,
        run_id=args.run_id,
        seed=args.seed,
        write_report=args.write_report,
    )
    print("CREATIVE_E2E_SMOKE_OK")
    print(f"run_id: {evidence.run_id}")
    print(f"evidence_path: {evidence.evidence_path}")
    if evidence.report_path is not None:
        print(f"report_path: {evidence.report_path}")
    print(f"selected_variant_id: {evidence.selected_variant_id}")
    print(f"task_contract_id: {evidence.task_contract_id}")
    print(f"workflow_status: {evidence.workflow_status}")
    print(f"verifier_passed: {evidence.verifier_passed}")
    print(f"curator_proposal_ready: {evidence.curator_proposal_ready}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
