"""
GLYPH Blob References

Content-addressed blob references with canonical `@blob cid=... mime=... bytes=N`
wire format. Matches the Go `glyph.BlobRef` semantics (see BLOB_POOL_SPEC.md).
"""

from __future__ import annotations

import hashlib
import threading
from typing import Dict, Optional

from .types import BlobRef, GValue
from .loose import canon_string, is_bare_safe


def compute_cid(content: bytes) -> str:
    """Compute SHA-256 CID for content."""
    return "sha256:" + hashlib.sha256(content).hexdigest()


def blob_from_content(
    content: bytes,
    mime: str,
    name: str = "",
    caption: str = "",
) -> GValue:
    """Create a Blob GValue from raw content, computing the CID."""
    return GValue.blob(BlobRef(
        cid=compute_cid(content),
        mime=mime,
        bytes=len(content),
        name=name,
        caption=caption,
    ))


def emit_blob(ref: BlobRef) -> str:
    """Emit canonical blob wire format. cid/mime are emitted raw; optional
    string fields go through canon_string (quoted when unsafe)."""
    parts = [
        "@blob",
        f"cid={ref.cid}",
        f"mime={ref.mime}",
        f"bytes={ref.bytes}",
    ]
    if ref.name:
        parts.append(f"name={canon_string(ref.name)}")
    if ref.caption:
        parts.append(f"caption={canon_string(ref.caption)}")
    if ref.preview:
        parts.append(f"preview={canon_string(ref.preview)}")
    return " ".join(parts)


class ParseBlobError(ValueError):
    """Raised when @blob wire format fails to parse."""


def parse_blob_ref(input: str) -> BlobRef:
    """Parse canonical blob format back into a BlobRef."""
    s = input.strip()
    if not s.startswith("@blob"):
        raise ParseBlobError("blob ref must start with @blob")
    s = s[len("@blob"):].lstrip()

    fields: Dict[str, str] = {}
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break

        eq = s.find("=", i)
        if eq < 0:
            raise ParseBlobError(f"missing = in blob field at pos {i}")
        key = s[i:eq]
        i = eq + 1

        if i < n and s[i] == '"':
            i += 1
            buf = []
            while i < n and s[i] != '"':
                if s[i] == "\\" and i + 1 < n:
                    nxt = s[i + 1]
                    if nxt == "n":
                        buf.append("\n")
                    elif nxt == "r":
                        buf.append("\r")
                    elif nxt == "t":
                        buf.append("\t")
                    elif nxt == "\\":
                        buf.append("\\")
                    elif nxt == '"':
                        buf.append('"')
                    else:
                        buf.append(nxt)
                    i += 2
                else:
                    buf.append(s[i])
                    i += 1
            if i >= n:
                raise ParseBlobError(f"unterminated quote for field {key}")
            i += 1
            fields[key] = "".join(buf)
        else:
            start = i
            while i < n and not s[i].isspace():
                i += 1
            fields[key] = s[start:i]

    if "cid" not in fields:
        raise ParseBlobError("blob ref missing required field: cid")
    if "mime" not in fields:
        raise ParseBlobError("blob ref missing required field: mime")
    if "bytes" not in fields:
        raise ParseBlobError("blob ref missing required field: bytes")

    try:
        bytes_val = int(fields["bytes"])
    except ValueError as e:
        raise ParseBlobError(f"invalid bytes field: {fields['bytes']}") from e

    return BlobRef(
        cid=fields["cid"],
        mime=fields["mime"],
        bytes=bytes_val,
        name=fields.get("name", ""),
        caption=fields.get("caption", ""),
        preview=fields.get("preview", ""),
    )


class MemoryBlobRegistry:
    """Thread-safe in-memory CID → content map for tests."""

    def __init__(self) -> None:
        self._store: Dict[str, bytes] = {}
        self._lock = threading.RLock()

    def put(self, cid: str, content: bytes) -> None:
        with self._lock:
            self._store[cid] = content

    def get(self, cid: str) -> Optional[bytes]:
        with self._lock:
            return self._store.get(cid)

    def has(self, cid: str) -> bool:
        with self._lock:
            return cid in self._store
