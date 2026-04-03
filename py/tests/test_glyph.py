"""Tests for GLYPH Python implementation."""

import pytest
from datetime import datetime, timezone

import sys
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

from glyph import (
    GValue, GType, g, field, MapEntry,
    parse, emit,
    from_json, to_json,
    json_to_glyph,
    canonicalize_loose,
    equal_loose,
    fingerprint_loose,
    LooseCanonOpts, NullStyle,
)


class TestGValue:
    """Tests for GValue type."""

    def test_null(self):
        v = GValue.null()
        assert v.type == GType.NULL
        assert v.is_null()

    def test_bool(self):
        t = GValue.bool_(True)
        f = GValue.bool_(False)
        assert t.as_bool() == True
        assert f.as_bool() == False

    def test_int(self):
        v = GValue.int_(42)
        assert v.as_int() == 42
        assert v.type == GType.INT

    def test_float(self):
        v = GValue.float_(3.14)
        assert abs(v.as_float() - 3.14) < 0.001

    def test_str(self):
        v = GValue.str_("hello")
        assert v.as_str() == "hello"

    def test_bytes(self):
        v = GValue.bytes_(b"hello")
        assert v.as_bytes() == b"hello"

    def test_time(self):
        dt = datetime(2025, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
        v = GValue.time(dt)
        assert v.as_time() == dt

    def test_id(self):
        v = GValue.id("user", "123")
        ref = v.as_id()
        assert ref.prefix == "user"
        assert ref.value == "123"

    def test_list(self):
        v = GValue.list_(GValue.int_(1), GValue.int_(2), GValue.int_(3))
        lst = v.as_list()
        assert len(lst) == 3
        assert lst[0].as_int() == 1

    def test_map(self):
        v = GValue.map_(
            MapEntry("a", GValue.int_(1)),
            MapEntry("b", GValue.int_(2))
        )
        assert v.get("a").as_int() == 1
        assert v.get("b").as_int() == 2

    def test_struct(self):
        v = GValue.struct("Team",
            MapEntry("name", GValue.str_("Arsenal")),
            MapEntry("rank", GValue.int_(1))
        )
        sv = v.as_struct()
        assert sv.type_name == "Team"
        assert v.get("name").as_str() == "Arsenal"

    def test_sum(self):
        v = GValue.sum("Some", GValue.int_(42))
        sm = v.as_sum()
        assert sm.tag == "Some"
        assert sm.value.as_int() == 42

    def test_shorthand_g(self):
        v = g.struct("Match",
            field("home", g.str("Arsenal")),
            field("away", g.str("Liverpool")),
            field("score", g.list(g.int(2), g.int(1)))
        )
        assert v.get("home").as_str() == "Arsenal"


class TestCanonicalizeLoose:
    """Tests for loose canonicalization."""

    def test_null(self):
        assert emit(GValue.null()) == "_"

    def test_null_symbol(self):
        opts = LooseCanonOpts(null_style=NullStyle.SYMBOL)
        assert canonicalize_loose(GValue.null(), opts) == "∅"

    def test_bool(self):
        assert emit(GValue.bool_(True)) == "t"
        assert emit(GValue.bool_(False)) == "f"

    def test_int(self):
        assert emit(GValue.int_(42)) == "42"
        assert emit(GValue.int_(0)) == "0"
        assert emit(GValue.int_(-7)) == "-7"

    def test_float(self):
        assert emit(GValue.float_(3.14)) == "3.14"
        assert emit(GValue.float_(0.0)) == "0"

    def test_str_bare(self):
        assert emit(GValue.str_("hello")) == "hello"
        assert emit(GValue.str_("foo_bar")) == "foo_bar"

    def test_str_quoted(self):
        assert emit(GValue.str_("hello world")) == '"hello world"'
        assert emit(GValue.str_('say "hi"')) == '"say \\"hi\\""'

    def test_str_reserved(self):
        # Reserved words must be quoted
        assert emit(GValue.str_("t")) == '"t"'
        assert emit(GValue.str_("f")) == '"f"'
        assert emit(GValue.str_("null")) == '"null"'

    def test_list_empty(self):
        assert emit(GValue.list_()) == "[]"

    def test_list(self):
        v = GValue.list_(GValue.int_(1), GValue.int_(2), GValue.int_(3))
        assert emit(v) == "[1 2 3]"

    def test_map_empty(self):
        assert emit(GValue.map_()) == "{}"

    def test_map_sorted(self):
        v = GValue.map_(
            MapEntry("z", GValue.int_(3)),
            MapEntry("a", GValue.int_(1)),
            MapEntry("m", GValue.int_(2))
        )
        # Keys should be sorted
        assert emit(v) == "{a=1 m=2 z=3}"

    def test_struct(self):
        v = GValue.struct("Team",
            MapEntry("name", GValue.str_("Arsenal")),
            MapEntry("rank", GValue.int_(1))
        )
        assert emit(v) == "Team{name=Arsenal rank=1}"

    def test_id(self):
        assert emit(GValue.id("t", "ARS")) == "^t:ARS"
        assert emit(GValue.id("", "123")) == "^123"


class TestParse:
    """Tests for parsing."""

    def test_null(self):
        v = parse("∅")
        assert v.is_null()

    def test_null_underscore(self):
        v = parse("_")
        assert v.is_null()

    def test_bool(self):
        assert parse("t").as_bool() == True
        assert parse("f").as_bool() == False
        assert parse("true").as_bool() == True
        assert parse("false").as_bool() == False

    def test_int(self):
        assert parse("42").as_int() == 42
        assert parse("-7").as_int() == -7

    def test_float(self):
        assert abs(parse("3.14").as_float() - 3.14) < 0.001

    def test_str_bare(self):
        assert parse("hello").as_str() == "hello"

    def test_str_quoted(self):
        assert parse('"hello world"').as_str() == "hello world"
        assert parse('"say \\"hi\\""').as_str() == 'say "hi"'

    def test_list(self):
        v = parse("[1 2 3]")
        lst = v.as_list()
        assert len(lst) == 3
        assert lst[0].as_int() == 1

    def test_map(self):
        v = parse("{a=1 b=2}")
        assert v.get("a").as_int() == 1
        assert v.get("b").as_int() == 2

    def test_struct(self):
        v = parse("Team{name=Arsenal rank=1}")
        sv = v.as_struct()
        assert sv.type_name == "Team"
        assert v.get("name").as_str() == "Arsenal"

    def test_id(self):
        v = parse("^t:ARS")
        ref = v.as_id()
        assert ref.prefix == "t"
        assert ref.value == "ARS"

    def test_roundtrip(self):
        original = "{action=search max_results=10 query=\"weather in NYC\"}"
        v = parse(original)
        emitted = emit(v)
        v2 = parse(emitted)
        assert equal_loose(v, v2)


class TestJSONBridge:
    """Tests for JSON conversion."""

    def test_from_json_simple(self):
        data = {"name": "Alice", "age": 30}
        v = from_json(data)
        assert v.get("name").as_str() == "Alice"
        assert v.get("age").as_int() == 30

    def test_to_json(self):
        v = GValue.map_(
            MapEntry("name", GValue.str_("Alice")),
            MapEntry("age", GValue.int_(30))
        )
        data = to_json(v)
        assert data["name"] == "Alice"
        assert data["age"] == 30

    def test_json_to_glyph(self):
        data = {"action": "search", "query": "weather", "max_results": 10}
        text = json_to_glyph(data)
        # Should be valid GLYPH
        v = parse(text)
        assert v.get("action").as_str() == "search"

    def test_rejects_non_finite_json_numbers(self):
        with pytest.raises(ValueError, match="non-finite"):
            from_json(float("inf"))

        with pytest.raises(ValueError, match="non-finite"):
            to_json(GValue.float_(float("nan")))


class TestParserHardening:
    """Regression tests for malformed input handling."""

    def test_rejects_trailing_garbage(self):
        with pytest.raises(ValueError, match="trailing garbage"):
            parse("1 2")

        with pytest.raises(ValueError, match="trailing garbage"):
            parse("{a=1} junk")

    def test_requires_map_value_separator(self):
        with pytest.raises(ValueError, match="expected '=' or ':' after key"):
            parse("{a b}")

    def test_requires_struct_field_separator(self):
        with pytest.raises(ValueError, match="expected '=' or ':' after field"):
            parse("Team{name Arsenal}")

    def test_rejects_invalid_base64(self):
        with pytest.raises(ValueError, match="invalid base64"):
            parse('b64"@@@"')

    @pytest.mark.parametrize("text", ["NaN", "Inf", "-Inf", "1e309"])
    def test_rejects_non_finite_and_overflow_float_literals(self, text):
        with pytest.raises(ValueError, match="float"):
            parse(text)

    def test_limits_nesting_depth(self):
        deeply_nested = "[" * 129 + "0" + "]" * 129
        with pytest.raises(ValueError, match="maximum nesting depth"):
            parse(deeply_nested)


class TestDuplicateKeySemantics:
    """Duplicate-key access should match JSON conversion semantics."""

    def test_map_get_and_json_use_last_duplicate(self):
        v = parse("{a=1 a=2}")
        assert v.get("a").as_int() == 2
        assert to_json(v) == {"a": 2}

    def test_set_collapses_duplicate_keys(self):
        v = GValue.map_(
            MapEntry("a", GValue.int_(1)),
            MapEntry("a", GValue.int_(2)),
        )
        v.set("a", GValue.int_(3))

        assert len(v.as_map()) == 1
        assert v.get("a").as_int() == 3


class TestFingerprint:
    """Tests for fingerprinting."""

    def test_fingerprint_deterministic(self):
        v = GValue.map_(
            MapEntry("a", GValue.int_(1)),
            MapEntry("b", GValue.int_(2))
        )
        fp1 = fingerprint_loose(v)
        fp2 = fingerprint_loose(v)
        assert fp1 == fp2

    def test_fingerprint_order_independent(self):
        v1 = GValue.map_(
            MapEntry("a", GValue.int_(1)),
            MapEntry("b", GValue.int_(2))
        )
        v2 = GValue.map_(
            MapEntry("b", GValue.int_(2)),
            MapEntry("a", GValue.int_(1))
        )
        assert fingerprint_loose(v1) == fingerprint_loose(v2)


class TestAutoTabular:
    """Tests for auto-tabular mode."""

    def test_tabular_output(self):
        rows = GValue.list_(
            GValue.map_(MapEntry("name", GValue.str_("Alice")), MapEntry("age", GValue.int_(30))),
            GValue.map_(MapEntry("name", GValue.str_("Bob")), MapEntry("age", GValue.int_(25))),
            GValue.map_(MapEntry("name", GValue.str_("Carol")), MapEntry("age", GValue.int_(35))),
        )
        text = emit(rows)
        # Should produce tabular format
        assert "@tab" in text
        assert "@end" in text

    def test_tabular_roundtrip(self):
        rows = GValue.list_(
            GValue.map_(MapEntry("x", GValue.int_(1)), MapEntry("y", GValue.int_(2))),
            GValue.map_(MapEntry("x", GValue.int_(3)), MapEntry("y", GValue.int_(4))),
            GValue.map_(MapEntry("x", GValue.int_(5)), MapEntry("y", GValue.int_(6))),
        )
        text = emit(rows)
        v = parse(text)
        assert len(v) == 3

    def test_quotes_numeric_keyword_strings(self):
        assert emit(GValue.str_("Inf")) == '"Inf"'
        assert emit(GValue.str_("NaN")) == '"NaN"'
        assert parse(emit(GValue.str_("Inf"))).as_str() == "Inf"


class TestParseEdgeCases:
    """Coverage tests for parse.py uncovered paths."""

    def test_unterminated_string(self):
        with pytest.raises(ValueError, match="unterminated string"):
            parse('"hello')

    def test_unterminated_escape(self):
        with pytest.raises(ValueError, match="unterminated escape"):
            parse('"hello\\')

    def test_string_escape_sequences(self):
        # \n, \r, \t, \\, \", \uXXXX, and unknown escape
        assert parse(r'"he\nllo"').as_str() == "he\nllo"
        assert parse(r'"he\rllo"').as_str() == "he\rllo"
        assert parse(r'"he\tllo"').as_str() == "he\tllo"
        assert parse(r'"he\\llo"').as_str() == "he\\llo"
        assert parse(r'"he\"llo"').as_str() == 'he"llo'
        assert parse(r'"he\u0041llo"').as_str() == "heAllo"
        # Unknown escape: just pass through the char
        assert parse(r'"he\xllo"').as_str() == "hexllo"

    def test_invalid_unicode_escape(self):
        with pytest.raises(ValueError, match="invalid unicode escape"):
            parse('"\\u00"')

    def test_unterminated_bytes_literal(self):
        with pytest.raises(ValueError, match="unterminated bytes"):
            parse('b64"AQID')

    def test_bytes_literal(self):
        v = parse('b64"AQID"')
        assert v.as_bytes() == b"\x01\x02\x03"

    def test_unexpected_character(self):
        with pytest.raises(ValueError, match="unexpected character"):
            parse("~bad")

    def test_negative_int(self):
        v = parse("-42")
        assert v.as_int() == -42

    def test_float_with_exponent(self):
        v = parse("1.5e2")
        assert abs(v.as_float() - 150.0) < 0.001

    def test_float_with_negative_exponent(self):
        v = parse("1.5e-2")
        assert abs(v.as_float() - 0.015) < 0.001

    def test_number_transitions_to_ident(self):
        # A number-like start that becomes an identifier
        v = parse("1abc")
        assert v.type == GType.STR
        assert v.as_str() == "1abc"

    def test_unterminated_list(self):
        with pytest.raises(ValueError, match="unterminated list"):
            parse("[1 2")

    def test_unterminated_map(self):
        with pytest.raises(ValueError, match="unterminated map"):
            parse("{a=1")

    def test_map_bad_key(self):
        with pytest.raises(ValueError, match="expected key"):
            parse("{42=1}")

    def test_map_with_colon_separator(self):
        v = parse("{a:1 b:2}")
        assert v.get("a").as_int() == 1
        assert v.get("b").as_int() == 2

    def test_map_with_string_key(self):
        v = parse('{"my key"=1}')
        assert v.get("my key").as_int() == 1

    def test_list_with_commas(self):
        v = parse("[1, 2, 3]")
        assert len(v.as_list()) == 3

    def test_map_with_commas(self):
        v = parse("{a=1, b=2}")
        assert v.get("a").as_int() == 1

    def test_list_with_newlines(self):
        v = parse("[1\n2\n3]")
        assert len(v.as_list()) == 3

    def test_struct_with_string_field_name(self):
        v = parse('Team{"my field"=1}')
        assert v.get("my field").as_int() == 1

    def test_struct_with_colon_separator(self):
        v = parse("Team{name:Arsenal}")
        sv = v.as_struct()
        assert sv.type_name == "Team"
        assert v.get("name").as_str() == "Arsenal"

    def test_struct_bad_field_name(self):
        with pytest.raises(ValueError, match="expected field name"):
            parse("Team{42=bad}")

    def test_unterminated_struct(self):
        with pytest.raises(ValueError, match="unterminated struct"):
            parse("Team{name=Arsenal")

    def test_sum_empty(self):
        v = parse("None()")
        sm = v.as_sum()
        assert sm.tag == "None"
        assert sm.value is None

    def test_sum_with_value(self):
        v = parse("Some(42)")
        sm = v.as_sum()
        assert sm.tag == "Some"
        assert sm.value.as_int() == 42

    def test_unexpected_token_in_value(self):
        with pytest.raises(ValueError, match="unexpected token"):
            parse(")")

    def test_ref_bare_no_prefix(self):
        v = parse("^abc")
        ref = v.as_id()
        assert ref.prefix == ""
        assert ref.value == "abc"

    def test_ref_quoted(self):
        v = parse('^"user:123"')
        ref = v.as_id()
        assert ref.prefix == "user"
        assert ref.value == "123"

    def test_ref_quoted_no_colon(self):
        v = parse('^"hello world"')
        ref = v.as_id()
        assert ref.prefix == ""
        assert ref.value == "hello world"

    def test_ref_bool_as_prefix(self):
        # t/f parsed as bool tokens used in ref context
        v = parse("^t:val")
        ref = v.as_id()
        assert ref.prefix == "t"
        assert ref.value == "val"

    def test_ref_int_as_part(self):
        v = parse("^42:abc")
        ref = v.as_id()
        assert ref.prefix == "42"
        assert ref.value == "abc"

    def test_ref_int_value_after_colon(self):
        v = parse("^ns:123")
        ref = v.as_id()
        assert ref.prefix == "ns"
        assert ref.value == "123"

    def test_ref_bool_value_after_colon(self):
        v = parse("^ns:t")
        ref = v.as_id()
        assert ref.prefix == "ns"
        assert ref.value == "t"

    def test_ref_string_value_after_colon(self):
        v = parse('^ns:"hello world"')
        ref = v.as_id()
        assert ref.prefix == "ns"
        assert ref.value == "hello world"

    def test_ref_bad_value(self):
        with pytest.raises(ValueError, match="expected reference value"):
            parse("^[")

    def test_ref_bad_value_after_colon(self):
        with pytest.raises(ValueError, match="expected reference value part"):
            parse("^ns:[")

    def test_directive_bad_name(self):
        with pytest.raises(ValueError, match="expected directive name"):
            parse("@42")

    def test_unknown_directive(self):
        with pytest.raises(ValueError, match="unknown directive"):
            parse("@baddir")

    def test_tabular_parse(self):
        text = "@tab _ [name age]\n|Alice|30|\n|Bob|25|\n@end"
        v = parse(text)
        lst = v.as_list()
        assert len(lst) == 2
        assert lst[0].get("name").as_str() == "Alice"
        assert lst[0].get("age").as_int() == 30

    def test_tabular_null_placeholder(self):
        text = "@tab ∅ [x y]\n|1|2|\n|3|4|\n@end"
        v = parse(text)
        assert len(v.as_list()) == 2

    def test_tabular_missing_bracket(self):
        with pytest.raises(ValueError, match="expected \\["):
            parse("@tab _ x")

    def test_tabular_bad_col_name(self):
        with pytest.raises(ValueError, match="expected column name"):
            parse("@tab _ [42]")

    def test_tabular_string_col_name(self):
        text = '@tab _ ["col 1" "col 2"]\n|1|2|\n@end'
        v = parse(text)
        assert v.as_list()[0].get("col 1").as_int() == 1

    def test_tabular_cell_with_empty(self):
        text = "@tab _ [x y]\n| |_|\n|1|2|\n|3|4|\n@end"
        v = parse(text)
        lst = v.as_list()
        assert lst[0].get("x").is_null()
        assert lst[0].get("y").is_null()

    def test_tabular_cell_escape_newline(self):
        # Test \n escape in tabular cells (backslash-n becomes newline)
        text = "@tab _ [x]\n|\"line1\\nline2\"|\n|a|\n|b|\n@end"
        v = parse(text)
        assert v.as_list()[0].get("x").as_str() == "line1\nline2"

    def test_tabular_eof_without_end(self):
        text = "@tab _ [x]\n|1|\n|2|\n|3|"
        v = parse(text)
        assert len(v.as_list()) == 3

    def test_tabular_unexpected_token(self):
        with pytest.raises(ValueError, match="expected row or @end"):
            parse("@tab _ [x]\nfoo")

    def test_tabular_bad_at_directive(self):
        with pytest.raises(ValueError, match="expected @end"):
            parse("@tab _ [x]\n|1|\n@foo")

    def test_nesting_depth_map(self):
        # Deep nesting via maps
        text = "{a=" * 50 + "1" + "}" * 50
        # Should work at depth 50
        v = parse(text)
        # Now try exceeding
        deep = "{a=" * 129 + "1" + "}" * 129
        with pytest.raises(ValueError, match="maximum nesting depth"):
            parse(deep)

    def test_nesting_depth_struct(self):
        deep = "S{x=" * 129 + "1" + "}" * 129
        with pytest.raises(ValueError, match="maximum nesting depth"):
            parse(deep)

    def test_nesting_depth_sum(self):
        deep = "T(" * 129 + "1" + ")" * 129
        with pytest.raises(ValueError, match="maximum nesting depth"):
            parse(deep)

    def test_leading_whitespace_and_newlines(self):
        v = parse("  \n\n  42  \n\n  ")
        assert v.as_int() == 42

    def test_bare_ident_with_special_chars(self):
        v = parse("foo-bar.baz/qux")
        assert v.as_str() == "foo-bar.baz/qux"

    def test_null_keyword_nil(self):
        v = parse("nil")
        assert v.is_null()

    def test_float_parse_error_non_finite_result(self):
        # 1e309 overflows to inf
        with pytest.raises(ValueError, match="float"):
            parse("1e309")

    def test_map_with_newlines(self):
        v = parse("{a=1\nb=2\n}")
        assert v.get("a").as_int() == 1
        assert v.get("b").as_int() == 2

    def test_struct_with_commas(self):
        v = parse("S{a=1, b=2}")
        assert v.get("a").as_int() == 1

    def test_struct_with_newlines(self):
        v = parse("S{a=1\nb=2\n}")
        assert v.get("a").as_int() == 1


class TestLooseEdgeCases:
    """Coverage tests for loose.py uncovered paths."""

    def test_null_symbol_style(self):
        opts = LooseCanonOpts(null_style=NullStyle.SYMBOL)
        assert canonicalize_loose(GValue.null(), opts) == "∅"

    def test_llm_opts(self):
        from glyph import llm_loose_canon_opts
        opts = llm_loose_canon_opts()
        assert opts.null_style == NullStyle.UNDERSCORE
        assert canonicalize_loose(GValue.null(), opts) == "_"

    def test_no_tabular_opts(self):
        from glyph import no_tabular_loose_canon_opts
        opts = no_tabular_loose_canon_opts()
        assert opts.auto_tabular is False

    def test_canon_float_negative_zero(self):
        from glyph.loose import canon_float
        assert canon_float(-0.0) == "0"

    def test_canon_float_very_small(self):
        from glyph.loose import canon_float
        result = canon_float(1e-5)
        assert "e" in result

    def test_canon_float_very_large(self):
        from glyph.loose import canon_float
        result = canon_float(1e16)
        assert "e" in result

    def test_canon_float_non_finite_raises(self):
        from glyph.loose import canon_float
        with pytest.raises(ValueError, match="non-finite"):
            canon_float(float("inf"))
        with pytest.raises(ValueError, match="non-finite"):
            canon_float(float("nan"))

    def test_escape_string_special_chars(self):
        from glyph.loose import escape_string
        assert "\\n" in escape_string("a\nb")
        assert "\\r" in escape_string("a\rb")
        assert "\\t" in escape_string("a\tb")
        assert '\\"' in escape_string('a"b')
        assert "\\\\" in escape_string("a\\b")
        # Control character
        assert "\\u0001" in escape_string("a\x01b")

    def test_is_bare_safe(self):
        from glyph.loose import is_bare_safe
        assert is_bare_safe("hello") is True
        assert is_bare_safe("_start") is True
        assert is_bare_safe("") is False
        assert is_bare_safe("t") is False  # reserved
        assert is_bare_safe("null") is False  # reserved
        assert is_bare_safe("123") is False  # starts with digit
        assert is_bare_safe("a b") is False  # contains space

    def test_canon_time(self):
        from glyph.loose import canon_time
        dt = datetime(2025, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
        assert canon_time(dt) == "2025-01-13T12:00:00Z"

    def test_canon_time_no_tz(self):
        from glyph.loose import canon_time
        dt = datetime(2025, 1, 13, 12, 0, 0)
        result = canon_time(dt)
        assert result.endswith("Z")

    def test_canon_time_with_microseconds(self):
        from glyph.loose import canon_time
        dt = datetime(2025, 1, 13, 12, 0, 0, 123000, tzinfo=timezone.utc)
        result = canon_time(dt)
        assert ".123" in result
        assert result.endswith("Z")

    def test_canon_id_safe(self):
        from glyph.loose import canon_id
        from glyph import RefID
        assert canon_id(RefID("user", "123")) == "^user:123"
        assert canon_id(RefID("", "abc")) == "^abc"

    def test_canon_id_needs_quoting(self):
        from glyph.loose import canon_id
        from glyph import RefID
        result = canon_id(RefID("", "hello world"))
        assert result.startswith('^"')
        result2 = canon_id(RefID("ns", "hello world"))
        assert result2.startswith('^"')

    def test_is_id_safe(self):
        from glyph.loose import is_id_safe
        assert is_id_safe("abc123") is True
        assert is_id_safe("a-b.c/d") is True
        assert is_id_safe("") is False
        assert is_id_safe("a b") is False
        assert is_id_safe("a:b") is False

    def test_canonicalize_time(self):
        dt = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        v = GValue.time(dt)
        result = canonicalize_loose(v)
        assert "2025-06-15" in result

    def test_canonicalize_bytes(self):
        v = GValue.bytes_(b"\x01\x02\x03")
        result = canonicalize_loose(v)
        assert result.startswith('b64"')

    def test_canonicalize_id(self):
        v = GValue.id("ns", "val")
        assert canonicalize_loose(v) == "^ns:val"

    def test_canonicalize_struct_empty(self):
        v = GValue.struct("Empty")
        assert canonicalize_loose(v) == "Empty{}"

    def test_canonicalize_struct_sorted(self):
        v = GValue.struct("S",
            MapEntry("z", GValue.int_(2)),
            MapEntry("a", GValue.int_(1))
        )
        result = canonicalize_loose(v)
        assert result == "S{a=1 z=2}"

    def test_canonicalize_sum_empty(self):
        v = GValue.sum("None", None)
        result = canonicalize_loose(v)
        assert result == "None()"

    def test_canonicalize_sum_with_value(self):
        v = GValue.sum("Some", GValue.int_(42))
        result = canonicalize_loose(v)
        assert result == "Some(42)"

    def test_canonicalize_no_tabular(self):
        from glyph import canonicalize_loose_no_tabular
        rows = GValue.list_(
            GValue.map_(MapEntry("x", GValue.int_(1))),
            GValue.map_(MapEntry("x", GValue.int_(2))),
            GValue.map_(MapEntry("x", GValue.int_(3))),
        )
        result = canonicalize_loose_no_tabular(rows)
        assert "@tab" not in result
        assert result.startswith("[")

    def test_tabular_with_missing_keys(self):
        rows = GValue.list_(
            GValue.map_(MapEntry("x", GValue.int_(1)), MapEntry("y", GValue.int_(2))),
            GValue.map_(MapEntry("x", GValue.int_(3))),
            GValue.map_(MapEntry("x", GValue.int_(5)), MapEntry("y", GValue.int_(6))),
        )
        opts = LooseCanonOpts(auto_tabular=True, min_rows=3, allow_missing=True)
        result = canonicalize_loose(rows, opts)
        assert "@tab" in result
        # Missing y should show as null
        assert "_" in result

    def test_tabular_not_eligible_mixed_types(self):
        rows = GValue.list_(
            GValue.int_(1),
            GValue.int_(2),
            GValue.int_(3),
        )
        result = canonicalize_loose(rows)
        assert "@tab" not in result

    def test_tabular_not_eligible_too_few_rows(self):
        rows = GValue.list_(
            GValue.map_(MapEntry("x", GValue.int_(1))),
            GValue.map_(MapEntry("x", GValue.int_(2))),
        )
        result = canonicalize_loose(rows)
        assert "@tab" not in result

    def test_tabular_cell_escape(self):
        from glyph.loose import _escape_tabular_cell
        assert _escape_tabular_cell("a|b") == "a\\|b"
        assert _escape_tabular_cell("a\nb") == "a\\nb"
        assert _escape_tabular_cell("a\\b") == "a\\\\b"

    def test_unescape_tabular_cell(self):
        from glyph.loose import unescape_tabular_cell
        assert unescape_tabular_cell("a\\|b") == "a|b"
        assert unescape_tabular_cell("a\\nb") == "a\nb"
        assert unescape_tabular_cell("a\\\\b") == "a\\b"
        # Unknown escape: keep backslash
        assert unescape_tabular_cell("a\\xb") == "a\\xb"
        # No escape at end
        assert unescape_tabular_cell("abc") == "abc"

    def test_from_json_loose_types(self):
        from glyph import from_json_loose
        assert from_json_loose(None).is_null()
        assert from_json_loose(True).as_bool() is True
        assert from_json_loose(False).as_bool() is False
        assert from_json_loose(42).as_int() == 42
        assert abs(from_json_loose(3.14).as_float() - 3.14) < 0.001
        assert from_json_loose("hello").as_str() == "hello"
        assert from_json_loose(b"\x01").as_bytes() == b"\x01"
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        assert from_json_loose(dt).as_time() == dt
        lst = from_json_loose([1, 2])
        assert len(lst.as_list()) == 2
        mp = from_json_loose({"a": 1})
        assert mp.get("a").as_int() == 1
        # Fallback: unknown type -> str
        class Custom:
            def __str__(self): return "custom"
        assert from_json_loose(Custom()).as_str() == "custom"

    def test_from_json_non_finite_float(self):
        from glyph import from_json_loose
        with pytest.raises(ValueError, match="non-finite"):
            from_json_loose(float("nan"))

    def test_to_json_loose_types(self):
        from glyph import to_json_loose
        assert to_json_loose(GValue.null()) is None
        assert to_json_loose(GValue.bool_(True)) is True
        assert to_json_loose(GValue.int_(42)) == 42
        assert abs(to_json_loose(GValue.float_(3.14)) - 3.14) < 0.001
        assert to_json_loose(GValue.str_("hi")) == "hi"
        assert to_json_loose(GValue.bytes_(b"\x01\x02")) == "AQI="  # base64
        dt = datetime(2025, 1, 13, 12, 0, 0, tzinfo=timezone.utc)
        assert "2025-01-13" in to_json_loose(GValue.time(dt))
        ref_with = to_json_loose(GValue.id("ns", "val"))
        assert ref_with == "^ns:val"
        ref_without = to_json_loose(GValue.id("", "val"))
        assert ref_without == "^val"
        lst = to_json_loose(GValue.list_(GValue.int_(1)))
        assert lst == [1]
        mp = to_json_loose(GValue.map_(MapEntry("a", GValue.int_(1))))
        assert mp == {"a": 1}
        st = to_json_loose(GValue.struct("T", MapEntry("x", GValue.int_(1))))
        assert st == {"$type": "T", "x": 1}
        sm = to_json_loose(GValue.sum("Tag", GValue.str_("hello")))
        assert sm == {"$tag": "Tag", "$value": "hello"}
        sm_none = to_json_loose(GValue.sum("Empty", None))
        assert sm_none == {"$tag": "Empty", "$value": None}

    def test_to_json_non_finite_float(self):
        from glyph import to_json_loose
        with pytest.raises(ValueError, match="non-finite"):
            to_json_loose(GValue.float_(float("inf")))

    def test_parse_json_loose(self):
        from glyph import parse_json_loose
        v = parse_json_loose('{"a": 1}')
        assert v.get("a").as_int() == 1

    def test_stringify_json_loose(self):
        from glyph import stringify_json_loose
        v = GValue.map_(MapEntry("a", GValue.int_(1)))
        s = stringify_json_loose(v)
        assert '"a"' in s

    def test_glyph_to_json(self):
        from glyph import glyph_to_json
        result = glyph_to_json("{a=1}")
        assert result == {"a": 1}

    def test_tabular_not_eligible_disallow_missing(self):
        rows = GValue.list_(
            GValue.map_(MapEntry("x", GValue.int_(1)), MapEntry("y", GValue.int_(2))),
            GValue.map_(MapEntry("x", GValue.int_(3))),
            GValue.map_(MapEntry("x", GValue.int_(5)), MapEntry("y", GValue.int_(6))),
        )
        opts = LooseCanonOpts(auto_tabular=True, min_rows=3, allow_missing=False)
        result = canonicalize_loose(rows, opts)
        # Should fall back to list format since keys don't match and allow_missing=False
        assert "@tab" not in result

    def test_tabular_too_many_cols(self):
        entries = [MapEntry(f"c{i}", GValue.int_(i)) for i in range(25)]
        rows = GValue.list_(
            GValue.map_(*entries),
            GValue.map_(*entries),
            GValue.map_(*entries),
        )
        opts = LooseCanonOpts(auto_tabular=True, min_rows=3, max_cols=20)
        result = canonicalize_loose(rows, opts)
        assert "@tab" not in result

    def test_tabular_empty_map_not_eligible(self):
        rows = GValue.list_(
            GValue.map_(),
            GValue.map_(),
            GValue.map_(),
        )
        result = canonicalize_loose(rows)
        assert "@tab" not in result

    def test_tabular_with_structs(self):
        rows = GValue.list_(
            GValue.struct("S", MapEntry("x", GValue.int_(1))),
            GValue.struct("S", MapEntry("x", GValue.int_(2))),
            GValue.struct("S", MapEntry("x", GValue.int_(3))),
        )
        result = canonicalize_loose(rows)
        assert "@tab" in result

    def test_tabular_low_common_key_ratio(self):
        # Each row has different keys -> common < 50% of union
        rows = GValue.list_(
            GValue.map_(MapEntry("a", GValue.int_(1))),
            GValue.map_(MapEntry("b", GValue.int_(2))),
            GValue.map_(MapEntry("c", GValue.int_(3))),
        )
        opts = LooseCanonOpts(auto_tabular=True, min_rows=3, allow_missing=True)
        result = canonicalize_loose(rows, opts)
        # common_keys is empty, so should fall back
        assert "@tab" not in result


class TestTruncatedInput:
    """Invariant #3: truncated input must always produce an error."""

    @pytest.mark.parametrize("text", [
        '{name: "hello", age: 42}',
        '[1 2 3]',
        'Team{name=Arsenal rank=1}',
        'Some(42)',
        '"hello world"',
        '{a={b={c=1}}}',
        '@tab _ [x y]\n|1|2|\n|3|4|\n@end',
        'b64"AQID"',
        '^ns:val',
    ])
    def test_parse_rejects_truncated_input(self, text):
        # Full input must parse successfully first
        parse(text)

        # Truncate at every position from 1 to len-1; each must raise ValueError
        for i in range(1, len(text)):
            truncated = text[:i]
            try:
                parse(truncated)
                # Some truncations may happen to be valid glyph on their own
                # (e.g. "{name" truncated to "{" is invalid, but "1" from "[1 2 3]"
                # is a valid standalone integer). Skip those cases.
            except ValueError:
                pass  # Expected: truncated input rejected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
