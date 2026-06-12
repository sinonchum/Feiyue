from __future__ import annotations

from collections.abc import Iterable

from feiyue_core.recovery import RecoveryManifest


class RecoveryPromptBuilder:
    """Build a compact, deterministic prompt from a recovery manifest."""

    def build(self, manifest: RecoveryManifest) -> str:
        sections = [
            "# Feiyue Recovery Context",
            f"Session: {manifest.session_id}",
            f"Current goal: {manifest.current_goal}",
            self._section("Confirmed facts", manifest.confirmed_facts),
            self._section("Known mistakes", manifest.known_mistakes),
            self._section("Do not repeat", manifest.do_not_repeat),
            self._section("Completed steps", manifest.completed_steps),
            self._section("Pending / unknown operations", manifest.pending_operations),
            self._section("Changed files", manifest.changed_files),
            self._section("Verified outputs", manifest.verified_outputs),
            self._section("Open questions", manifest.open_questions),
            self._section("Next safe action", [manifest.next_safe_action] if manifest.next_safe_action else []),
        ]
        return "\n\n".join(sections).strip() + "\n"

    @staticmethod
    def _section(title: str, items: Iterable[str]) -> str:
        values = [str(item).strip() for item in items if str(item).strip()]
        if not values:
            values = ["None"]
        bullet_lines = "\n".join(f"- {value}" for value in values)
        return f"## {title}\n{bullet_lines}"
