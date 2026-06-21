"""
Standard UI Event Types for GS1 streams.

These are recommended payload schemas for kind=ui frames.
They provide a consistent way to stream agent/workflow status.

Mirrors go/stream/ui_events.go and js/src/stream/ui_events.ts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from ..types import GValue, MapEntry
from ..loose import canonicalize_loose


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _field(key: str, value: GValue) -> MapEntry:
    return MapEntry(key, value)


MAX_GLYPH_EVENT_INT = (1 << 63) - 1


def _uint_field(key: str, value: int) -> MapEntry:
    """Encode a uint64 as int (if <= MAX_GLYPH_EVENT_INT) or str (if larger)."""
    if value > MAX_GLYPH_EVENT_INT:
        return _field(key, GValue.str_(str(value)))
    return _field(key, GValue.int_(value))


# ---------------------------------------------------------------------------
# UI Event constructors
# ---------------------------------------------------------------------------

def progress(pct: float, msg: str) -> GValue:
    """
    Progress update event.
    Payload: Progress@(pct 0.42 msg "processing step 3")
    """
    return GValue.struct(
        "Progress",
        _field("pct", GValue.float_(pct)),
        _field("msg", GValue.str_(msg)),
    )


def log(level: str, msg: str) -> GValue:
    """
    Log event with timestamp.
    Payload: Log@(level "info" msg "decoded 1000 rows" ts "2025-06-20T10:30:00Z")
    """
    return GValue.struct(
        "Log",
        _field("level", GValue.str_(level)),
        _field("msg",   GValue.str_(msg)),
        _field("ts",    GValue.time(datetime.now(timezone.utc))),
    )


def log_info(msg: str) -> GValue:
    return log("info", msg)


def log_warn(msg: str) -> GValue:
    return log("warn", msg)


def log_error(msg: str) -> GValue:
    return log("error", msg)


def log_debug(msg: str) -> GValue:
    return log("debug", msg)


def metric(name: str, value: float, unit: Optional[str] = None) -> GValue:
    """
    Numeric metric event.
    Payload: Metric@(name "latency_ms" value 12.5 unit "ms")
    """
    fields = [
        _field("name",  GValue.str_(name)),
        _field("value", GValue.float_(value)),
    ]
    if unit:
        fields.append(_field("unit", GValue.str_(unit)))
    return GValue.struct("Metric", *fields)


def counter(name: str, count: int) -> GValue:
    """Integer counter metric."""
    return GValue.struct(
        "Metric",
        _field("name",  GValue.str_(name)),
        _field("value", GValue.int_(count)),
        _field("unit",  GValue.str_("count")),
    )


def artifact(mime: str, ref: str, name: str) -> GValue:
    """
    Artifact reference event.
    Payload: Artifact@(mime "image/png" ref "blob:sha256:..." name "plot.png")
    """
    return GValue.struct(
        "Artifact",
        _field("mime", GValue.str_(mime)),
        _field("ref",  GValue.str_(ref)),
        _field("name", GValue.str_(name)),
    )


# ---------------------------------------------------------------------------
# Resync events
# ---------------------------------------------------------------------------

def resync_request(sid: int, seq: int, want: str, reason: str) -> GValue:
    """
    Resync request — sent when receiver needs a fresh snapshot.
    Payload: ResyncRequest@(sid 1 seq 42 want "sha256:..." reason "BASE_MISMATCH")
    """
    return GValue.struct(
        "ResyncRequest",
        _uint_field("sid",    sid),
        _uint_field("seq",    seq),
        _field("want",   GValue.str_(want)),
        _field("reason", GValue.str_(reason)),
    )


# ---------------------------------------------------------------------------
# Error events
# ---------------------------------------------------------------------------

def error(code: str, msg: str, sid: int, seq: int) -> GValue:
    """
    Error event for kind=err frames.
    Payload: Error@(code "BASE_MISMATCH" msg "state hash mismatch" sid 1 seq 42)
    """
    return GValue.struct(
        "Error",
        _field("code",  GValue.str_(code)),
        _field("msg",   GValue.str_(msg)),
        _uint_field("sid", sid),
        _uint_field("seq", seq),
    )


# ---------------------------------------------------------------------------
# Emit helpers (return bytes for frame payloads)
# ---------------------------------------------------------------------------

def emit_ui(v: GValue) -> bytes:
    """Emit any UI event value as UTF-8 bytes."""
    return canonicalize_loose(v).encode("utf-8")


def emit_progress(pct: float, msg: str) -> bytes:
    return emit_ui(progress(pct, msg))


def emit_log(level: str, msg: str) -> bytes:
    return emit_ui(log(level, msg))


def emit_metric(name: str, value: float, unit: Optional[str] = None) -> bytes:
    return emit_ui(metric(name, value, unit))


def emit_artifact(mime: str, ref: str, name: str) -> bytes:
    return emit_ui(artifact(mime, ref, name))


def emit_error(code: str, msg: str, sid: int, seq: int) -> bytes:
    return emit_ui(error(code, msg, sid, seq))


def emit_resync_request(sid: int, seq: int, want: str, reason: str) -> bytes:
    return emit_ui(resync_request(sid, seq, want, reason))


# ---------------------------------------------------------------------------
# Parse helper
# ---------------------------------------------------------------------------

def parse_ui_event(payload: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Parse a UI event payload and return (type_name, fields).

    Delegates to the standard GLYPH parser so all GLYPH value types are
    handled correctly (strings, ints, floats, bools, times, etc.).

    Raises ValueError if the payload is not a struct.
    """
    from ..parse import parse_loose

    text = payload.decode("utf-8")
    v = parse_loose(text)

    if v.type.value != "struct":
        raise ValueError(f"ui event must be a struct, got {v.type.value}")

    sv = v.as_struct()
    fields: Dict[str, Any] = {}

    for f in sv.fields:
        fv = f.value
        ft = fv.type.value
        if ft == "str":
            fields[f.key] = fv.as_str()
        elif ft == "int":
            fields[f.key] = fv.as_int()
        elif ft == "float":
            fields[f.key] = fv.as_float()
        elif ft == "bool":
            fields[f.key] = fv.as_bool()
        elif ft == "time":
            fields[f.key] = fv.as_time()
        else:
            fields[f.key] = fv

    return sv.type_name, fields
