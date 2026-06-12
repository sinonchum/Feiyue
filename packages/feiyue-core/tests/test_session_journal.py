import json

from feiyue_core.recovery import RecoveryManifest
from feiyue_core.runtime.journal import SessionJournal
from feiyue_core.schemas import TraceEvent, TraceEventType


def test_session_journal_appends_and_reads_events(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    first = TraceEvent(
        id="evt_001",
        session_id="sess_001",
        type=TraceEventType.USER_MESSAGE_PERSISTED,
        message="user asked to continue",
        data={"source": "telegram"},
    )
    second = TraceEvent(
        id="evt_002",
        session_id="sess_001",
        type=TraceEventType.TOOL_OPERATION_STARTED,
        message="terminal started",
        data={"tool": "terminal"},
    )

    journal.append(first)
    journal.append(second)

    events = journal.read_all()
    assert [event.id for event in events] == ["evt_001", "evt_002"]
    assert events[0].type == TraceEventType.USER_MESSAGE_PERSISTED
    raw_lines = (tmp_path / "session.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(raw_lines[1])["message"] == "terminal started"


def test_session_journal_ignores_blank_lines(tmp_path) -> None:
    path = tmp_path / "session.jsonl"
    path.write_text("\n", encoding="utf-8")
    journal = SessionJournal(path)

    assert journal.read_all() == []


def test_manifest_store_writes_latest_manifest_atomically(tmp_path) -> None:
    journal = SessionJournal(tmp_path / "session.jsonl")
    manifest = RecoveryManifest(
        session_id="sess_001",
        current_goal="continue development",
        confirmed_facts=["tests passed before restart"],
        known_mistakes=["do not assume python3 has pytest"],
        next_safe_action="run pytest with current interpreter",
    )

    journal.write_manifest(manifest)

    loaded = journal.read_manifest()
    assert loaded.session_id == "sess_001"
    assert loaded.known_mistakes == ["do not assume python3 has pytest"]
    assert loaded.next_safe_action == "run pytest with current interpreter"
    assert (tmp_path / "latest_manifest.json").exists()
