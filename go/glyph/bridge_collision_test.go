//go:build cogs

package glyph

import (
	"testing"
	"time"

	cowrie "github.com/Neumenon/cowrie/go/v2"
)

// TestBridge_CollisionFix_CaretString verifies that a cowrie string beginning
// with "^" is decoded as Str in strict mode and not reinterpreted as an ID.
// This was the original collision bug at bridge.go:100-106.
func TestBridge_CollisionFix_CaretString(t *testing.T) {
	cv := cowrie.String("^not-an-id")
	gv := FromSJSON(cv)

	if gv.Type() != TypeStr {
		t.Fatalf("expected TypeStr, got %s", gv.Type())
	}
	s, err := gv.AsStr()
	if err != nil || s != "^not-an-id" {
		t.Errorf("expected string %q, got %q (err=%v)", "^not-an-id", s, err)
	}
}

// TestBridge_CollisionFix_TypeObject verifies that a cowrie object with
// "_type" string is decoded as Map in strict mode, not reinterpreted as Struct.
// This was the original collision bug at bridge.go:126-137.
func TestBridge_CollisionFix_TypeObject(t *testing.T) {
	cv := cowrie.Object(
		cowrie.Member{Key: "_type", Value: cowrie.String("x")},
		cowrie.Member{Key: "foo", Value: cowrie.Int64(1)},
	)
	gv := FromSJSON(cv)

	if gv.Type() != TypeMap {
		t.Fatalf("expected TypeMap (not Struct), got %s", gv.Type())
	}
}

// TestBridge_CollisionFix_TagObject verifies that a cowrie object with
// "_tag" string is decoded as Map in strict mode, not reinterpreted as Sum.
// This was the original collision bug at bridge.go:140-145.
func TestBridge_CollisionFix_TagObject(t *testing.T) {
	cv := cowrie.Object(
		cowrie.Member{Key: "_tag", Value: cowrie.String("ok")},
		cowrie.Member{Key: "_value", Value: cowrie.Int64(42)},
	)
	gv := FromSJSON(cv)

	if gv.Type() != TypeMap {
		t.Fatalf("expected TypeMap (not Sum), got %s", gv.Type())
	}
}

// TestBridge_Extended_IDRoundTrip verifies that TypeID values round-trip
// losslessly in extended mode via the $glyph id marker.
func TestBridge_Extended_IDRoundTrip(t *testing.T) {
	cases := []*GValue{
		ID("m", "ARS-LIV"),
		ID("ns", "path/value"),
		ID("ns", "a:b"),
		ID("", "bare"),
	}

	opts := BridgeOpts{Extended: true}
	for _, v := range cases {
		want := Emit(v)
		cv, err := ToSJSONWithOpts(v, opts)
		if err != nil {
			t.Errorf("ToSJSONWithOpts(%s): %v", want, err)
			continue
		}
		back, err := FromSJSONWithOpts(cv, opts)
		if err != nil {
			t.Errorf("FromSJSONWithOpts(%s): %v", want, err)
			continue
		}
		if got := Emit(back); got != want {
			t.Errorf("ID round-trip: want %q got %q", want, got)
		}
	}
}

// TestBridge_Extended_StructRoundTrip verifies that TypeStruct values
// round-trip losslessly (TypeName preserved) in extended mode.
func TestBridge_Extended_StructRoundTrip(t *testing.T) {
	v := Struct("Match",
		MapEntry{Key: "id", Value: ID("m", "ARS-LIV")},
		MapEntry{Key: "score", Value: Int(2)},
	)
	opts := BridgeOpts{Extended: true}

	cv, err := ToSJSONWithOpts(v, opts)
	if err != nil {
		t.Fatalf("ToSJSONWithOpts: %v", err)
	}
	back, err := FromSJSONWithOpts(cv, opts)
	if err != nil {
		t.Fatalf("FromSJSONWithOpts: %v", err)
	}
	if back.Type() != TypeStruct {
		t.Fatalf("expected TypeStruct, got %s", back.Type())
	}
	want := Emit(v)
	if got := Emit(back); got != want {
		t.Errorf("Struct round-trip: want %q got %q", want, got)
	}
}

// TestBridge_Extended_SumRoundTrip verifies that TypeSum values round-trip
// losslessly in extended mode.
func TestBridge_Extended_SumRoundTrip(t *testing.T) {
	v := Sum("ok", Int(42))
	opts := BridgeOpts{Extended: true}

	cv, err := ToSJSONWithOpts(v, opts)
	if err != nil {
		t.Fatalf("ToSJSONWithOpts: %v", err)
	}
	back, err := FromSJSONWithOpts(cv, opts)
	if err != nil {
		t.Fatalf("FromSJSONWithOpts: %v", err)
	}
	if back.Type() != TypeSum {
		t.Fatalf("expected TypeSum, got %s", back.Type())
	}
	want := Emit(v)
	if got := Emit(back); got != want {
		t.Errorf("Sum round-trip: want %q got %q", want, got)
	}
}

// TestBridge_Extended_GuardReservedKey verifies that emitting a Map/Struct
// with "$glyph" as a field key in extended mode returns an error.
func TestBridge_Extended_GuardReservedKey(t *testing.T) {
	opts := BridgeOpts{Extended: true}

	// Map with reserved key
	_, err := ToSJSONWithOpts(Map(MapEntry{Key: "$glyph", Value: Str("user")}), opts)
	if err == nil {
		t.Error("expected error for Map with $glyph key, got nil")
	}

	// Struct with reserved field
	_, err = ToSJSONWithOpts(Struct("T", MapEntry{Key: "$glyph", Value: Str("user")}), opts)
	if err == nil {
		t.Error("expected error for Struct with $glyph field, got nil")
	}

	// Sum with reserved tag
	_, err = ToSJSONWithOpts(Sum("$glyph", Int(1)), opts)
	if err == nil {
		t.Error("expected error for Sum with $glyph tag, got nil")
	}
}

// TestBridge_Extended_MalformedMarker verifies that malformed $glyph marker
// objects are rejected loudly rather than silently misinterpreted.
func TestBridge_Extended_MalformedMarker(t *testing.T) {
	opts := BridgeOpts{Extended: true}

	cases := []struct {
		name string
		cv   *cowrie.Value
	}{
		{
			"id-extra-key",
			cowrie.Object(
				cowrie.Member{Key: "$glyph", Value: cowrie.String("id")},
				cowrie.Member{Key: "value", Value: cowrie.String("^p:val")},
				cowrie.Member{Key: "extra", Value: cowrie.String("boom")},
			),
		},
		{
			"id-missing-value",
			cowrie.Object(
				cowrie.Member{Key: "$glyph", Value: cowrie.String("id")},
			),
		},
		{
			"struct-missing-fields",
			cowrie.Object(
				cowrie.Member{Key: "$glyph", Value: cowrie.String("struct")},
				cowrie.Member{Key: "type", Value: cowrie.String("T")},
			),
		},
		{
			"unknown-marker",
			cowrie.Object(
				cowrie.Member{Key: "$glyph", Value: cowrie.String("unknown")},
			),
		},
	}

	for _, tc := range cases {
		_, err := FromSJSONWithOpts(tc.cv, opts)
		if err == nil {
			t.Errorf("case %s: expected error, got nil", tc.name)
		}
	}
}

// TestBridge_Extended_NativeTypes verifies that Time and Bytes round-trip via
// their native cowrie types (no marker needed, already lossless).
func TestBridge_Extended_NativeTypes(t *testing.T) {
	opts := BridgeOpts{Extended: true}

	now := time.Date(2026, 6, 20, 12, 0, 0, 500000000, time.UTC)
	tv := Time(now)
	tcv, err := ToSJSONWithOpts(tv, opts)
	if err != nil {
		t.Fatalf("ToSJSONWithOpts(Time): %v", err)
	}
	// Time must come back as cowrie.TypeDatetime64, not a marker object
	if tcv.Type() != cowrie.TypeDatetime64 {
		t.Errorf("expected TypeDatetime64 cowrie type, got %v", tcv.Type())
	}
	tback, err := FromSJSONWithOpts(tcv, opts)
	if err != nil {
		t.Fatalf("FromSJSONWithOpts(Time): %v", err)
	}
	if Emit(tback) != Emit(tv) {
		t.Errorf("Time round-trip mismatch: want %q got %q", Emit(tv), Emit(tback))
	}

	bv := Bytes([]byte{0xDE, 0xAD, 0xBE, 0xEF})
	bcv, err := ToSJSONWithOpts(bv, opts)
	if err != nil {
		t.Fatalf("ToSJSONWithOpts(Bytes): %v", err)
	}
	// Bytes must come back as cowrie.TypeBytes, not a marker object
	if bcv.Type() != cowrie.TypeBytes {
		t.Errorf("expected TypeBytes cowrie type, got %v", bcv.Type())
	}
	bback, err := FromSJSONWithOpts(bcv, opts)
	if err != nil {
		t.Fatalf("FromSJSONWithOpts(Bytes): %v", err)
	}
	if Emit(bback) != Emit(bv) {
		t.Errorf("Bytes round-trip mismatch: want %q got %q", Emit(bv), Emit(bback))
	}
}

// TestBridge_Strict_IsLossy documents and verifies the intentional lossiness
// of strict mode: ID→Str, Struct→Map, Sum→Map.
func TestBridge_Strict_IsLossy(t *testing.T) {
	strictDecoded := func(v *GValue) *GValue {
		return FromSJSON(ToSJSON(v))
	}

	if got := strictDecoded(ID("p", "smith")); got.Type() != TypeStr {
		t.Errorf("strict: ID should decode as Str, got %s", got.Type())
	}
	if got := strictDecoded(Struct("T", MapEntry{Key: "x", Value: Int(1)})); got.Type() != TypeMap {
		t.Errorf("strict: Struct should decode as Map, got %s", got.Type())
	}
	if got := strictDecoded(Sum("ok", Int(1))); got.Type() != TypeMap {
		t.Errorf("strict: Sum should decode as Map, got %s", got.Type())
	}
}

