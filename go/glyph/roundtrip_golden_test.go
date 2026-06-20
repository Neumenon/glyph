package glyph

import (
	"bytes"
	"math"
	"strings"
	"testing"
	"time"
)

// roundtrip_golden_test.go asserts the P0 invariant for the main typed
// Parse/Emit path: Parse(Emit(v)) == v across every GType. These tests encode
// *why* the codec is trustworthy — anything the emitter writes must read back as
// the identical value, so a producer and consumer can never silently disagree.

// gvalEqual is a semantic deep-equality for GValues. Bytes compare by content,
// times by instant, NaN floats compare equal to each other (so the float NaN
// sentinel can be asserted to round-trip), and maps/structs compare by key set
// rather than entry order (the emitter canonically sorts them).
func gvalEqual(a, b *GValue) bool {
	if a.IsNull() || b.IsNull() {
		return a.IsNull() && b.IsNull()
	}
	if a.Type() != b.Type() {
		return false
	}
	switch a.Type() {
	case TypeBool:
		return a.boolVal == b.boolVal
	case TypeInt:
		return a.intVal == b.intVal
	case TypeFloat:
		af, bf := a.floatVal, b.floatVal
		if math.IsNaN(af) || math.IsNaN(bf) {
			return math.IsNaN(af) && math.IsNaN(bf)
		}
		return af == bf
	case TypeStr:
		return a.strVal == b.strVal
	case TypeBytes:
		return bytes.Equal(a.bytesVal, b.bytesVal)
	case TypeTime:
		return a.timeVal.Equal(b.timeVal)
	case TypeID:
		return a.idVal == b.idVal
	case TypeList:
		if len(a.listVal) != len(b.listVal) {
			return false
		}
		for i := range a.listVal {
			if !gvalEqual(a.listVal[i], b.listVal[i]) {
				return false
			}
		}
		return true
	case TypeMap:
		return mapEntriesEqual(a.mapVal, b.mapVal)
	case TypeStruct:
		if a.structVal.TypeName != b.structVal.TypeName {
			return false
		}
		return mapEntriesEqual(a.structVal.Fields, b.structVal.Fields)
	case TypeSum:
		return a.sumVal.Tag == b.sumVal.Tag && gvalEqual(a.sumVal.Value, b.sumVal.Value)
	}
	return false
}

// mapEntriesEqual compares entries by key (order-independent). It assumes unique
// keys, which holds for emitter output and for parser output after the last-wins
// duplicate-key collapse.
func mapEntriesEqual(a, b []MapEntry) bool {
	if len(a) != len(b) {
		return false
	}
	bm := make(map[string]*GValue, len(b))
	for _, e := range b {
		bm[e.Key] = e.Value
	}
	for _, e := range a {
		bv, ok := bm[e.Key]
		if !ok || !gvalEqual(e.Value, bv) {
			return false
		}
	}
	return true
}

// assertRoundTrip emits v, parses the result, and verifies no errors plus
// semantic equality with the original.
func assertRoundTrip(t *testing.T, name string, v *GValue) {
	t.Helper()
	emitted := Emit(v)
	res, err := Parse(emitted)
	if err != nil {
		t.Errorf("%s: Parse(%q) returned error: %v", name, emitted, err)
		return
	}
	if res.HasErrors() {
		t.Errorf("%s: Parse(%q) reported errors: %v", name, emitted, res.Errors)
		return
	}
	if !gvalEqual(res.Value, v) {
		t.Errorf("%s: round-trip mismatch (emitted %q)\n  want: %#v\n  got:  %#v", name, emitted, v, res.Value)
	}
}

func TestRoundTripScalars(t *testing.T) {
	cases := []struct {
		name string
		v    *GValue
	}{
		{"null", Null()},
		{"bool-true", Bool(true)},
		{"bool-false", Bool(false)},
		{"int-zero", Int(0)},
		{"int-pos", Int(42)},
		{"int-neg", Int(-42)},
		{"int-max", Int(math.MaxInt64)},
		{"int-min", Int(math.MinInt64)},
		{"float-simple", Float(1.5)},
		{"float-neg", Float(-2.25)},
		{"float-zero", Float(0)},
		{"float-whole", Float(3)},
		{"float-large", Float(1e300)},
		{"float-small", Float(1e-300)},
		{"id-prefixed", ID("m", "123")},
		{"id-bare", ID("", "plain")},
		{"id-dotted", ID("t", "a-b.c")},
		{"time-utc", Time(time.Date(2025, 12, 19, 20, 0, 0, 0, time.UTC))},
		{"time-offset", Time(time.Date(2025, 6, 1, 9, 30, 15, 0, time.FixedZone("x", 2*3600)))},
	}
	for _, tc := range cases {
		assertRoundTrip(t, tc.name, tc.v)
	}
}

// TestRoundTripFloatSentinels documents the NaN/Inf policy: they round-trip as
// the documented sentinels NaN / Inf / -Inf (NaN via gvalEqual's NaN==NaN rule).
func TestRoundTripFloatSentinels(t *testing.T) {
	assertRoundTrip(t, "nan", Float(math.NaN()))
	assertRoundTrip(t, "inf", Float(math.Inf(1)))
	assertRoundTrip(t, "neg-inf", Float(math.Inf(-1)))
}

func TestRoundTripStrings(t *testing.T) {
	strs := []string{
		"hello",          // bare-eligible identifier
		"",               // empty
		"with space",     // space forces quoting
		"with\"quote",    // embedded quote
		"with\\back",     // embedded backslash
		"with\ttab",      // tab control char
		"with\nnewline",  // newline control char
		"with\rreturn",   // carriage return
		"ctl\x01\x02end", // sub-0x20 control chars (emitted as \uXXXX)
		"café",           // non-ASCII letters
		"日本語",            // multi-byte Unicode
		"with-hyphen",    // hyphen (ASCII lexer rejects bare)
		"with.dot",       // dot
		"with/slash",     // slash
		"with|pipe",      // pipe
		"123",            // digit-leading: must quote or it parses as int
		"-5",             // leading minus: must quote
		"true",           // keyword: must quote to stay a string
		"t",              // single-letter keyword
		"null",           // null keyword
		"NaN",            // float keyword
		"b64",            // bytes prefix without a following quote
	}
	for _, s := range strs {
		assertRoundTrip(t, "str:"+s, Str(s))
	}
}

func TestRoundTripBytes(t *testing.T) {
	cases := []struct {
		name string
		b    []byte
	}{
		{"empty", []byte{}},
		{"simple", []byte("hello")},
		{"binary", []byte{0, 1, 2, 254, 255}},
		{"all", func() []byte {
			b := make([]byte, 256)
			for i := range b {
				b[i] = byte(i)
			}
			return b
		}()},
	}
	for _, tc := range cases {
		assertRoundTrip(t, "bytes:"+tc.name, Bytes(tc.b))
	}
}

func TestRoundTripContainers(t *testing.T) {
	mixedList := List(
		Null(),
		Bool(true),
		Int(7),
		Float(1.25),
		Str("with space"),
		Bytes([]byte{1, 2, 3}),
		Time(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)),
		ID("m", "9"),
	)
	assertRoundTrip(t, "list-mixed", mixedList)
	assertRoundTrip(t, "list-nested", List(List(Int(1), Int(2)), List(Str("a"), Str("b"))))

	// Map with out-of-order keys (emitter sorts) and a key that needs quoting.
	assertRoundTrip(t, "map", Map(
		FieldVal("z", Int(1)),
		FieldVal("a", Str("x")),
		FieldVal("with space", Bool(false)),
	))

	assertRoundTrip(t, "struct", Struct("Point",
		FieldVal("x", Int(3)),
		FieldVal("y", Int(-4)),
		FieldVal("label", Str("origin pt")),
	))

	// Sum with scalar, list and map payloads all round-trip. (Sum with a struct
	// payload is intentionally excluded: the Tag{...} emission is ambiguous with
	// a plain struct on parse — a documented P1 grammar gap, see PR notes.)
	assertRoundTrip(t, "sum-scalar", Sum("Some", Int(5)))
	assertRoundTrip(t, "sum-null", Sum("None", Null()))
	assertRoundTrip(t, "sum-list", Sum("Many", List(Int(1), Int(2))))
	assertRoundTrip(t, "sum-map", Sum("Obj", Map(FieldVal("k", Str("v")))))

	// A deeper nested document.
	assertRoundTrip(t, "nested-doc", Struct("Doc",
		FieldVal("items", List(
			Map(FieldVal("id", ID("i", "1")), FieldVal("data", Bytes([]byte{9, 8, 7}))),
			Map(FieldVal("id", ID("i", "2")), FieldVal("tags", List(Str("a-b"), Str("c/d")))),
		)),
		FieldVal("count", Int(2)),
	))
}

// TestRoundTripIntOverflowErrors verifies that an integer literal that overflows
// int64 is a parse error, not a silently-clamped wrong value.
func TestRoundTripIntOverflowErrors(t *testing.T) {
	res, _ := Parse("9223372036854775808") // math.MaxInt64 + 1
	if !res.HasErrors() {
		t.Fatalf("expected overflow to produce a parse error, got value %#v", res.Value)
	}
	if !res.Value.IsNull() {
		t.Errorf("expected null value on overflow, got %#v", res.Value)
	}
}

// TestRoundTripInvalidBase64Errors verifies invalid base64 is a hard error and
// is never silently coerced to a string.
func TestRoundTripInvalidBase64Errors(t *testing.T) {
	res, _ := Parse(`b64"!@#$"`)
	if !res.HasErrors() {
		t.Fatalf("expected invalid base64 to produce a parse error, got value %#v", res.Value)
	}
	if res.Value.Type() == TypeStr {
		t.Errorf("invalid base64 must not be coerced to a string, got %#v", res.Value)
	}
}

// TestDuplicateMapKeyLastWins documents and verifies the duplicate-key policy.
func TestDuplicateMapKeyLastWins(t *testing.T) {
	res, err := Parse(`{a:1 a:2 b:3}`)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(res.Warnings) == 0 {
		t.Errorf("expected a warning for the duplicate key")
	}
	m := res.Value
	if got := m.Len(); got != 2 {
		t.Errorf("expected 2 entries after dedup, got %d", got)
	}
	a := m.Get("a")
	if a == nil || a.typ != TypeInt || a.intVal != 2 {
		t.Errorf("expected last-wins a=2, got %#v", a)
	}
}

// TestTolerantNullCoercionIsLoud verifies that the tolerant-mode unexpected-token
// -> null coercion always emits a warning (never silent).
func TestTolerantNullCoercionIsLoud(t *testing.T) {
	res, _ := Parse("=") // an unexpected token at value position
	if !res.Value.IsNull() {
		t.Errorf("expected null coercion, got %#v", res.Value)
	}
	found := false
	for _, w := range res.Warnings {
		if strings.Contains(w.Message, "coercing to null") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected a loud 'coercing to null' warning, got %v", res.Warnings)
	}
}
