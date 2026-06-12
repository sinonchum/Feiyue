import json

from feiyue_core.audit.trace_writer import JsonlTraceWriter
from feiyue_core.schemas import TraceEvent, TraceEventType


def test_jsonl_trace_writer_appends_events(tmp_path) -> None:
    trace_path = tmp_path / "events.jsonl"
    writer = JsonlTraceWriter(trace_path)

    writer.append(
        TraceEvent(
            id="evt_001",
            session_id="sess_001",
            type=TraceEventType.TOOL_OPERATION_FINISHED,
            message="command completed",
            data={"exit_code": 0},
        )
    )
    writer.append(
        TraceEvent(
            id="evt_002",
            session_id="sess_001",
            type=TraceEventType.MANIFEST_UPDATED,
            message="manifest updated",
            data={"pending_operations": []},
        )
    )

    lines = trace_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0])["id"] == "evt_001"
    assert json.loads(lines[1])["type"] == "manifest_updated"
