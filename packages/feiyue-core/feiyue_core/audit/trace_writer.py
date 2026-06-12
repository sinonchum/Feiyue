from __future__ import annotations

import json
from pathlib import Path

from feiyue_core.schemas import TraceEvent


class JsonlTraceWriter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: TraceEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.model_dump(mode="json")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
