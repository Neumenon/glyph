"""
GS1 (GLYPH Stream v1) Types

Frame kinds, Frame dataclass, header fields, error types, and error code registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Protocol version
# ---------------------------------------------------------------------------

VERSION: int = 1

# ---------------------------------------------------------------------------
# Frame kinds
# ---------------------------------------------------------------------------

# Kind values match the GS1 spec wire integers exactly.
FrameKind = int

KIND_DOC:   FrameKind = 0  # Snapshot or general GLYPH document
KIND_PATCH: FrameKind = 1  # GLYPH patch doc (@patch ... @end)
KIND_ROW:   FrameKind = 2  # Single row value (streaming tabular)
KIND_UI:    FrameKind = 3  # UI event (progress/log/artifact)
KIND_ACK:   FrameKind = 4  # Acknowledgement
KIND_ERR:   FrameKind = 5  # Error event
KIND_PING:  FrameKind = 6  # Keepalive
KIND_PONG:  FrameKind = 7  # Ping response

KIND_VALUES: dict[str, FrameKind] = {
    "doc":   KIND_DOC,
    "patch": KIND_PATCH,
    "row":   KIND_ROW,
    "ui":    KIND_UI,
    "ack":   KIND_ACK,
    "err":   KIND_ERR,
    "ping":  KIND_PING,
    "pong":  KIND_PONG,
}

VALUE_KINDS: dict[FrameKind, str] = {v: k for k, v in KIND_VALUES.items()}


def kind_to_str(kind: FrameKind) -> str:
    """Return the string name for a kind value."""
    name = VALUE_KINDS.get(kind)
    if name is not None:
        return name
    return f"unknown({kind})"


def parse_kind(s: str) -> tuple[FrameKind, bool]:
    """Parse a kind name or numeric string. Returns (kind, ok)."""
    if s in KIND_VALUES:
        return KIND_VALUES[s], True
    try:
        n = int(s)
        if 0 <= n <= 255:
            return FrameKind(n), True
    except ValueError:
        pass
    return 0, False


# ---------------------------------------------------------------------------
# Flag bits
# ---------------------------------------------------------------------------

FLAG_HAS_CRC:     int = 0x01  # CRC-32 is present
FLAG_HAS_BASE:    int = 0x02  # Base hash is present
FLAG_FINAL:       int = 0x04  # End-of-stream for this SID (GS1-B only)
FLAG_COMPRESSED:  int = 0x08  # Payload compressed (reserved for GS1.1)

# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------

@dataclass
class Frame:
    """A single GS1 frame (header + payload)."""

    # Required fields
    version: int       # Protocol version (must be 1)
    sid: int           # Stream identifier (uint64)
    seq: int           # Sequence number per-SID (uint64, monotonic)
    kind: FrameKind    # Frame kind
    payload: bytes     # GLYPH payload bytes (UTF-8); may be empty

    # Optional fields
    crc: Optional[int]   = field(default=None)   # CRC-32 of payload
    base: Optional[bytes] = field(default=None)  # SHA-256 state hash (32 bytes)
    flags: int            = field(default=0)
    final: bool           = field(default=False)

    def has_crc(self) -> bool:
        return self.crc is not None

    def has_base(self) -> bool:
        return self.base is not None and len(self.base) == 32

    def is_final(self) -> bool:
        return self.final or bool(self.flags & FLAG_FINAL)


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_PAYLOAD_SIZE: int = 64 * 1024 * 1024   # 64 MiB
MAX_HEADER_SIZE:  int = 64 * 1024           # 64 KiB

# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class ParseError(Exception):
    """Structural parse failure."""
    def __init__(self, reason: str, offset: int = -1) -> None:
        self.reason = reason
        self.offset = offset
        if offset >= 0:
            super().__init__(f"gs1: {reason} at offset {offset}")
        else:
            super().__init__(f"gs1: {reason}")


class CRCMismatchError(Exception):
    """CRC-32 verification failed."""
    def __init__(self, expected: int, got: int) -> None:
        self.expected = expected
        self.got = got
        super().__init__(
            f"gs1: CRC mismatch: expected {expected:08x}, got {got:08x}"
        )


class BaseMismatchError(Exception):
    """Base hash mismatch on patch verification."""
    def __init__(
        self,
        expected: Optional[bytes] = None,
        got: Optional[bytes] = None,
    ) -> None:
        self.expected = expected
        self.got = got
        super().__init__("gs1: base hash mismatch")


# ---------------------------------------------------------------------------
# Error Code Registry  (§8.5 of GS1_SPEC.md)
# ---------------------------------------------------------------------------

ERR_BASE_MISMATCH:      str = "BASE_MISMATCH"
ERR_SEQ_GAP:            str = "SEQ_GAP"
ERR_SEQ_DUP:            str = "SEQ_DUP"
ERR_NO_STATE:           str = "NO_STATE"
ERR_CRC_MISMATCH:       str = "CRC_MISMATCH"
ERR_VERSION_UNSUPPORTED: str = "VERSION_UNSUPPORTED"
ERR_PAYLOAD_TOO_LARGE:  str = "PAYLOAD_TOO_LARGE"
ERR_HEADER_TOO_LARGE:   str = "HEADER_TOO_LARGE"
ERR_FRAME_INVALID:      str = "FRAME_INVALID"
