from __future__ import annotations

import argparse
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class StaticRunsReportBundle:
    bundle_path: Path
    entries: list[str]


def _bundle_entries(report_dir: Path) -> list[Path]:
    entries = [report_dir / "index.html", report_dir / "manifest.json"]
    assets_dir = report_dir / "assets"
    if assets_dir.exists():
        entries.extend(sorted(path for path in assets_dir.rglob("*") if path.is_file()))
    review_inbox_dir = report_dir / "review-inbox"
    if review_inbox_dir.exists():
        entries.extend(sorted(path for path in review_inbox_dir.rglob("*") if path.is_file()))
    runs_dir = report_dir / "runs"
    if runs_dir.exists():
        entries.extend(sorted(runs_dir.glob("*.html")))
    return entries


def pack_static_runs_report(report_dir: str | Path, bundle_path: str | Path) -> StaticRunsReportBundle:
    """Pack an already exported static runs report into a portable ZIP bundle."""

    root = Path(report_dir)
    target = Path(bundle_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    files = _bundle_entries(root)
    archive_entries: list[str] = []

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if not path.exists():
                continue
            arcname = path.relative_to(root).as_posix()
            archive.write(path, arcname)
            archive_entries.append(arcname)

    return StaticRunsReportBundle(bundle_path=target, entries=archive_entries)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feiyue-runs-export-bundle",
        description="Pack a Feiyue static run report directory into a portable ZIP bundle.",
    )
    parser.add_argument("--report", required=True, help="Static report directory containing index.html and manifest.json")
    parser.add_argument("--out", required=True, help="Output .zip path")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = pack_static_runs_report(args.report, args.out)
    print(f"bundle: {result.bundle_path}")
    print(f"entries: {len(result.entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
