"""
GLYPH Python Correctness Gauntlet
==================================
Mirrors the gauntlet contract defined in gauntlet/data/gauntlet-data.json.

All numeric assertions come from the real codec — never fabricated.
If a feature is absent or broken, we skip with a documented reason or fail loud.

Known gaps documented here:
- GValue.time() round-trip: canonicalize_loose() emits bare ISO text (e.g.
  '2025-01-13T12:34:56Z') that parse() cannot re-parse because the lexer
  tokenizes '2025' as INT then hits '-' as trailing garbage.  This is a real
  round-trip gap for native GTime values (not for date strings, which work fine).
- Streaming validator format: Python uses 'toolname{field=val}' whereas the
  gauntlet data records JS '{action=toolname field=val}' format.  Detection
  timing numbers differ accordingly; we assert Python-format semantics.
- Big-int precision: 9007199254740992 > MAX_SAFE_INT so Python (like JS) maps it
  to float.  Go handles int64 correctly.  Documented in edgeCases['big_int'].
- Python has no incremental/streaming text parser (no chunk-invariance path at
  the glyph-text level).  StreamingValidator is token-push, not text-chunk.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from typing import Any

import pytest

# ── importable as: PYTHONPATH=py python -m pytest ... ──────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import glyph
from glyph import (
    GValue,
    GType,
    MapEntry,
    parse,
    parse_loose,
    canonicalize_loose,
    canonicalize_loose_no_tabular,
    from_json_loose,
    to_json_loose,
    json_to_glyph,
    glyph_to_json,
    fingerprint_loose,
    equal_loose,
    StreamingValidator,
    ToolRegistry,
    parse_patch,
    apply_patch,
    compute_base_fingerprint,
    verify_patch_base,
    PatchBaseMismatch,
)

# ── load real gauntlet data once ────────────────────────────────────────────
_GAUNTLET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "gauntlet", "data", "gauntlet-data.json"
)

with open(_GAUNTLET_PATH) as _fh:
    _DATA: dict = json.load(_fh)

_EDGE_CASES: list[dict] = _DATA["edgeCases"]
_EDGE_BY_NAME: dict[str, dict] = {ec["name"]: ec for ec in _EDGE_CASES}

_FIREWALL = _DATA["toolFirewall"]
_MATCH_STREAM = _DATA["matchStream"]
_TABULAR = _DATA["tabular"]
_BENCH = _DATA["benchMatrix"]


# ============================================================
# Helpers
# ============================================================

def _default_firewall_registry() -> ToolRegistry:
    """Build a ToolRegistry mirroring defaultToolRegistry.

    JS defaultToolRegistry includes: search, calculate, browse, execute,
    read_file, write_file.  wire_transfer is intentionally absent.
    """
    registry = ToolRegistry()
    registry.add_tool("search", {
        "query": {"type": "str"},
        "max_results": {"type": "int"},
    })
    for tool in ("calculate", "browse", "execute", "read_file", "write_file"):
        registry.add_tool(tool, {})
    return registry


def _assert_rt(json_value: Any, *, name: str) -> str:
    """Round-trip json_value through glyph and return the glyph text."""
    gv = from_json_loose(json_value)
    text = canonicalize_loose(gv)
    back = glyph_to_json(text)
    assert back == json_value, (
        f"{name}: glyph_to_json(json_to_glyph(v)) != v\n"
        f"  original : {json_value!r}\n"
        f"  glyph    : {text!r}\n"
        f"  round-trip: {back!r}"
    )
    return text


# ============================================================
# 1. Museum of Edge Cases — JSON semantic round-trip + glyph text assertion
# ============================================================

class TestGauntletEdgeCases:
    """
    For each record in gauntlet-data.json edgeCases:
      - json_to_glyph(json.loads(jsonText)) must equal the recorded glyphText
      - glyph_to_json(glyphText) round-trips back to the original JSON value
      - canonicalize_loose is idempotent: canon(parse(canon(v))) == canon(v)

    Big-int is special: Python converts it to float (same as JS), documented.
    The GTime native-type round-trip gap is skipped with explanation.
    """

    def _run(self, name: str) -> None:
        ec = _EDGE_BY_NAME[name]
        json_val = json.loads(ec["jsonText"])
        expected_glyph = ec["glyphText"]

        # Forward direction
        produced = json_to_glyph(json_val)
        assert produced == expected_glyph, (
            f"edge_case '{name}': json_to_glyph produced wrong glyph text\n"
            f"  expected : {expected_glyph!r}\n"
            f"  produced : {produced!r}"
        )

        # Semantic round-trip (JSON -> glyph -> JSON)
        back = glyph_to_json(produced)
        assert back == json_val, (
            f"edge_case '{name}': semantic round-trip failed\n"
            f"  original : {json_val!r}\n"
            f"  back     : {back!r}"
        )

        # Idempotence of canonicalize_loose: canon(parse(canon(v))) == canon(v)
        v = parse(produced)
        canon2 = canonicalize_loose(v)
        assert canon2 == produced, (
            f"edge_case '{name}': canonicalize_loose not idempotent\n"
            f"  first  : {produced!r}\n"
            f"  second : {canon2!r}"
        )

    def test_empty_str(self):    self._run("empty_str")
    def test_unicode(self):      self._run("unicode")
    def test_embedded_quote(self): self._run("embedded_quote")
    def test_pipe(self):         self._run("pipe")
    def test_newlines(self):     self._run("newlines")
    def test_null_value(self):   self._run("null_value")
    def test_bool_true(self):    self._run("bool_true")
    def test_bool_false(self):   self._run("bool_false")
    def test_float_sci(self):    self._run("float_sci")
    def test_date_string(self):  self._run("date_string")
    def test_nested_list(self):  self._run("nested_list")
    def test_nested_map(self):   self._run("nested_map")

    def test_big_int(self):
        """
        9007199254740992 > MAX_SAFE_INT: Python maps it to float, matching JS.
        Go handles int64 correctly (different output).
        Gauntlet records: glyphText='9.007199254740992e+15'.
        """
        ec = _EDGE_BY_NAME["big_int"]
        json_val = json.loads(ec["jsonText"])
        expected_glyph = ec["glyphText"]

        produced = json_to_glyph(json_val)
        assert produced == expected_glyph, (
            f"big_int: expected {expected_glyph!r}, got {produced!r}"
        )
        # Round-trip back: float, not int — this is the documented precision loss
        back = glyph_to_json(produced)
        assert isinstance(back, float), f"big_int should round-trip as float, got {type(back)}"
        assert back == float(ec["jsonText"]), (
            f"big_int float value mismatch: {back!r}"
        )

    def test_neg_zero(self):
        """
        Gauntlet: jsonText='0', glyphText='0'.
        json.loads('0') yields int 0, not -0.0; from_json_loose(0) -> GInt -> '0'.
        """
        ec = _EDGE_BY_NAME["neg_zero"]
        json_val = json.loads(ec["jsonText"])
        produced = json_to_glyph(json_val)
        assert produced == ec["glyphText"], (
            f"neg_zero: expected {ec['glyphText']!r}, got {produced!r}"
        )
        # Also verify -0.0 float normalizes the same way
        gv_neg_zero = from_json_loose(-0.0)
        assert canonicalize_loose(gv_neg_zero) == "0", (
            "from_json_loose(-0.0) should yield GInt(0) -> '0'"
        )


# ============================================================
# 2. TypeZoo — native GValue types beyond JSON primitives
# ============================================================

class TestGauntletTypeZoo:
    """
    Tests for GValue types that are not present in plain JSON:
    bytes, ID references, struct, sum, and datetime (partial).
    """

    def test_bytes_roundtrip(self):
        """bytes -> b64"..." -> back to bytes via parse+to_json."""
        raw = b"hello bytes\x00\xff"
        gv = GValue.bytes_(raw)
        text = canonicalize_loose(gv)
        assert text.startswith('b64"'), f"bytes should start with b64\", got {text!r}"

        # parse it back
        v2 = parse(text)
        assert v2.type == GType.BYTES
        assert v2.as_bytes() == raw

    def test_id_bare_roundtrip(self):
        """ID with safe prefix:value emits bare ^prefix:value and round-trips."""
        gv = GValue.id("user", "123")
        text = canonicalize_loose(gv)
        assert text == "^user:123", f"expected ^user:123, got {text!r}"
        v2 = parse(text)
        assert v2.type == GType.ID
        ref = v2.as_id()
        assert ref.prefix == "user"
        assert ref.value == "123"

    def test_id_no_prefix(self):
        """ID without prefix emits ^value."""
        gv = GValue.id("", "myref-001")
        text = canonicalize_loose(gv)
        assert text == "^myref-001"
        v2 = parse(text)
        assert v2.as_id().value == "myref-001"

    def test_struct_roundtrip(self):
        """Struct emits TypeName{field=val} and round-trips via parse."""
        gv = GValue.struct(
            "Team",
            MapEntry("name", GValue.str_("Arsenal")),
            MapEntry("rank", GValue.int_(1)),
        )
        text = canonicalize_loose(gv)
        assert text == "Team{name=Arsenal rank=1}", f"unexpected struct text: {text!r}"
        v2 = parse(text)
        assert v2.type == GType.STRUCT
        sv = v2.as_struct()
        assert sv.type_name == "Team"

    def test_sum_roundtrip(self):
        """Sum (tagged union) emits tag(value) and round-trips."""
        gv = GValue.sum("Ok", GValue.int_(42))
        text = canonicalize_loose(gv)
        assert text == "Ok(42)", f"unexpected sum text: {text!r}"
        v2 = parse(text)
        assert v2.type == GType.SUM
        sm = v2.as_sum()
        assert sm.tag == "Ok"
        assert sm.value.as_int() == 42

    def test_time_forward_only(self):
        """
        GValue.time() emits bare ISO text (e.g. '2025-01-13T12:34:56Z').
        parse() CANNOT re-parse this — the lexer reads '2025' as INT then
        hits '-' as trailing garbage.  This is a documented round-trip gap
        for native GTime values.

        Forward direction (GTime -> glyph text) works; we assert the format.
        Round-trip (parse the emitted text) is skipped as a known gap.
        """
        dt = datetime(2025, 1, 13, 12, 34, 56, tzinfo=timezone.utc)
        gv = GValue.time(dt)
        text = canonicalize_loose(gv)
        assert text == "2025-01-13T12:34:56Z", f"unexpected time text: {text!r}"

        # Document the known gap — parse() fails on bare ISO datetime
        with pytest.raises(ValueError, match="trailing garbage"):
            parse(text)

        # NOTE: date strings (str type) round-trip fine — this is separate
        date_str_gv = from_json_loose("2024-03-15T12:00:00Z")
        date_str_text = canonicalize_loose(date_str_gv)
        assert date_str_text == '"2024-03-15T12:00:00Z"'
        back = glyph_to_json(date_str_text)
        assert back == "2024-03-15T12:00:00Z"

    def test_null_variants(self):
        """Null emits '_' (default) or '∅' depending on opts."""
        from glyph import LooseCanonOpts, NullStyle
        gv = GValue.null()
        assert canonicalize_loose(gv) == "_"
        opts = LooseCanonOpts(null_style=NullStyle.SYMBOL)
        assert canonicalize_loose(gv, opts) == "∅"

    def test_bool_encoding(self):
        assert canonicalize_loose(GValue.bool_(True)) == "t"
        assert canonicalize_loose(GValue.bool_(False)) == "f"

    def test_float_neg_zero(self):
        """Float -0.0 must canonicalize to '0.0' (D4 rule)."""
        from glyph.loose import canon_float
        assert canon_float(-0.0) == "0.0"
        assert canon_float(0.0) == "0.0"

    def test_float_scientific(self):
        """Small floats use Go-compatible exponential notation."""
        from glyph.loose import canon_float
        assert canon_float(1.23e-9) == "1.23e-09"
        assert canon_float(1e6) == "1e+06"


# ============================================================
# 3. JSON Semantic Round-Trip — json_to_glyph / glyph_to_json
# ============================================================

class TestGauntletJsonSemanticRoundTrip:
    """
    Full round-trip: Python dict/list -> json_to_glyph -> glyph_to_json -> back.
    Tests realistic AI agent payloads.
    """

    def test_flat_tool_call(self):
        data = {"action": "search", "query": "hello world", "count": 42, "active": True}
        text = json_to_glyph(data)
        back = glyph_to_json(text)
        assert back == data

    def test_nested_structure(self):
        data = {"a": 1, "b": {"c": 2, "d": [1, 2, 3]}, "e": None}
        text = json_to_glyph(data)
        back = glyph_to_json(text)
        assert back == data

    def test_empty_string_preserved(self):
        data = {"key": ""}
        text = json_to_glyph(data)
        back = glyph_to_json(text)
        assert back == data

    def test_unicode_preserved(self):
        data = {"msg": "café ☕ λ ñ 中文"}
        text = json_to_glyph(data)
        back = glyph_to_json(text)
        assert back == data

    def test_embedded_quote_preserved(self):
        data = {"msg": 'say "hello"'}
        text = json_to_glyph(data)
        back = glyph_to_json(text)
        assert back == data

    def test_newlines_preserved(self):
        data = {"body": "line1\nline2\r\nline3"}
        text = json_to_glyph(data)
        back = glyph_to_json(text)
        assert back == data

    def test_pipe_char_preserved(self):
        data = {"csv": "a|b|c"}
        text = json_to_glyph(data)
        back = glyph_to_json(text)
        assert back == data

    def test_all_json_types(self):
        data = {
            "null_val": None,
            "bool_t": True,
            "bool_f": False,
            "int_val": 42,
            "float_val": 3.14,
            "str_val": "hello",
            "list_val": [1, "two", None, True],
            "map_val": {"nested": "yes"},
        }
        text = json_to_glyph(data)
        back = glyph_to_json(text)
        assert back == data

    def test_tabular_round_trip_via_parse(self):
        """
        Homogeneous list of dicts with >=3 rows auto-tabularizes.
        After tabularization the text starts with @tab _.
        glyph_to_json on the tabular text must return the original list.
        """
        rows = [
            {"id": i, "name": f"item_{i}", "score": i * 10}
            for i in range(5)
        ]
        text = json_to_glyph(rows)
        assert text.startswith("@tab _"), f"expected tabular output, got: {text!r}"
        back = glyph_to_json(text)
        assert back == rows, f"tabular round-trip failed:\n  expected: {rows}\n  got: {back}"

    def test_small_list_not_tabular(self):
        """2 rows < min_rows=3: no auto-tabular."""
        rows = [{"id": 0, "name": "a"}, {"id": 1, "name": "b"}]
        text = json_to_glyph(rows)
        assert not text.startswith("@tab"), f"expected non-tabular for 2 rows, got: {text!r}"


# ============================================================
# 4. Canonicalize Idempotence
# ============================================================

class TestGauntletIdempotence:
    """
    canonicalize_loose(parse(canonicalize_loose(v))) == canonicalize_loose(v)
    for all types.
    """

    def _assert_idempotent(self, v: GValue, label: str) -> None:
        c1 = canonicalize_loose(v)
        v2 = parse(c1)
        c2 = canonicalize_loose(v2)
        assert c1 == c2, (
            f"not idempotent for {label}:\n  first:  {c1!r}\n  second: {c2!r}"
        )

    def test_null(self):
        self._assert_idempotent(GValue.null(), "null")

    def test_bool_true(self):
        self._assert_idempotent(GValue.bool_(True), "bool(True)")

    def test_bool_false(self):
        self._assert_idempotent(GValue.bool_(False), "bool(False)")

    def test_int_zero(self):
        self._assert_idempotent(GValue.int_(0), "int(0)")

    def test_int_pos(self):
        self._assert_idempotent(GValue.int_(12345), "int(12345)")

    def test_int_neg(self):
        self._assert_idempotent(GValue.int_(-42), "int(-42)")

    def test_float_sci(self):
        self._assert_idempotent(GValue.float_(1.23e-9), "float(1.23e-9)")

    def test_float_pos(self):
        self._assert_idempotent(GValue.float_(3.14159), "float(3.14159)")

    def test_string_bare(self):
        self._assert_idempotent(GValue.str_("hello"), "str(hello)")

    def test_string_quoted(self):
        self._assert_idempotent(GValue.str_("hello world"), "str(hello world)")

    def test_string_unicode(self):
        self._assert_idempotent(GValue.str_("café ☕"), "str(unicode)")

    def test_list_flat(self):
        gv = from_json_loose([1, 2, "three", None])
        self._assert_idempotent(gv, "flat list")

    def test_map_sorted(self):
        gv = from_json_loose({"z": 26, "a": 1, "m": 13})
        self._assert_idempotent(gv, "map with sorting")

    def test_big_int_as_float(self):
        """9007199254740992 -> float -> idempotent glyph text."""
        gv = from_json_loose(9007199254740992)
        c1 = canonicalize_loose(gv)
        assert c1 == "9.007199254740992e+15"
        v2 = parse(c1)
        c2 = canonicalize_loose(v2)
        assert c1 == c2

    def test_bytes_idempotent(self):
        self._assert_idempotent(GValue.bytes_(b"\x00\xff\x42"), "bytes")

    def test_struct_idempotent(self):
        gv = GValue.struct("Point", MapEntry("x", GValue.int_(1)), MapEntry("y", GValue.int_(2)))
        self._assert_idempotent(gv, "struct")

    def test_sum_idempotent(self):
        gv = GValue.sum("Ok", GValue.str_("done"))
        self._assert_idempotent(gv, "sum")


# ============================================================
# 5. Tabular Auto-Trigger (from gauntlet tabular section)
# ============================================================

class TestGauntletTabular:
    """
    Auto-tabular kicks in for homogeneous lists of >= 3 maps.
    Savings % are not asserted (tabular vs JSON would require re-implementing
    the size measurement); instead we assert format correctness and round-trip.
    """

    def _make_rows(self, n: int) -> list:
        return [
            {"id": i, "name": f"item_{i}", "value": i * 100, "active": True}
            for i in range(n)
        ]

    def test_tabular_trigger_at_3_rows(self):
        rows = self._make_rows(3)
        text = json_to_glyph(rows)
        assert text.startswith("@tab _"), f"3 rows should trigger tabular, got: {text!r}"
        assert "@end" in text

    def test_tabular_no_trigger_at_2_rows(self):
        rows = self._make_rows(2)
        text = json_to_glyph(rows)
        assert not text.startswith("@tab"), f"2 rows should NOT trigger tabular, got: {text!r}"

    def test_tabular_header_format(self):
        """Header is '@tab _ rows=N cols=M [col1 col2 ...]' with sorted cols.

        The rows/cols metadata (v2.4.0, for streaming resync) is part of the
        canonical form. Go is the cross-language source of truth for the loose
        canonical form, and Go/JS both emit this header; Python matches them.
        """
        rows = [{"z": 1, "a": 2, "m": 3} for _ in range(3)]
        text = json_to_glyph(rows)
        first_line = text.split("\n")[0]
        # Columns must be sorted; rows/cols metadata precedes the bracket.
        assert first_line == "@tab _ rows=3 cols=3 [a m z]", f"unexpected header: {first_line!r}"

    def test_tabular_roundtrip_10_rows(self):
        rows = self._make_rows(10)
        text = json_to_glyph(rows)
        assert text.startswith("@tab _")
        back = glyph_to_json(text)
        assert back == rows

    def test_tabular_roundtrip_50_rows(self):
        """50 rows: matches the 'Verified: 50 match rows' from contract doc."""
        rows = self._make_rows(50)
        text = json_to_glyph(rows)
        assert text.startswith("@tab _")
        back = glyph_to_json(text)
        assert back == rows

    def test_tabular_smaller_than_json(self):
        """Tabular glyph output is substantially smaller than JSON for large lists."""
        rows = self._make_rows(100)
        text = json_to_glyph(rows)
        json_text = json.dumps(rows, separators=(",", ":"))
        assert len(text.encode()) < len(json_text.encode()), (
            f"tabular should be smaller than JSON: glyph={len(text)} json={len(json_text)}"
        )

    def test_tabular_with_pipe_in_cell(self):
        """Pipe chars in cell values must be escaped in tabular output."""
        rows = [{"key": "a|b|c"} for _ in range(3)]
        text = json_to_glyph(rows)
        back = glyph_to_json(text)
        assert back == rows, f"pipe round-trip failed: {back}"

    def test_tabular_with_missing_keys(self):
        """Rows with missing keys fill with null (_) when allow_missing=True."""
        rows = [
            {"a": 1, "b": 2, "c": 3},
            {"a": 4, "b": 5},          # missing c
            {"a": 6, "b": 7, "c": 9},
        ]
        text = json_to_glyph(rows)
        # Should still tabularize (allow_missing=True by default)
        assert text.startswith("@tab _"), f"expected tabular with missing keys, got: {text!r}"
        back = glyph_to_json(text)
        # Missing key round-trips as null -> None
        assert back[1].get("c") is None


# ============================================================
# 6. Firewall — StreamingValidator tool allow/block
# ============================================================

class TestGauntletFirewall:
    """
    Python validator format: 'toolname{field=val ...}'
    (different from JS '{action=toolname ...}' format in gauntlet data).

    Gauntlet contract facts we DO assert:
    - wire_transfer is not in defaultToolRegistry -> rejected
    - search IS in registry -> allowed
    - blocking produces errors containing 'UNKNOWN_TOOL'
    - should_cancel is True on block
    - bytes_avoided = total_chars - error_at_char  (gauntlet: 30 for JS format)
    """

    def test_allowed_tool_completes_valid(self):
        """search{...} completes valid."""
        registry = _default_firewall_registry()
        validator = StreamingValidator(registry)
        for ch in "search{query=\"test\" max_results=5}":
            result = validator.push_token(ch)
        assert result.complete
        assert result.valid
        assert result.tool_name == "search"
        assert not result.errors

    def test_allowed_tool_early_detection(self):
        """Tool name is detected before the closing brace."""
        registry = _default_firewall_registry()
        validator = StreamingValidator(registry)
        detected_at = None
        for ch in "search{query=\"test\"}":
            result = validator.push_token(ch)
            if result.tool_detected_at_char > 0 and detected_at is None:
                detected_at = result.tool_detected_at_char
        assert detected_at is not None, "tool should be detected before end"
        # Python format: tool name is in stream before '{', so detection is early
        assert detected_at <= len("search"), (
            f"search should be detected by char {len('search')}, got {detected_at}"
        )

    def test_blocked_tool_has_error(self):
        """wire_transfer is absent from registry -> UNKNOWN_TOOL error."""
        registry = _default_firewall_registry()
        validator = StreamingValidator(registry)
        for ch in "wire_transfer{amount=1000000 target=unknown}":
            result = validator.push_token(ch)
        assert any("UNKNOWN_TOOL" in e for e in result.errors), (
            f"expected UNKNOWN_TOOL error, got: {result.errors}"
        )
        assert result.should_cancel

    def test_blocked_tool_name_identified(self):
        """Even blocked tool: tool_name is set to 'wire_transfer'."""
        registry = _default_firewall_registry()
        validator = StreamingValidator(registry)
        for ch in "wire_transfer{amount=1000000}":
            result = validator.push_token(ch)
        assert result.tool_name == "wire_transfer"

    def test_blocked_bytes_avoided(self):
        """
        Python format 'wire_transfer{amount=1000000 target=unknown}' (44 chars).
        Error fires at char 14 ('{' seen after 13-char tool name).
        bytes_avoided = 44 - 14 = 30 — matches gauntlet contract value of 30.
        """
        registry = _default_firewall_registry()
        validator = StreamingValidator(registry)
        text = "wire_transfer{amount=1000000 target=unknown}"
        total = len(text)
        error_at = None
        for ch in text:
            result = validator.push_token(ch)
            if result.errors and error_at is None:
                error_at = validator.char_count
        assert error_at is not None
        bytes_avoided = total - error_at
        assert bytes_avoided == 30, (
            f"bytes_avoided should be 30, got {bytes_avoided} "
            f"(error_at={error_at}, total={total})"
        )

    def test_known_tools_not_blocked(self):
        """All tools in the default registry should validate without UNKNOWN_TOOL."""
        registry = _default_firewall_registry()
        for tool in ("search", "calculate", "browse", "execute", "read_file", "write_file"):
            validator = StreamingValidator(registry)
            for ch in f"{tool}{{}}":
                result = validator.push_token(ch)
            assert not any("UNKNOWN_TOOL" in e for e in result.errors), (
                f"tool '{tool}' should be allowed, errors: {result.errors}"
            )


# ============================================================
# 7. PatchApply — parse_patch / apply_patch / compute_base_fingerprint
# ============================================================

class TestGauntletPatch:
    """
    Tests against the sample @patch from gauntlet matchStream data.

    Sample patch from gauntlet:
        @patch @keys=wire @target=match:001
        = minute 45
        = score_away 0
        = score_home 1
        @end
    """

    _SAMPLE_PATCH = _MATCH_STREAM["samplePatchText"]
    _TARGET = "match:001"

    def _make_match_base(self, minute: int = 0, score_home: int = 0, score_away: int = 0) -> GValue:
        return from_json_loose({
            "id": self._TARGET,
            "minute": minute,
            "score_home": score_home,
            "score_away": score_away,
        })

    def test_parse_sample_patch(self):
        """Sample patch parses to 3 SET operations."""
        p = parse_patch(self._SAMPLE_PATCH)
        assert len(p.ops) == 3
        fields = {op.path[0].field for op in p.ops}
        assert fields == {"minute", "score_away", "score_home"}

    def test_apply_sample_patch(self):
        """Applying the sample patch updates minute and scores."""
        base = self._make_match_base(minute=0, score_home=0, score_away=0)
        p = parse_patch(self._SAMPLE_PATCH)
        result = apply_patch(base, p)
        result_json = to_json_loose(result)
        assert result_json["minute"] == 45
        assert result_json["score_home"] == 1
        assert result_json["score_away"] == 0

    def test_patch_target_preserved(self):
        """parse_patch reads @target= field."""
        p = parse_patch(self._SAMPLE_PATCH)
        assert p.target == self._TARGET

    def test_compute_base_fingerprint_length(self):
        """Fingerprint is exactly 16 hex chars."""
        base = self._make_match_base()
        fp = compute_base_fingerprint(base)
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp), f"not hex: {fp!r}"

    def test_compute_base_fingerprint_deterministic(self):
        """Same base state always yields same fingerprint."""
        base = self._make_match_base()
        fp1 = compute_base_fingerprint(base)
        fp2 = compute_base_fingerprint(base)
        assert fp1 == fp2

    def test_verify_patch_base_ok(self):
        """verify_patch_base passes when @base fingerprint matches."""
        base = self._make_match_base()
        fp = compute_base_fingerprint(base)
        patch_text = f"@patch @base={fp} @target={self._TARGET}\n= minute 45\n@end"
        p = parse_patch(patch_text)
        # No exception
        verify_patch_base(base, p)

    def test_verify_patch_base_mismatch(self):
        """verify_patch_base raises PatchBaseMismatch on wrong fingerprint."""
        base = self._make_match_base()
        wrong_fp = "deadbeef12345678"
        patch_text = f"@patch @base={wrong_fp}\n= minute 45\n@end"
        p = parse_patch(patch_text)
        with pytest.raises(PatchBaseMismatch):
            verify_patch_base(base, p)

    def test_verify_patch_no_base_noop(self):
        """verify_patch_base is a no-op when patch has no @base."""
        base = self._make_match_base()
        p = parse_patch("@patch @target=x\n= minute 10\n@end")
        assert p.base_fingerprint == ""
        # Should not raise
        verify_patch_base(base, p)

    def test_patch_does_not_mutate_base(self):
        """apply_patch returns a copy; the original base is unchanged."""
        base = self._make_match_base(minute=0)
        p = parse_patch("@patch\n= minute 90\n@end")
        result = apply_patch(base, p)
        # Base unchanged
        base_json = to_json_loose(base)
        assert base_json["minute"] == 0
        # Result updated
        result_json = to_json_loose(result)
        assert result_json["minute"] == 90

    def test_sequential_patch_chain(self):
        """Apply multiple patches in sequence, fingerprint chain is consistent."""
        state = self._make_match_base(minute=0, score_home=0, score_away=0)
        for minute in range(1, 6):
            fp = compute_base_fingerprint(state)
            patch_text = (
                f"@patch @base={fp} @target={self._TARGET}\n"
                f"= minute {minute}\n@end"
            )
            p = parse_patch(patch_text)
            verify_patch_base(state, p)
            state = apply_patch(state, p)
        assert to_json_loose(state)["minute"] == 5

    def test_patch_savings_cumulative(self):
        """
        Gauntlet records 32.81% savings for 100 updates (cumPatchBytes / cumSnapshotBytes).
        cumSnapshotBytes=12192, cumPatchBytes=8192 (per gauntlet-data.json).

        We replicate the measurement: a richer match state yields ~122B snapshots;
        3-field patches are ~82B.  Assert cumulative savings >= 25% over 10 updates.
        """
        # Richer state matching gauntlet snapshot size (~122 bytes as JSON)
        def make_state(minute: int, score_home: int, score_away: int) -> GValue:
            return from_json_loose({
                "id": "match:001",
                "minute": minute,
                "score_home": score_home,
                "score_away": score_away,
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "status": "active",
                "stadium": "Emirates",
            })

        cum_snap = 0
        cum_patch = 0
        state = make_state(0, 0, 0)
        for i in range(1, 11):
            # Snapshot size
            snap = json.dumps(to_json_loose(state), separators=(",", ":"))
            cum_snap += len(snap.encode())
            # Patch text
            patch_text = (
                f"@patch @target=match:001\n"
                f"= minute {i}\n"
                f"= score_home 0\n"
                f"= score_away 0\n"
                f"@end"
            )
            cum_patch += len(patch_text.encode())
            # Apply patch
            p = parse_patch(patch_text)
            state = apply_patch(state, p)

        savings = 1.0 - cum_patch / cum_snap
        assert savings >= 0.25, (
            f"cumulative patch savings should be >= 25%, got {savings:.1%} "
            f"(cum_patch={cum_patch}, cum_snap={cum_snap}). "
            f"Gauntlet contract: 32.81% over 100 updates."
        )

    def test_patch_all_op_kinds(self):
        """Exercise =, +, -, ~ operations on a map value."""
        base = from_json_loose({"count": 5, "items": [1, 2], "tag": "old"})

        p_set = parse_patch("@patch\n= count 10\n@end")
        state = apply_patch(base, p_set)
        assert to_json_loose(state)["count"] == 10

        p_delta = parse_patch("@patch\n~ count 5\n@end")
        state = apply_patch(state, p_delta)
        assert to_json_loose(state)["count"] == 15

        p_delete = parse_patch("@patch\n- tag\n@end")
        state = apply_patch(state, p_delete)
        assert "tag" not in to_json_loose(state)


# ============================================================
# 8. Streaming validator chunk-invariance note
# ============================================================

class TestGauntletStreamChunkInvariance:
    """
    Python StreamingValidator is token-push (push_token(str)).
    There is no incremental glyph-TEXT chunk-level parser.
    We verify that token-by-token (char-by-char) yields the same final result
    as whole-text (one-shot push), which is the Python-level analogue.
    """

    def test_char_by_char_equals_oneshot(self):
        """Feeding chars one at a time must yield same final state as one push."""
        registry = _default_firewall_registry()
        text = "search{query=\"hello world\" max_results=10}"

        # One-shot
        v1 = StreamingValidator(registry)
        result_oneshot = v1.push_token(text)

        # Char-by-char
        v2 = StreamingValidator(registry)
        result_charwise = None
        for ch in text:
            result_charwise = v2.push_token(ch)

        assert result_oneshot.complete == result_charwise.complete
        assert result_oneshot.valid == result_charwise.valid
        assert result_oneshot.tool_name == result_charwise.tool_name
        assert result_oneshot.errors == result_charwise.errors
        assert result_oneshot.fields == result_charwise.fields

    def test_no_incremental_glyph_text_parser(self):
        """
        There is no parse_loose_incremental or equivalent in the Python surface.
        This test documents the gap — it asserts that parse() and parse_loose()
        require a complete glyph text and will raise on truncated input.
        """
        truncated = '{"a"'   # incomplete glyph text
        with pytest.raises((ValueError, Exception)):
            parse(truncated)

    def test_fingerprint_stable(self):
        """fingerprint_loose is deterministic — same value -> same hex."""
        v = from_json_loose({"action": "search", "q": "test"})
        fp1 = fingerprint_loose(v)
        fp2 = fingerprint_loose(v)
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex

    def test_equal_loose_semantic(self):
        """equal_loose ignores map insertion order."""
        a = from_json_loose({"x": 1, "y": 2})
        b = from_json_loose({"y": 2, "x": 1})
        assert equal_loose(a, b)
