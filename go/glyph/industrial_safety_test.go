package glyph

import (
	"math"
	"strings"
	"testing"
	"unicode/utf8"
)

// =============================================================================
// INDUSTRIAL SAFETY TESTS — GLYPH PARSER
//
// Covers: parser bombs, string handling, injection, tolerant-mode semantics,
// type coercion, Unicode edge cases, and input size limits.
//
// Run:  go test -v -run TestIndustrial ./go/glyph/
// Race: go test -race -run TestIndustrial ./go/glyph/
// =============================================================================

// ---------------------------------------------------------------------------
// 1. Parser bombs — recursion depth
// ---------------------------------------------------------------------------

func TestIndustrial_DeepNesting_Map(t *testing.T) {
	// Build deeply nested map: {a: {a: {a: ... }}}
	depths := []int{100, 500, 1000, 5000}
	for _, depth := range depths {
		t.Run(strings.Repeat("_", 1), func(t *testing.T) {
			var b strings.Builder
			for i := 0; i < depth; i++ {
				b.WriteString("{a: ")
			}
			b.WriteString("1")
			for i := 0; i < depth; i++ {
				b.WriteString("}")
			}

			func() {
				defer func() {
					if r := recover(); r != nil {
						t.Errorf("PANIC at depth %d: %v (need recursion limit)", depth, r)
					}
				}()
				_, err := Parse(b.String())
				// Either parse succeeds or returns error — both acceptable. Panic is not.
				_ = err
			}()
		})
	}
}

func TestIndustrial_DeepNesting_List(t *testing.T) {
	depths := []int{100, 500, 1000, 5000}
	for _, depth := range depths {
		var b strings.Builder
		for i := 0; i < depth; i++ {
			b.WriteString("[")
		}
		b.WriteString("1")
		for i := 0; i < depth; i++ {
			b.WriteString("]")
		}

		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("PANIC at depth %d: %v (need recursion limit)", depth, r)
				}
			}()
			_, err := Parse(b.String())
			_ = err
		}()
	}
}

func TestIndustrial_DeepNesting_Struct(t *testing.T) {
	depths := []int{100, 500, 1000}
	for _, depth := range depths {
		var b strings.Builder
		for i := 0; i < depth; i++ {
			b.WriteString("Outer{inner: ")
		}
		b.WriteString("1")
		for i := 0; i < depth; i++ {
			b.WriteString("}")
		}

		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("PANIC at depth %d: %v (need recursion limit)", depth, r)
				}
			}()
			_, err := Parse(b.String())
			_ = err
		}()
	}
}

func TestIndustrial_DeepNesting_Emit(t *testing.T) {
	// Build deeply nested GValue programmatically
	var v *GValue = Int(42)
	for i := 0; i < 1000; i++ {
		v = Map(MapEntry{Key: "n", Value: v})
	}

	func() {
		defer func() {
			if r := recover(); r != nil {
				t.Errorf("PANIC in Emit with deep nesting: %v", r)
			}
		}()
		_ = Emit(v)
	}()
}

// ---------------------------------------------------------------------------
// 2. String handling — null bytes, control chars, unterminated
// ---------------------------------------------------------------------------

func TestIndustrial_NullByteInString(t *testing.T) {
	// Embedded null byte in quoted string (escaped)
	input := `"hello\u0000world"`
	result, err := Parse(input)
	if err != nil {
		t.Skipf("parse error (acceptable): %v", err)
	}
	s, sErr := result.Value.AsStr()
	if sErr != nil {
		t.Skipf("AsStr error (acceptable): %v", sErr)
	}
	// If null byte passes through, flag it
	for i := 0; i < len(s); i++ {
		if s[i] == 0 {
			t.Logf("WARNING: null byte at position %d survives parsing (may cause C interop issues)", i)
			break
		}
	}
}

func TestIndustrial_ControlCharsInString(t *testing.T) {
	// Control characters 0x01-0x1F in strings
	for c := byte(1); c < 0x20; c++ {
		input := `"` + string([]byte{c}) + `"`
		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("PANIC on control char 0x%02X: %v", c, r)
				}
			}()
			_, _ = Parse(input)
		}()
	}
}

func TestIndustrial_UnterminatedString(t *testing.T) {
	inputs := []string{
		`"hello`,       // no closing quote
		`"hello\`,      // trailing backslash
		`"hello\"`,     // escaped quote at end (still no close)
		`{key: "value`, // in map context
		`[1 "partial`,  // in list context
	}
	for _, input := range inputs {
		t.Run("", func(t *testing.T) {
			func() {
				defer func() {
					if r := recover(); r != nil {
						t.Errorf("PANIC on unterminated string %q: %v", input[:min(len(input), 20)], r)
					}
				}()
				// Tolerant mode should handle gracefully
				result, err := Parse(input)
				if err != nil {
					return // Error is fine
				}
				if result != nil && len(result.Warnings) > 0 {
					t.Logf("warnings: %v", result.Warnings[0].Message)
				}
			}()
		})
	}
}

func TestIndustrial_HugeString(t *testing.T) {
	// 10MB string — should not crash, but may be slow
	big := `"` + strings.Repeat("x", 10*1024*1024) + `"`
	func() {
		defer func() {
			if r := recover(); r != nil {
				t.Errorf("PANIC on 10MB string: %v", r)
			}
		}()
		result, err := Parse(big)
		if err != nil {
			return
		}
		s, sErr := result.Value.AsStr()
		if sErr != nil {
			return
		}
		if s == "" {
			t.Error("parsed empty from 10MB string")
		}
	}()
}

// ---------------------------------------------------------------------------
// 3. Injection — GLYPH → JSON bridge
// ---------------------------------------------------------------------------

func TestIndustrial_JSONBridge_HugeKey(t *testing.T) {
	// 1MB key in JSON → GLYPH
	bigKey := strings.Repeat("k", 1024*1024)
	json := []byte(`{"` + bigKey + `": 1}`)

	func() {
		defer func() {
			if r := recover(); r != nil {
				t.Errorf("PANIC on 1MB JSON key: %v", r)
			}
		}()
		gv, err := FromJSONLoose(json)
		if err != nil {
			return // rejection is fine
		}
		// Round-trip back to JSON
		out, err := ToJSONLoose(gv)
		if err != nil {
			t.Logf("round-trip error (acceptable): %v", err)
			return
		}
		if len(out) < 1024*1024 {
			t.Error("key was silently truncated")
		}
	}()
}

func TestIndustrial_JSONBridge_SpecialChars(t *testing.T) {
	// Keys with special characters that could cause injection
	keys := []string{
		`"`,           // quote in key
		`\`,           // backslash
		`</script>`,   // HTML injection
		"\n\r\t",      // whitespace
		"null",        // keyword
		"true",        // keyword
	}
	for _, key := range keys {
		t.Run(key[:min(len(key), 8)], func(t *testing.T) {
			gv := Map(MapEntry{Key: key, Value: Int(1)})
			out, err := ToJSONLoose(gv)
			if err != nil {
				return // rejection acceptable
			}
			// Verify JSON is well-formed by round-tripping
			_, err = FromJSONLoose(out)
			if err != nil {
				t.Errorf("GLYPH→JSON→GLYPH round-trip broken for key %q: %v", key, err)
			}
		})
	}
}

func TestIndustrial_JSONBridge_DeepNesting(t *testing.T) {
	// Build deeply nested JSON
	depth := 500
	var b strings.Builder
	for i := 0; i < depth; i++ {
		b.WriteString(`{"a":`)
	}
	b.WriteString("1")
	for i := 0; i < depth; i++ {
		b.WriteString("}")
	}

	func() {
		defer func() {
			if r := recover(); r != nil {
				t.Errorf("PANIC on deep JSON→GLYPH: %v", r)
			}
		}()
		_, err := FromJSONLoose([]byte(b.String()))
		_ = err
	}()
}

// ---------------------------------------------------------------------------
// 4. Tolerant mode — auto-close semantics
// ---------------------------------------------------------------------------

func TestIndustrial_TolerantAutoClose_DataIntegrity(t *testing.T) {
	// Truncated input should not silently produce wrong data
	tests := []struct {
		name     string
		input    string
		wantKey  string
		wantVal  string
		wantWarn bool // expect warnings about auto-close
	}{
		{
			name:     "truncated_map",
			input:    `{id: "123" secret: "hidden"`,
			wantKey:  "id",
			wantVal:  "123",
			wantWarn: true,
		},
		{
			name:     "truncated_list",
			input:    `[1 2 3`,
			wantKey:  "",
			wantVal:  "",
			wantWarn: true,
		},
		{
			name:     "truncated_struct",
			input:    `User{name: "alice" role: "admin"`,
			wantKey:  "name",
			wantVal:  "alice",
			wantWarn: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := Parse(tt.input)
			if err != nil {
				t.Skipf("parse error (strict mode): %v", err)
			}

			if tt.wantWarn && len(result.Warnings) == 0 {
				t.Error("expected warnings about auto-close, got none — truncation is SILENT")
			}

			if tt.wantKey != "" {
				v := result.Value.Get(tt.wantKey)
				if v == nil {
					t.Errorf("expected key %q extractable from truncated input", tt.wantKey)
				} else {
					s, sErr := v.AsStr()
					if sErr != nil {
						t.Errorf("AsStr error for key %q: %v", tt.wantKey, sErr)
					} else if s != tt.wantVal {
						t.Errorf("key %q = %q, want %q", tt.wantKey, s, tt.wantVal)
					}
				}
			}
		})
	}
}

func TestIndustrial_StrictMode_RejectsTruncated(t *testing.T) {
	// In strict mode, truncated input MUST error
	inputs := []string{
		`{a: 1`,
		`[1 2`,
		`Foo{x: 1`,
	}
	for _, input := range inputs {
		t.Run("", func(t *testing.T) {
			result, err := ParseWithOptions(input, ParseOptions{Tolerant: false})
			if err == nil && (result == nil || !result.HasErrors()) {
				t.Errorf("strict mode accepted truncated input %q without error", input)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// 5. Type coercion — lossy round-trips
// ---------------------------------------------------------------------------

func TestIndustrial_Int64PrecisionLoss_JSONBridge(t *testing.T) {
	// Integers beyond 2^53 lose precision in JSON (float64)
	values := []int64{
		9007199254740992, // 2^53 — exact boundary
		9007199254740993, // 2^53 + 1 — CANNOT be represented in float64
		math.MaxInt64,
		math.MinInt64,
	}
	for _, val := range values {
		t.Run("", func(t *testing.T) {
			gv := Int(val)
			jsonBytes, err := ToJSONLoose(gv)
			if err != nil {
				t.Skipf("ToJSONLoose error: %v", err)
			}
			gv2, err := FromJSONLoose(jsonBytes)
			if err != nil {
				t.Skipf("FromJSONLoose error: %v", err)
			}

			// After JSON round-trip, large ints may come back as float
			if gv2.Type() != TypeInt {
				t.Logf("FINDING: int64 %d became %s after JSON round-trip (precision loss)", val, gv2.Type())
				return
			}
			rt, rtErr := gv2.AsInt()
			if rtErr != nil {
				t.Skipf("AsInt error: %v", rtErr)
			}
			if rt != val {
				t.Errorf("int64 precision lost: %d → %d (delta=%d)",
					val, rt, val-rt)
			}
		})
	}
}

func TestIndustrial_FloatSpecialValues(t *testing.T) {
	// NaN, Inf, -Inf should round-trip or be explicitly rejected
	specials := []struct {
		name string
		val  float64
	}{
		{"NaN", math.NaN()},
		{"Inf", math.Inf(1)},
		{"-Inf", math.Inf(-1)},
		{"SmallestNonzero", math.SmallestNonzeroFloat64},
		{"MaxFloat64", math.MaxFloat64},
	}
	for _, tt := range specials {
		t.Run(tt.name, func(t *testing.T) {
			gv := Float(tt.val)
			emitted := Emit(gv)

			// Parse back
			result, err := Parse(emitted)
			if err != nil {
				t.Logf("parse error for %s (may be expected): %v", tt.name, err)
				return
			}
			if result.Value == nil {
				t.Errorf("parsed nil for %s", tt.name)
				return
			}

			// After round-trip, special values may change type (NaN→str "NaN")
			if result.Value.Type() != TypeFloat {
				t.Logf("FINDING: float %s became %s after round-trip (type changed)", tt.name, result.Value.Type())
				return
			}
			got, gotErr := result.Value.AsFloat()
			if gotErr != nil {
				t.Errorf("AsFloat error: %v", gotErr)
				return
			}
			if math.IsNaN(tt.val) {
				if !math.IsNaN(got) {
					t.Errorf("NaN did not round-trip: got %v", got)
				}
			} else if got != tt.val {
				t.Errorf("%s did not round-trip: %v → %v", tt.name, tt.val, got)
			}
		})
	}
}

func TestIndustrial_FloatSpecialValues_JSONBridge(t *testing.T) {
	// NaN/Inf in GLYPH→JSON should be handled, not crash
	specials := []float64{math.NaN(), math.Inf(1), math.Inf(-1)}
	for _, val := range specials {
		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("PANIC on float special value %v in JSON bridge: %v", val, r)
				}
			}()
			gv := Float(val)
			_, err := ToJSONLoose(gv)
			if err != nil {
				t.Logf("JSON bridge rejects %v (expected): %v", val, err)
			}
		}()
	}
}

// ---------------------------------------------------------------------------
// 6. Unicode edge cases
// ---------------------------------------------------------------------------

func TestIndustrial_InvalidUTF8(t *testing.T) {
	invalid := []struct {
		name  string
		bytes string
	}{
		{"lone_surrogate_utf8", "\"hello\xED\xA0\x80world\""},
		{"overlong_null", "\"hello\xC0\x80world\""},
		{"truncated_2byte", "\"hello\xC3\""},
		{"truncated_3byte", "\"hello\xE0\xA0\""},
		{"truncated_4byte", "\"hello\xF0\x90\x80\""},
		{"invalid_continuation", "\"hello\x80world\""},
	}
	for _, tt := range invalid {
		t.Run(tt.name, func(t *testing.T) {
			func() {
				defer func() {
					if r := recover(); r != nil {
						t.Errorf("PANIC on invalid UTF-8 %q: %v", tt.name, r)
					}
				}()
				result, err := Parse(tt.bytes)
				if err != nil {
					return // rejection is fine
				}
				if result.Value != nil {
					s, sErr := result.Value.AsStr()
					if sErr != nil {
						return
					}
					if !utf8.ValidString(s) {
						t.Logf("FINDING: invalid UTF-8 survived parsing in %q — needs sanitization for C interop/JSON", tt.name)
					}
				}
			}()
		})
	}
}

func TestIndustrial_InvalidUTF8_JSONBridge(t *testing.T) {
	// GValue with invalid UTF-8 → JSON should not produce invalid JSON
	badStr := "hello\xED\xA0\x80world" // lone surrogate
	gv := Str(badStr)

	func() {
		defer func() {
			if r := recover(); r != nil {
				t.Errorf("PANIC on invalid UTF-8 in JSON bridge: %v", r)
			}
		}()
		out, err := ToJSONLoose(gv)
		if err != nil {
			return // rejection fine
		}
		if !utf8.Valid(out) {
			t.Error("JSON output contains invalid UTF-8")
		}
	}()
}

// ---------------------------------------------------------------------------
// 7. Input size limits
// ---------------------------------------------------------------------------

func TestIndustrial_LargeInput_NoOOM(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping large input test in short mode")
	}
	// 50MB of trivial GLYPH — should not OOM
	size := 50 * 1024 * 1024
	input := "[" + strings.Repeat("1 ", size/2) + "]"

	func() {
		defer func() {
			if r := recover(); r != nil {
				t.Errorf("PANIC on %dMB input: %v", size/(1024*1024), r)
			}
		}()
		_, err := Parse(input)
		_ = err
	}()
}

func TestIndustrial_ManyKeys_NoOOM(t *testing.T) {
	// Map with 100k keys — should not OOM or be extremely slow
	var b strings.Builder
	b.WriteString("{")
	for i := 0; i < 100000; i++ {
		if i > 0 {
			b.WriteString(" ")
		}
		b.WriteString("k")
		b.WriteString(strings.Repeat("x", 10))
		b.WriteString(string(rune('0' + i%10)))
		b.WriteString(": ")
		b.WriteString("1")
	}
	b.WriteString("}")

	func() {
		defer func() {
			if r := recover(); r != nil {
				t.Errorf("PANIC on 100k-key map: %v", r)
			}
		}()
		_, err := Parse(b.String())
		_ = err
	}()
}

// ---------------------------------------------------------------------------
// 8. GLYPH round-trip integrity
// ---------------------------------------------------------------------------

func TestIndustrial_RoundTrip_AllTypes(t *testing.T) {
	// Every GLYPH type must survive Parse → Emit → Parse
	values := map[string]*GValue{
		"null":       Null(),
		"true":       Bool(true),
		"false":      Bool(false),
		"int":        Int(42),
		"int_neg":    Int(-999),
		"float":      Float(3.14159),
		"string":     Str("hello world"),
		"empty_str":  Str(""),
		"escaped_str": Str(`line1\nline2\ttab`),
		"list":       List(Int(1), Int(2), Int(3)),
		"map":        Map(MapEntry{"a", Int(1)}, MapEntry{"b", Str("two")}),
		"struct":     Struct("Point", MapEntry{"x", Float(1.0)}, MapEntry{"y", Float(2.0)}),
		"nested":     Map(MapEntry{"inner", List(Map(MapEntry{"deep", Int(99)}))}),
	}

	for name, original := range values {
		t.Run(name, func(t *testing.T) {
			emitted := Emit(original)
			result, err := Parse(emitted)
			if err != nil {
				t.Fatalf("round-trip parse failed for %s: %v\nemitted: %s", name, err, emitted)
			}
			reEmitted := Emit(result.Value)
			if emitted != reEmitted {
				t.Errorf("round-trip mismatch for %s:\n  first:  %s\n  second: %s", name, emitted, reEmitted)
			}
		})
	}
}

func TestIndustrial_RoundTrip_JSONBridge(t *testing.T) {
	// GLYPH → JSON → GLYPH must preserve data (within JSON's type limits)
	values := map[string]*GValue{
		"null":   Null(),
		"bool":   Bool(true),
		"int":    Int(42),
		"float":  Float(3.14),
		"string": Str("hello"),
		"list":   List(Int(1), Str("two"), Bool(false)),
		"map":    Map(MapEntry{"key", Str("value")}),
	}

	for name, original := range values {
		t.Run(name, func(t *testing.T) {
			jsonBytes, err := ToJSONLoose(original)
			if err != nil {
				t.Fatalf("ToJSONLoose: %v", err)
			}
			roundTripped, err := FromJSONLoose(jsonBytes)
			if err != nil {
				t.Fatalf("FromJSONLoose: %v", err)
			}
			// Re-emit both and compare
			origStr := Emit(original)
			rtStr := Emit(roundTripped)
			if origStr != rtStr {
				t.Errorf("JSON round-trip mismatch:\n  original: %s\n  roundtrip: %s", origStr, rtStr)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// 9. Fuzz targets (for `go test -fuzz`)
// ---------------------------------------------------------------------------

func FuzzParse(f *testing.F) {
	// Seed corpus
	f.Add(`{a: 1 b: "hello"}`)
	f.Add(`[1 2 3]`)
	f.Add(`User{name: "alice" age: 30}`)
	f.Add(`"hello world"`)
	f.Add(`42`)
	f.Add(`true`)
	f.Add(`null`)
	f.Add(`{deeply: {nested: {value: 1}}}`)
	f.Add(`Ok(42)`)
	f.Add(`Err("fail")`)
	f.Add(`"escape sequences: \n \t \\ \""`)
	f.Add(`{a: "unterminated`)
	f.Add(`[1 2 3`)

	f.Fuzz(func(t *testing.T, input string) {
		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("PANIC on input %q: %v", input[:min(len(input), 100)], r)
				}
			}()
			result, err := Parse(input)
			if err != nil {
				return
			}
			// If parse succeeds, emit should not panic
			if result.Value != nil {
				_ = Emit(result.Value)
			}
		}()
	})
}

func FuzzFromJSONLoose(f *testing.F) {
	f.Add([]byte(`{"key": "value"}`))
	f.Add([]byte(`[1, 2, 3]`))
	f.Add([]byte(`"hello"`))
	f.Add([]byte(`42`))
	f.Add([]byte(`null`))
	f.Add([]byte(`{"nested": {"deep": [1, {"x": true}]}}`))

	f.Fuzz(func(t *testing.T, data []byte) {
		func() {
			defer func() {
				if r := recover(); r != nil {
					t.Errorf("PANIC on JSON input: %v", r)
				}
			}()
			gv, err := FromJSONLoose(data)
			if err != nil {
				return
			}
			// Round-trip: GLYPH→JSON should not panic
			_, _ = ToJSONLoose(gv)
		}()
	})
}
