"""
SHA-256 state hash helpers for GS1.

state_hash_loose(value) computes sha256(CanonicalizeLoose(value)), where
CanonicalizeLoose uses the *default* opts (auto_tabular=True).  This matches
Go's stream.StateHashLoose, which calls glyph.CanonicalizeLoose(value) —
the default-opts variant with auto-tabular enabled.

This is intentionally different from fingerprint_loose (which uses
no_tabular_loose_canon_opts).  Do NOT use fingerprint_loose for the GS1
base field; use state_hash_loose.

Wire-format identity guarantee:
  state_hash_loose(v) == Go stream.StateHashLoose(v)
  (same CanonicalizeLoose output → same SHA-256 bytes)
"""

from __future__ import annotations

import hashlib
from typing import Optional

from ..types import GValue
from ..loose import canonicalize_loose, default_loose_canon_opts


def state_hash_loose(value: GValue) -> bytes:
    """
    Compute the GS1 state hash: sha256(CanonicalizeLoose(value)).

    Uses default loose canon opts (auto_tabular=True), matching Go's
    stream.StateHashLoose / JS's stateHashLooseSync.

    Returns 32 bytes.
    """
    canonical = canonicalize_loose(value, default_loose_canon_opts())
    return hashlib.sha256(canonical.encode("utf-8")).digest()


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
