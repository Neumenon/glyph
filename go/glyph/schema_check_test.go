package glyph

import "testing"

// schema_check_test.go verifies Schema.Check() lints each malformed class and
// accepts a valid schema.

func hasCheckCode(errs []SchemaError, code string) bool {
	for _, e := range errs {
		if e.Code == code {
			return true
		}
	}
	return false
}

func TestSchemaCheck_ValidSchema(t *testing.T) {
	s := NewSchemaBuilder().
		AddPackedStruct("Player", "v1",
			Field("name", PrimitiveType("str"), WithFID(1), WithWireKey("n")),
			Field("rank", PrimitiveType("int"), WithFID(2), WithConstraint(RangeConstraint(0, 100))),
			Field("note", PrimitiveType("str"), WithFID(3), WithOptional(), WithDefault(Str("none"))),
		).
		Build()
	errs := s.Check()
	// Only expect required_field_has_default for none (since note is optional, not required)
	// Actually note is optional so no required_field_has_default
	for _, e := range errs {
		if e.Code != "required_field_has_default" {
			t.Errorf("unexpected error in valid schema: %v", e)
		}
	}
}

func TestSchemaCheck_DuplicateFieldName(t *testing.T) {
	// Build directly to bypass SchemaBuilder's dedup
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "x", Type: PrimitiveType("int")},
			{Name: "x", Type: PrimitiveType("str")}, // dup
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "duplicate_field_name") {
		t.Errorf("expected duplicate_field_name, got: %v", errs)
	}
}

func TestSchemaCheck_DuplicateWireKey(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "alpha", WireKey: "a", Type: PrimitiveType("int")},
			{Name: "beta", WireKey: "a", Type: PrimitiveType("str")}, // dup wire key
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "duplicate_wire_key") {
		t.Errorf("expected duplicate_wire_key, got: %v", errs)
	}
}

func TestSchemaCheck_WireKeyCollidesWithFieldName(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "alpha", WireKey: "beta", Type: PrimitiveType("int")}, // wire key = another field's name
			{Name: "beta", Type: PrimitiveType("str")},
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "duplicate_wire_key") {
		t.Errorf("expected duplicate_wire_key, got: %v", errs)
	}
}

func TestSchemaCheck_DuplicateFID(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Packed"] = &TypeDef{
		Name:        "Packed",
		Kind:        TypeDefStruct,
		PackEnabled: true,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "a", FID: 1, Type: PrimitiveType("int")},
			{Name: "b", FID: 1, Type: PrimitiveType("str")}, // dup FID
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "duplicate_fid") {
		t.Errorf("expected duplicate_fid, got: %v", errs)
	}
}

func TestSchemaCheck_MissingFIDInPackedStruct(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Packed"] = &TypeDef{
		Name:        "Packed",
		Kind:        TypeDefStruct,
		PackEnabled: true,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "a", FID: 1, Type: PrimitiveType("int")},
			{Name: "b", FID: 0, Type: PrimitiveType("str")}, // missing FID
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "missing_fid_in_packed_struct") {
		t.Errorf("expected missing_fid_in_packed_struct, got: %v", errs)
	}
}

func TestSchemaCheck_InvalidFID(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "a", FID: -1, Type: PrimitiveType("int")}, // negative FID
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "invalid_fid") {
		t.Errorf("expected invalid_fid, got: %v", errs)
	}
}

func TestSchemaCheck_ConstraintTypeMismatch_MinOnStr(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "x", Type: PrimitiveType("str"), Constraints: []Constraint{MinConstraint(5)}},
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "constraint_type_mismatch") {
		t.Errorf("expected constraint_type_mismatch (min on str), got: %v", errs)
	}
}

func TestSchemaCheck_ConstraintTypeMismatch_RegexOnInt(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "x", Type: PrimitiveType("int"), Constraints: []Constraint{RegexConstraint(`\d+`)}},
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "constraint_type_mismatch") {
		t.Errorf("expected constraint_type_mismatch (regex on int), got: %v", errs)
	}
}

func TestSchemaCheck_ConstraintTypeMismatch_UniqueOnStr(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "x", Type: PrimitiveType("str"), Constraints: []Constraint{{Kind: ConstraintUnique}}},
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "constraint_type_mismatch") {
		t.Errorf("expected constraint_type_mismatch (unique on str), got: %v", errs)
	}
}

func TestSchemaCheck_UnsupportedMapKeyType(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "m", Type: MapType(PrimitiveType("float"), PrimitiveType("str"))}, // float key
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "unsupported_map_key_type") {
		t.Errorf("expected unsupported_map_key_type, got: %v", errs)
	}
}

func TestSchemaCheck_RequiredFieldHasDefault_Warning(t *testing.T) {
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "x", Type: PrimitiveType("int"), Optional: false, Default: Int(0)}, // required + default
		}},
	}
	errs := s.Check()
	if !hasCheckCode(errs, "required_field_has_default") {
		t.Errorf("expected required_field_has_default warning, got: %v", errs)
	}
}

func TestSchemaCheck_ValidConstraints(t *testing.T) {
	// This should produce no errors (only maybe required_field_has_default)
	s := &Schema{Types: make(map[string]*TypeDef)}
	s.Types["Foo"] = &TypeDef{
		Name: "Foo",
		Kind: TypeDefStruct,
		Struct: &StructDef{Fields: []*FieldDef{
			{Name: "age", Type: PrimitiveType("int"), Constraints: []Constraint{MinConstraint(0), MaxConstraint(150)}},
			{Name: "name", Type: PrimitiveType("str"), Constraints: []Constraint{RegexConstraint(`\w+`), EnumConstraint([]string{"alice", "bob"})}},
			{Name: "tags", Type: ListType(PrimitiveType("str")), Constraints: []Constraint{{Kind: ConstraintUnique}, NonEmptyConstraint()}},
		}},
	}
	errs := s.Check()
	for _, e := range errs {
		if e.Code != "required_field_has_default" {
			t.Errorf("unexpected error in schema with valid constraints: %v", e)
		}
	}
}
