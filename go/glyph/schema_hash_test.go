package glyph

import "testing"

// schema_hash_test.go proves the P1 ship-blocker fix: the schema hash must cover
// every decoding-relevant bit. If two schemas decode the same wire bytes
// differently, they MUST hash differently — otherwise a `@schema#<hash>` header
// could match a schema that mis-decodes the payload.

// TestSchemaHashDivergesOnFIDOrder is the headline case: two schemas identical
// except for which FID is assigned to which field. They pack to different wire
// layouts, so they must not collide.
func TestSchemaHashDivergesOnFIDOrder(t *testing.T) {
	a := NewSchemaBuilder().AddPackedStruct("Foo", "v1",
		Field("x", PrimitiveType("int"), WithFID(1)),
		Field("y", PrimitiveType("int"), WithFID(2)),
	).Build()

	b := NewSchemaBuilder().AddPackedStruct("Foo", "v1",
		Field("x", PrimitiveType("int"), WithFID(2)),
		Field("y", PrimitiveType("int"), WithFID(1)),
	).Build()

	if a.Hash == b.Hash {
		t.Fatalf("schemas differing only in FID assignment must not share a hash (got %s)", a.Hash)
	}
}

// TestSchemaHashStableAcrossDeclarationOrder is the complement: FID assignment is
// what matters, not declaration order. Two schemas with the same fields and the
// same FIDs but declared in a different order pack identically and so must hash
// identically.
func TestSchemaHashStableAcrossDeclarationOrder(t *testing.T) {
	a := NewSchemaBuilder().AddPackedStruct("Foo", "v1",
		Field("x", PrimitiveType("int"), WithFID(1)),
		Field("y", PrimitiveType("int"), WithFID(2)),
	).Build()

	b := NewSchemaBuilder().AddPackedStruct("Foo", "v1",
		Field("y", PrimitiveType("int"), WithFID(2)),
		Field("x", PrimitiveType("int"), WithFID(1)),
	).Build()

	if a.Hash != b.Hash {
		t.Fatalf("same fields + same FIDs in different declaration order must hash equal (%s vs %s)", a.Hash, b.Hash)
	}
}

// TestSchemaHashDivergesOnDecodingBits sweeps the remaining decoding-relevant
// bits. Each variant differs from the baseline by exactly one bit and must
// produce a distinct hash.
func TestSchemaHashDivergesOnDecodingBits(t *testing.T) {
	base := NewSchemaBuilder().AddPackedStruct("Foo", "v1",
		Field("x", PrimitiveType("int"), WithFID(1)),
	).Build()

	mutants := map[string]*Schema{
		"pack-flag": func() *Schema {
			// Same field + FID, but not packed.
			return NewSchemaBuilder().AddStruct("Foo", "v1",
				Field("x", PrimitiveType("int"), WithFID(1)),
			).Build()
		}(),
		"tab-flag": func() *Schema {
			s := NewSchemaBuilder().AddPackedStruct("Foo", "v1",
				Field("x", PrimitiveType("int"), WithFID(1)),
			).Build()
			s.Types["Foo"].TabEnabled = !s.Types["Foo"].TabEnabled
			s.ComputeHash()
			return s
		}(),
		"open-flag": func() *Schema {
			return NewSchemaBuilder().AddOpenPackedStruct("Foo", "v1",
				Field("x", PrimitiveType("int"), WithFID(1)),
			).Build()
		}(),
		"wire-key": NewSchemaBuilder().AddPackedStruct("Foo", "v1",
			Field("x", PrimitiveType("int"), WithFID(1), WithWireKey("xx")),
		).Build(),
		"keep-null": NewSchemaBuilder().AddPackedStruct("Foo", "v1",
			Field("x", PrimitiveType("int"), WithFID(1), WithKeepNull()),
		).Build(),
		"codec": NewSchemaBuilder().AddPackedStruct("Foo", "v1",
			Field("x", PrimitiveType("int"), WithFID(1), WithCodec("dict")),
		).Build(),
		"default": NewSchemaBuilder().AddPackedStruct("Foo", "v1",
			Field("x", PrimitiveType("int"), WithFID(1), WithDefault(Int(7))),
		).Build(),
		"optional": NewSchemaBuilder().AddPackedStruct("Foo", "v1",
			Field("x", PrimitiveType("int"), WithFID(1), WithOptional()),
		).Build(),
		"constraint": NewSchemaBuilder().AddPackedStruct("Foo", "v1",
			Field("x", PrimitiveType("int"), WithFID(1), WithConstraint(MinConstraint(0))),
		).Build(),
		"field-type": NewSchemaBuilder().AddPackedStruct("Foo", "v1",
			Field("x", PrimitiveType("str"), WithFID(1)),
		).Build(),
	}

	seen := map[string]string{base.Hash: "base"}
	for name, m := range mutants {
		if m.Hash == base.Hash {
			t.Errorf("%s: schema differing in %q must not match the baseline hash (%s)", name, name, base.Hash)
		}
		if other, dup := seen[m.Hash]; dup {
			t.Errorf("%s: hash collides with %q (%s)", name, other, m.Hash)
		}
		seen[m.Hash] = name
	}
}

// TestSchemaHashDivergesOnSumVariants ensures sum-type variants are covered.
func TestSchemaHashDivergesOnSumVariants(t *testing.T) {
	a := NewSchemaBuilder().AddSum("E", "v1",
		Variant("A", PrimitiveType("int")),
		Variant("B", PrimitiveType("str")),
	).Build()
	b := NewSchemaBuilder().AddSum("E", "v1",
		Variant("A", PrimitiveType("int")),
		Variant("B", PrimitiveType("int")), // B's wrapped type differs
	).Build()
	if a.Hash == b.Hash {
		t.Fatalf("sum schemas with a differing variant type must not collide (%s)", a.Hash)
	}

	// Variant declaration order is not decoding-relevant (variants match by tag).
	c := NewSchemaBuilder().AddSum("E", "v1",
		Variant("B", PrimitiveType("str")),
		Variant("A", PrimitiveType("int")),
	).Build()
	if a.Hash != c.Hash {
		t.Fatalf("sum variant declaration order must not change the hash (%s vs %s)", a.Hash, c.Hash)
	}
}
