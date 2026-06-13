from __future__ import annotations

import argparse
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from feiyue_core.workflow.runs_export import StaticRunsReportExport, export_static_runs_report
from feiyue_core.workflow.runs_export_bundle import StaticRunsReportBundle, pack_static_runs_report
from feiyue_core.workflow.runs_export_verify import StaticRunsReportVerification, verify_static_runs_report


@dataclass(frozen=True)
class StaticRunsReportPipeline:
    report: StaticRunsReportExport
    initial_verification: StaticRunsReportVerification
    bundle: StaticRunsReportBundle
    extracted_dir: Path
    extracted_verification: StaticRunsReportVerification


def export_static_runs_report_all(
    project_root: str | Path,
    output_dir: str | Path,
    bundle_path: str | Path,
) -> StaticRunsReportPipeline:
    """Run export, verify, bundle, extract, and verify in one provider-free pipeline."""

    report = export_static_runs_report(project_root, output_dir)
    initial_verification = verify_static_runs_report(report.manifest_path)
    if not initial_verification.valid:
        return StaticRunsReportPipeline(
            report=report,
            initial_verification=initial_verification,
            bundle=StaticRunsReportBundle(bundle_path=Path(bundle_path), entries=[]),
            extracted_dir=Path(bundle_path).with_suffix(".extracted"),
            extracted_verification=initial_verification,
        )

    bundle = pack_static_runs_report(Path(output_dir), bundle_path)
    extracted_dir = Path(bundle_path).with_suffix(".extracted")
    if extracted_dir.exists():
        shutil.rmtree(extracted_dir)
    extracted_dir.mkdir(parents=True)
    with zipfile.ZipFile(bundle.bundle_path) as archive:
        archive.extractall(extracted_dir)

    extracted_verification = verify_static_runs_report(extracted_dir / "manifest.json")
    return StaticRunsReportPipeline(
        report=report,
        initial_verification=initial_verification,
        bundle=bundle,
        extracted_dir=extracted_dir,
        extracted_verification=extracted_verification,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feiyue-runs-export-all",
        description="Export, verify, bundle, extract, and verify Feiyue static run reports.",
    )
    parser.add_argument("--root", default=".", help="Project root containing .hermes/runs")
    parser.add_argument("--out", required=True, help="Output static report directory")
    parser.add_argument("--bundle", required=True, help="Output portable .zip bundle path")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = export_static_runs_report_all(args.root, args.out, args.bundle)
    print(f"index: {result.report.index_path}")
    print(f"manifest: {result.report.manifest_path}")
    print(f"bundle: {result.bundle.bundle_path}")
    print(f"extracted: {result.extracted_dir}")
    print(f"initial_verify: {result.initial_verification.valid}")
    print(f"extracted_verify: {result.extracted_verification.valid}")
    if not result.initial_verification.valid or not result.extracted_verification.valid:
        for issue in result.initial_verification.issues + result.extracted_verification.issues:
            print(f"- {issue}")
        return 1
    print("STATIC_EXPORT_ALL_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
