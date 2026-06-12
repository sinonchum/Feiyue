"""Provider-free model routing table assets.

This module manages the project-local `.hermes/model-routing.yaml` file used to
map workflow roles to model/profile names. It intentionally performs only local
parsing and filesystem operations: no provider calls and no global Hermes config
mutation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

MODEL_ROUTING_FILENAME = "model-routing.yaml"

REQUIRED_MODEL_ROUTING_ROLES: tuple[str, ...] = (
    "creative_expansion",
    "prd",
    "spec",
    "worker",
    "teacher_debug",
    "curator",
)

_ROUTE_FIELD_ORDER: tuple[str, ...] = ("primary", "fallback", "reviewer", "teacher")

_DEFAULT_MODEL_NAME = "default"


class RoleRoute(BaseModel):
    """Model/profile names configured for one workflow role."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    primary: str
    fallback: str | None = None
    reviewer: str | None = None
    teacher: str | None = None

    @field_validator("primary", "fallback", "reviewer", "teacher", mode="before")
    @classmethod
    def _strip_and_validate_model_name(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("configured model/profile names must be non-empty")
            return stripped
        return value


class ModelRoutingTable(BaseModel):
    """Mapping from workflow roles to local model/profile route settings."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    routes: dict[str, RoleRoute]

    @model_validator(mode="after")
    def _validate_required_roles(self) -> "ModelRoutingTable":
        missing_roles = [role for role in REQUIRED_MODEL_ROUTING_ROLES if role not in self.routes]
        if missing_roles:
            raise ValueError("missing required model routing roles: " + ", ".join(missing_roles))
        return self

    @classmethod
    def default(cls) -> "ModelRoutingTable":
        """Build a deterministic default routing table using local placeholders."""

        return cls(
            routes={
                role: RoleRoute(primary=_DEFAULT_MODEL_NAME)
                for role in REQUIRED_MODEL_ROUTING_ROLES
            }
        )

    @classmethod
    def parse_yaml(cls, text: str) -> "ModelRoutingTable":
        """Parse YAML-like routing text with optional PyYAML and local fallbacks."""

        parsed = _parse_yaml_like_text(text)
        if not isinstance(parsed, dict):
            raise ValueError("model routing table must be a mapping")
        return cls.model_validate(parsed)

    def render_yaml(self) -> str:
        """Render deterministic simple YAML in stable role order."""

        lines = ["routes:"]
        for role in _ordered_roles(self.routes):
            route = self.routes[role]
            lines.append(f"  {role}:")
            route_data = route.model_dump(exclude_none=True)
            for field_name in _ROUTE_FIELD_ORDER:
                value = route_data.get(field_name)
                if value is not None:
                    lines.append(f"    {field_name}: {_render_scalar(value)}")
        return "\n".join(lines) + "\n"


class ModelRoutingTableLoader:
    """Load the project-local `.hermes/model-routing.yaml` routing table."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.hermes_dir = self.project_root / ".hermes"
        self.path = self.hermes_dir / MODEL_ROUTING_FILENAME

    def load(self) -> ModelRoutingTable:
        return ModelRoutingTable.parse_yaml(self.path.read_text(encoding="utf-8"))


class ModelRoutingTableInitializer:
    """Create a default project-local model routing table file."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.hermes_dir = self.project_root / ".hermes"
        self.path = self.hermes_dir / MODEL_ROUTING_FILENAME

    def initialize(self, *, overwrite: bool = False) -> Path:
        """Create `.hermes/model-routing.yaml`, preserving it unless requested."""

        self.hermes_dir.mkdir(parents=True, exist_ok=True)
        if overwrite or not self.path.exists():
            self.path.write_text(ModelRoutingTable.default().render_yaml(), encoding="utf-8")
        return self.path


def _ordered_roles(routes: dict[str, RoleRoute]) -> list[str]:
    required = [role for role in REQUIRED_MODEL_ROUTING_ROLES if role in routes]
    extras = sorted(role for role in routes if role not in REQUIRED_MODEL_ROUTING_ROLES)
    return required + extras


def _parse_yaml_like_text(text: str) -> Any:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        yaml = None

    if yaml is not None:
        return yaml.safe_load(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _parse_simple_model_routing_yaml(text)


def _parse_simple_model_routing_yaml(text: str) -> dict[str, Any]:
    """Parse the small deterministic YAML subset emitted by render_yaml()."""

    data: dict[str, Any] = {}
    routes: dict[str, dict[str, str]] | None = None
    current_role: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        key, separator, value = stripped.partition(":")
        if separator != ":":
            raise ValueError(f"invalid model routing line: {raw_line!r}")
        key = key.strip()
        value = value.strip()

        if indent == 0:
            if key != "routes" or value:
                raise ValueError("model routing table must contain a top-level routes mapping")
            routes = {}
            data["routes"] = routes
            current_role = None
        elif indent == 2:
            if routes is None or value:
                raise ValueError(f"invalid route entry: {raw_line!r}")
            current_role = key
            routes[current_role] = {}
        elif indent == 4:
            if routes is None or current_role is None:
                raise ValueError(f"route field without route: {raw_line!r}")
            routes[current_role][key] = _parse_scalar(value)
        else:
            raise ValueError(f"unsupported indentation in model routing line: {raw_line!r}")

    return data


def _parse_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _render_scalar(value: str) -> str:
    # Render plain scalars for the model/profile names used by defaults and tests;
    # quote uncommon values so the fallback parser can round-trip safely.
    if value and all(character.isalnum() or character in {"_", "-", ".", "/", ":", "@"} for character in value):
        return value
    return json.dumps(value)
