"""P0 round-trip golden table for the Python codec.

Mirrors go/glyph/roundtrip_golden_test.go. Python exposes a single (loose)
codec — parse() == parse_loose() and emit() == canonicalize_loose() — so the
P0 invariant here is parse(emit(v)) == v across every GType. These tests pin
the cross-language P0 behaviors: conservative quoting, bytes round-trip, \\u
control-char decode, dup-key last-wins, and the NaN/Inf reject policy.
"""

import sys
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

import pytest

from glyph import GValue, GType, MapEntry, parse, emit, equal_loose, from_json, to_json

# Scope note: Python exposes only the loose codec, which (per the maintainer
# decision) collapses to JSON-like semantics. The round-trippable GTypes here are
# null/bool/int/float/str/bytes/id/list/map/struct/sum. `time` is intentionally
# NOT asserted: the loose layer emits it as a bare ISO string and does not
# reconstruct a typed time on parse — typed time round-trip is a Go-only
# Parse/Emit-path feature, out of scope for these P0 cross-language behaviors.


def rt(v: GValue) -> GValue:
    """Round-trip a value through emit + parse."""
    return parse(emit(v))


class TestRoundTripScalars:
    def test_scalars(self):
        cases = [
            GValue.null(),
            GValue.bool_(True),
            GValue.bool_(False),
            GValue.int_(0),
            GValue.int_(42),
            GValue.int_(-42),
            GValue.int_(9223372036854775807),   # int64 max
            GValue.int_(-9223372036854775808),  # int64 min
            GValue.int_(2 ** 70),               # beyond int64 (Python is arbitrary precision)
            GValue.float_(1.5),
            GValue.float_(-2.25),
            GValue.float_(0.0),
            GValue.float_(3.0),
            GValue.float_(1e300),
            GValue.float_(1e-300),
            GValue.id("m", "123"),
            GValue.id("", "plain"),
            GValue.id("t", "a-b.c"),
        ]
        for v in cases:
            assert equal_loose(rt(v), v), f"round-trip mismatch for {emit(v)!r}"

    def test_large_int_value_preserved(self):
        n = 2 ** 70 + 12345
        assert rt(GValue.int_(n)).as_int() == n


class TestRoundTripStrings:
    # Each of these forces a distinct quoting/escaping decision; all must read
    # back as the identical string.
    STRINGS = [
        "hello",          # bare-eligible identifier
        "",               # empty -> quoted
        "with space",     # space forces quoting
        'with"quote',     # embedded quote
        "with\\back",     # embedded backslash
        "with\ttab",      # tab control char
        "with\nnewline",  # newline control char
        "with\rreturn",   # carriage return
        "ctl\x01\x02end",  # sub-0x20 control chars (emitted as \\uXXXX)
        "café",           # non-ASCII letters
        "日本語",            # multi-byte Unicode
        "with-hyphen",
        "with.dot",
        "with/slash",
        "with|pipe",
        "123",            # digit-leading: must quote or it parses as int
        "-5",             # leading minus: must quote
        "true",           # keyword: must quote to stay a string
        "t",
        "null",
        "NaN",
        "b64",            # bytes prefix without a following quote
    ]

    def test_strings(self):
        for s in self.STRINGS:
            v = GValue.str_(s)
            back = rt(v)
            assert back.type == GType.STR, f"{s!r} did not parse back as a string (emitted {emit(v)!r})"
            assert back.as_str() == s, f"string mismatch: {s!r} -> {back.as_str()!r} (emitted {emit(v)!r})"


class TestRoundTripBytes:
    def test_bytes(self):
        cases = [
            b"",
            b"hello",
            bytes([0, 1, 2, 254, 255]),
            bytes(range(256)),
        ]
        for b in cases:
            back = rt(GValue.bytes_(b))
            assert back.type == GType.BYTES, f"bytes did not round-trip (emitted {emit(GValue.bytes_(b))!r})"
            assert back.as_bytes() == b


class TestRoundTripContainers:
    def test_list(self):
        v = GValue.list_(
            GValue.null(),
            GValue.bool_(True),
            GValue.int_(42),
            GValue.str_("hi there"),
            GValue.bytes_(b"\x00\x01"),
        )
        assert equal_loose(rt(v), v)

    def test_map(self):
        v = GValue.map_(
            MapEntry("name", GValue.str_("Arsenal")),
            MapEntry("rank", GValue.int_(1)),
            MapEntry("blob", GValue.bytes_(b"xyz")),
        )
        assert equal_loose(rt(v), v)

    def test_nested(self):
        v = GValue.map_(
            MapEntry("items", GValue.list_(GValue.int_(1), GValue.int_(2))),
            MapEntry("meta", GValue.map_(MapEntry("k", GValue.str_("v")))),
        )
        assert equal_loose(rt(v), v)

    def test_struct_and_sum_collapse(self):
        # Loose collapses struct -> object and sum -> {tag: value}; the canonical
        # form is stable across the round-trip (equal_loose compares canon).
        st = GValue.struct("Team", MapEntry("name", GValue.str_("Arsenal")))
        assert equal_loose(rt(st), st)
        sm = GValue.sum("Ok", GValue.int_(42))
        assert equal_loose(rt(sm), sm)


class TestDuplicateKeyLastWins:
    def test_last_wins(self):
        # Mirrors the documented duplicate_keys_last_wins policy.
        assert parse("{a=1 a=2}").get("a").as_int() == 2


class TestNaNInfPolicy:
    # Maintainer decision: NaN/Inf are REJECTED on emit (and in the JSON bridge);
    # the canonical loose form must be deterministic and JSON-like.
    def test_emit_rejects_nan(self):
        with pytest.raises(ValueError):
            emit(GValue.float_(float("nan")))

    def test_emit_rejects_inf(self):
        with pytest.raises(ValueError):
            emit(GValue.float_(float("inf")))
        with pytest.raises(ValueError):
            emit(GValue.float_(float("-inf")))

    def test_json_bridge_rejects_nan_inf(self):
        with pytest.raises(ValueError):
            to_json(GValue.float_(float("nan")))
        with pytest.raises(ValueError):
            from_json(float("inf"))
