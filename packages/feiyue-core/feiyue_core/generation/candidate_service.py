from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from feiyue_core.providers import ModelProfile, ProviderRequest, ProviderResponse, ProviderRole
from feiyue_core.routing import ModelRoleRouter, RoutingDecision, TeacherInterventionContext
from feiyue_core.schemas import Candidate, StrategyVersion, TaskSpec
from feiyue_core.schemas.common import FeiyueModel

from .prompt_loader import PromptArtifact, PromptTemplateLoader
from .structured_output import CandidateOutputParser, ProviderCandidateOutput


class CompletionProvider(Protocol):
    profile: ModelProfile

    def complete(self, request: ProviderRequest) -> ProviderResponse: ...


class CandidateServiceError(RuntimeError):
    pass


class CandidateServiceResult(FeiyueModel):
    candidate: Candidate | None = None
    teacher_guidance: dict[str, Any] | None = None
    routing_decision: RoutingDecision
    prompt_artifact: PromptArtifact
    provider_response: ProviderResponse
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateService:
    def __init__(
        self,
        *,
        router: ModelRoleRouter,
        providers: dict[ProviderRole, CompletionProvider],
        prompt_loader: PromptTemplateLoader | None = None,
        output_parser: CandidateOutputParser | None = None,
    ) -> None:
        self.router = router
        self.providers = providers
        self.prompt_loader = prompt_loader or PromptTemplateLoader()
        self.output_parser = output_parser or CandidateOutputParser()

    def generate_candidate(
        self,
        *,
        task: TaskSpec,
        strategy: StrategyVersion,
        intervention_context: TeacherInterventionContext,
        provider_metadata: dict[str, Any] | None = None,
    ) -> CandidateServiceResult:
        routing_decision = self.router.route(intervention_context)
        provider = self.providers.get(routing_decision.selected_role)
        if provider is None:
            raise CandidateServiceError(f"missing provider for selected role {routing_decision.selected_role.value}")

        prompt_artifact = self.prompt_loader.render_student_candidate_prompt(
            task=task,
            output_schema=ProviderCandidateOutput.model_json_schema(),
        )
        if prompt_artifact.rendered_prompt is None:
            raise CandidateServiceError("prompt artifact did not include rendered prompt")

        request_metadata = self._request_metadata(
            task=task,
            strategy=strategy,
            prompt_artifact=prompt_artifact,
            routing_decision=routing_decision,
            provider_metadata=provider_metadata or {},
        )
        response = provider.complete(
            ProviderRequest(
                task_id=task.id,
                role=routing_decision.selected_role,
                prompt=prompt_artifact.rendered_prompt,
                metadata=request_metadata,
            )
        )

        if routing_decision.selected_role == ProviderRole.TEACHER:
            return CandidateServiceResult(
                candidate=None,
                teacher_guidance=response.content,
                routing_decision=routing_decision,
                prompt_artifact=prompt_artifact,
                provider_response=response,
                metadata={"path": "teacher_guidance"},
            )

        parsed = self.output_parser.parse_response(response)
        candidate = parsed.to_candidate(task=task, strategy=strategy, model_profile=routing_decision.selected_profile)
        candidate.metadata.update(
            {
                "prompt_template": prompt_artifact.name,
                "prompt_template_version": prompt_artifact.version,
                "prompt_template_hash": prompt_artifact.template_hash,
                "prompt_rendered_hash": prompt_artifact.rendered_hash,
                "routing_trigger": routing_decision.trigger.value,
                "routing_reason": routing_decision.reason,
                "routing_metadata": routing_decision.routing_metadata,
            }
        )
        return CandidateServiceResult(
            candidate=candidate,
            teacher_guidance=None,
            routing_decision=routing_decision,
            prompt_artifact=prompt_artifact,
            provider_response=response,
            metadata={"path": "candidate"},
        )

    @staticmethod
    def _request_metadata(
        *,
        task: TaskSpec,
        strategy: StrategyVersion,
        prompt_artifact: PromptArtifact,
        routing_decision: RoutingDecision,
        provider_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "task_id": task.id,
            "strategy_version_id": strategy.id,
            "prompt_template": prompt_artifact.name,
            "prompt_template_version": prompt_artifact.version,
            "prompt_template_hash": prompt_artifact.template_hash,
            "prompt_rendered_hash": prompt_artifact.rendered_hash,
            "routing_trigger": routing_decision.trigger.value,
            "routing_reason": routing_decision.reason,
            "routing_metadata": routing_decision.routing_metadata,
        }
        metadata.update(provider_metadata)
        return metadata
