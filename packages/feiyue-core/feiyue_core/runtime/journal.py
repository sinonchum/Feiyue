from __future__ import annotations

import json
import os
from pathlib import Path

from feiyue_core.recovery import RecoveryManifest
from feiyue_core.schemas import TraceEvent


class SessionJournal:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.manifest_path = self.path.with_name("latest_manifest.json")

    def append(self, event: TraceEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.model_dump(mode="json")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def read_all(self) -> list[TraceEvent]:
        if not self.path.exists():
            return []
        events: list[TraceEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            events.append(TraceEvent.model_validate_json(line))
        return events

    def write_manifest(self, manifest: RecoveryManifest) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.manifest_path.with_suffix(self.manifest_path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, self.manifest_path)

    def read_manifest(self) -> RecoveryManifest:
        return RecoveryManifest.model_validate_json(self.manifest_path.read_text(encoding="utf-8"))
