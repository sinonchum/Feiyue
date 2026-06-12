from __future__ import annotations

import hashlib
import json
from typing import Any

from .base import ModelProfile, ProviderRequest, ProviderResponse, ProviderRole
from .errors import ProviderError


class BaseProvider:
    def __init__(self, profile: ModelProfile) -> None:
        self.profile = profile

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self._ensure_role(request)
        return self._complete(request)

    def _complete(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError

    def _ensure_role(self, request: ProviderRequest) -> None:
        if request.role != self.profile.role:
            raise ProviderError.role_mismatch(
                provider=self.profile.provider,
                model=self.profile.model,
                expected_role=self.profile.role.value,
                actual_role=request.role.value,
                request_id=self._request_id(request),
            )

    def _request_id(self, request: ProviderRequest) -> str:
        payload = json.dumps(
            {
                "provider": self.profile.provider,
                "model": self.profile.model,
                "role": request.role.value,
                "task_id": request.task_id,
                "prompt": request.prompt,
                "metadata": request.model_dump(mode="json")["metadata"],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"fake-{self.profile.role.value}-{hashlib.sha256(payload).hexdigest()[:16]}"


class FakeStudentProvider(BaseProvider):
    def _complete(self, request: ProviderRequest) -> ProviderResponse:
        file_writes = request.metadata.get("file_writes")
        if not isinstance(file_writes, dict):
            file_writes = {}
        content: dict[str, Any] = {
            "kind": "candidate",
            "summary": f"fake student candidate for {request.task_id}",
            "file_writes": file_writes,
            "assumptions": request.metadata.get("assumptions", []),
            "must_be_verified_externally": True,
        }
        return ProviderResponse(
            provider=self.profile.provider,
            model=self.profile.model,
            role=ProviderRole.STUDENT,
            request_id=self._request_id(request),
            content=content,
            finish_reason="stop",
            usage={"prompt_tokens": len(request.prompt.split()), "completion_tokens": len(json.dumps(content)) // 4},
        )


class FakeTeacherProvider(BaseProvider):
    def _complete(self, request: ProviderRequest) -> ProviderResponse:
        failure_category = str(request.metadata.get("failure_category", "unknown_failure"))
        evidence = str(request.metadata.get("evidence_excerpt", ""))
        guidance = f"Analyze {failure_category} using verifier evidence before revising the student candidate."
        if evidence:
            guidance += " Preserve the cited failing evidence in the revision rationale."
        content: dict[str, Any] = {
            "kind": "teacher_guidance",
            "failure_category": failure_category,
            "guidance": guidance,
            "recommended_student_action": "revise_candidate_then_rerun_verifier",
            "must_be_verified_externally": True,
        }
        return ProviderResponse(
            provider=self.profile.provider,
            model=self.profile.model,
            role=ProviderRole.TEACHER,
            request_id=self._request_id(request),
            content=content,
            finish_reason="stop",
            usage={"prompt_tokens": len(request.prompt.split()), "completion_tokens": len(json.dumps(content)) // 4},
        )
