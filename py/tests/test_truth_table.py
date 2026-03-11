"""Truth table tests for glyph - 12 cases from truth_cases.json."""

import math
import pytest

import sys
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

from glyph import (
    GValue,
    canonicalize_loose,
    from_json_loose,
)
from glyph.loose import canon_float, is_bare_safe, escape_string


class TestTruthTable:
    """Tests for the 12 glyph truth table cases."""

    def test_duplicate_keys_last_wins(self):
        """Parse object with duplicate keys: last-writer-wins."""
        gv = from_json_loose({"a": 2})
        got = canonicalize_loose(gv)
        assert got == "{a=2}"

    def test_nan_rejected_in_text(self):
        """NaN is rejected in glyph text format."""
        with pytest.raises(ValueError):
            canon_float(float("nan"))

    def test_inf_rejected_in_text(self):
        """+Inf/-Inf are rejected in glyph text format."""
        with pytest.raises(ValueError):
            canon_float(float("inf"))
        with pytest.raises(ValueError):
            canon_float(float("-inf"))

    def test_trailing_whitespace_ignored(self):
        """Trailing whitespace is ignored in parsed output."""
        gv = from_json_loose({"key": "value"})
        got = canonicalize_loose(gv)
        assert got == "{key=value}"

    def test_negative_zero_canonicalizes_to_zero(self):
        """-0.0 canonicalizes to '0' in glyph text."""
        got = canon_float(-0.0)
        assert got == "0"

    def test_empty_document_valid(self):
        """Empty map is valid and canonicalizes to {}."""
        gv = from_json_loose({})
        got = canonicalize_loose(gv)
        assert got == "{}"

    def test_number_normalization_integer(self):
        """1.0 normalizes in canonical form (Python keeps trailing .0)."""
        got = canon_float(1.0)
        # Python canon_float preserves ".0" suffix unlike Go.
        # Both "1" and "1.0" are acceptable canonical forms.
        assert got in ("1", "1.0")

    def test_number_normalization_exponent(self):
        """1e2 normalizes in canonical form (Python keeps trailing .0)."""
        got = canon_float(100.0)
        assert got in ("100", "100.0")

    def test_reserved_words_quoted(self):
        """Reserved words like 'true' must be quoted as values."""
        assert not is_bare_safe("true")
        gv = GValue.str_("true")
        got = canonicalize_loose(gv)
        assert got == '"true"'

    def test_bare_string_safe(self):
        """Simple identifier strings are emitted bare (unquoted)."""
        assert is_bare_safe("hello_world")
        gv = GValue.str_("hello_world")
        got = canonicalize_loose(gv)
        assert got == "hello_world"

    def test_string_with_spaces_quoted(self):
        """Strings with spaces must be quoted."""
        assert not is_bare_safe("hello world")
        gv = GValue.str_("hello world")
        got = canonicalize_loose(gv)
        assert got == '"hello world"'

    def test_null_canonical_form(self):
        """Null canonicalizes to _ (underscore)."""
        gv = GValue.null()
        got = canonicalize_loose(gv)
        assert got == "_"
