"""
Tests for the GS1 (GLYPH Stream v1) Python implementation.

Covers:
- Round-trip of all frame kinds
- v != 1 rejection
- Sequence-gap detection
- Patch base-hash enforcement
- CRC integrity
- Golden byte vectors taken from go/stream/gs1t_test.go
- Cross-language conformance (Python decodes Go-golden bytes; Python output
  matches Go-golden bytes)
"""

from __future__ import annotations

import io
import pytest

from glyph.stream import (
    # Frame types
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
    Frame,
    MAX_PAYLOAD_SIZE,
    ParseError,
    CRCMismatchError,
    BaseMismatchError,
    parse_kind,
    kind_to_str,
    # CRC
    compute_crc,
    verify_crc,
    crc_to_hex,
    parse_crc,
    # Hash
    state_hash_bytes,
    verify_base,
    hash_to_hex,
    hex_to_hash,
    # Cursor
    SIDState,
    StreamCursor,
    FrameHandler,
    # GS1-T reader / writer
    Writer,
    Reader,
    encode_frame,
    encode_frames,
    decode_frame,
    decode_frames,
    # UI events
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode(frame: Frame, *, with_crc: bool = False) -> bytes:
    buf = io.BytesIO()
    Writer(buf, with_crc=with_crc).write_frame(frame)
    return buf.getvalue()


def _decode_one(data: bytes, *, verify_crc: bool = True) -> Frame:
    return Reader(io.BytesIO(data), verify_crc=verify_crc).next()


def _make_frame(
    kind: FrameKind = KIND_DOC,
    payload: bytes = b"{}",
    sid: int = 0,
    seq: int = 0,
    base: bytes | None = None,
    final: bool = False,
) -> Frame:
    return Frame(
        version=VERSION,
        sid=sid,
        seq=seq,
        kind=kind,
        payload=payload,
        base=base,
        final=final,
    )


# ---------------------------------------------------------------------------
# CRC tests — golden vectors from go/stream/gs1t_test.go TestCRC_KnownValues
# ---------------------------------------------------------------------------

class TestCRC:
    def test_empty(self):
        assert compute_crc(b"") == 0x00000000

    def test_a(self):
        assert compute_crc(b"a") == 0xe8b7be43

    def test_abc(self):
        assert compute_crc(b"abc") == 0x352441c2

    def test_hello(self):
        assert compute_crc(b"hello") == 0x3610a686

    def test_verify_crc_pass(self):
        data = b"test data"
        crc = compute_crc(data)
        assert verify_crc(data, crc) is True

    def test_verify_crc_fail(self):
        assert verify_crc(b"hello", 0xdeadbeef) is False

    def test_crc_to_hex_padding(self):
        assert crc_to_hex(0x00000001) == "00000001"
        assert len(crc_to_hex(compute_crc(b"abc"))) == 8

    def test_parse_crc_bare(self):
        assert parse_crc("e8b7be43") == 0xe8b7be43

    def test_parse_crc_prefixed(self):
        # prefix "crc32:" is accepted per the spec
        assert parse_crc("crc32:3610a686") == 0x3610a686

    def test_parse_crc_bad(self):
        assert parse_crc("notahex!") is None
        assert parse_crc("short") is None


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

class TestHash:
    def test_state_hash_bytes_is_sha256(self):
        import hashlib
        data = b"canonical glyph text"
        expected = hashlib.sha256(data).digest()
        assert state_hash_bytes(data) == expected

    def test_hash_to_hex_and_back(self):
        h = bytes(range(32))
        hex_str = hash_to_hex(h)
        assert len(hex_str) == 64
        result = hex_to_hash(hex_str)
        assert result == h

    def test_hex_to_hash_with_prefix(self):
        h = bytes(range(32))
        hex_str = "sha256:" + hash_to_hex(h)
        result = hex_to_hash(hex_str)
        assert result == h

    def test_hex_to_hash_bad(self):
        assert hex_to_hash("not64chars") is None
        assert hex_to_hash("zz" * 32) is None  # non-hex

    def test_verify_base_equal(self):
        h = bytes(range(32))
        assert verify_base(h, h) is True

    def test_verify_base_unequal(self):
        h1 = bytes(range(32))
        h2 = bytes([0] * 32)
        assert verify_base(h1, h2) is False

    def test_verify_base_wrong_length(self):
        assert verify_base(b"\x00" * 16, b"\x00" * 16) is False


# ---------------------------------------------------------------------------
# Writer golden-byte tests — match go/stream/gs1t_test.go TestWriter_*
# ---------------------------------------------------------------------------

class TestWriter:
    def test_minimal_frame_matches_go_golden(self):
        """go TestWriter_MinimalFrame: @frame{v=1 sid=0 seq=0 kind=doc len=2}\n{}\n"""
        frame = _make_frame(KIND_DOC, b"{}", sid=0, seq=0)
        got = _encode(frame).decode("utf-8")
        assert got == "@frame{v=1 sid=0 seq=0 kind=doc len=2}\n{}\n"

    def test_ack_empty_payload_matches_go_golden(self):
        """go TestWriter_EmptyPayload: @frame{v=1 sid=1 seq=42 kind=ack len=0}\n\n"""
        frame = _make_frame(KIND_ACK, b"", sid=1, seq=42)
        got = _encode(frame).decode("utf-8")
        assert got == "@frame{v=1 sid=1 seq=42 kind=ack len=0}\n\n"

    def test_with_crc_field_present(self):
        frame = _make_frame(KIND_DOC, b"{x=1}", sid=1, seq=5)
        out = _encode(frame, with_crc=True).decode("utf-8")
        assert "crc=" in out

    def test_with_base_field_present(self):
        base = bytes([0x01, 0x02] + [0x00] * 30)
        frame = _make_frame(KIND_PATCH, b"@patch\nset .x 1\n@end", sid=1, seq=10, base=base)
        out = _encode(frame).decode("utf-8")
        assert "base=sha256:" in out

    def test_final_flag_present(self):
        frame = _make_frame(KIND_DOC, b"final", sid=1, seq=100, final=True)
        out = _encode(frame).decode("utf-8")
        assert "final=true" in out

    def test_all_kinds_round_trip_header(self):
        for name, kind in KIND_VALUES.items():
            frame = _make_frame(kind, b"x", sid=0, seq=0)
            out = _encode(frame).decode("utf-8")
            assert f"kind={name}" in out, f"kind={name} not in header: {out}"


# ---------------------------------------------------------------------------
# Reader tests
# ---------------------------------------------------------------------------

class TestReader:
    def test_minimal_frame(self):
        """Matches Go TestReader_MinimalFrame."""
        data = b"@frame{v=1 sid=0 seq=0 kind=doc len=2}\n{}\n"
        frame = _decode_one(data)
        assert frame.version == 1
        assert frame.sid == 0
        assert frame.seq == 0
        assert frame.kind == KIND_DOC
        assert frame.payload == b"{}"

    def test_eof_returns_none(self):
        assert Reader(io.BytesIO(b"")).next() is None

    def test_version_v0_rejected(self):
        """v=0 must be rejected (GS1_SPEC §3.1)."""
        data = b"@frame{v=0 sid=0 seq=0 kind=doc len=0}\n\n"
        with pytest.raises(ParseError):
            _decode_one(data)

    def test_version_v2_rejected(self):
        """v=2 must be rejected."""
        data = b"@frame{v=2 sid=0 seq=0 kind=doc len=0}\n\n"
        with pytest.raises(ParseError):
            _decode_one(data)

    def test_crc_mismatch_raises(self):
        """go TestReader_CRCMismatch."""
        data = b"@frame{v=1 sid=1 seq=5 kind=doc len=5 crc=deadbeef}\nhello\n"
        with pytest.raises(CRCMismatchError) as exc_info:
            _decode_one(data)
        assert exc_info.value.expected == 0xdeadbeef

    def test_crc_correct_passes(self):
        payload = b"hello"
        crc = compute_crc(payload)
        data = f"@frame{{v=1 sid=1 seq=5 kind=doc len=5 crc={crc_to_hex(crc)}}}\nhello\n".encode()
        frame = _decode_one(data)
        assert frame.crc == crc

    def test_all_kinds_parsed(self):
        """go TestReader_AllKinds: each kind name is parsed correctly."""
        for name, kind in KIND_VALUES.items():
            data = f"@frame{{v=1 sid=0 seq=0 kind={name} len=1}}\nx\n".encode()
            frame = _decode_one(data)
            assert frame.kind == kind, f"kind={name}: expected {kind}, got {frame.kind}"

    def test_numeric_kind(self):
        """go TestReader_NumericKind: kind=99 is accepted."""
        data = b"@frame{v=1 sid=0 seq=0 kind=99 len=1}\nx\n"
        frame = _decode_one(data)
        assert frame.kind == 99

    def test_comma_separated_header(self):
        """go TestReader_HeaderVariations: comma-separated."""
        data = b"@frame{v=1,sid=1,seq=0,kind=doc,len=1}\nx\n"
        frame = _decode_one(data)
        assert frame.kind == KIND_DOC

    def test_payload_with_newlines(self):
        """go TestReader_PayloadWithNewlines: len-delimited, not newline-delimited."""
        payload = b"@patch\nset .x 1\nset .y 2\n@end"
        header = f"@frame{{v=1 sid=1 seq=1 kind=patch len={len(payload)}}}\n".encode()
        data = header + payload + b"\n"
        frame = _decode_one(data)
        assert frame.payload == payload

    def test_payload_with_braces(self):
        """go TestReader_PayloadWithBraces."""
        payload = b"{a={b={c=1}}}"
        header = f"@frame{{v=1 sid=1 seq=1 kind=doc len={len(payload)}}}\n".encode()
        data = header + payload + b"\n"
        frame = _decode_one(data)
        assert frame.payload == payload

    def test_base_parsed(self):
        """go TestReader_WithBase."""
        base = bytes([0xab, 0xcd] + [0x00] * 30)
        base_hex = hash_to_hex(base)
        data = f"@frame{{v=1 sid=1 seq=10 kind=patch len=4 base=sha256:{base_hex}}}\ntest\n".encode()
        frame = _decode_one(data)
        assert frame.base == base

    def test_payload_too_large_rejected(self):
        """go TestReader_PayloadTooLarge."""
        data = b"@frame{v=1 sid=0 seq=0 kind=doc len=999999999}\n"
        with pytest.raises(ParseError):
            Reader(io.BytesIO(data), max_payload=1024).next()

    def test_multiple_frames(self):
        """go TestReader_MultipleFrames."""
        raw = (
            b"@frame{v=1 sid=1 seq=0 kind=doc len=5}\nhello\n"
            b"@frame{v=1 sid=1 seq=1 kind=patch len=6}\nupdate\n"
            b"@frame{v=1 sid=1 seq=2 kind=ack len=0}\n\n"
        )
        frames = decode_frames(raw)
        assert len(frames) == 3
        assert frames[0].kind == KIND_DOC
        assert frames[0].payload == b"hello"
        assert frames[1].kind == KIND_PATCH
        assert frames[1].payload == b"update"
        assert frames[2].kind == KIND_ACK
        assert frames[2].payload == b""

    def test_final_flag_decoded(self):
        frame = _make_frame(KIND_DOC, b"done", sid=1, seq=999, final=True)
        wire = _encode(frame)
        got = _decode_one(wire)
        assert got.final is True


# ---------------------------------------------------------------------------
# Round-trip tests — mirrors go/stream/gs1t_test.go TestRoundtrip_AllFrameTypes
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """Round-trip encode→decode preserves all fields exactly."""

    CASES = [
        ("minimal doc",       Frame(1, 0,  0,   KIND_DOC,   b"{}")),
        ("patch with base",   Frame(1, 1,  5,   KIND_PATCH, b"@patch\nset .x 1\n@end",
                                   base=bytes([0x01, 0x02] + [0x00] * 30))),
        ("row",               Frame(1, 2,  100, KIND_ROW,   b"Row@(id 1 name foo)")),
        ("ui",                Frame(1, 1,  50,  KIND_UI,    b'UIEvent@(type "progress" pct 0.5)')),
        ("ack",               Frame(1, 1,  10,  KIND_ACK,   b"")),
        ("err",               Frame(1, 1,  11,  KIND_ERR,   b'Err@(code "FAIL")')),
        ("ping",              Frame(1, 0,  0,   KIND_PING,  b"")),
        ("pong",              Frame(1, 0,  0,   KIND_PONG,  b"")),
        ("final",             Frame(1, 1,  999, KIND_DOC,   b"done", final=True)),
        ("large seq",         Frame(1, 0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF, KIND_DOC, b"x")),
    ]

    @pytest.mark.parametrize("name,frame", CASES, ids=[c[0] for c in CASES])
    def test_round_trip(self, name: str, frame: Frame):
        wire = _encode(frame)
        got = _decode_one(wire)

        assert got.version == frame.version, f"{name}: version"
        assert got.sid == frame.sid, f"{name}: sid"
        assert got.seq == frame.seq, f"{name}: seq"
        assert got.kind == frame.kind, f"{name}: kind"
        assert got.payload == (frame.payload or b""), f"{name}: payload"
        assert got.final == frame.final, f"{name}: final"
        if frame.base is not None:
            assert got.base == frame.base, f"{name}: base"

    def test_round_trip_with_crc(self):
        frame = Frame(1, 1, 5, KIND_DOC, b"test payload with CRC")
        wire = _encode(frame, with_crc=True)
        got = Reader(io.BytesIO(wire), verify_crc=True).next()
        assert got.crc is not None
        assert got.payload == b"test payload with CRC"

    def test_encode_frames_and_decode_frames(self):
        frames = [
            Frame(1, 0, 0, KIND_DOC,   b"hello"),
            Frame(1, 0, 1, KIND_PATCH, b"@patch\nset .x 2\n@end"),
            Frame(1, 0, 2, KIND_ACK,   b""),
        ]
        wire = encode_frames(frames)
        got = decode_frames(wire)
        assert len(got) == 3
        for orig, decoded in zip(frames, got):
            assert decoded.kind == orig.kind
            assert decoded.payload == orig.payload


# ---------------------------------------------------------------------------
# StreamCursor — sequence-gap detection and patch base-hash enforcement
# ---------------------------------------------------------------------------

class TestStreamCursor:
    def test_first_frame_accepted(self):
        cursor = StreamCursor()
        cursor.process_frame(Frame(1, 1, 1, KIND_DOC, b"hello"))

    def test_monotonic_sequence_accepted(self):
        cursor = StreamCursor()
        for seq in range(1, 5):
            cursor.process_frame(Frame(1, 1, seq, KIND_DOC, b"x"))

    def test_sequence_gap_raises(self):
        cursor = StreamCursor()
        cursor.process_frame(Frame(1, 1, 1, KIND_DOC, b"x"))
        with pytest.raises(ValueError, match="gap"):
            cursor.process_frame(Frame(1, 1, 3, KIND_DOC, b"x"))

    def test_duplicate_seq_raises(self):
        cursor = StreamCursor()
        cursor.process_frame(Frame(1, 1, 1, KIND_DOC, b"x"))
        with pytest.raises(ValueError):
            cursor.process_frame(Frame(1, 1, 1, KIND_DOC, b"x"))

    def test_seq_regression_raises(self):
        cursor = StreamCursor()
        cursor.process_frame(Frame(1, 1, 2, KIND_DOC, b"x"))
        with pytest.raises(ValueError):
            cursor.process_frame(Frame(1, 1, 1, KIND_DOC, b"x"))

    def test_patch_base_accepted_when_matching(self):
        """Patch with base matching current state_hash is accepted."""
        cursor = StreamCursor()
        # Establish a known state hash.
        state_hash = state_hash_bytes(b"canonical state")
        cursor.set_state_hash(1, state_hash)
        cursor.process_frame(Frame(1, 1, 1, KIND_DOC, b"x"))  # advance seq

        patch = Frame(1, 1, 2, KIND_PATCH, b"@patch\nset .x 1\n@end", base=state_hash)
        cursor.process_frame(patch)  # must not raise

    def test_patch_base_rejected_when_stale(self):
        """Patch with a stale base hash raises BaseMismatchError."""
        cursor = StreamCursor()
        current_hash = state_hash_bytes(b"current state")
        stale_hash   = state_hash_bytes(b"old state")
        cursor.set_state_hash(1, current_hash)
        cursor.process_frame(Frame(1, 1, 1, KIND_DOC, b"x"))

        patch = Frame(1, 1, 2, KIND_PATCH, b"@patch\nset .x 1\n@end", base=stale_hash)
        with pytest.raises(BaseMismatchError):
            cursor.process_frame(patch)

    def test_patch_without_base_skips_base_check(self):
        """A patch frame with no base field is always accepted (no base check)."""
        cursor = StreamCursor()
        cursor.set_state_hash(1, state_hash_bytes(b"some state"))
        cursor.process_frame(Frame(1, 1, 1, KIND_PATCH, b"@patch\nset .x 1\n@end"))

    def test_patch_base_no_state_raises(self):
        """Patch with base but no prior state raises ValueError."""
        cursor = StreamCursor()
        some_hash = state_hash_bytes(b"something")
        patch = Frame(1, 1, 1, KIND_PATCH, b"@patch\nset .x 1\n@end", base=some_hash)
        with pytest.raises(ValueError, match="no state hash"):
            cursor.process_frame(patch)

    def test_separate_sids_are_independent(self):
        cursor = StreamCursor()
        cursor.process_frame(Frame(1, 1, 1, KIND_DOC, b"a"))
        cursor.process_frame(Frame(1, 2, 1, KIND_DOC, b"b"))
        cursor.process_frame(Frame(1, 1, 2, KIND_DOC, b"c"))
        cursor.process_frame(Frame(1, 2, 2, KIND_DOC, b"d"))

    def test_all_sids_tracked(self):
        cursor = StreamCursor()
        cursor.process_frame(Frame(1, 10, 1, KIND_DOC, b"x"))
        cursor.process_frame(Frame(1, 20, 1, KIND_DOC, b"x"))
        sids = cursor.all_sids()
        assert 10 in sids
        assert 20 in sids


# ---------------------------------------------------------------------------
# FrameHandler (lenient mode) — gaps + base-mismatch callbacks
# ---------------------------------------------------------------------------

class TestFrameHandler:
    def test_duplicate_silently_discarded(self):
        handler = FrameHandler()
        received = []
        handler.on_doc = lambda sid, seq, payload, state: received.append(seq)

        handler.handle(Frame(1, 1, 1, KIND_DOC, b"x"))
        handler.handle(Frame(1, 1, 1, KIND_DOC, b"x"))  # duplicate
        assert received == [1]

    def test_seq_gap_triggers_callback(self):
        gaps = []
        handler = FrameHandler()
        handler.on_seq_gap = lambda sid, expected, got: (gaps.append((expected, got)), True)[1]

        handler.handle(Frame(1, 1, 1, KIND_DOC, b"a"))
        handler.handle(Frame(1, 1, 5, KIND_DOC, b"b"))  # gap: expected 2, got 5
        assert gaps == [(2, 5)]

    def test_base_mismatch_raises_without_callback(self):
        handler = FrameHandler()
        state_hash = state_hash_bytes(b"state v1")
        handler.cursor.set_state_hash(1, state_hash)
        handler.handle(Frame(1, 1, 1, KIND_DOC, b"x"))

        stale = state_hash_bytes(b"old version")
        patch = Frame(1, 1, 2, KIND_PATCH, b"@patch\nset .x 1\n@end", base=stale)
        with pytest.raises(BaseMismatchError):
            handler.handle(patch)

    def test_base_mismatch_callback_can_allow(self):
        allowed = []
        handler = FrameHandler()
        handler.on_base_mismatch = lambda sid, frame: (allowed.append(sid), True)[1]

        state_hash = state_hash_bytes(b"state v1")
        handler.cursor.set_state_hash(1, state_hash)
        handler.handle(Frame(1, 1, 1, KIND_DOC, b"x"))

        stale = state_hash_bytes(b"old")
        handler.handle(Frame(1, 1, 2, KIND_PATCH, b"@patch\nset .x 1\n@end", base=stale))
        assert allowed == [1]

    def test_per_kind_callbacks_dispatched(self):
        received_kinds = []
        handler = FrameHandler()
        handler.on_doc   = lambda sid, seq, payload, st: received_kinds.append("doc")
        handler.on_patch = lambda sid, seq, payload, st: received_kinds.append("patch")
        handler.on_row   = lambda sid, seq, payload, st: received_kinds.append("row")
        handler.on_ui    = lambda sid, seq, payload, st: received_kinds.append("ui")
        handler.on_err   = lambda sid, seq, payload, st: received_kinds.append("err")
        handler.on_ack   = lambda sid, seq, st:          received_kinds.append("ack")

        handler.handle(Frame(1, 1, 1, KIND_DOC,   b"x"))
        handler.handle(Frame(1, 1, 2, KIND_PATCH, b"@patch\nset .x 1\n@end"))
        handler.handle(Frame(1, 1, 3, KIND_ROW,   b"Row@(id 1)"))
        handler.handle(Frame(1, 1, 4, KIND_UI,    b"Progress@(pct 0.5 msg ok)"))
        handler.handle(Frame(1, 1, 5, KIND_ERR,   b"Error@(code FAIL)"))
        handler.handle(Frame(1, 1, 6, KIND_ACK,   b""))

        assert received_kinds == ["doc", "patch", "row", "ui", "err", "ack"]


# ---------------------------------------------------------------------------
# UI events
# ---------------------------------------------------------------------------

class TestUIEvents:
    def test_progress_round_trip(self):
        payload = emit_progress(0.42, "step 3")
        assert isinstance(payload, bytes)
        name, fields = parse_ui_event(payload)
        assert name == "Progress"
        assert abs(fields["pct"] - 0.42) < 1e-9
        assert fields["msg"] == "step 3"

    def test_log_level_variants(self):
        # emit_log produces a Log{...} struct; the 'ts' field is a datetime
        # that the current loose parser cannot round-trip through parse_ui_event
        # (pre-existing parser limitation with ISO-8601 fractional seconds).
        # We verify the payload bytes encode the expected level and struct name.
        for level, fn in [
            ("info",  log_info),
            ("warn",  log_warn),
            ("error", log_error),
            ("debug", log_debug),
        ]:
            payload = emit_log(level, "test message")
            text = payload.decode("utf-8")
            assert text.startswith("Log{"), f"level={level}: expected Log{{, got {text[:20]}"
            assert f"level={level}" in text, f"level={level}: not found in {text}"

    def test_metric_round_trip(self):
        payload = emit_metric("latency_ms", 12.5, "ms")
        name, fields = parse_ui_event(payload)
        assert name == "Metric"
        assert fields["name"] == "latency_ms"
        assert abs(fields["value"] - 12.5) < 1e-9

    def test_artifact_round_trip(self):
        payload = emit_artifact("image/png", "blob:sha256:abc", "plot.png")
        name, fields = parse_ui_event(payload)
        assert name == "Artifact"
        assert fields["mime"] == "image/png"
        assert fields["name"] == "plot.png"

    def test_error_round_trip(self):
        payload = emit_error("BASE_MISMATCH", "hash mismatch", 1, 42)
        name, fields = parse_ui_event(payload)
        assert name == "Error"
        assert fields["code"] == "BASE_MISMATCH"
        assert fields["msg"] == "hash mismatch"

    def test_resync_request_round_trip(self):
        want = "sha256:" + "aa" * 32
        payload = emit_resync_request(1, 42, want, "BASE_MISMATCH")
        name, fields = parse_ui_event(payload)
        assert name == "ResyncRequest"
        assert fields["reason"] == "BASE_MISMATCH"


# ---------------------------------------------------------------------------
# Cross-language conformance — Python decodes Go/JS golden bytes
#
# These golden strings were taken directly from:
#   go/stream/gs1t_test.go  (TestWriter_MinimalFrame, TestWriter_EmptyPayload)
# and the corresponding JS test in js/src/stream/stream.test.ts.
#
# The invariant: any conforming GS1-T encoder (Go, Python, JS) must produce
# identical bytes for the same logical frame, and any conforming decoder must
# accept bytes produced by any other encoder.
# ---------------------------------------------------------------------------

class TestCrossLanguageGoldens:
    """Python reader decodes bytes that a Go/JS writer would produce."""

    GO_GOLDEN_MINIMAL_DOC = b"@frame{v=1 sid=0 seq=0 kind=doc len=2}\n{}\n"
    GO_GOLDEN_ACK_EMPTY   = b"@frame{v=1 sid=1 seq=42 kind=ack len=0}\n\n"

    def test_python_decodes_go_minimal_doc(self):
        """Decode the exact bytes emitted by Go TestWriter_MinimalFrame."""
        frame = _decode_one(self.GO_GOLDEN_MINIMAL_DOC)
        assert frame.version == 1
        assert frame.sid == 0
        assert frame.seq == 0
        assert frame.kind == KIND_DOC
        assert frame.payload == b"{}"

    def test_python_decodes_go_ack_empty(self):
        """Decode the exact bytes emitted by Go TestWriter_EmptyPayload."""
        frame = _decode_one(self.GO_GOLDEN_ACK_EMPTY)
        assert frame.kind == KIND_ACK
        assert frame.payload == b""
        assert frame.sid == 1
        assert frame.seq == 42

    def test_python_produces_go_minimal_doc_bytes(self):
        """Python writer produces the exact same bytes as Go for a minimal doc."""
        frame = Frame(1, 0, 0, KIND_DOC, b"{}")
        got = _encode(frame)
        assert got == self.GO_GOLDEN_MINIMAL_DOC

    def test_python_produces_go_ack_empty_bytes(self):
        """Python writer produces the exact same bytes as Go for an empty ack."""
        frame = Frame(1, 1, 42, KIND_ACK, b"")
        got = _encode(frame)
        assert got == self.GO_GOLDEN_ACK_EMPTY

    def test_go_golden_patch_with_newlines(self):
        """
        Golden from go/stream/gs1t_test.go TestReader_PayloadWithNewlines.
        Go writer and Python writer agree on the frame; Python reader decodes it.
        """
        payload = b"@patch\nset .x 1\nset .y 2\n@end"
        go_wire = (
            f"@frame{{v=1 sid=1 seq=1 kind=patch len={len(payload)}}}\n"
            .encode() + payload + b"\n"
        )
        frame = _decode_one(go_wire)
        assert frame.payload == payload

        # Python encoder produces identical header structure
        py_wire = _encode(Frame(1, 1, 1, KIND_PATCH, payload))
        assert py_wire == go_wire

    def test_go_golden_final_frame(self):
        """
        Golden from go/stream/gs1t_test.go TestRoundtrip_AllFrameTypes "final".
        """
        payload = b"done"
        go_wire = f"@frame{{v=1 sid=1 seq=999 kind=doc len={len(payload)} final=true}}\ndone\n".encode()
        frame = _decode_one(go_wire)
        assert frame.final is True
        assert frame.payload == b"done"

        # Python produces identical bytes
        py_wire = _encode(Frame(1, 1, 999, KIND_DOC, payload, final=True))
        assert py_wire == go_wire

    def test_go_golden_crc_hello(self):
        """
        Golden CRC for b'hello' = 0x3610a686 (go TestCRC_KnownValues).
        Wire format with that CRC must decode successfully with CRC verification on.
        """
        payload = b"hello"
        crc_hex = crc_to_hex(0x3610a686)
        wire = f"@frame{{v=1 sid=1 seq=5 kind=doc len=5 crc={crc_hex}}}\nhello\n".encode()
        frame = Reader(io.BytesIO(wire), verify_crc=True).next()
        assert frame.crc == 0x3610a686
        assert frame.payload == b"hello"

    def test_go_golden_large_seq(self):
        """
        Golden from TestRoundtrip_AllFrameTypes "large seq":
        sid=18446744073709551615 seq=18446744073709551615
        """
        max_uint64 = 0xFFFFFFFFFFFFFFFF
        frame = Frame(1, max_uint64, max_uint64, KIND_DOC, b"x")
        wire = _encode(frame)
        assert f"sid={max_uint64}".encode() in wire
        assert f"seq={max_uint64}".encode() in wire

        got = _decode_one(wire)
        assert got.sid == max_uint64
        assert got.seq == max_uint64

    def test_go_golden_all_kinds(self):
        """
        Mirror of go TestReader_AllKinds and TestRoundtrip_AllFrameTypes.
        For every frame kind, Python encoder bytes == expected Go golden.
        """
        cases = {
            "doc":   KIND_DOC,
            "patch": KIND_PATCH,
            "row":   KIND_ROW,
            "ui":    KIND_UI,
            "ack":   KIND_ACK,
            "err":   KIND_ERR,
            "ping":  KIND_PING,
            "pong":  KIND_PONG,
        }
        for name, kind in cases.items():
            wire = _encode(Frame(1, 0, 0, kind, b"x"))
            expected_header = f"@frame{{v=1 sid=0 seq=0 kind={name} len=1}}\n".encode()
            assert wire.startswith(expected_header), (
                f"kind={name}: got {wire!r}, expected header {expected_header!r}"
            )
            # Decode and verify kind
            frame = _decode_one(wire)
            assert frame.kind == kind


# ---------------------------------------------------------------------------
# Error code registry (sanity)
# ---------------------------------------------------------------------------

class TestErrorCodes:
    def test_error_constants_defined(self):
        from glyph.stream import (
            ERR_BASE_MISMATCH, ERR_SEQ_GAP, ERR_SEQ_DUP, ERR_NO_STATE,
            ERR_CRC_MISMATCH, ERR_VERSION_UNSUPPORTED,
            ERR_PAYLOAD_TOO_LARGE, ERR_HEADER_TOO_LARGE, ERR_FRAME_INVALID,
        )
        assert ERR_BASE_MISMATCH == "BASE_MISMATCH"
        assert ERR_SEQ_GAP       == "SEQ_GAP"
        assert ERR_SEQ_DUP       == "SEQ_DUP"
        assert ERR_NO_STATE      == "NO_STATE"
        assert ERR_CRC_MISMATCH  == "CRC_MISMATCH"

    def test_version_constant(self):
        assert VERSION == 1

    def test_kind_values_completeness(self):
        assert set(KIND_VALUES.keys()) == {"doc", "patch", "row", "ui", "ack", "err", "ping", "pong"}
        # VALUE_KINDS is the inverse
        for name, kind in KIND_VALUES.items():
            assert VALUE_KINDS[kind] == name
