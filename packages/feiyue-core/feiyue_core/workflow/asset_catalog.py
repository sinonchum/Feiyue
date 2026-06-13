"""Read-only catalog for project-local Hermes workflow assets.

The catalog intentionally exposes only stable metadata (category counts plus item
IDs, relative paths, and titles when safely parseable). It never returns raw file
contents, absolute paths, provider data, or credentials.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import Field

from feiyue_core.schemas.common import FeiyueModel

ASSET_CATEGORY_KEYS: tuple[str, ...] = (
    "lessons",
    "evals",
    "model_routing",
    "capability_profiles",
    "creative_proposals",
    "asset_proposals",
)

_SECRET_HINT_RE = re.compile(r"(secret|token|api[_-]?key|password|bearer)", re.IGNORECASE)
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
_TEXT_SUFFIXES = {".json", ".md", ".markdown", ".yaml", ".yml", ".txt", ".sh"}
_MAX_PARSE_BYTES = 64 * 1024


class AssetCatalogItem(FeiyueModel):
    """Safe metadata for one project-local asset file."""

    id: str
    path: str
    title: str | None = None


class AssetCatalogSummary(FeiyueModel):
    """Stable machine-readable read-only asset catalog summary."""

    total_assets: int
    counts: dict[str, int]
    categories: dict[str, list[AssetCatalogItem]] = Field(default_factory=dict)


class AssetCatalog:
    """Scan `.hermes/` assets without mutating project state."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.hermes_dir = self.project_root / ".hermes"

    def summary(self) -> AssetCatalogSummary:
        categories: dict[str, list[AssetCatalogItem]] = {
            key: [] for key in ASSET_CATEGORY_KEYS
        }
        categories["lessons"] = self._scan_directory("lessons")
        categories["evals"] = self._scan_directory("evals")
        categories["model_routing"] = self._scan_file("model-routing.yaml")
        categories["capability_profiles"] = self._scan_directory("capability-profiles")
        categories["creative_proposals"] = self._scan_directory("creative-proposals")
        categories["asset_proposals"] = self._scan_directory("asset-proposals")

        counts = {key: len(categories[key]) for key in ASSET_CATEGORY_KEYS}
        return AssetCatalogSummary(
            total_assets=sum(counts.values()),
            counts=counts,
            categories=categories,
        )

    def _scan_file(self, relative_to_hermes: str) -> list[AssetCatalogItem]:
        path = self.hermes_dir / relative_to_hermes
        if not path.is_file() or path.is_symlink():
            return []
        return [self._item_for_path(path)]

    def _scan_directory(self, relative_to_hermes: str) -> list[AssetCatalogItem]:
        directory = self.hermes_dir / relative_to_hermes
        if not directory.is_dir():
            return []
        items: list[AssetCatalogItem] = []
        for path in sorted(directory.rglob("*"), key=lambda candidate: candidate.as_posix()):
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in _TEXT_SUFFIXES:
                items.append(self._item_for_path(path))
        return items

    def _item_for_path(self, path: Path) -> AssetCatalogItem:
        metadata = _parse_safe_metadata(path)
        item_id = _safe_value(metadata.get("id")) or _safe_id_from_path(path)
        title = _safe_value(metadata.get("title"))
        return AssetCatalogItem(
            id=item_id,
            path=path.relative_to(self.project_root).as_posix(),
            title=title,
        )


def _parse_safe_metadata(path: Path) -> dict[str, str | None]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _parse_json_metadata(path)
    if suffix in {".md", ".markdown"}:
        return _parse_markdown_metadata(path)
    if suffix in {".yaml", ".yml"}:
        return _parse_yamlish_metadata(path)
    return {"id": path.stem, "title": None}


def _parse_json_metadata(path: Path) -> dict[str, str | None]:
    try:
        data = json.loads(_read_small_text(path))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"id": path.stem, "title": None}
    if not isinstance(data, dict):
        return {"id": path.stem, "title": None}
    return {
        "id": _first_present(data, ("id", "lesson_id", "proposal_id", "check_id", "name")),
        "title": _first_present(data, ("title", "name", "summary")),
    }


def _parse_markdown_metadata(path: Path) -> dict[str, str | None]:
    try:
        for line in _read_small_text(path).splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                lesson_prefix = "Lesson Packet: "
                item_id = title.removeprefix(lesson_prefix).strip() if title.startswith(lesson_prefix) else path.stem
                return {"id": item_id or path.stem, "title": title or None}
    except (OSError, UnicodeDecodeError):
        pass
    return {"id": path.stem, "title": None}


def _parse_yamlish_metadata(path: Path) -> dict[str, str | None]:
    data: dict[str, str] = {}
    try:
        for line in _read_small_text(path).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            if key in {"id", "lesson_id", "proposal_id", "title", "name", "schema_version"}:
                data[key] = value
    except (OSError, UnicodeDecodeError):
        return {"id": path.stem, "title": None}
    return {
        "id": _first_present(data, ("id", "lesson_id", "proposal_id", "name")) or path.stem,
        "title": _first_present(data, ("title", "name", "schema_version")),
    }


def _read_small_text(path: Path) -> str:
    return path.read_bytes()[:_MAX_PARSE_BYTES].decode("utf-8")


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _safe_value(value: str | None) -> str | None:
    if value is None:
        return None
    compact = " ".join(value.split())[:160]
    if not compact or _SECRET_HINT_RE.search(compact):
        return None
    return compact


def _safe_id_from_path(path: Path) -> str:
    safe = _SAFE_ID_RE.sub("-", path.stem).strip(".-_")
    return safe or "asset"
