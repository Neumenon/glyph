"""Canonical JSON profile ``glyph-canon-json-1.1.0`` (see ``SPEC-CANON.md``).

The only byte form GLYPH hashes. ``fingerprint``, the patch ``base`` and the GS1
state hash are all ``sha256(canon_json(v))``. GLYPH text is a renderer and is
never hashed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from typing import List, Sequence

from .loose import (
    MAX_SAFE_INT,
    TENSOR_DTYPE_BITS,
    canon_float,
    canon_time,
    from_json_loose,
)
from .types import GType, GValue, MapEntry

MAX_DEPTH = 1000


class CanonError(ValueError):
    """Value cannot be canonicalized: int outside ±(2^53-1), non-finite float,
    duplicate object key, or nesting deeper than MAX_DEPTH."""


def canon_json(v: GValue) -> str:
    """Canonical JSON text of *v* (SPEC-CANON.md §1-§3)."""
    return _canon(v, 0)


def fingerprint(v: GValue) -> str:
    """The one digest: 64 lowercase hex of sha256(canon_json(v)) (SPEC-CANON.md §5)."""
    return hashlib.sha256(canon_json(v).encode("utf-8")).hexdigest()


def is_canonical(b: bytes) -> bool:
    """True iff *b* is exactly the canonical JSON of the value it encodes.

    Receivers at trust boundaries (patch ingest, GS1 state frames) reject bytes
    that fail this: "exactly one valid encoding" with a stdlib parser.
    """
    if isinstance(b, str):
        b = b.encode("utf-8")
    try:
        return (
            canon_json(from_json_loose(json.loads(b.decode("utf-8")))).encode("utf-8")
            == b
        )
    except (ValueError, OverflowError, RecursionError):
        # JSONDecodeError, UnicodeDecodeError, CanonError, bridge limits,
        # float() overflow on huge ints, and RecursionError on nesting past
        # the interpreter/bridge depth guards — all mean "not canonical".
        return False


def tensor_ref(dtype: str, shape: Sequence[int], data: bytes) -> GValue:
    """``{"$tensor":{dtype,shape,sha256}}`` for raw element bytes (SPEC-CANON.md §4).

    Only sha256(data) enters the value. Raises ValueError for an unknown dtype,
    a shape that is not non-negative ints, or data that is not the packed size
    dtype and shape imply (little-endian, row-major, sub-byte dtypes LSB-first).
    """
    bits = TENSOR_DTYPE_BITS.get(dtype)
    if bits is None:
        raise ValueError(f"unknown tensor dtype {dtype!r}")
    n = 1
    for d in shape:
        # Shape dims are strict ints: floats (even integral ones) and bools
        # are rejected, matching the $tensor bridge (_is_dim in loose.py).
        if isinstance(d, bool) or not isinstance(d, int):
            raise ValueError(f"tensor shape dim must be an int, got {d!r}")
        if d < 0:
            raise ValueError(f"tensor shape has negative dim {d}")
        n *= d
    want = (n * bits + 7) // 8
    if len(data) != want:
        raise ValueError(
            f"tensor data is {len(data)} bytes; dtype {dtype} shape {list(shape)} packs to {want}"
        )
    # Sub-byte dtypes pack LSB-first, so the unused high bits of the last
    # byte are padding and must be zero — otherwise two byte strings would
    # name different tensors with the same element sequence.
    if data and (n * bits) % 8:
        if data[-1] >> ((n * bits) % 8):
            raise ValueError(
                f"tensor data has non-zero padding bits for dtype {dtype} shape {list(shape)}"
            )
    return from_json_loose(
        {"$tensor": {"dtype": dtype, "shape": list(shape), "sha256": hashlib.sha256(data).hexdigest()}}
    )


def _quote(s: str) -> str:
    # RFC 8785 §3.2.2.2 escaping == json.dumps(ensure_ascii=False).
    return json.dumps(s, ensure_ascii=False)


def _canon(v: GValue, depth: int) -> str:
    t = v.type
    if t == GType.NULL:
        return "null"
    if t == GType.BOOL:
        return "true" if v.as_bool() else "false"
    if t == GType.INT:
        n = v.as_int()
        if not -MAX_SAFE_INT <= n <= MAX_SAFE_INT:
            raise CanonError(f"integer outside ±(2^53-1): {n}")
        return str(n)
    if t == GType.FLOAT:
        f = v.as_float()
        if not math.isfinite(f):
            raise CanonError("non-finite float")
        if f.is_integer() and abs(f) <= MAX_SAFE_INT:
            return str(int(f))
        return canon_float(f)
    if t == GType.STR:
        return _quote(v.as_str())
    if t == GType.BYTES:
        return (
            '{"$bytes":' + _quote(base64.b64encode(v.as_bytes()).decode("ascii")) + "}"
        )
    if t == GType.TIME:
        return '{"$time":"' + canon_time(v.as_time()) + '"}'
    if t == GType.ID:
        r = v.as_id()
        return '{"$id":[' + _quote(r.prefix) + "," + _quote(r.value) + "]}"
    if t == GType.LIST:
        _check_depth(depth)
        return "[" + ",".join(_canon(x, depth + 1) for x in v.as_list()) + "]"
    if t == GType.MAP:
        return _object(v.as_map(), depth)
    if t == GType.STRUCT:
        return _object(v.as_struct().fields, depth)
    if t == GType.SUM:
        _check_depth(depth)
        s = v.as_sum()
        inner = "null" if s.value is None else _canon(s.value, depth + 1)
        return "{" + _quote(s.tag) + ":" + inner + "}"
    raise CanonError(f"unsupported type {t}")


def _object(entries: List[MapEntry], depth: int) -> str:
    _check_depth(depth)
    # str order == code point order == UTF-8 byte order.
    entries = sorted(entries, key=lambda e: e.key)
    for a, b in zip(entries, entries[1:]):
        if a.key == b.key:
            raise CanonError(f"duplicate key {a.key!r}")
    return (
        "{"
        + ",".join(_quote(e.key) + ":" + _canon(e.value, depth + 1) for e in entries)
        + "}"
    )


def _check_depth(depth: int) -> None:
    if depth >= MAX_DEPTH:
        raise CanonError(f"nesting depth exceeds {MAX_DEPTH}")
