from __future__ import annotations

from pathlib import Path

CLI_REFERENCE_COMMANDS: dict[str, list[tuple[str, str]]] = {
    "Core evidence inspection": [
        ("feiyue-runs list [--json]", "List persisted run evidence or emit catalog JSON."),
        ("feiyue-runs show <task_id>", "Print one run-evidence.json payload."),
        ("feiyue-runs handoff <task_id>", "Render a compact fallback handoff summary."),
        ("feiyue-runs review-inbox", "List pending local review items without mutating state."),
        ("feiyue-runs semantic-review --review-id <id> --artifact-id <id> --artifact-path <path>", "Run the provider-free semantic reviewer and optionally write audit evidence."),
        ("feiyue-runs creative-metrics-record --proposal-id <id> --seed-id <id> --decision <accepted|rejected|deferred>", "Record human creative proposal acceptance/taste metrics without provider calls."),
        ("feiyue-runs workflow-smoke <run_id>", "Inspect real-profile workflow dry-run evidence."),
        ("feiyue-runs workflow-promotion <run_id>", "Inspect approval-gated workflow promotion evidence."),
        ("feiyue-runs live-profile-matrix <run_id>", "Inspect retained Phase C live profile matrix summary evidence."),
        ("feiyue-runs controlled-teacher-escalation <run_id>", "Inspect retained controlled teacher-escalation summary evidence."),
    ],
    "Capability and learning loop": [
        ("feiyue-runs capability-history [--write-report]", "Collect workflow evidence into longitudinal capability history."),
        ("feiyue-runs longitudinal-gain [--min-samples N] [--window-size N] [--write-report]", "Evaluate before/after gains from capability history."),
        ("feiyue-runs longitudinal-mini-program --run-id <id> [--write-report]", "Run a provider-free 3-batch mini-program that measures lesson/template/routing improvement."),
        ("feiyue-runs asset-reuse-smoke --run-id <id> --lesson-path <path> [--write-report]", "Run provider-free promoted lesson reuse evidence."),
        ("feiyue-runs curator-live-proposal --run-id <id> --proposal-id <id> [--write-proposal]", "Build a review-required asset proposal from verified live evidence."),
        ("feiyue-runs promote-curator-asset --proposal-id <id> --reviewer <name> --reason <text> --rollback-ref <ref> --patch-id <id>", "Promote one approved project-local asset patch with rollback evidence."),
    ],
    "Multi-worker and real-profile dry runs": [
        ("feiyue-runs multi-worker-plan --plan-id <id> --task-id <id> --capability <name>", "Create a provider-free multi-worker route plan."),
        ("feiyue-runs approve-multi-worker-dry-run --plan-id <id> --approved-by <name> --approval-id <id> --reason <text>", "Create exact approval evidence for a multi-worker dry-run plan."),
        ("feiyue-runs run-approved-multi-worker-dry-run --plan-id <id> --run-id <id> ...", "Run an approved fake-first multi-worker workflow dry-run."),
        ("feiyue-runs real-multi-worker-live-dry-run --authorization-path <path> --plan-id <id> --run-id <id> ...", "Run an explicitly authorized real multi-worker live dry-run seam."),
    ],
    "Approval-gated operations": [
        ("feiyue-runs approve-promotion <run_id> ...", "Create exact approval evidence for a verified workflow dry-run."),
        ("feiyue-runs promote-approved <run_id> --commit-message <text>", "Promote a dry-run using persisted approval evidence."),
        ("feiyue-runs draft-pr-plan <run_id> --allowed-target-branch <branch>", "Create a local-only draft PR plan from verified promotion evidence."),
        ("feiyue-runs approve-draft-pr <run_id> --approved-by <name> --approval-id <id> --reason <text>", "Create exact approval evidence for fake-first draft PR creation."),
        ("feiyue-runs create-approved-draft-pr <run_id>", "Create draft PR evidence through the fake adapter; no external PR is opened."),
        ("feiyue-runs release-candidate-plan <release_id> --run-id <id> --allowed-target-branch <branch> --ci-evidence-path <path> --post-promotion-verification-command <cmd>", "Create a fail-closed local-only release-candidate plan."),
        ("feiyue-runs approve-production-promotion <release_id> --approved-by <name> --approval-id <id> --reason <text>", "Create exact approval evidence for production-promotion readiness only."),
        ("feiyue-runs verify-production-promotion-readiness <release_id>", "Verify production-promotion readiness without mutating production."),
    ],
}


def render_cli_reference() -> str:
    lines = [
        "# Feiyue CLI Reference",
        "",
        "Generated from the productized `feiyue-runs` command registry.",
        "",
        "## Safety defaults",
        "",
        "- Provider-free and read-only commands are the default inspection path.",
        "- Approval-gated commands require exact persisted approvals before any state mutation.",
        "- Draft PR, release-candidate, and production-promotion commands are fail-closed and local-only unless a separate adapter is explicitly authorized.",
        "- No command in this reference requires secrets to be written into docs.",
        "",
    ]
    for section, commands in CLI_REFERENCE_COMMANDS.items():
        lines.append(f"## {section}")
        lines.append("")
        for command, description in commands:
            lines.append(f"- `{command}` — {description}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_cli_reference(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_cli_reference(), encoding="utf-8")
    return path
