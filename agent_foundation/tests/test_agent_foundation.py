from __future__ import annotations

import sys

from agent_foundation import (
    Checkpoint,
    Event,
    EventKind,
    FileCheckpointStore,
    ProcessSpec,
    ProcessSupervisor,
    RetryPolicy,
    Termination,
    TranscriptReader,
    TranscriptWriter,
    decode_json_lines,
    extract_json_object,
    extract_text,
    json_pointer_values,
    normalize_stream_line,
    retry,
)


def test_stream_normalization_and_json_lines_are_schema_free():
    assert normalize_stream_line("\x1b]0;title\x07data: {\"any\": 1}") == '{"any": 1}'
    decoded, rejected = decode_json_lines(['data: {"x": 1}\nnot-json\n[1, 2]'])
    assert decoded == [{"x": 1}, [1, 2]]
    assert rejected == ["not-json"]


def test_content_extraction_needs_no_provider_shape():
    document = {"arbitrary": {"answer": "hello"}, "items": [{"value": 3}]}
    assert json_pointer_values(document, ["/arbitrary/answer", "/items/0/value"]) == ["hello", 3]
    assert extract_text(document, pointers=["/arbitrary/answer"]) == "hello"
    assert extract_json_object("notes\n```json\n{\"free\": true}\n```") == {"free": True}
    assert extract_json_object('before ["a", {"b": "}"}] after') == ["a", {"b": "}"}]


def test_checkpoint_and_transcript_are_restart_safe(tmp_path):
    store = FileCheckpointStore(tmp_path / "checkpoints")
    checkpoint = Checkpoint(key="conversation/one", continuation="opaque-token", data={"state": "sample"})
    store.save(checkpoint)
    restored = store.load("conversation/one")
    assert restored is not None
    assert restored.continuation == "opaque-token"

    path = tmp_path / "transcript.jsonl"
    writer = TranscriptWriter(path)
    writer.append(Event(EventKind.OUTPUT, "Authorization: top-secret"))
    assert list(TranscriptReader(path).events())[0].message == "***REDACTED***"
    writer.append(Event(EventKind.OUTPUT, "Authorization: Bearer top-secret"))
    private_block = "-----BEGIN " + "PRIVATE KEY-----\nsample\n-----END " + "PRIVATE KEY-----"
    writer.append(Event(EventKind.OUTPUT, private_block))
    events = list(TranscriptReader(path).events())
    assert events[1].message == "***REDACTED***"
    assert events[2].message == "***REDACTED***"


def test_supervisor_reports_output_heartbeat_and_idle_timeout():
    command = [sys.executable, "-c", "import time; print('ready', flush=True); time.sleep(0.3)"]
    completed = ProcessSupervisor().run(
        ProcessSpec(command, hard_timeout_seconds=2, idle_timeout_seconds=1, heartbeat_interval_seconds=0.05)
    )
    assert completed.termination == Termination.EXITED
    assert completed.stdout == "ready\n"
    assert any(event.kind == EventKind.HEARTBEAT for event in completed.events)
    start_event = next(event for event in completed.events if event.kind == EventKind.START)
    assert start_event.data == {"executable": sys.executable, "argument_count": 2}

    idle = ProcessSupervisor().run(
        ProcessSpec([sys.executable, "-c", "import time; time.sleep(2)"], idle_timeout_seconds=0.1)
    )
    assert idle.termination == Termination.IDLE_TIMEOUT

    output_then_idle = ProcessSupervisor().run(
        ProcessSpec(
            [sys.executable, "-c", "import time; print('one', flush=True); time.sleep(2)"],
            idle_timeout_seconds=0.1,
        )
    )
    assert output_then_idle.termination == Termination.IDLE_TIMEOUT
    assert output_then_idle.stdout == "one\n"


def test_retry_uses_caller_defined_transient_boundary():
    attempts = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("temporary")
        return "done"

    result = retry(
        operation,
        policy=RetryPolicy(max_attempts=4, initial_delay_seconds=0.1, multiplier=2),
        is_retryable=lambda error: isinstance(error, ConnectionError),
        on_retry=lambda _attempt, _error, delay: delays.append(delay),
        sleep=lambda _delay: None,
    )
    assert result == "done"
    assert delays == [0.1, 0.2]
