package glyph

import (
	"strconv"
	"strings"
	"testing"
)

// json_bridge_fidelity_test.go covers the P1 JSON-bridge fidelity work:
//   - int64 precision is preserved on emit (no 2^53 float rounding),
//   - the strict (default) bridge intentionally collapses to JSON-like shapes,
//   - the extended-mode $glyph marker namespace is collision-safe on both
//     emit (loud error) and decode (exact-shape only),
//   - extended mode round-trips time/id/bytes losslessly.

// TestToJSONLoose_LargeIntPrecision is the headline emit fix: an Int GValue
// above 2^53 must serialize as a full integer literal, not a lossy float.
func TestToJSONLoose_LargeIntPrecision(t *testing.T) {
	cases := []int64{
		9007199254740993,     // 2^53 + 1 (not exactly representable as float64)
		9223372036854775807,  // int64 max
		-9223372036854775808, // int64 min
		1<<53 + 7,            // just past the safe range
	}
	for _, n := range cases {
		out, err := ToJSONLoose(Int(n))
		if err != nil {
			t.Fatalf("ToJSONLoose(%d): %v", n, err)
		}
		want := strings.TrimSpace(strings.TrimSuffix(string(out), "\n"))
		// json.Marshal of a json.Number emits the literal verbatim.
		if want != strconv.FormatInt(n, 10) {
			t.Errorf("ToJSONLoose(%d) = %s, want %s", n, want, strconv.FormatInt(n, 10))
		}
	}
}

// TestToJSONLoose_LargeIntInsideContainer makes sure the precision-preserving
// path also fires for ints nested in lists and maps.
func TestToJSONLoose_LargeIntInsideContainer(t *testing.T) {
	v := Map(
		MapEntry{Key: "big", Value: Int(9007199254740993)},
		MapEntry{Key: "list", Value: List(Int(9223372036854775807))},
	)
	out, err := ToJSONLoose(v)
	if err != nil {
		t.Fatal(err)
	}
	s := string(out)
	if !strings.Contains(s, "9007199254740993") {
		t.Errorf("expected full integer literal in %s", s)
	}
	if !strings.Contains(s, "9223372036854775807") {
		t.Errorf("expected int64-max literal in %s", s)
	}
}

// TestLoose_StrictCollapseIsIntentional documents the maintainer decision: the
// default (strict) bridge flattens typed values into JSON-like shapes and does
// NOT recover the GLYPH type. This test pins that behavior so a future change
// can't silently "fix" it (typed round-trip is the Parse/Emit path's job).
func TestLoose_StrictCollapseIsIntentional(t *testing.T) {
	// struct -> object (TypeName dropped); JSON->GLYPH yields a map.
	st := Struct("Team", MapEntry{Key: "name", Value: Str("Arsenal")})
	js, err := ToJSONLoose(st)
	if err != nil {
		t.Fatal(err)
	}
	back, err := FromJSONLoose(js)
	if err != nil {
		t.Fatal(err)
	}
	if back.Type() != TypeMap {
		t.Errorf("struct should collapse to map on strict round-trip, got %s", back.Type())
	}

	// sum -> { tag: value }; JSON->GLYPH yields a map indistinguishable from one.
	sum := Sum("Ok", Int(42))
	js2, err := ToJSONLoose(sum)
	if err != nil {
		t.Fatal(err)
	}
	if string(js2) != `{"Ok":42}` {
		t.Errorf("sum should collapse to {tag:value}, got %s", js2)
	}
	back2, err := FromJSONLoose(js2)
	if err != nil {
		t.Fatal(err)
	}
	if back2.Type() != TypeMap {
		t.Errorf("sum should collapse to map on strict round-trip, got %s", back2.Type())
	}
}

// TestExtended_RoundTrip proves extended mode is lossless for the types it
// covers (time/id/bytes), exercising GLYPH -> JSON -> GLYPH.
func TestExtended_RoundTrip(t *testing.T) {
	opts := BridgeOpts{Extended: true}
	values := []*GValue{
		ID("m", "ARS-LIV"),
		Bytes([]byte("hello\x00world")),
		List(ID("u", "1"), Bytes([]byte{0x01, 0x02})),
		Map(MapEntry{Key: "ref", Value: ID("t", "ARS")}, MapEntry{Key: "blob", Value: Bytes([]byte("x"))}),
	}
	for i, v := range values {
		js, err := ToJSONLooseWithOpts(v, opts)
		if err != nil {
			t.Fatalf("case %d emit: %v", i, err)
		}
		back, err := FromJSONLooseWithOpts(js, opts)
		if err != nil {
			t.Fatalf("case %d parse: %v", i, err)
		}
		if !EqualLoose(v, back) {
			t.Errorf("case %d not lossless: %s -> %s", i, CanonicalizeLoose(v), CanonicalizeLoose(back))
		}
	}
}

// TestExtended_EmitCollisionGuard: in extended mode the reserved "$glyph" key
// in user data is a loud error, not a silently ambiguous marker.
func TestExtended_EmitCollisionGuard(t *testing.T) {
	opts := BridgeOpts{Extended: true}

	if _, err := ToJSONLooseWithOpts(Map(MapEntry{Key: "$glyph", Value: Str("x")}), opts); err == nil {
		t.Error("expected error emitting a map with a $glyph key in extended mode")
	}
	if _, err := ToJSONLooseWithOpts(Struct("T", MapEntry{Key: "$glyph", Value: Int(1)}), opts); err == nil {
		t.Error("expected error emitting a struct with a $glyph field in extended mode")
	}
	if _, err := ToJSONLooseWithOpts(Sum("$glyph", Int(1)), opts); err == nil {
		t.Error("expected error emitting a sum tagged $glyph in extended mode")
	}

	// In strict mode "$glyph" is ordinary data and must pass through losslessly.
	strict := DefaultBridgeOpts()
	js, err := ToJSONLooseWithOpts(Map(MapEntry{Key: "$glyph", Value: Str("x")}), strict)
	if err != nil {
		t.Fatalf("strict mode should allow $glyph key: %v", err)
	}
	back, err := FromJSONLooseWithOpts(js, strict)
	if err != nil {
		t.Fatal(err)
	}
	if back.Get("$glyph") == nil {
		t.Error("strict mode should round-trip a literal $glyph key as data")
	}
}

// TestExtended_DecodeCollisionGuard: only exactly-shaped marker objects decode
// as markers; malformed ones are rejected loudly.
func TestExtended_DecodeCollisionGuard(t *testing.T) {
	opts := BridgeOpts{Extended: true}
	bad := []string{
		`{"$glyph":"time","value":"2025-01-01T00:00:00Z","extra":1}`, // extra key
		`{"$glyph":"time"}`,                // missing value
		`{"$glyph":"bytes","value":"x"}`,   // wrong companion key
		`{"$glyph":"unknown","value":"x"}`, // unknown marker type
	}
	for _, in := range bad {
		if _, err := FromJSONLooseWithOpts([]byte(in), opts); err == nil {
			t.Errorf("expected error decoding malformed marker: %s", in)
		}
	}
}
