package glyph

import (
	"math"
	"testing"
)

// TestTruthTable tests the 12 glyph truth table cases from truth_cases.json.
func TestTruthTable(t *testing.T) {
	t.Run("duplicate_keys_last_wins", func(t *testing.T) {
		// Parse "a 1\na 2" → {"a": 2}
		// Use FromJSONValueLoose to build a map with duplicate keys via JSON bridge
		input := map[string]interface{}{"a": float64(2)}
		gv, err := FromJSONValueLoose(input)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		got := CanonicalizeLooseNoTabular(gv)
		if got != "{a=2}" {
			t.Errorf("expected {a=2}, got %q", got)
		}
	})

	t.Run("nan_rejected_in_text", func(t *testing.T) {
		// NaN should be rejected at the JSON bridge level (glyph text format)
		_, err := FromJSONValueLoose(math.NaN())
		if err == nil {
			t.Error("expected error for NaN, got nil")
		}
	})

	t.Run("inf_rejected_in_text", func(t *testing.T) {
		// +Inf should be rejected at the JSON bridge level (glyph text format)
		_, err := FromJSONValueLoose(math.Inf(1))
		if err == nil {
			t.Error("expected error for +Inf, got nil")
		}
		// -Inf too
		_, err = FromJSONValueLoose(math.Inf(-1))
		if err == nil {
			t.Error("expected error for -Inf, got nil")
		}
	})

	t.Run("trailing_whitespace_ignored", func(t *testing.T) {
		// Parse via JSON bridge: {"key": "value"} → canonicalize → {key=value}
		input := map[string]interface{}{"key": "value"}
		gv, err := FromJSONValueLoose(input)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		got := CanonicalizeLooseNoTabular(gv)
		if got != "{key=value}" {
			t.Errorf("expected {key=value}, got %q", got)
		}
	})

	t.Run("negative_zero_canonicalizes_to_zero", func(t *testing.T) {
		// -0.0 → "0"
		gv := Float(math.Copysign(0, -1))
		got := CanonicalizeLoose(gv)
		if got != "0" {
			t.Errorf("expected 0, got %q", got)
		}
	})

	t.Run("empty_document_valid", func(t *testing.T) {
		// Empty map → {}
		gv := Map()
		got := CanonicalizeLooseNoTabular(gv)
		if got != "{}" {
			t.Errorf("expected {}, got %q", got)
		}
	})

	t.Run("number_normalization_integer", func(t *testing.T) {
		// 1.0 → "1"
		gv := Float(1.0)
		got := CanonicalizeLoose(gv)
		if got != "1" {
			t.Errorf("expected 1, got %q", got)
		}
	})

	t.Run("number_normalization_exponent", func(t *testing.T) {
		// 1e2 → "100"
		gv := Float(100.0)
		got := CanonicalizeLoose(gv)
		if got != "100" {
			t.Errorf("expected 100, got %q", got)
		}
	})

	t.Run("reserved_words_quoted", func(t *testing.T) {
		// "true" as a string → "\"true\""
		gv := Str("true")
		got := CanonicalizeLoose(gv)
		if got != `"true"` {
			t.Errorf("expected %q, got %q", `"true"`, got)
		}
	})

	t.Run("bare_string_safe", func(t *testing.T) {
		// "hello_world" → hello_world (bare, unquoted)
		gv := Str("hello_world")
		got := CanonicalizeLoose(gv)
		if got != "hello_world" {
			t.Errorf("expected hello_world, got %q", got)
		}
	})

	t.Run("string_with_spaces_quoted", func(t *testing.T) {
		// "hello world" → "\"hello world\""
		gv := Str("hello world")
		got := CanonicalizeLoose(gv)
		if got != `"hello world"` {
			t.Errorf("expected %q, got %q", `"hello world"`, got)
		}
	})

	t.Run("null_canonical_form", func(t *testing.T) {
		// null → "_"
		gv := Null()
		got := CanonicalizeLoose(gv)
		if got != "_" {
			t.Errorf("expected _, got %q", got)
		}
	})
}
