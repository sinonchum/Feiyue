"""Provider-free multi-worker orchestration planning over approved routing evidence.

Wave4-5 hardens the seam between project-local routing updates and worker
selection.  The planner reads `.hermes/model-routing.yaml` plus the latest local
routing apply evidence, builds a provider-free multi-worker route plan, and
persists audit evidence without executing providers or mutating global Hermes
configuration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from feiyue_core.providers import ModelProfile, ProviderRole
from feiyue_core.routing.multi_worker_gate import MultiWorkerRouter, WorkerCapabilityProfile, WorkerRouteContext, WorkerRoutePlan
from feiyue_core.schemas.common import FeiyueModel
from feiyue_core.workflow.model_routing_table import ModelRoutingTableLoader, RoleRoute

RiskLevel = Literal["low", "medium", "high"]


class MultiWorkerPlanError(RuntimeError):
    """Raised when a multi-worker plan cannot be produced safely."""


class MultiWorkerOrchestrationPlan(FeiyueModel):
    plan_id: str
    task_id: str
    route: WorkerRoutePlan
    selected_route_source: str
    routing_apply_evidence_id: str | None = None
    routing_apply_evidence_path: str | None = None
    reason_codes: list[str]
    provider_execution_requested: bool = False
    global_hermes_config_mutated: bool = False
    audit_metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("plan_id", "task_id", "selected_route_source")
    @classmethod
    def _required_string(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("multi-worker orchestration plan strings must be non-empty")
        return normalized

    @field_validator("reason_codes")
    @classmethod
    def _required_reason_codes(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("reason_codes must be non-empty")
        return [str(item).strip() for item in value if str(item).strip()]


class MultiWorkerOrchestrationPlanner:
    """Build provider-free route plans from project-local routing state."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.hermes_dir = self.project_root / ".hermes"
        self.routing_path = self.hermes_dir / "model-routing.yaml"
        self.output_root = self.hermes_dir / "multi-worker-plans"

    def plan(
        self,
        *,
        plan_id: str,
        task_id: str,
        required_capabilities: list[str],
        risk_level: RiskLevel = "low",
        student_failure_count: int = 0,
        failure_category: str | None = None,
        verifier_confidence: float | None = None,
        teacher_calls_used: int = 0,
        teacher_call_budget: int = 0,
    ) -> MultiWorkerOrchestrationPlan:
        if not self.routing_path.exists():
            raise MultiWorkerPlanError(f"model routing table not found: {self.routing_path}")
        if not required_capabilities:
            raise MultiWorkerPlanError("required_capabilities must be non-empty")

        routing = ModelRoutingTableLoader(self.project_root).load()
        worker_route = routing.routes.get("worker")
        teacher_route = routing.routes.get("teacher_debug")
        if worker_route is None:
            raise MultiWorkerPlanError("worker route is missing from model routing table")

        apply_evidence = self._latest_apply_evidence()
        evidence_ids = ["routing-table:.hermes/model-routing.yaml"]
        reason_codes = ["model_routing_table_loaded"]
        routing_apply_evidence_id: str | None = None
        routing_apply_evidence_path: str | None = None
        if apply_evidence is not None:
            routing_apply_evidence_id = str(apply_evidence["proposal_id"])
            routing_apply_evidence_path = str(apply_evidence["path"])
            evidence_ids.append(f"routing-apply:{routing_apply_evidence_id}")
            reason_codes.append("routing_apply_evidence_loaded")
        else:
            reason_codes.append("routing_apply_evidence_absent")

        workers = _workers_from_route(worker_route, capabilities=required_capabilities)
        teacher = _teacher_from_route(teacher_route, capabilities=required_capabilities)
        router = MultiWorkerRouter(workers=workers, teacher=teacher)
        route = router.route(
            WorkerRouteContext(
                task_id=task_id,
                required_capabilities=required_capabilities,
                risk_level=risk_level,
                evidence_ids=evidence_ids,
                student_failure_count=student_failure_count,
                failure_category=failure_category,
                verifier_confidence=verifier_confidence,
                teacher_calls_used=teacher_calls_used,
                teacher_call_budget=teacher_call_budget,
                metadata={"plan_id": plan_id, "routing_source": ".hermes/model-routing.yaml"},
            )
        )
        reason_codes.extend(route.reason_codes)

        return MultiWorkerOrchestrationPlan(
            plan_id=plan_id,
            task_id=task_id,
            route=route,
            selected_route_source=".hermes/model-routing.yaml",
            routing_apply_evidence_id=routing_apply_evidence_id,
            routing_apply_evidence_path=routing_apply_evidence_path,
            reason_codes=_dedupe(reason_codes),
            provider_execution_requested=False,
            global_hermes_config_mutated=False,
            audit_metadata={
                "required_capabilities": list(required_capabilities),
                "risk_level": risk_level,
                "routing_path": ".hermes/model-routing.yaml",
                "available_teacher_profile_id": teacher.profile_id if teacher is not None else None,
                "writes_only_local_plan_evidence": True,
            },
        )

    def write_plan(self, **kwargs: object) -> MultiWorkerOrchestrationPlan:
        plan = self.plan(**kwargs)  # type: ignore[arg-type]
        output_dir = self.output_root / plan.plan_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        (output_dir / "plan.md").write_text(_render_plan_markdown(plan), encoding="utf-8")
        return plan

    def _latest_apply_evidence(self) -> dict[str, object] | None:
        proposals_root = self.hermes_dir / "routing-proposals"
        if not proposals_root.exists():
            return None
        candidates = sorted(
            proposals_root.glob("*/apply-evidence.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if payload.get("status") == "applied" and payload.get("routing_table_mutated") is True:
                proposal_id = str(payload.get("proposal_id") or path.parent.name)
                return {"proposal_id": proposal_id, "path": path}
        return None


def _workers_from_route(route: RoleRoute, *, capabilities: list[str]) -> list[WorkerCapabilityProfile]:
    profile_ids = _route_profile_ids(route)
    return [
        WorkerCapabilityProfile(
            profile_id=profile_id,
            model_profile=ModelProfile(
                provider="project-routing",
                model=profile_id,
                role=ProviderRole.STUDENT,
                cost_tier="routed",
                strengths=list(capabilities),
                metadata={"source": ".hermes/model-routing.yaml", "route_role": "worker"},
            ),
            capabilities=list(capabilities),
            risk_ceiling="medium",
            metadata={"source": ".hermes/model-routing.yaml", "route_role": "worker"},
        )
        for profile_id in profile_ids
    ]


def _teacher_from_route(route: RoleRoute | None, *, capabilities: list[str]) -> WorkerCapabilityProfile | None:
    if route is None:
        return None
    profile_ids = _route_profile_ids(route)
    if not profile_ids:
        return None
    profile_id = profile_ids[0]
    if profile_id == "default":
        return None
    teacher_capabilities = _dedupe([*capabilities, "debugging", "architecture"])
    return WorkerCapabilityProfile(
        profile_id=profile_id,
        model_profile=ModelProfile(
            provider="project-routing",
            model=profile_id,
            role=ProviderRole.TEACHER,
            cost_tier="routed",
            strengths=teacher_capabilities,
            metadata={"source": ".hermes/model-routing.yaml", "route_role": "teacher_debug"},
        ),
        capabilities=teacher_capabilities,
        risk_ceiling="high",
        metadata={"source": ".hermes/model-routing.yaml", "route_role": "teacher_debug"},
    )


def _route_profile_ids(route: RoleRoute) -> list[str]:
    candidates = [route.primary, route.fallback, route.reviewer, route.teacher]
    return _dedupe([candidate for candidate in candidates if candidate])


def _render_plan_markdown(plan: MultiWorkerOrchestrationPlan) -> str:
    return "\n".join(
        [
            f"# Multi-worker plan: {plan.plan_id}",
            "",
            f"task_id: {plan.task_id}",
            f"status: {plan.route.status}",
            f"worker_profile_ids: {', '.join(plan.route.worker_profile_ids)}",
            f"teacher_profile_id: {plan.route.teacher_profile_id or 'none'}",
            f"routing_apply_evidence_id: {plan.routing_apply_evidence_id or 'none'}",
            f"provider_execution_requested: {str(plan.provider_execution_requested).lower()}",
            f"global_hermes_config_mutated: {str(plan.global_hermes_config_mutated).lower()}",
            "",
            "## Reason codes",
            *[f"- {reason}" for reason in plan.reason_codes],
            "",
        ]
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
