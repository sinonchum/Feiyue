"""Typed provider-free benchmark case schema v1."""

from __future__ import annotations

import shlex
from typing import Any, Literal

from pydantic import field_validator

from feiyue_core.schemas.common import FeiyueModel, RiskLevel

BENCHMARK_CASE_SCHEMA_VERSION = "feiyue.benchmark.case.v1"
_SAFE_VERIFIER_TOKENS = {"python", "pytest", "uv", "tox", "nox", "make"}
_UNSAFE_SHELL_TOKENS = {";", "&&", "||", "|", "`", "$", ">", "<", "\n", "\r"}


class BenchmarkCase(FeiyueModel):
    """Future real weak/strong benchmark task contract without provider coupling."""

    schema_version: Literal["feiyue.benchmark.case.v1"] = BENCHMARK_CASE_SCHEMA_VERSION
    task_id: str
    category: str
    input: str | dict[str, Any]
    expected_artifacts: list[str]
    verifier_command: list[str] | str
    allowed_roles: list[str]
    risk_level: RiskLevel | str

    @field_validator("task_id", "category", "risk_level", mode="before")
    @classmethod
    def _validate_required_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("value must be non-empty")
            return stripped
        return value

    @field_validator("input")
    @classmethod
    def _validate_input(cls, value: str | dict[str, Any]) -> str | dict[str, Any]:
        if isinstance(value, str) and not value.strip():
            raise ValueError("input must be non-empty when provided as a string")
        if isinstance(value, dict) and not value:
            raise ValueError("input must be non-empty when provided as an object")
        return value

    @field_validator("expected_artifacts", "allowed_roles")
    @classmethod
    def _validate_string_list(cls, value: list[str], info: Any) -> list[str]:
        if not value:
            raise ValueError(f"{info.field_name} must be non-empty")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError(f"{info.field_name} entries must be strings")
            stripped = item.strip()
            if not stripped:
                raise ValueError(f"{info.field_name} entries must be non-empty")
            normalized.append(stripped)
        return normalized

    @field_validator("verifier_command")
    @classmethod
    def _validate_verifier_command(cls, value: list[str] | str) -> list[str] | str:
        if isinstance(value, str):
            command = value.strip()
            if not command:
                raise ValueError("verifier_command must be non-empty")
            _reject_unsafe_shell_shape(command)
            _validate_command_tokens(shlex.split(command))
            return command

        if not value:
            raise ValueError("verifier_command must be non-empty")
        normalized: list[str] = []
        for token in value:
            if not isinstance(token, str):
                raise TypeError("verifier_command entries must be strings")
            stripped = token.strip()
            if not stripped:
                raise ValueError("verifier_command entries must be non-empty")
            _reject_unsafe_shell_shape(stripped)
            normalized.append(stripped)
        _validate_command_tokens(normalized)
        return normalized


def _reject_unsafe_shell_shape(value: str) -> None:
    if any(token in value for token in _UNSAFE_SHELL_TOKENS):
        raise ValueError("verifier_command must not include shell control operators")


def _validate_command_tokens(tokens: list[str]) -> None:
    if not tokens:
        raise ValueError("verifier_command must include at least one token")
    executable = tokens[0]
    if executable not in _SAFE_VERIFIER_TOKENS and not executable.startswith("./"):
        raise ValueError("verifier_command executable is not in the provider-free safe allowlist")
