"""SPEC-CANON.md conformance: the one digest must be byte-identical across
Python, Go and JS, so every rule here is a cross-language agreement rule."""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from glyph import (
    CanonError,
    GValue,
    MapEntry,
    RefID,
    canon_json,
    compute_base_fingerprint,
    fingerprint,
    from_json_loose,
    is_canonical,
    tensor_ref,
)
from glyph.stream import state_hash_loose


def M(**kw):
    return GValue.map_(*[MapEntry(k, v) for k, v in kw.items()])


def test_scalars_and_containers():
    v = M(
        b=GValue.list_(
            GValue.int_(1), GValue.float_(2.5), GValue.null(), GValue.bool_(True)
        ),
        a=GValue.str_('q"\\\n\t\x01é😀'),
    )
    assert canon_json(v) == '{"a":"q\\"\\\\\\n\\t\\u0001é😀","b":[1,2.5,null,true]}'


def test_number_collapse_matches_json_domain():
    # JSON readers cannot tell 1 from 1.0, so identity must not either.
    assert canon_json(GValue.float_(1.0)) == "1"
    assert canon_json(GValue.float_(-0.0)) == "0"
    assert canon_json(GValue.int_(0)) == "0"
    assert canon_json(GValue.float_(1e300)) == "1e+300"
    assert canon_json(GValue.float_(2.0**53)) == "9.007199254740992e+15"
    assert canon_json(GValue.float_(1e-7)) == "1e-07"
    assert canon_json(GValue.int_(2**53 - 1)) == "9007199254740991"


def test_int_beyond_safe_range_is_an_error_not_a_lie():
    # JS cannot hold it; collapsing silently would let two languages disagree.
    with pytest.raises(CanonError):
        canon_json(GValue.int_(2**53))
    with pytest.raises(CanonError):
        canon_json(GValue.float_(float("nan")))


def test_keys_sort_by_code_point_not_utf16():
    v = M(**{"": GValue.int_(1), "😀": GValue.int_(2)})
    assert canon_json(v) == '{"":1,"😀":2}'
    with pytest.raises(CanonError):
        canon_json(
            GValue.map_(MapEntry("k", GValue.int_(1)), MapEntry("k", GValue.int_(2)))
        )


def test_non_json_scalars_use_reserved_keys():
    assert canon_json(GValue.bytes_(b"\x00\xff")) == '{"$bytes":"AP8="}'
    t = datetime(2025, 1, 13, 12, 34, 56, 500000, tzinfo=timezone.utc)
    assert canon_json(GValue.time(t)) == '{"$time":"2025-01-13T12:34:56.5Z"}'
    assert canon_json(GValue.id_from_ref(RefID("m", "1"))) == '{"$id":["m","1"]}'
    st = GValue.struct(
        "Team", MapEntry("z", GValue.int_(1)), MapEntry("a", GValue.int_(2))
    )
    assert canon_json(st) == '{"a":2,"z":1}'
    assert canon_json(GValue.sum("Ok", GValue.int_(1))) == '{"Ok":1}'
    assert canon_json(GValue.sum("None", None)) == '{"None":null}'


def test_depth_limit():
    sys.setrecursionlimit(20000)
    v = GValue.list_()
    for _ in range(999):
        v = GValue.list_(v)
    canon_json(v)  # depth 1000 ok
    with pytest.raises(CanonError):
        canon_json(GValue.list_(v))  # 1001


def test_one_digest_everywhere():
    v = from_json_loose({"b": [1, 2.0, None], "a": "x"})
    fp = fingerprint(v)
    assert fp == hashlib.sha256(canon_json(v).encode()).hexdigest()
    assert compute_base_fingerprint(v) == fp
    assert state_hash_loose(v).hex() == fp


def test_is_canonical_strict_check():
    assert is_canonical(b'{"a":1,"b":[true,null]}')
    assert not is_canonical(b'{"b":[true,null],"a":1}')  # order
    assert not is_canonical(b'{"a": 1}')  # whitespace
    assert not is_canonical(b'{"a":1.0}')  # number form
    assert not is_canonical(b'{"a":1,"a":2}')  # duplicate key
    assert not is_canonical(b"nope")


# SPEC-CANON.md §4: a tensor is identified by sha256 of its raw element bytes.
# The fixtures are cowrie's 8 tensor cases with the bytes lifted from its golden
# encodings, so glyph and cowrie name the same tensor by the same hash.
TENSOR_FIXTURES = Path(__file__).resolve().parents[2] / "harness/state_identity/data/tensor_refs.jsonl"


def test_tensor_ref_matches_cowrie_bytes():
    rows = [json.loads(l) for l in TENSOR_FIXTURES.read_text().splitlines() if l.strip()]
    assert len(rows) == 8
    for fx in rows:
        for t in fx["tensors"]:
            ref = tensor_ref(t["dtype"], t["shape"], bytes.fromhex(t["data_hex"]))
            want = {"$tensor": {k: t[k] for k in ("dtype", "shape", "sha256")}}
            assert canon_json(ref) == json.dumps(want, separators=(",", ":"), sort_keys=True)
        v = from_json_loose(json.loads(fx["json"]))
        assert canon_json(v) == fx["json"]
        assert fingerprint(v) == fx["fingerprint"]


def test_tensor_ref_rejects_wrong_packed_size():
    tensor_ref("qint4", [3], b"\x21\x03")  # 12 bits -> 2 bytes
    with pytest.raises(ValueError):
        tensor_ref("qint4", [3], b"\x21\x03\x00")
    with pytest.raises(ValueError):
        tensor_ref("float32", [2], b"\x00" * 7)
    with pytest.raises(ValueError):
        tensor_ref("f32", [2], b"\x00" * 8)  # cowrie names only, no aliases


def test_bridge_rejects_malformed_tensor_ref():
    # An uppercase or short sha256 would fingerprint differently from the same
    # tensor written correctly: the bridge refuses to mint that second identity.
    ok = {"dtype": "float32", "shape": [1], "sha256": "0" * 64}
    from_json_loose({"$tensor": ok})
    for bad in (
        {**ok, "sha256": "A" * 64},
        {**ok, "sha256": "0" * 63},
        {**ok, "shape": [-1]},
        {**ok, "shape": [True]},
        {**ok, "dtype": "f32"},
        {"dtype": "float32", "shape": [1]},
        {**ok, "extra": 1},
        "x",
    ):
        with pytest.raises(ValueError):
            from_json_loose({"$tensor": bad})
