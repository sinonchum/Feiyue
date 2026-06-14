from __future__ import annotations

import subprocess
from collections import deque
from collections.abc import Sequence
from pathlib import Path

from feiyue_core.providers.authorization import AuthorizedProviderRunRecord
from feiyue_core.providers.profile_runner import HermesProfileSubprocessRunner, ProfileRunRequest, ProfileRunResult


class SequencedHermesProfileRunner:
    """Run exact authorized Hermes profile records in per-profile sequence.

    This productizes the Live-B teacher-retry seam: one selected worker may be
    called, then a teacher, then the same worker again, while each subprocess is
    still bound to a persisted AuthorizedProviderRunRecord. Missing records or
    profile mismatches fail closed before falling through to any other command.
    """

    def __init__(
        self,
        *,
        project_root: str | Path,
        run_records: Sequence[AuthorizedProviderRunRecord],
        subprocess_runner=None,
    ) -> None:
        self._project_root = Path(project_root)
        self._subprocess_runner = subprocess_runner or subprocess.run
        self._records: dict[str, deque[AuthorizedProviderRunRecord]] = {}
        for record in run_records:
            profile = record.authorization.provider_or_profile
            self._records.setdefault(profile, deque()).append(record)

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        queue = self._records.get(request.profile)
        if not queue:
            return ProfileRunResult(
                stdout="",
                stderr=f"no authorized provider run record remains for {request.profile}",
                exit_code=126,
            )
        record = queue.popleft()
        return HermesProfileSubprocessRunner(
            run_record=record,
            project_root=self._project_root,
            subprocess_runner=self._subprocess_runner,
        ).run(request)


def load_authorized_provider_run_record(path: str | Path) -> AuthorizedProviderRunRecord:
    record_path = Path(path)
    if not record_path.exists():
        raise FileNotFoundError(f"Authorized provider run record not found: {record_path}")
    return AuthorizedProviderRunRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
