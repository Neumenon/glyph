"""
SHA-256 state hash helpers for GS1.

state_hash_loose(value) = sha256(canon_json(value)) — the one digest (SPEC-CANON.md §5),
as 32 raw bytes. Its hex is glyph.fingerprint(value). Identical in Go and JS.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from ..canon import canon_json
from ..types import GValue


def state_hash_loose(value: GValue) -> bytes:
    """GS1 state hash: sha256(canon_json(value)), 32 bytes.

    The name is historical: it hashes canon_json despite the name (kept for
    API parity with Go/JS — no rename).
    """
    return hashlib.sha256(canon_json(value).encode("utf-8")).digest()


def state_hash_bytes(data: bytes) -> bytes:
    """
    Compute SHA-256 of raw bytes.  Use when you already have canonical bytes.

    Returns 32 bytes.
    """
    return hashlib.sha256(data).digest()


def verify_base(current: bytes, expected: bytes) -> bool:
    """Return True iff current and expected are equal 32-byte hashes."""
    if len(current) != 32 or len(expected) != 32:
        return False
    return current == expected


def hash_to_hex(h: bytes) -> str:
    """Convert 32-byte hash to lowercase 64-character hex string."""
    return h.hex()


def hex_to_hash(s: str) -> Optional[bytes]:
    """
    Parse a 64-character hex string (optionally prefixed with ``sha256:``)
    into 32 bytes.  Returns None on invalid input.
    """
    if s.startswith("sha256:"):
        s = s[7:]
    if len(s) != 64:
        return None
    try:
        b = bytes.fromhex(s)
    except ValueError:
        return None
    if len(b) != 32:
        return None
    return b
