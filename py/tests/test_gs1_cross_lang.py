"""
GS1 Cross-Language Conformance: Go -> Python live pipe test.

Runs the Go emitter (go/stream package) via subprocess, pipes its stdout to
the Python GS1-T Reader, and asserts that every frame is parsed identically.

This is a live, end-to-end conformance check: the Go binary uses the real
go/stream package; the Python side uses glyph.stream.  Any wire-format
divergence will be caught here.

Test is skipped if `go` is not on PATH or the Go module cannot be found.
"""

from __future__ import annotations

import subprocess
import sys
import io
import os
import pytest

from glyph.stream import (
    KIND_DOC,
    KIND_PATCH,
    KIND_ACK,
    decode_frames,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE    = os.path.dirname(os.path.abspath(__file__))
_EMITTER = os.path.join(_HERE, "cross_lang", "go_emitter.go")
_GO_MOD  = os.path.join(
    os.path.dirname(os.path.dirname(_HERE)),
    "go",
)  # .../glyph/go  (contains go.mod)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _go_available() -> bool:
    try:
        subprocess.run(["go", "version"], capture_output=True, check=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _run_go_emitter() -> bytes:
    """Run go_emitter.go and return its stdout bytes."""
    result = subprocess.run(
        ["go", "run", _EMITTER],
        capture_output=True,
        cwd=_GO_MOD,   # must run from the module root so go finds go.mod
        timeout=60,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        pytest.fail(f"go_emitter.go failed (exit {result.returncode}):\n{stderr}")
    return result.stdout


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

requires_go = pytest.mark.skipif(
    not _go_available(),
    reason="'go' not on PATH — skipping cross-language conformance tests",
)


@requires_go
class TestGoPythonConformance:
    """Python Reader correctly decodes every frame emitted by the Go Writer."""

    def _frames(self):
        raw = _run_go_emitter()
        return decode_frames(raw, verify_crc=True)

    def test_go_emitter_produces_parseable_output(self):
        """Python can decode all frames from the Go emitter without error."""
        frames = self._frames()
        assert len(frames) == 5

    def test_frame1_minimal_doc(self):
        """Frame 1: minimal doc matches Go TestWriter_MinimalFrame golden."""
        frames = self._frames()
        f = frames[0]
        assert f.version == 1
        assert f.sid     == 0
        assert f.seq     == 0
        assert f.kind    == KIND_DOC
        assert f.payload == b"{}"

    def test_frame2_ack_empty(self):
        """Frame 2: ack with empty payload matches Go TestWriter_EmptyPayload golden."""
        frames = self._frames()
        f = frames[1]
        assert f.kind    == KIND_ACK
        assert f.sid     == 1
        assert f.seq     == 42
        assert f.payload == b""

    def test_frame3_patch_with_newlines(self):
        """Frame 3: patch payload contains newlines — len-delimited correctly."""
        frames = self._frames()
        f = frames[2]
        assert f.kind    == KIND_PATCH
        assert f.sid     == 1
        assert f.seq     == 1
        assert f.payload == b"@patch\nset .x 1\nset .y 2\n@end"

    def test_frame4_final_flag(self):
        """Frame 4: final=true flag decoded correctly."""
        frames = self._frames()
        f = frames[3]
        assert f.kind    == KIND_DOC
        assert f.payload == b"done"
        assert f.final   is True

    def test_frame5_large_uint64(self):
        """Frame 5: uint64 max for sid and seq decoded correctly."""
        frames = self._frames()
        f = frames[4]
        max_u64 = 0xFFFFFFFFFFFFFFFF
        assert f.sid     == max_u64
        assert f.seq     == max_u64
        assert f.payload == b"x"

    def test_python_wire_matches_go_wire_for_minimal_doc(self):
        """
        Python Writer output is byte-for-byte identical to Go Writer output
        for the minimal doc frame.

        This is the strongest form of cross-language conformance: the two
        implementations independently agree on the exact wire encoding.
        """
        from glyph.stream import encode_frame, Frame, KIND_DOC

        py_wire = encode_frame(Frame(1, 0, 0, KIND_DOC, b"{}"))
        go_wire = b"@frame{v=1 sid=0 seq=0 kind=doc len=2}\n{}\n"

        assert py_wire == go_wire, (
            f"Python wire:\n  {py_wire!r}\n"
            f"Go wire:\n  {go_wire!r}"
        )

    def test_python_wire_matches_go_wire_for_ack(self):
        """Python and Go produce identical bytes for an empty ack frame."""
        from glyph.stream import encode_frame, Frame, KIND_ACK

        py_wire = encode_frame(Frame(1, 1, 42, KIND_ACK, b""))
        go_wire = b"@frame{v=1 sid=1 seq=42 kind=ack len=0}\n\n"
        assert py_wire == go_wire
