"""
GS1 (GLYPH Stream v1) — Stream framing protocol for GLYPH payloads.

GS1 is a transport envelope for GLYPH payloads, providing:
- Message boundaries and resync
- Multiplexing via stream IDs (sid)
- Ordering via sequence numbers (seq)
- Integrity via optional CRC-32
- Patch safety via optional state hash (base)

GS1 headers are NOT part of GLYPH canonicalization.
The payload is standard GLYPH text passed to existing parsers unchanged.
"""

from .types import (
    VERSION,
    FrameKind,
    KIND_DOC,
    KIND_PATCH,
    KIND_ROW,
    KIND_UI,
    KIND_ACK,
    KIND_ERR,
    KIND_PING,
    KIND_PONG,
    KIND_VALUES,
    VALUE_KINDS,
    FLAG_HAS_CRC,
    FLAG_HAS_BASE,
    FLAG_FINAL,
    FLAG_COMPRESSED,
    Frame,
    MAX_PAYLOAD_SIZE,
    ParseError,
    CRCMismatchError,
    BaseMismatchError,
    parse_kind,
    kind_to_str,
    # Error code registry
    ERR_BASE_MISMATCH,
    ERR_SEQ_GAP,
    ERR_SEQ_DUP,
    ERR_NO_STATE,
    ERR_CRC_MISMATCH,
    ERR_VERSION_UNSUPPORTED,
    ERR_PAYLOAD_TOO_LARGE,
    ERR_HEADER_TOO_LARGE,
    ERR_FRAME_INVALID,
)

from .crc import (
    compute_crc,
    verify_crc,
    crc_to_hex,
    parse_crc,
)

from .hash import (
    state_hash_loose,
    state_hash_bytes,
    verify_base,
    hash_to_hex,
    hex_to_hash,
)

from .cursor import (
    SIDState,
    StreamCursor,
    FrameHandler,
)

from .ui_events import (
    progress,
    log,
    log_info,
    log_warn,
    log_error,
    log_debug,
    metric,
    counter,
    artifact,
    resync_request,
    error,
    emit_ui,
    emit_progress,
    emit_log,
    emit_metric,
    emit_artifact,
    emit_error,
    emit_resync_request,
    parse_ui_event,
)

from .gs1t import (
    Writer,
    Reader,
    encode_frame,
    encode_frames,
    decode_frame,
    decode_frames,
)

__all__ = [
    # Types
    "VERSION",
    "FrameKind",
    "KIND_DOC",
    "KIND_PATCH",
    "KIND_ROW",
    "KIND_UI",
    "KIND_ACK",
    "KIND_ERR",
    "KIND_PING",
    "KIND_PONG",
    "KIND_VALUES",
    "VALUE_KINDS",
    "FLAG_HAS_CRC",
    "FLAG_HAS_BASE",
    "FLAG_FINAL",
    "FLAG_COMPRESSED",
    "Frame",
    "MAX_PAYLOAD_SIZE",
    "ParseError",
    "CRCMismatchError",
    "BaseMismatchError",
    "parse_kind",
    "kind_to_str",
    "ERR_BASE_MISMATCH",
    "ERR_SEQ_GAP",
    "ERR_SEQ_DUP",
    "ERR_NO_STATE",
    "ERR_CRC_MISMATCH",
    "ERR_VERSION_UNSUPPORTED",
    "ERR_PAYLOAD_TOO_LARGE",
    "ERR_HEADER_TOO_LARGE",
    "ERR_FRAME_INVALID",
    # CRC
    "compute_crc",
    "verify_crc",
    "crc_to_hex",
    "parse_crc",
    # Hash
    "state_hash_loose",
    "state_hash_bytes",
    "verify_base",
    "hash_to_hex",
    "hex_to_hash",
    # Cursor
    "SIDState",
    "StreamCursor",
    "FrameHandler",
    # UI events
    "progress",
    "log",
    "log_info",
    "log_warn",
    "log_error",
    "log_debug",
    "metric",
    "counter",
    "artifact",
    "resync_request",
    "error",
    "emit_ui",
    "emit_progress",
    "emit_log",
    "emit_metric",
    "emit_artifact",
    "emit_error",
    "emit_resync_request",
    "parse_ui_event",
    # GS1-T reader / writer
    "Writer",
    "Reader",
    "encode_frame",
    "encode_frames",
    "decode_frame",
    "decode_frames",
]
