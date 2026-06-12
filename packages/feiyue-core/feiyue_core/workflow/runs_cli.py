from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from feiyue_core.workflow.execution import RunCatalog, RunEvidenceLoader, RunEvidenceNotFoundError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feiyue-runs",
        description="Inspect persisted Feiyue run evidence and fallback handoff summaries.",
    )
    parser.add_argument("--root", default=".", help="Project root containing .hermes/runs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List persisted run ids")
    list_parser.add_argument("--json", action="store_true", help="Print catalog summary JSON")

    show_parser = subparsers.add_parser("show", help="Print run-evidence.json for a task")
    show_parser.add_argument("task_id")

    handoff_parser = subparsers.add_parser("handoff", help="Render compact fallback handoff summary")
    handoff_parser.add_argument("task_id")

    args = parser.parse_args(list(argv) if argv is not None else None)
    root = Path(args.root)
    loader = RunEvidenceLoader(root)

    try:
        if args.command == "list":
            catalog = RunCatalog(root)
            if args.json:
                print(catalog.summary().model_dump_json(indent=2))
                return 0
            for run in catalog.summary().runs:
                print(run.task_id)
            return 0
        if args.command == "show":
            evidence = loader.load(args.task_id)
            print(evidence.model_dump_json(indent=2))
            return 0
        if args.command == "handoff":
            print(loader.render_handoff_summary(args.task_id), end="")
            return 0
    except RunEvidenceNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
