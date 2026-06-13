from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from feiyue_core.workflow.execution import RunCatalog
from feiyue_core.workflow.runs_api import render_run_detail, render_runs_dashboard


@dataclass(frozen=True)
class StaticRunsReportExport:
    index_path: Path
    detail_paths: dict[str, Path]


def _safe_html_filename(task_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", task_id).strip("._")
    return f"{safe or 'run'}.html"


def export_static_runs_report(project_root: str | Path, output_dir: str | Path) -> StaticRunsReportExport:
    """Export read-only run dashboard and detail pages as offline HTML files."""

    root = Path(project_root)
    out = Path(output_dir)
    runs_dir = out / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    summary = RunCatalog(root).summary()
    filename_by_task = {run.task_id: _safe_html_filename(run.task_id) for run in summary.runs}

    index_html = render_runs_dashboard(root)
    for task_id, filename in filename_by_task.items():
        index_html = index_html.replace(f'href="/dashboard/runs/{task_id}"', f'href="runs/{filename}"')
        index_html = index_html.replace(f'href="/runs/{task_id}/handoff"', f'href="runs/{filename}"')
    index_html = index_html.replace("Read-only evidence surface", "Offline read-only evidence surface")

    index_path = out / "index.html"
    index_path.write_text(index_html, encoding="utf-8")

    detail_paths: dict[str, Path] = {}
    for task_id, filename in filename_by_task.items():
        detail_html = render_run_detail(root, task_id)
        detail_html = detail_html.replace('href="/dashboard"', 'href="../index.html"')
        detail_html = detail_html.replace(f'href="/runs/{task_id}"', 'href="#evidence-json-unavailable-offline"')
        detail_html = detail_html.replace(f'href="/runs/{task_id}/handoff"', 'href="#handoff-unavailable-offline"')
        detail_html = detail_html.replace("Read-only run evidence", "Offline read-only run evidence")
        path = runs_dir / filename
        path.write_text(detail_html, encoding="utf-8")
        detail_paths[task_id] = path

    return StaticRunsReportExport(index_path=index_path, detail_paths=detail_paths)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feiyue-runs-export",
        description="Export Feiyue run evidence as offline read-only HTML reports.",
    )
    parser.add_argument("--root", default=".", help="Project root containing .hermes/runs")
    parser.add_argument("--out", required=True, help="Output directory for static report files")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = export_static_runs_report(args.root, args.out)
    print(f"index: {result.index_path}")
    print(f"details: {len(result.detail_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
