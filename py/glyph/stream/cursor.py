"""
StreamCursor — per-SID state tracking for GS1 streams.

Mirrors go/stream/cursor.go (source of truth for behaviour) and
js/src/stream/cursor.ts.

Two classes are provided:

* StreamCursor — strict mode: ProcessFrame raises on seq gaps and duplicates,
  and on base-hash mismatches for patch frames.

* FrameHandler — lenient mode: silently discards duplicates; invokes optional
  callbacks on seq gaps and base mismatches (continuing if the callback returns
  None/True), and dispatches per-kind callbacks.

Both are conformant with the GS1 spec (§7.1 "Gap vs duplicate handling" note).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..types import GValue
from .types import (
    Frame,
    FrameKind,
    KIND_PATCH,
    BaseMismatchError,
)
from .hash import state_hash_loose, verify_base


# ---------------------------------------------------------------------------
# SIDState
# ---------------------------------------------------------------------------

@dataclass
class SIDState:
    """State for a single stream ID."""
    sid: int
    last_seq: int = 0
    last_acked: int = 0
    state_hash: Optional[bytes] = None   # 32-byte SHA-256; None if not set
    has_state: bool = False
    state: Optional[GValue] = None
    final: bool = False


# ---------------------------------------------------------------------------
# StreamCursor (strict mode)
# ---------------------------------------------------------------------------

class StreamCursor:
    """
    Tracks per-SID state for stream processing (strict mode).

    Thread-safe: a single lock guards all per-SID state.
    Raises on seq gaps, seq duplicates, and base-hash mismatches.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cursors: Dict[int, SIDState] = {}

    # ------------------------------------------------------------------
    # SID state access
    # ------------------------------------------------------------------

    def get(self, sid: int) -> SIDState:
        """Return state for *sid*, creating it if needed."""
        with self._lock:
            if sid not in self._cursors:
                self._cursors[sid] = SIDState(sid=sid)
            return self._cursors[sid]

    def get_read_only(self, sid: int) -> Optional[SIDState]:
        """Return state for *sid* without creating it."""
        with self._lock:
            return self._cursors.get(sid)

    def delete(self, sid: int) -> None:
        """Remove state for *sid*."""
        with self._lock:
            self._cursors.pop(sid, None)

    def all_sids(self) -> List[int]:
        """Return all tracked SIDs."""
        with self._lock:
            return list(self._cursors.keys())

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def process_frame(self, frame: Frame) -> None:
        """
        Validate and update cursor state for *frame*.

        Raises:
            ValueError — seq not monotonic (gap or duplicate).
            BaseMismatchError — base hash mismatch on patch frame.
        """
        state = self.get(frame.sid)

        # seq=0 is the stream-open sentinel; a fresh SID starts at last_seq=0.
        # Any seq <= last_seq after the stream has been opened is either a
        # duplicate (seq == last_seq and seq != 0) or a replay of seq=0 after
        # a higher seq has already been seen — both are hard errors in strict mode.
        if frame.seq != 0 and frame.seq <= state.last_seq:
            raise ValueError(
                f"sequence not monotonic: got {frame.seq}, last was {state.last_seq}"
            )

        # Gap check: after the first frame, every seq must be last_seq + 1.
        if state.last_seq > 0 and frame.seq != state.last_seq + 1:
            raise ValueError(
                f"sequence gap: expected {state.last_seq + 1}, got {frame.seq}"
            )

        # Patch base verification.
        if frame.kind == KIND_PATCH and frame.base is not None:
            if not state.has_state:
                raise ValueError(
                    f"cannot verify base: no state hash for SID {frame.sid}"
                )
            if not verify_base(state.state_hash, frame.base):  # type: ignore[arg-type]
                raise BaseMismatchError(expected=frame.base, got=state.state_hash)

        # Commit.
        state.last_seq = frame.seq
        if frame.is_final():
            state.final = True

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def set_state(self, sid: int, value: GValue) -> None:
        """Set the current state and compute its hash from *value*."""
        state = self.get(sid)
        state.state = value
        state.state_hash = state_hash_loose(value)
        state.has_state = True

    def set_state_hash(self, sid: int, hash_bytes: bytes) -> None:
        """Set the state hash directly (32 bytes, pre-computed)."""
        state = self.get(sid)
        state.state_hash = hash_bytes
        state.has_state = True

    # ------------------------------------------------------------------
    # Acknowledgement
    # ------------------------------------------------------------------

    def ack(self, sid: int, seq: int) -> None:
        """Mark *seq* as acknowledged for *sid*."""
        state = self.get(sid)
        if seq > state.last_acked:
            state.last_acked = seq

    def pending_acks(self, sid: int) -> List[int]:
        """Return seq numbers that have been seen but not yet acked."""
        state = self.get_read_only(sid)
        if state is None:
            return []
        if state.last_seq <= state.last_acked:
            return []
        return list(range(state.last_acked + 1, state.last_seq + 1))

    def needs_resync(self, sid: int) -> bool:
        """Return True if the SID has no state hash (resync required)."""
        state = self.get_read_only(sid)
        return state is None or not state.has_state


# ---------------------------------------------------------------------------
# FrameHandler (lenient mode)
# ---------------------------------------------------------------------------

# Callback type aliases
_PayloadCb = Callable[[int, int, bytes, SIDState], None]
_AckCb     = Callable[[int, int, SIDState], None]
_FinalCb   = Callable[[int, SIDState], None]
_GapCb     = Callable[[int, int, int], bool]   # sid, expected, got → allow
_MismatchCb = Callable[[int, Frame], bool]       # sid, frame → allow


class FrameHandler:
    """
    Processes frames with state tracking and per-kind callbacks (lenient mode).

    Duplicates are silently discarded.  Seq gaps invoke on_seq_gap (if set);
    the handler continues if the callback returns True (or None).
    Base mismatches invoke on_base_mismatch (if set); raises BaseMismatchError
    if not set.
    """

    def __init__(self) -> None:
        self.cursor: StreamCursor = StreamCursor()

        # Per-kind callbacks (optional)
        self.on_doc:    Optional[_PayloadCb] = None
        self.on_patch:  Optional[_PayloadCb] = None
        self.on_row:    Optional[_PayloadCb] = None
        self.on_ui:     Optional[_PayloadCb] = None
        self.on_ack:    Optional[_AckCb]     = None
        self.on_err:    Optional[_PayloadCb] = None
        self.on_final:  Optional[_FinalCb]   = None

        # Error callbacks
        self.on_seq_gap:       Optional[_GapCb]     = None
        self.on_base_mismatch: Optional[_MismatchCb] = None

    def handle(self, frame: Frame) -> None:
        """Handle *frame*, updating cursor state and dispatching callbacks."""
        state = self.cursor.get(frame.sid)

        # Sequence checks.
        if frame.seq != 0 and state.last_seq > 0:
            if frame.seq <= state.last_seq:
                # Duplicate — silently discard.
                return
            if frame.seq != state.last_seq + 1:
                # Gap detected.
                if self.on_seq_gap is not None:
                    allow = self.on_seq_gap(frame.sid, state.last_seq + 1, frame.seq)
                    if not allow:
                        return
                # If no callback or callback allowed, fall through.

        # Base check for patches.
        if frame.kind == KIND_PATCH and frame.base is not None and state.has_state:
            if not verify_base(state.state_hash, frame.base):  # type: ignore[arg-type]
                if self.on_base_mismatch is not None:
                    allow = self.on_base_mismatch(frame.sid, frame)
                    if not allow:
                        return
                else:
                    raise BaseMismatchError(expected=frame.base, got=state.state_hash)

        # Commit seq.
        state.last_seq = frame.seq

        # Dispatch per-kind callbacks.
        if frame.kind == KIND_PATCH:
            if self.on_patch is not None:
                self.on_patch(frame.sid, frame.seq, frame.payload, state)
        elif frame.kind == 0:   # KIND_DOC
            if self.on_doc is not None:
                self.on_doc(frame.sid, frame.seq, frame.payload, state)
        elif frame.kind == 2:   # KIND_ROW
            if self.on_row is not None:
                self.on_row(frame.sid, frame.seq, frame.payload, state)
        elif frame.kind == 3:   # KIND_UI
            if self.on_ui is not None:
                self.on_ui(frame.sid, frame.seq, frame.payload, state)
        elif frame.kind == 4:   # KIND_ACK
            if self.on_ack is not None:
                self.on_ack(frame.sid, frame.seq, state)
        elif frame.kind == 5:   # KIND_ERR
            if self.on_err is not None:
                self.on_err(frame.sid, frame.seq, frame.payload, state)

        # Final flag.
        if frame.is_final():
            state.final = True
            if self.on_final is not None:
                self.on_final(frame.sid, state)
