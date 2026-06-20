package glyph

import (
	"strings"
	"testing"
)

// schema_text_roundtrip_test.go proves the P1 schema-text round-trip:
// ParseSchema(EmitSchema(s)) reproduces s for the packed-decoding-relevant
// subset (FID, @pack/@tab/@open, @keepnull, @codec, wire keys, optional,
// scalar @default) plus range constraints via the .. operator.
//
// Remainder (noted in the PR, not yet round-trippable through schema TEXT):
// container/bytes defaults, and the min-len/max-len/regex/enum/unique
// constraints (these emit but the parser does not yet read them back). They
// still round-trip through the programmatic schema API.

// TestSchemaText_RoundTrip_Fixpoint emits a feature-rich schema, parses it back,
// re-emits, and asserts the text + hash are stable. EmitSchema is deterministic,
// so a fixpoint means every emitted bit was parsed back.
func TestSchemaText_RoundTrip_Fixpoint(t *testing.T) {
	s := NewSchemaBuilder().
		AddPackedStruct("Player", "v1",
			Field("name", PrimitiveType("str"), WithFID(1), WithWireKey("n")),
			Field("rank", PrimitiveType("int"), WithFID(2), WithConstraint(RangeConstraint(0, 100))),
			Field("note", PrimitiveType("str"), WithFID(3), WithOptional(), WithDefault(Str("none"))),
			Field("tier", PrimitiveType("str"), WithFID(4), WithCodec("dict"), WithKeepNull()),
		).
		AddOpenStruct("Team", "v1",
			Field("city", PrimitiveType("str")),
			Field("score", PrimitiveType("float"), WithDefault(Float(1.5))),
		).
		AddSum("Result", "v1",
			Variant("Win", PrimitiveType("int")),
			Variant("Loss", PrimitiveType("str")),
		).
		Build()

	text1 := EmitSchema(s)

	s2, err := ParseSchema(text1)
	if err != nil {
		t.Fatalf("ParseSchema(EmitSchema(s)) failed: %v\n--- text ---\n%s", err, text1)
	}
	text2 := EmitSchema(s2)

	if text1 != text2 {
		t.Errorf("schema text not a round-trip fixpoint:\n--- first ---\n%s\n--- second ---\n%s", text1, text2)
	}
	if s.Hash != s2.Hash {
		t.Errorf("schema hash changed across round-trip: %s != %s", s.Hash, s2.Hash)
	}
}

// TestSchemaText_RoundTrip_FieldsSurvive checks the individual decoding-relevant
// bits directly (not just the fixpoint), so a bug that drops a bit on BOTH emit
// and parse can't hide behind a stable fixpoint.
func TestSchemaText_RoundTrip_FieldsSurvive(t *testing.T) {
	s := NewSchemaBuilder().
		AddPackedStruct("Player", "v1",
			Field("name", PrimitiveType("str"), WithFID(7), WithWireKey("n")),
			Field("tier", PrimitiveType("str"), WithFID(8), WithCodec("dict"), WithKeepNull()),
			Field("note", PrimitiveType("str"), WithFID(9), WithOptional(), WithDefault(Str("none"))),
		).
		Build()

	s2, err := ParseSchema(EmitSchema(s))
	if err != nil {
		t.Fatalf("ParseSchema failed: %v", err)
	}

	td := s2.GetType("Player")
	if td == nil {
		t.Fatal("Player type missing after round-trip")
	}
	if !td.PackEnabled {
		t.Error("@pack flag lost")
	}
	if !td.TabEnabled {
		t.Error("@tab flag lost")
	}

	name := s2.GetField("Player", "name")
	if name == nil || name.FID != 7 || name.WireKey != "n" {
		t.Errorf("name field FID/wirekey lost: %+v", name)
	}
	tier := s2.GetField("Player", "tier")
	if tier == nil || tier.FID != 8 || tier.Codec != "dict" || !tier.KeepNull {
		t.Errorf("tier field codec/keepnull lost: %+v", tier)
	}
	note := s2.GetField("Player", "note")
	if note == nil || note.FID != 9 || !note.Optional || note.Default == nil {
		t.Fatalf("note field optional/default lost: %+v", note)
	}
	if got, _ := note.Default.AsStr(); got != "none" {
		t.Errorf("note default value lost: got %q", got)
	}
}

// TestSchemaText_OpenFlag confirms @open round-trips (previously it was emitted
// but the parser could not read it back).
func TestSchemaText_OpenFlag(t *testing.T) {
	s := NewSchemaBuilder().
		AddOpenStruct("Cfg", "v1", Field("k", PrimitiveType("str"))).
		Build()
	s2, err := ParseSchema(EmitSchema(s))
	if err != nil {
		t.Fatalf("ParseSchema failed: %v", err)
	}
	if !s2.GetType("Cfg").Open {
		t.Error("@open flag lost on round-trip")
	}
}

// TestSchemaText_RangeOperator covers the .. lexer fix directly: [0..10] must
// tokenize and parse into a range constraint, and round-trip.
func TestSchemaText_RangeOperator(t *testing.T) {
	s, err := ParseSchema(`@schema{ M:v1 struct{ p: float [0..10] } }`)
	if err != nil {
		t.Fatalf("ParseSchema with [0..10] failed: %v", err)
	}
	f := s.GetField("M", "p")
	if f == nil || len(f.Constraints) != 1 || f.Constraints[0].Kind != ConstraintRange {
		t.Fatalf("range constraint not parsed: %+v", f)
	}
	r := f.Constraints[0].Value.([2]float64)
	if r[0] != 0 || r[1] != 10 {
		t.Errorf("range bounds wrong: got %v", r)
	}

	// And it survives an emit/parse cycle.
	emitted := EmitSchema(s)
	if !strings.Contains(emitted, "0..10") {
		t.Errorf("emitted schema missing range: %s", emitted)
	}
	if _, err := ParseSchema(emitted); err != nil {
		t.Fatalf("re-parse of emitted range schema failed: %v", err)
	}
}

// TestSchemaText_LoneDotErrors ensures a stray single '.' is still a lex error
// (the .. handling must not accidentally accept a lone dot). Note [0.10] is a
// valid float and is NOT a lone dot — a bare '.' token is.
func TestSchemaText_LoneDotErrors(t *testing.T) {
	if _, err := ParseSchema(`@schema{ . }`); err == nil {
		t.Error("expected lex error for a lone '.'")
	}
}
