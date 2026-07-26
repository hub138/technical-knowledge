"""Framework-neutral building blocks for long-running agent sessions."""

from .cli_session import (
    ProcessResult,
    ProcessSpec,
    ProcessSupervisor,
    Termination,
    decode_json_lines,
    normalize_stream_line,
)
from .content import extract_json_object, extract_text, json_pointer_values
from .events import Event, EventKind
from .probe import CommandProbe, probe_command
from .recovery import Checkpoint, FileCheckpointStore, RetryPolicy, retry
from .transcript import TranscriptReader, TranscriptWriter, hmac_digest, redact_text

__all__ = [
    "Checkpoint",
    "CommandProbe",
    "Event",
    "EventKind",
    "FileCheckpointStore",
    "ProcessResult",
    "ProcessSpec",
    "ProcessSupervisor",
    "RetryPolicy",
    "Termination",
    "TranscriptReader",
    "TranscriptWriter",
    "decode_json_lines",
    "extract_json_object",
    "extract_text",
    "hmac_digest",
    "json_pointer_values",
    "normalize_stream_line",
    "probe_command",
    "redact_text",
    "retry",
]
