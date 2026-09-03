"""Edge-case properties for the deep-review Python fixes.

Deterministic plain-pytest checks (no hypothesis): time is pinned to
milliseconds, huge ints fail closed, sub-byte tensor padding must be zero,
fractional deltas on int fields raise, and patch targets keep their
``prefix:value`` shape.
"""

import json
from datetime import datetime, timezone

import pytest

from glyph import (
    GValue,
    MapEntry,
    apply_patch,
    canon_json,
    from_json_loose,
    is_canonical,
    parse_patch,
    tensor_ref,
)
from glyph.loose import canon_time


def _wire(*ops, **hdr):
    doc = {"glyph_patch": 1, "ops": [dict(op=o, path=p, **({"value": v[0]} if v else {}))
                                     for o, p, *v in ops]}
    doc.update({k: v for k, v in hdr.items() if v})
    return json.dumps(doc)


class TestMsTruncation:
    def test_micro_truncates_not_rounds(self):
        # 123456us -> 123ms (would round to 124ms if rounded).
        dt = datetime(2025, 1, 13, 12, 34, 56, 123456, tzinfo=timezone.utc)
        assert canon_time(dt) == "2025-01-13T12:34:56.123Z"

    def test_sub_ms_dropped(self):
        # 999us is less than 1ms -> no fractional part at all.
        dt = datetime(2025, 1, 13, 12, 34, 56, 999, tzinfo=timezone.utc)
        assert canon_time(dt) == "2025-01-13T12:34:56Z"

    def test_trailing_zeros_trimmed(self):
        dt = datetime(2025, 1, 13, 12, 34, 56, 120000, tzinfo=timezone.utc)
        assert canon_time(dt) == "2025-01-13T12:34:56.12Z"

    def test_canon_json_time_uses_ms(self):
        t = datetime(2025, 1, 13, 12, 34, 56, 500999, tzinfo=timezone.utc)
        assert canon_json(GValue.time(t)) == '{"$time":"2025-01-13T12:34:56.5Z"}'


class TestHugeIntFailsClosed:
    def test_from_json_loose_raises_value_error_not_overflow(self):
        with pytest.raises(ValueError):
            from_json_loose(10**10000)
        with pytest.raises(ValueError):
            from_json_loose(-(10**10000))

    def test_is_canonical_returns_false_never_raises(self):
        # A JSON int far beyond float64 range is not canonical — and must
        # report False, not leak OverflowError/RecursionError. (4001 digits:
        # ~13k bits, past the float64 guard but under the interpreter's
        # int<->str digit limit so the bytes actually reach the codec.)
        assert is_canonical(b'{"n":' + str(10**4000).encode() + b'}') is False

    def test_boundary_int_still_collapses_to_float(self):
        # Just outside the safe window but float64-representable: unchanged.
        v = from_json_loose(2**53)
        assert v.type.name == "FLOAT"


class TestTensorPadding:
    def test_nonzero_padding_bits_rejected(self):
        # binary[3]: 3 bits used, high 5 bits of the byte are padding.
        with pytest.raises(ValueError, match="padding"):
            tensor_ref("binary", [3], b"\xff")
        with pytest.raises(ValueError, match="padding"):
            tensor_ref("qint2", [1], b"\xfc")

    def test_zero_padding_accepted(self):
        tensor_ref("binary", [3], b"\x05")
        tensor_ref("qint2", [1], b"\x01")

    def test_exact_fit_unaffected(self):
        tensor_ref("qint4", [3], b"\x21\x03")  # 12 bits -> 2 bytes, no padding

    def test_bad_dims_rejected_with_clear_error(self):
        with pytest.raises(ValueError, match="must be an int"):
            tensor_ref("int8", [2.0], b"\x00\x00")
        with pytest.raises(ValueError, match="must be an int"):
            tensor_ref("int8", [True], b"\x00")
        with pytest.raises(ValueError, match="negative dim"):
            tensor_ref("int8", [-1], b"")


class TestDeltaTruncation:
    def test_fractional_delta_on_int_raises(self):
        base = from_json_loose({"n": 10})
        p = parse_patch(_wire(("~", ["n"], 1.5)))
        with pytest.raises(ValueError, match="would truncate"):
            apply_patch(base, p)

    def test_whole_float_delta_on_int_ok(self):
        base = from_json_loose({"n": 10})
        p = parse_patch(_wire(("~", ["n"], 5.0)))
        state = apply_patch(base, p)
        assert state.get("n").as_int() == 15

    def test_fractional_delta_on_float_ok(self):
        base = from_json_loose({"x": 1.5})
        p = parse_patch(_wire(("~", ["x"], 0.25)))
        state = apply_patch(base, p)
        assert state.get("x").as_float() == pytest.approx(1.75)


class TestPatchTarget:
    def test_bare_target_rejected(self):
        with pytest.raises(ValueError, match="prefix:value"):
            parse_patch(_wire(("=", ["a"], 1), target="bare"))

    def test_prefix_value_target_kept_raw(self):
        p = parse_patch(_wire(("=", ["a"], 1), target="match:001"))
        assert p.target == "match:001"

    def test_missing_target_ok(self):
        p = parse_patch(_wire(("=", ["a"], 1)))
        assert p.target == ""

    def test_root_set_without_value_raises(self):
        from glyph.patch import Patch, PatchOp, PatchOpKind

        base = from_json_loose({"a": 1})
        with pytest.raises(ValueError, match="no value"):
            apply_patch(base, Patch(ops=[PatchOp(op=PatchOpKind.SET, path=[])]))

    def test_root_set_with_value_still_replaces(self):
        from glyph.patch import Patch, PatchOp, PatchOpKind

        base = from_json_loose({"a": 1})
        out = apply_patch(
            base, Patch(ops=[PatchOp(op=PatchOpKind.SET, path=[], value=GValue.int_(2))])
        )
        assert out.as_int() == 2
