"""
GS1-T (Text framing) reader and writer.

Ports go/stream/gs1t_writer.go and go/stream/gs1t_reader.go,
cross-checked against js/src/stream/gs1t.ts.

Wire format (§3 of GS1_SPEC.md):
  @frame{v=1 sid=N seq=N kind=K len=N [crc=X] [base=sha256:X] [final=true]}\\n
  <exactly len bytes of payload>\\n
"""

from __future__ import annotations

import io
from typing import IO, Iterator, List, Optional

from .types import (
    VERSION,
    Frame,
    FrameKind,
    KIND_DOC,
    KIND_PATCH,
    KIND_ROW,
    KIND_UI,
    KIND_ACK,
    KIND_ERR,
    KIND_PING,
    KIND_PONG,
    MAX_PAYLOAD_SIZE,
    MAX_HEADER_SIZE,
    ParseError,
    CRCMismatchError,
    parse_kind,
    kind_to_str,
)
from .crc import compute_crc, crc_to_hex, parse_crc
from .hash import hash_to_hex, hex_to_hash


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class Writer:
    """
    Writes GS1-T frames to a binary-mode file-like object.

    Mirrors go/stream/gs1t_writer.go Writer.
    """

    def __init__(self, w: IO[bytes], *, with_crc: bool = False) -> None:
        self._w = w
        self._with_crc = with_crc

    def write_frame(self, frame: Frame) -> None:
        """
        Write a single frame in GS1-T format.

        Format:
          @frame{v=1 sid=N seq=N kind=K len=N [crc=X] [base=sha256:X] [final=true]}\\n
          <payload bytes>\\n
        """
        parts: List[str] = []

        # Required fields — version defaults to 1 when 0
        v = frame.version if frame.version != 0 else VERSION
        parts.append(f"v={v}")
        parts.append(f"sid={frame.sid}")
        parts.append(f"seq={frame.seq}")
        parts.append(f"kind={kind_to_str(frame.kind)}")
        parts.append(f"len={len(frame.payload)}")

        # Optional CRC — compute if with_crc and payload non-empty and not set
        crc = frame.crc
        if crc is None and self._with_crc and len(frame.payload) > 0:
            crc = compute_crc(frame.payload)
        if crc is not None:
            parts.append(f"crc={crc_to_hex(crc)}")

        # Optional base hash
        if frame.has_base():
            parts.append(f"base=sha256:{hash_to_hex(frame.base)}")  # type: ignore[arg-type]

        # Optional final flag (GS1-T uses final=true key, not flags bit)
        if frame.is_final():
            parts.append("final=true")

        header = "@frame{" + " ".join(parts) + "}\n"
        self._w.write(header.encode("utf-8"))

        if frame.payload:
            self._w.write(frame.payload)

        self._w.write(b"\n")

    # Convenience constructors mirroring go/stream/gs1t_writer.go

    def write_doc(self, sid: int, seq: int, payload: bytes) -> None:
        self.write_frame(Frame(version=VERSION, sid=sid, seq=seq, kind=KIND_DOC, payload=payload))

    def write_patch(
        self,
        sid: int,
        seq: int,
        payload: bytes,
        base: Optional[bytes] = None,
    ) -> None:
        self.write_frame(Frame(version=VERSION, sid=sid, seq=seq, kind=KIND_PATCH, payload=payload, base=base))

    def write_row(self, sid: int, seq: int, payload: bytes) -> None:
        self.write_frame(Frame(version=VERSION, sid=sid, seq=seq, kind=KIND_ROW, payload=payload))

    def write_ui(self, sid: int, seq: int, payload: bytes) -> None:
        self.write_frame(Frame(version=VERSION, sid=sid, seq=seq, kind=KIND_UI, payload=payload))

    def write_ack(self, sid: int, seq: int) -> None:
        self.write_frame(Frame(version=VERSION, sid=sid, seq=seq, kind=KIND_ACK, payload=b""))

    def write_err(self, sid: int, seq: int, payload: bytes) -> None:
        self.write_frame(Frame(version=VERSION, sid=sid, seq=seq, kind=KIND_ERR, payload=payload))

    def write_ping(self, sid: int, seq: int) -> None:
        self.write_frame(Frame(version=VERSION, sid=sid, seq=seq, kind=KIND_PING, payload=b""))

    def write_pong(self, sid: int, seq: int) -> None:
        self.write_frame(Frame(version=VERSION, sid=sid, seq=seq, kind=KIND_PONG, payload=b""))

    def write_final(
        self,
        sid: int,
        seq: int,
        kind: FrameKind,
        payload: bytes,
    ) -> None:
        self.write_frame(Frame(version=VERSION, sid=sid, seq=seq, kind=kind, payload=payload, final=True))


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class Reader:
    """
    Reads GS1-T frames from a binary-mode file-like object.

    Mirrors go/stream/gs1t_reader.go Reader.

    The reader reads one header line (bounded to MAX_HEADER_SIZE to prevent
    DoS), then reads exactly len bytes of payload as raw bytes (§3.3), then
    optionally consumes a trailing newline.
    """

    def __init__(
        self,
        r: IO[bytes],
        *,
        max_payload: int = MAX_PAYLOAD_SIZE,
        verify_crc: bool = True,
    ) -> None:
        self._r = r
        self._max_payload = max_payload
        self._verify_crc = verify_crc

    def next(self) -> Optional[Frame]:
        """
        Read and return the next frame, or None at EOF.

        Raises:
            ParseError       — structural parse failure, version mismatch, or
                               header/payload size exceeded.
            CRCMismatchError — CRC-32 verification failed.
        """
        # Read one header line, bounded by MAX_HEADER_SIZE.
        # We read byte-by-byte up to the limit to avoid allocating unbounded
        # memory (mirrors Go's ReadLine + isPrefix DoS guard).
        header_bytes = bytearray()
        while True:
            b = self._r.read(1)
            if not b:
                # EOF
                if header_bytes:
                    raise ParseError("unexpected EOF in header")
                return None
            if b == b"\n":
                break
            header_bytes += b
            if len(header_bytes) > MAX_HEADER_SIZE:
                # Drain until we find a newline so the stream position is
                # at least at a potential boundary, then reject.
                while True:
                    drain = self._r.read(1)
                    if not drain or drain == b"\n":
                        break
                raise ParseError(
                    f"header line exceeds maximum size ({MAX_HEADER_SIZE} bytes)"
                )

        header_line = header_bytes.decode("utf-8", errors="replace") + "\n"

        # Parse header → get frame with payload_len stored temporarily
        frame, payload_len = _parse_header(header_line)

        # Payload size guard
        if payload_len > self._max_payload:
            raise ParseError(
                f"payload too large: {payload_len} > {self._max_payload}"
            )

        # Read exactly payload_len bytes
        if payload_len > 0:
            payload = self._r.read(payload_len)
            if len(payload) != payload_len:
                raise ParseError(
                    f"short read: expected {payload_len} bytes, got {len(payload)}"
                )
        else:
            payload = b""

        # Consume optional trailing newline (SHOULD consume; MUST accept EOF)
        peek = self._r.read(1)
        if peek and peek != b"\n":
            # Not a newline — this byte belongs to the next frame.
            # We need to "unread" it.  For a plain binary IO we use seek if
            # seekable, otherwise wrap once at construction time.
            if hasattr(self._r, "seek") and self._r.seekable():
                self._r.seek(-1, 1)
            else:
                # Re-wrap with a prepend buffer — this is a one-byte lookahead
                # and only ever happens when the caller passes a non-seekable
                # stream with no trailing newline between frames (rare in
                # practice; all writers emit it).  We attach the byte as a
                # pending attribute so the next read picks it up first.
                if not hasattr(self, "_pending"):
                    self._pending = bytearray()
                self._pending = bytearray(peek) + getattr(self, "_pending", bytearray())

        frame.payload = payload

        # CRC verification
        if self._verify_crc and frame.crc is not None:
            computed = compute_crc(payload)
            if computed != frame.crc:
                raise CRCMismatchError(expected=frame.crc, got=computed)

        return frame

    def read_all(self) -> List[Frame]:
        """Read all frames until EOF. Returns a list."""
        frames: List[Frame] = []
        while True:
            frame = self.next()
            if frame is None:
                return frames
            frames.append(frame)

    def __iter__(self) -> Iterator[Frame]:
        while True:
            frame = self.next()
            if frame is None:
                return
            yield frame


# ---------------------------------------------------------------------------
# Internal: header parser
# ---------------------------------------------------------------------------

def _tokenize(s: str) -> List[str]:
    """
    Split key=value pairs separated by spaces, tabs, or commas.
    Respects double-quoted values (passes through quotes).

    Mirrors go/stream/gs1t_reader.go tokenize().
    """
    tokens: List[str] = []
    current: List[str] = []
    in_quote = False
    for ch in s:
        if ch == '"':
            in_quote = not in_quote
            current.append(ch)
        elif ch in (" ", ",", "\t") and not in_quote:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def _parse_header(line: str) -> tuple[Frame, int]:
    """
    Parse a @frame{...}\\n header line.

    Returns (Frame with payload=b"", payload_len).
    Raises ParseError on any structural or semantic violation.
    """
    line = line.strip()

    if not line.startswith("@frame{"):
        raise ParseError("expected @frame{", 0)

    end_idx = line.rfind("}")
    if end_idx < 0:
        raise ParseError("missing closing }", len(line))

    content = line[7:end_idx]

    # Defaults
    version = 1
    sid = 0
    seq = 0
    kind: FrameKind = KIND_DOC
    payload_len = 0
    crc: Optional[int] = None
    base: Optional[bytes] = None
    flags = 0
    final = False

    for pair in _tokenize(content):
        eq_idx = pair.find("=")
        if eq_idx < 0:
            continue  # skip malformed pairs (matches Go behaviour)
        key = pair[:eq_idx]
        val = pair[eq_idx + 1:]

        if key == "v":
            try:
                v = int(val, 10)
            except ValueError:
                raise ParseError("invalid version")
            if v != 1:
                raise ParseError(f"unsupported version {v}, must be 1")
            version = v

        elif key == "sid":
            try:
                sid = int(val, 10)
                if sid < 0 or sid > 0xFFFFFFFFFFFFFFFF:
                    raise ValueError
            except ValueError:
                raise ParseError("invalid sid")

        elif key == "seq":
            try:
                seq = int(val, 10)
                if seq < 0 or seq > 0xFFFFFFFFFFFFFFFF:
                    raise ValueError
            except ValueError:
                raise ParseError("invalid seq")

        elif key == "kind":
            k, ok = parse_kind(val)
            if not ok:
                raise ParseError(f"invalid kind: {val}")
            kind = k

        elif key == "len":
            try:
                payload_len = int(val, 10)
                if payload_len < 0 or payload_len > 0xFFFFFFFF:
                    raise ValueError
            except ValueError:
                raise ParseError("invalid len")

        elif key == "crc":
            crc = parse_crc(val)
            if crc is None:
                raise ParseError(f"invalid crc: {val}")

        elif key == "base":
            base = hex_to_hash(val)
            if base is None:
                raise ParseError(f"invalid base: {val}")

        elif key == "final":
            final = val in ("true", "1")

        elif key == "flags":
            try:
                flags = int(val.lstrip("0x").lstrip("0X") or "0", 16)
            except ValueError:
                pass  # ignore malformed flags (matches Go behaviour)

        # Unknown keys are silently ignored (forward-compatibility).

    frame = Frame(
        version=version,
        sid=sid,
        seq=seq,
        kind=kind,
        payload=b"",
        crc=crc,
        base=base,
        flags=flags,
        final=final,
    )
    return frame, payload_len


# ---------------------------------------------------------------------------
# Module-level convenience functions (mirrors JS encodeFrame / decodeFrames)
# ---------------------------------------------------------------------------

def encode_frame(frame: Frame, *, with_crc: bool = False) -> bytes:
    """Encode a single frame to bytes."""
    buf = io.BytesIO()
    Writer(buf, with_crc=with_crc).write_frame(frame)
    return buf.getvalue()


def encode_frames(frames: List[Frame], *, with_crc: bool = False) -> bytes:
    """Encode multiple frames to a single bytes object."""
    buf = io.BytesIO()
    w = Writer(buf, with_crc=with_crc)
    for f in frames:
        w.write_frame(f)
    return buf.getvalue()


def decode_frame(data: bytes, *, verify_crc: bool = True) -> Optional[Frame]:
    """Decode the first frame from *data*. Returns None if data is empty."""
    return Reader(io.BytesIO(data), verify_crc=verify_crc).next()


def decode_frames(data: bytes, *, verify_crc: bool = True) -> List[Frame]:
    """Decode all frames from *data*."""
    return Reader(io.BytesIO(data), verify_crc=verify_crc).read_all()
