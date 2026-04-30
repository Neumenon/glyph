package glyph

import (
	"math"
	"testing"
	"time"
)

// ============================================================
// canon.go — uncovered paths
// ============================================================

func TestCanonValue(t *testing.T) {
	// Test all types through canonValue
	tests := []struct {
		name string
		val  *GValue
	}{
		{"nil", nil},
		{"null", Null()},
		{"bool_true", Bool(true)},
		{"bool_false", Bool(false)},
		{"int_zero", Int(0)},
		{"int_pos", Int(42)},
		{"float_pi", Float(3.14)},
		{"str_bare", Str("hello")},
		{"str_quoted", Str("has space")},
		{"id", ID("m", "123")},
		{"time", Time(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))},
		{"bytes", Bytes([]byte("hello"))},
		// Container types should return empty string
		{"list", List(Int(1))},
		{"map", Map(MapEntry{Key: "a", Value: Int(1)})},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_ = canonValue(tt.val) // just exercise the code paths
		})
	}
}

func TestCanonFloat_EdgeCases(t *testing.T) {
	// Negative zero
	if got := canonFloat(math.Copysign(0, -1)); got != "0" {
		t.Errorf("expected 0 for -0, got %q", got)
	}
	// Zero
	if got := canonFloat(0); got != "0" {
		t.Errorf("expected 0, got %q", got)
	}
	// Small integer float
	if got := canonFloat(42.0); got != "42" {
		t.Errorf("expected 42, got %q", got)
	}
	// Large value that needs precision
	val := 1.23456789e15
	got := canonFloat(val)
	if got == "" {
		t.Error("expected non-empty")
	}
}

func TestCanonRef_UnsafeChars(t *testing.T) {
	// Ref with space should be quoted
	ref := RefID{Prefix: "x", Value: "has space"}
	got := canonRef(ref)
	if got[0] != '^' {
		t.Error("should start with ^")
	}
	if got == "^x:has space" {
		t.Error("should be quoted due to space")
	}
}

func TestIsRefSafe(t *testing.T) {
	if isRefSafe("") {
		t.Error("empty should not be safe")
	}
	if !isRefSafe("abc:123") {
		t.Error("abc:123 should be safe")
	}
	if isRefSafe("has space") {
		t.Error("space should not be safe")
	}
}

func TestQuoteString_ControlChars(t *testing.T) {
	// Test control character escaping
	s := string([]byte{0x01, 0x02, 0x1f})
	got := quoteString(s)
	if got == "" {
		t.Error("expected non-empty")
	}
	// Should contain \u00 escapes
	if !containsSubstring(got, `\u00`) {
		t.Errorf("expected \\u00 escapes in %q", got)
	}
}

func TestBinaryToMask_Errors(t *testing.T) {
	// No 0b prefix
	_, err := binaryToMask("1010")
	if err == nil {
		t.Error("expected error without 0b prefix")
	}
	// Empty bitmap
	_, err = binaryToMask("0b")
	if err == nil {
		t.Error("expected error for empty bitmap")
	}
	// Invalid character
	_, err = binaryToMask("0b102")
	if err == nil {
		t.Error("expected error for invalid char")
	}
}

// ============================================================
// emit.go — uncovered paths
// ============================================================

func TestEmitCompact(t *testing.T) {
	v := Struct("Team",
		MapEntry{Key: "name", Value: Str("Arsenal")},
		MapEntry{Key: "rank", Value: Int(1)},
	)
	got := EmitCompact(v)
	if got == "" {
		t.Error("expected non-empty")
	}
}

func TestEmitSchema(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Team", "",
			Field("name", PrimitiveType("str")),
		).
		Build()
	got := EmitSchema(schema)
	if got == "" {
		t.Error("expected non-empty")
	}
}

func TestEmitSchemaRef(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Team", "",
			Field("name", PrimitiveType("str")),
		).
		Build()
	got := EmitSchemaRef(schema)
	if got == "" {
		t.Error("expected non-empty")
	}
	if !containsSubstring(got, "@schema#") {
		t.Errorf("expected @schema# prefix, got %q", got)
	}
}

func TestEmit_Pretty(t *testing.T) {
	v := Map(
		MapEntry{Key: "a", Value: List(Int(1), Int(2))},
		MapEntry{Key: "b", Value: Int(3)},
	)
	opts := EmitOptions{Pretty: true, Indent: "  ", SortFields: true}
	got := EmitWithOptions(v, opts)
	if got == "" {
		t.Error("expected non-empty")
	}
	// Should contain newlines
	if !containsSubstring(got, "\n") {
		t.Error("pretty mode should contain newlines")
	}
}

func TestEmit_PrettyStruct(t *testing.T) {
	v := Struct("Team",
		MapEntry{Key: "name", Value: Str("Arsenal")},
		MapEntry{Key: "rank", Value: Int(1)},
	)
	opts := EmitOptions{Pretty: true, Indent: "  ", SortFields: true}
	got := EmitWithOptions(v, opts)
	if !containsSubstring(got, "\n") {
		t.Error("pretty mode should contain newlines")
	}
}

func TestEmit_Sum(t *testing.T) {
	// Sum with null value
	v := Sum("None", nil)
	got := Emit(v)
	if got != "None()" {
		t.Errorf("expected 'None()', got %q", got)
	}

	// Sum with struct value
	sv := Sum("Ok", Struct("Result",
		MapEntry{Key: "val", Value: Int(42)},
	))
	got2 := Emit(sv)
	if got2 == "" {
		t.Error("expected non-empty")
	}

	// Sum with non-struct value
	sv2 := Sum("Value", Int(42))
	got3 := Emit(sv2)
	if got3 != "Value(42)" {
		t.Errorf("expected 'Value(42)', got %q", got3)
	}
}

func TestEmit_Bytes(t *testing.T) {
	v := Bytes([]byte("hello"))
	got := Emit(v)
	if got == "" {
		t.Error("expected non-empty")
	}
	if !containsSubstring(got, "b64") {
		t.Errorf("expected b64 prefix, got %q", got)
	}
}

func TestEmit_Time(t *testing.T) {
	v := Time(time.Date(2025, 3, 9, 12, 0, 0, 0, time.UTC))
	got := Emit(v)
	if got == "" {
		t.Error("expected non-empty")
	}
}

func TestEmit_NaN(t *testing.T) {
	v := Float(math.NaN())
	got := Emit(v)
	if got != "NaN" {
		t.Errorf("expected NaN, got %q", got)
	}
}

func TestEmit_Inf(t *testing.T) {
	v := Float(math.Inf(1))
	got := Emit(v)
	if got != "Inf" {
		t.Errorf("expected Inf, got %q", got)
	}
	v2 := Float(math.Inf(-1))
	got2 := Emit(v2)
	if got2 != "-Inf" {
		t.Errorf("expected -Inf, got %q", got2)
	}
}

// ============================================================
// types.go — uncovered accessor error paths
// ============================================================

func TestGType_String_Unknown(t *testing.T) {
	var gt GType = 200
	if gt.String() != "unknown" {
		t.Errorf("expected 'unknown', got %q", gt.String())
	}
}

func TestGType_String_AllTypes(t *testing.T) {
	types := []GType{TypeNull, TypeBool, TypeInt, TypeFloat, TypeStr, TypeBytes, TypeTime, TypeID, TypeList, TypeMap, TypeStruct, TypeSum}
	for _, tt := range types {
		s := tt.String()
		if s == "" || s == "unknown" {
			t.Errorf("type %d should have a name", tt)
		}
	}
}

func TestGValue_AsBytes(t *testing.T) {
	v := Bytes([]byte("hello"))
	b, err := v.AsBytes()
	if err != nil {
		t.Fatal(err)
	}
	if string(b) != "hello" {
		t.Errorf("expected 'hello', got %q", string(b))
	}

	// Error path
	_, err = Int(42).AsBytes()
	if err == nil {
		t.Error("expected error")
	}
	// Nil path
	var nilv *GValue
	_, err = nilv.AsBytes()
	if err == nil {
		t.Error("expected error for nil")
	}
}

func TestGValue_AsTime(t *testing.T) {
	now := time.Now()
	v := Time(now)
	tm, err := v.AsTime()
	if err != nil {
		t.Fatal(err)
	}
	if !tm.Equal(now) {
		t.Error("times don't match")
	}

	_, err = Int(42).AsTime()
	if err == nil {
		t.Error("expected error")
	}
	var nilv *GValue
	_, err = nilv.AsTime()
	if err == nil {
		t.Error("expected error for nil")
	}
}

func TestGValue_Len_AllTypes(t *testing.T) {
	if List(Int(1), Int(2)).Len() != 2 {
		t.Error("list len")
	}
	if Map(MapEntry{Key: "a", Value: Int(1)}).Len() != 1 {
		t.Error("map len")
	}
	if Struct("T", MapEntry{Key: "a", Value: Int(1)}).Len() != 1 {
		t.Error("struct len")
	}
	if Int(42).Len() != 0 {
		t.Error("scalar len should be 0")
	}
}

func TestGValue_Index_Errors(t *testing.T) {
	_, err := Int(42).Index(0)
	if err == nil {
		t.Error("expected error for non-list")
	}
	var nilv *GValue
	_, err = nilv.Index(0)
	if err == nil {
		t.Error("expected error for nil")
	}
	v := List(Int(1))
	_, err = v.Index(-1)
	if err == nil {
		t.Error("expected error for negative index")
	}
	_, err = v.Index(10)
	if err == nil {
		t.Error("expected error for out of bounds")
	}
}

func TestGValue_Pos(t *testing.T) {
	v := Int(42)
	v.SetPos(Position{Line: 1, Column: 5, Offset: 10})
	p := v.Pos()
	if p.Line != 1 || p.Column != 5 {
		t.Errorf("unexpected pos: %v", p)
	}

	var nilv *GValue
	p2 := nilv.Pos()
	if p2.Line != 0 {
		t.Error("nil should return zero pos")
	}
}

func TestGValue_Set(t *testing.T) {
	// Map: update existing
	m := Map(MapEntry{Key: "a", Value: Int(1)})
	m.Set("a", Int(2))
	v, _ := m.Get("a").AsInt()
	if v != 2 {
		t.Error("expected updated value")
	}
	// Map: add new
	m.Set("b", Int(3))
	if m.Get("b") == nil {
		t.Error("expected new key")
	}

	// Struct: update existing
	s := Struct("T", MapEntry{Key: "x", Value: Int(1)})
	s.Set("x", Int(99))
	v, _ = s.Get("x").AsInt()
	if v != 99 {
		t.Error("expected updated struct field")
	}
	// Struct: add new
	s.Set("y", Int(100))
	if s.Get("y") == nil {
		t.Error("expected new struct field")
	}
}

func TestGValue_Set_PanicOnScalar(t *testing.T) {
	defer func() {
		if r := recover(); r == nil {
			t.Error("expected panic")
		}
	}()
	Int(42).Set("a", Int(1))
}

func TestGValue_Append(t *testing.T) {
	v := List(Int(1))
	v.Append(Int(2))
	if v.Len() != 2 {
		t.Error("expected length 2")
	}
}

func TestGValue_Append_PanicOnNonList(t *testing.T) {
	defer func() {
		if r := recover(); r == nil {
			t.Error("expected panic")
		}
	}()
	Int(42).Append(Int(1))
}

func TestGValue_Number(t *testing.T) {
	n, ok := Int(42).Number()
	if !ok || n != 42 {
		t.Error("expected 42")
	}
	n, ok = Float(3.14).Number()
	if !ok || n != 3.14 {
		t.Error("expected 3.14")
	}
	_, ok = Str("x").Number()
	if ok {
		t.Error("expected false for string")
	}
}

func TestGValue_IsNumeric(t *testing.T) {
	if !Int(42).IsNumeric() {
		t.Error("int should be numeric")
	}
	if !Float(3.14).IsNumeric() {
		t.Error("float should be numeric")
	}
	if Str("x").IsNumeric() {
		t.Error("string should not be numeric")
	}
}

func TestGValue_Type_Nil(t *testing.T) {
	var nilv *GValue
	if nilv.Type() != TypeNull {
		t.Error("nil should be TypeNull")
	}
}

func TestPosition_String(t *testing.T) {
	p := Position{Line: 3, Column: 7}
	if p.String() != "3:7" {
		t.Errorf("expected '3:7', got %q", p.String())
	}
}

// ============================================================
// validate.go — uncovered paths
// ============================================================

func TestValidationError_Error(t *testing.T) {
	e := &ValidationError{Path: "a.b", Message: "bad value"}
	if e.Error() != "a.b: bad value" {
		t.Errorf("unexpected: %q", e.Error())
	}
	e2 := &ValidationError{Message: "bad"}
	if e2.Error() != "bad" {
		t.Errorf("unexpected: %q", e2.Error())
	}
}

func TestValidateSum(t *testing.T) {
	schema := NewSchemaBuilder().
		AddSum("Result", "",
			Variant("Ok", PrimitiveType("int")),
			Variant("Err", PrimitiveType("str")),
		).
		Build()

	// Valid
	v := Sum("Ok", Int(42))
	result := ValidateAs(v, schema, "Result")
	if !result.Valid {
		t.Errorf("expected valid: %v", result.Errors)
	}

	// Invalid variant
	v2 := Sum("Unknown", Int(1))
	result2 := ValidateAs(v2, schema, "Result")
	if result2.Valid {
		t.Error("expected invalid for unknown variant")
	}

	// Wrong type entirely
	v3 := Int(42)
	result3 := ValidateAs(v3, schema, "Result")
	if result3.Valid {
		t.Error("expected invalid for non-sum")
	}
}

func TestValidate_TypeMismatch(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Team", "",
			Field("name", PrimitiveType("str")),
		).Build()

	// Pass int where struct expected
	result := ValidateAs(Int(42), schema, "Team")
	if result.Valid {
		t.Error("expected invalid")
	}
}

func TestValidate_UnknownType(t *testing.T) {
	schema := NewSchemaBuilder().Build()
	result := ValidateAs(Int(42), schema, "NonExistent")
	if result.Valid {
		t.Error("expected invalid for unknown type")
	}
}

func TestIsValid(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Team", "",
			Field("name", PrimitiveType("str")),
		).Build()
	v := Struct("Team", MapEntry{Key: "name", Value: Str("Arsenal")})
	if !IsValid(v, schema) {
		t.Error("expected valid")
	}
}

func TestValidateValue_AllTypeSpecs(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Test", "",
			Field("b", PrimitiveType("bool")),
			Field("i", PrimitiveType("int")),
			Field("f", PrimitiveType("float")),
			Field("s", PrimitiveType("str")),
			Field("by", PrimitiveType("bytes")),
			Field("t", PrimitiveType("time")),
			Field("id", PrimitiveType("id")),
			Field("l", ListType(PrimitiveType("int"))),
			Field("m", MapType(PrimitiveType("str"), PrimitiveType("int"))),
		).Build()

	good := Struct("Test",
		MapEntry{Key: "b", Value: Bool(true)},
		MapEntry{Key: "i", Value: Int(1)},
		MapEntry{Key: "f", Value: Float(1.0)},
		MapEntry{Key: "s", Value: Str("x")},
		MapEntry{Key: "by", Value: Bytes([]byte("x"))},
		MapEntry{Key: "t", Value: Time(time.Now())},
		MapEntry{Key: "id", Value: ID("m", "123")},
		MapEntry{Key: "l", Value: List(Int(1))},
		MapEntry{Key: "m", Value: Map(MapEntry{Key: "a", Value: Int(1)})},
	)
	result := ValidateAs(good, schema, "Test")
	if !result.Valid {
		t.Errorf("expected valid: %v", result.Errors)
	}

	// Wrong types for each field
	bad := Struct("Test",
		MapEntry{Key: "b", Value: Int(1)},   // not bool
		MapEntry{Key: "i", Value: Str("x")}, // not int
		MapEntry{Key: "f", Value: Str("x")}, // not float
		MapEntry{Key: "s", Value: Int(1)},    // not str
		MapEntry{Key: "by", Value: Int(1)},   // not bytes
		MapEntry{Key: "t", Value: Int(1)},    // not time
		MapEntry{Key: "id", Value: Int(1)},   // not id
		MapEntry{Key: "l", Value: Int(1)},    // not list
		MapEntry{Key: "m", Value: Int(1)},    // not map
	)
	result2 := ValidateAs(bad, schema, "Test")
	if result2.Valid {
		t.Error("expected invalid for all wrong types")
	}
}

func TestValidateConstraints_Extended(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Test", "",
			Field("name", PrimitiveType("str"),
				WithConstraint(MinLenConstraint(2)),
				WithConstraint(MaxLenConstraint(10)),
				WithConstraint(RegexConstraint("^[a-z]+$")),
			),
			Field("tags", ListType(PrimitiveType("str")),
				WithConstraint(NonEmptyConstraint()),
			),
			Field("code", PrimitiveType("str"),
				WithConstraint(LenConstraint(3)),
				WithConstraint(EnumConstraint([]string{"aaa", "bbb"})),
			),
		).Build()

	// Valid
	good := Struct("Test",
		MapEntry{Key: "name", Value: Str("hello")},
		MapEntry{Key: "tags", Value: List(Str("a"))},
		MapEntry{Key: "code", Value: Str("aaa")},
	)
	result := ValidateAs(good, schema, "Test")
	if !result.Valid {
		t.Errorf("expected valid: %v", result.Errors)
	}

	// Constraint violations
	bad := Struct("Test",
		MapEntry{Key: "name", Value: Str("x")},        // too short
		MapEntry{Key: "tags", Value: List()},            // empty
		MapEntry{Key: "code", Value: Str("invalid!!")},  // wrong length + not in enum
	)
	result2 := ValidateAs(bad, schema, "Test")
	if result2.Valid {
		t.Error("expected invalid")
	}
}

func TestValidateStrict_UnknownFields(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Team", "",
			Field("name", PrimitiveType("str")),
		).Build()

	v := Struct("Team",
		MapEntry{Key: "name", Value: Str("Arsenal")},
		MapEntry{Key: "extra", Value: Int(1)},
	)

	result := ValidateStrict(v, schema)
	if result.Valid {
		t.Error("strict should reject unknown fields")
	}
}

func TestValidate_OpenStruct(t *testing.T) {
	schema := NewSchemaBuilder().
		AddOpenStruct("Team", "",
			Field("name", PrimitiveType("str")),
		).Build()

	v := Struct("Team",
		MapEntry{Key: "name", Value: Str("Arsenal")},
		MapEntry{Key: "extra", Value: Int(1)},
	)

	result := ValidateAs(v, schema, "Team")
	if !result.Valid {
		t.Errorf("open struct should allow unknown fields: %v", result.Errors)
	}
}

func TestValidate_MapAsStruct(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Team", "",
			Field("name", PrimitiveType("str")),
		).Build()

	v := Map(MapEntry{Key: "name", Value: Str("Arsenal")})
	result := ValidateAs(v, schema, "Team")
	if !result.Valid {
		t.Errorf("map should validate as struct: %v", result.Errors)
	}
}

// ============================================================
// document.go — uncovered paths
// ============================================================

func TestParseDocument_EmbeddedTab(t *testing.T) {
	input := `{messages=@tab _ [id name]
|1|alice|
|2|bob|
system=hello}`
	gv, err := ParseDocument(input)
	if err != nil {
		t.Fatalf("ParseDocument: %v", err)
	}
	if gv.Type() != TypeMap {
		t.Fatalf("expected map, got %v", gv.Type())
	}
	msgs := gv.Get("messages")
	if msgs == nil || msgs.Type() != TypeList {
		t.Fatal("expected messages list")
	}
}

func TestParseDocument_EmbeddedTab_WithEnd(t *testing.T) {
	input := `{messages=@tab _ [id name]
|1|alice|
@end
other=42}`
	gv, err := ParseDocument(input)
	if err != nil {
		t.Fatalf("ParseDocument: %v", err)
	}
	if gv.Type() != TypeMap {
		t.Fatalf("expected map, got %v", gv.Type())
	}
}

func TestIsDocKeyStart(t *testing.T) {
	if !isDocKeyStart("key=value") {
		t.Error("should recognize key=")
	}
	if isDocKeyStart("=value") {
		t.Error("should reject starting with =")
	}
	if isDocKeyStart("no equals") {
		t.Error("should reject no equals")
	}
	if isDocKeyStart("") {
		t.Error("should reject empty")
	}
}

// ============================================================
// parse_header.go — uncovered paths
// ============================================================

func TestParseHeader_AllModes(t *testing.T) {
	tests := []struct {
		input string
		mode  Mode
	}{
		{"@lyph v2 @mode=auto", ModeAuto},
		{"@lyph v2 @mode=struct", ModeStruct},
		{"@lyph v2 @mode=packed", ModePacked},
		{"@lyph v2 @mode=tabular", ModeTabular},
		{"@lyph v2 @mode=tab", ModeTabular},
		{"@lyph v2 @mode=patch", ModePatch},
		{"@lyph v2 @patch", ModePatch},
		{"@lyph v2 @tab", ModeTabular},
		{"@glyph v2", ModeAuto},
	}
	for _, tt := range tests {
		h, err := ParseHeader(tt.input)
		if err != nil {
			t.Errorf("ParseHeader(%q): %v", tt.input, err)
			continue
		}
		if h.Mode != tt.mode {
			t.Errorf("ParseHeader(%q): mode=%v, want %v", tt.input, h.Mode, tt.mode)
		}
	}
}

func TestParseHeader_NotHeader(t *testing.T) {
	h, err := ParseHeader("not a header")
	if err != nil {
		t.Fatal(err)
	}
	if h != nil {
		t.Error("should return nil for non-header")
	}
}

func TestParseHeader_UnknownMode(t *testing.T) {
	_, err := ParseHeader("@lyph v2 @mode=unknown")
	if err == nil {
		t.Error("expected error for unknown mode")
	}
}

func TestParseHeader_UnknownKeyMode(t *testing.T) {
	_, err := ParseHeader("@lyph v2 @keys=unknown")
	if err == nil {
		t.Error("expected error for unknown key mode")
	}
}

func TestParseHeader_WithTarget(t *testing.T) {
	h, err := ParseHeader("@lyph v2 @target=m:123")
	if err != nil {
		t.Fatal(err)
	}
	if h.Target.Prefix != "m" || h.Target.Value != "123" {
		t.Errorf("unexpected target: %v", h.Target)
	}
}

func TestParseHeader_WithSchema(t *testing.T) {
	h, err := ParseHeader("@lyph v2 @schema#abc123")
	if err != nil {
		t.Fatal(err)
	}
	if h.SchemaID != "abc123" {
		t.Errorf("expected schema abc123, got %q", h.SchemaID)
	}
}

func TestEmitHeader(t *testing.T) {
	h := &Header{
		Version:  "v2",
		SchemaID: "abc",
		Mode:     ModePacked,
		KeyMode:  KeyModeName,
		Target:   RefID{Prefix: "m", Value: "123"},
	}
	got := EmitHeader(h)
	if !containsSubstring(got, "@schema#abc") {
		t.Error("expected schema in header")
	}
	if !containsSubstring(got, "@mode=packed") {
		t.Error("expected mode in header")
	}
	if !containsSubstring(got, "@keys=name") {
		t.Error("expected keys in header")
	}
	if !containsSubstring(got, "@target=m:123") {
		t.Error("expected target in header")
	}
}

func TestEmitHeader_FIDKeyMode(t *testing.T) {
	h := &Header{Version: "v2", KeyMode: KeyModeFID}
	got := EmitHeader(h)
	if !containsSubstring(got, "@keys=fid") {
		t.Errorf("expected @keys=fid, got %q", got)
	}
}

func TestDetectMode(t *testing.T) {
	if DetectMode("@patch\nset .x 1\n@end") != ModePatch {
		t.Error("should detect patch")
	}
	if DetectMode("@tab _ [a b]\n|1|2|") != ModeTabular {
		t.Error("should detect tabular")
	}
	if DetectMode(`Team@(name "x" rank 1)`) != ModePacked {
		t.Error("should detect packed")
	}
	if DetectMode("{a=1}") != ModeStruct {
		t.Error("should default to struct")
	}
}

// ============================================================
// json_bridge.go — uncovered paths
// ============================================================

func TestFromJSONValueLoose(t *testing.T) {
	gv, err := FromJSONValueLoose(map[string]interface{}{
		"name": "test",
		"val":  float64(42),
	})
	if err != nil {
		t.Fatal(err)
	}
	if gv.Type() != TypeMap {
		t.Errorf("expected map, got %v", gv.Type())
	}
}

func TestToJSONValueLoose(t *testing.T) {
	gv := Map(MapEntry{Key: "a", Value: Int(1)})
	v, err := ToJSONValueLoose(gv)
	if err != nil {
		t.Fatal(err)
	}
	m, ok := v.(map[string]interface{})
	if !ok {
		t.Fatal("expected map")
	}
	if m["a"] != float64(1) {
		t.Errorf("expected 1, got %v", m["a"])
	}
}

func TestToJSON_ExtendedMode(t *testing.T) {
	opts := BridgeOpts{Extended: true}

	// Time
	gv := Time(time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC))
	b, err := ToJSONLooseWithOpts(gv, opts)
	if err != nil {
		t.Fatal(err)
	}
	if !containsSubstring(string(b), "$glyph") {
		t.Error("expected $glyph marker")
	}

	// ID
	gv2 := ID("m", "123")
	b2, err := ToJSONLooseWithOpts(gv2, opts)
	if err != nil {
		t.Fatal(err)
	}
	if !containsSubstring(string(b2), "$glyph") {
		t.Error("expected $glyph marker")
	}

	// Bytes
	gv3 := Bytes([]byte("hello"))
	b3, err := ToJSONLooseWithOpts(gv3, opts)
	if err != nil {
		t.Fatal(err)
	}
	if !containsSubstring(string(b3), "$glyph") {
		t.Error("expected $glyph marker")
	}
}

func TestFromJSON_ExtendedMode(t *testing.T) {
	opts := BridgeOpts{Extended: true}

	// Time marker
	timeJSON := []byte(`{"$glyph":"time","value":"2025-01-01T00:00:00Z"}`)
	gv, err := FromJSONLooseWithOpts(timeJSON, opts)
	if err != nil {
		t.Fatal(err)
	}
	if gv.Type() != TypeTime {
		t.Errorf("expected time, got %v", gv.Type())
	}

	// ID marker
	idJSON := []byte(`{"$glyph":"id","value":"^m:123"}`)
	gv2, err := FromJSONLooseWithOpts(idJSON, opts)
	if err != nil {
		t.Fatal(err)
	}
	if gv2.Type() != TypeID {
		t.Errorf("expected id, got %v", gv2.Type())
	}

	// Bytes marker
	bytesJSON := []byte(`{"$glyph":"bytes","base64":"aGVsbG8="}`)
	gv3, err := FromJSONLooseWithOpts(bytesJSON, opts)
	if err != nil {
		t.Fatal(err)
	}
	if gv3.Type() != TypeBytes {
		t.Errorf("expected bytes, got %v", gv3.Type())
	}

	// Unknown marker
	unknownJSON := []byte(`{"$glyph":"unknown"}`)
	_, err = FromJSONLooseWithOpts(unknownJSON, opts)
	if err == nil {
		t.Error("expected error for unknown marker")
	}
}

func TestToJSON_NaNError(t *testing.T) {
	gv := Float(math.NaN())
	_, err := ToJSONLoose(gv)
	if err == nil {
		t.Error("expected error for NaN")
	}
}

func TestFromJSON_NaN(t *testing.T) {
	// NaN can't be represented in JSON, so test Infinity through interface
	_, err := FromJSONValueLoose(math.NaN())
	if err == nil {
		t.Error("expected error for NaN")
	}
}

func TestJSONRoundTripLoose(t *testing.T) {
	input := []byte(`{"a":1,"b":"hello"}`)
	output, err := JSONRoundTripLoose(input)
	if err != nil {
		t.Fatal(err)
	}
	if len(output) == 0 {
		t.Error("expected non-empty output")
	}
}

func TestJSONEqual(t *testing.T) {
	a := []byte(`{"a":1,"b":"hello"}`)
	b := []byte(`{"b":"hello","a":1}`)
	eq, err := JSONEqual(a, b)
	if err != nil {
		t.Fatal(err)
	}
	if !eq {
		t.Error("should be equal")
	}

	c := []byte(`{"a":2}`)
	eq2, err := JSONEqual(a, c)
	if err != nil {
		t.Fatal(err)
	}
	if eq2 {
		t.Error("should not be equal")
	}
}

func TestToJSON_Sum(t *testing.T) {
	gv := Sum("Ok", Int(42))
	b, err := ToJSONLoose(gv)
	if err != nil {
		t.Fatal(err)
	}
	if !containsSubstring(string(b), "Ok") {
		t.Errorf("expected Ok in output: %s", string(b))
	}
}

func TestToJSON_Struct(t *testing.T) {
	gv := Struct("Team", MapEntry{Key: "name", Value: Str("Arsenal")})
	b, err := ToJSONLoose(gv)
	if err != nil {
		t.Fatal(err)
	}
	if !containsSubstring(string(b), "Arsenal") {
		t.Errorf("expected Arsenal in output: %s", string(b))
	}
}

// ============================================================
// schema.go — uncovered paths
// ============================================================

func TestSchema_String_ConstraintTypes(t *testing.T) {
	constraints := []Constraint{
		MinConstraint(0),
		MaxConstraint(100),
		MinLenConstraint(1),
		MaxLenConstraint(10),
		LenConstraint(5),
		RegexConstraint("^[a-z]+$"),
		EnumConstraint([]string{"a", "b"}),
		NonEmptyConstraint(),
		RangeConstraint(0, 1),
		OptionalConstraint(),
	}
	for _, c := range constraints {
		s := c.String()
		if s == "" || s == "unknown" {
			t.Errorf("constraint %v should have a string", c.Kind)
		}
	}
}

func TestSchema_GetField(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Team", "",
			Field("name", PrimitiveType("str"), WithWireKey("n")),
		).Build()

	f := schema.GetField("Team", "name")
	if f == nil {
		t.Error("should find field by name")
	}
	f2 := schema.GetField("Team", "n")
	if f2 == nil {
		t.Error("should find field by wire key")
	}
	f3 := schema.GetField("Team", "nonexistent")
	if f3 != nil {
		t.Error("should not find nonexistent field")
	}
	f4 := schema.GetField("NonExistent", "name")
	if f4 != nil {
		t.Error("should not find field in nonexistent type")
	}
}

func TestSchema_Nil(t *testing.T) {
	var s *Schema
	if s.GetType("x") != nil {
		t.Error("nil schema should return nil")
	}
}

// ============================================================
// parse.go — uncovered paths
// ============================================================

func TestParse_Time(t *testing.T) {
	tests := []string{
		"2025-01-01T00:00:00Z",
		"2025-01-01T00:00:00+05:00",
		"2025-01-01",
	}
	for _, tt := range tests {
		result, err := Parse(tt)
		if err != nil {
			t.Errorf("Parse(%q): %v", tt, err)
			continue
		}
		if result.Value.Type() != TypeTime {
			t.Errorf("Parse(%q): expected time, got %v", tt, result.Value.Type())
		}
	}
}

func TestParse_InvalidTime(t *testing.T) {
	// This should fall back to string in tolerant mode
	result, _ := Parse("2025-99-99T00:00:00Z")
	if result.Value.Type() != TypeStr {
		t.Errorf("expected string fallback, got %v", result.Value.Type())
	}
}

func TestParse_StructWithField(t *testing.T) {
	// Exercise parseStructField paths
	input := `Team{name="Arsenal" rank=1 league="EPL"}`
	result, err := Parse(input)
	if err != nil {
		t.Fatal(err)
	}
	sv := result.Value
	if sv.Type() != TypeStruct {
		t.Fatalf("expected struct, got %v", sv.Type())
	}
}

func TestParse_SumWithStruct(t *testing.T) {
	input := `Ok{value=42}`
	result, err := Parse(input)
	if err != nil {
		t.Fatal(err)
	}
	// This could be parsed as struct or sum depending on context
	if result.Value == nil {
		t.Fatal("expected non-nil value")
	}
}

func TestParse_Tolerant_UnexpectedToken(t *testing.T) {
	// In tolerant mode, unexpected tokens should be handled
	result, _ := Parse("[1 2 3]")
	if result == nil || result.Value == nil {
		t.Fatal("expected result")
	}
}

// ============================================================
// loose.go — uncovered paths
// ============================================================

func TestCanonBytes(t *testing.T) {
	got := canonBytes(nil)
	if got != `b64""` {
		t.Errorf("expected b64\"\", got %q", got)
	}
	got2 := canonBytes([]byte("hello"))
	if got2 == "" {
		t.Error("expected non-empty")
	}
}

func TestFingerprintLoose(t *testing.T) {
	v := Map(MapEntry{Key: "a", Value: Int(1)})
	fp := FingerprintLoose(v)
	if fp == "" {
		t.Error("expected non-empty fingerprint")
	}
}

func TestPrettyLooseCanonOpts(t *testing.T) {
	opts := PrettyLooseCanonOpts()
	if !opts.AutoTabular {
		t.Error("expected AutoTabular=true")
	}
}

func TestTabularLooseCanonOpts(t *testing.T) {
	opts := TabularLooseCanonOpts()
	if !opts.AutoTabular {
		t.Error("expected AutoTabular=true")
	}
}

func TestCanonNullWithStyle(t *testing.T) {
	// Exercise the underscore null style via LLM opts
	v := Null()
	opts := LLMLooseCanonOpts()
	got := CanonicalizeLooseWithOpts(v, opts)
	if got != "_" {
		t.Errorf("expected '_', got %q", got)
	}
}

// ============================================================
// streaming.go — uncovered paths
// ============================================================

func TestStreamDict_Decode(t *testing.T) {
	d := NewStreamDict(DefaultStreamDictOptions())
	d.Add("hello")
	got := d.Decode(0)
	if got != "hello" {
		t.Errorf("expected 'hello', got %q", got)
	}
}

func TestStreamSession_DecodeKey_Coverage(t *testing.T) {
	s := NewStreamSession(SessionOptions{DictOptions: DefaultStreamDictOptions()})
	s.Dict().Add("test_key")
	got := s.DecodeKey(0)
	if got != "test_key" {
		t.Errorf("expected 'test_key', got %q", got)
	}
}

func TestStreamSession_LearnKeys_Coverage(t *testing.T) {
	s := NewStreamSession(SessionOptions{DictOptions: DefaultStreamDictOptions()})

	// Learn from a map
	v := Map(
		MapEntry{Key: "name", Value: Str("test")},
		MapEntry{Key: "count", Value: Int(1)},
	)
	s.LearnKeys(v)

	// Should have learned the keys
	d := s.Dict()
	if d.Len() == 0 {
		t.Error("should have learned keys")
	}
}

func TestStreamSession_LearnKeys_Nested_Coverage(t *testing.T) {
	s := NewStreamSession(SessionOptions{DictOptions: DefaultStreamDictOptions()})

	v := Map(
		MapEntry{Key: "outer", Value: Map(
			MapEntry{Key: "inner", Value: Int(1)},
		)},
		MapEntry{Key: "list", Value: List(
			Map(MapEntry{Key: "item_key", Value: Int(1)}),
		)},
	)
	s.LearnKeys(v)
}

func TestStreamSession_EncodeKey_Coverage(t *testing.T) {
	s := NewStreamSession(SessionOptions{
		DictOptions: DefaultStreamDictOptions(),
	})
	s.Dict().Add("test_key")

	idx, ok := s.EncodeKey("test_key")
	if !ok {
		t.Error("should encode known key")
	}
	if idx != 0 {
		t.Errorf("expected 0, got %d", idx)
	}

	// Freeze dict then try unknown (frozen dict rejects adds)
	s.Dict().Freeze()
	_, ok = s.EncodeKey("unknown_frozen")
	// In learning mode, EncodeOrAdd is called but Freeze prevents Add
	// Just ensure we don't panic
	_ = ok
}

// ============================================================
// decimal128.go — uncovered paths
// ============================================================

func TestDecimal128_Add_EdgeCases(t *testing.T) {
	// Test add with different exponents
	a, _ := NewDecimal128FromString("1.5")
	b, _ := NewDecimal128FromString("2.25")
	result, err := a.Add(b)
	if err != nil {
		t.Fatal(err)
	}
	if result.String() != "3.75" {
		t.Errorf("expected 3.75, got %s", result.String())
	}

	// Add with zero
	zero := NewDecimal128FromInt64(0)
	r2, err := a.Add(zero)
	if err != nil {
		t.Fatal(err)
	}
	if r2.String() != "1.5" {
		t.Errorf("expected 1.5, got %s", r2.String())
	}
}

func TestDecimalFromAny(t *testing.T) {
	tests := []struct {
		input interface{}
		err   bool
	}{
		{int64(42), false},
		{int(42), false},
		{float64(3.14), false},
		{"1.5", false},
		{"invalid", true},
		{true, true},
	}
	for _, tt := range tests {
		_, err := DecimalFromAny(tt.input)
		if (err != nil) != tt.err {
			t.Errorf("DecimalFromAny(%v): err=%v, want err=%v", tt.input, err, tt.err)
		}
	}
}

func TestParseDecimalLiteral_Coverage(t *testing.T) {
	d, err := ParseDecimalLiteral("3.14m")
	if err != nil {
		t.Fatal(err)
	}
	if d.String() != "3.14" {
		t.Errorf("expected 3.14, got %s", d.String())
	}

	_, err = ParseDecimalLiteral("notadecimal")
	if err == nil {
		t.Error("expected error")
	}
}

// ============================================================
// token.go — uncovered paths
// ============================================================

func TestTokenType_String(t *testing.T) {
	// Exercise all token type strings
	types := []TokenType{TokenEOF, TokenInt, TokenFloat, TokenString, TokenTrue, TokenFalse, TokenNull, TokenRef, TokenIdent, TokenLBrace, TokenRBrace, TokenLBracket, TokenRBracket, TokenLParen, TokenRParen, TokenEq, TokenAt, TokenTime, TokenBareStr, TokenComma}
	for _, tt := range types {
		s := tt.String()
		if s == "" {
			t.Errorf("token type %d has empty string", tt)
		}
	}
}

func TestTokenStream_PeekN(t *testing.T) {
	lexer := NewLexer("[1 2]")
	tokens, _ := lexer.Tokenize()
	ts := NewTokenStream(tokens)

	tok := ts.PeekN(0) // same as Peek
	if tok.Type != TokenLBracket {
		t.Errorf("expected [, got %v", tok.Type)
	}
	tok2 := ts.PeekN(1)
	if tok2.Type != TokenInt {
		t.Errorf("expected int, got %v", tok2.Type)
	}
	// Past end
	tok3 := ts.PeekN(100)
	if tok3.Type != TokenEOF {
		t.Errorf("expected EOF for past-end peek")
	}
}

func TestTokenStream_Reset(t *testing.T) {
	lexer := NewLexer("42")
	tokens, _ := lexer.Tokenize()
	ts := NewTokenStream(tokens)
	ts.Advance()
	ts.Reset(0)
	tok := ts.Peek()
	if tok.Type != TokenInt {
		t.Error("after reset, should be back at start")
	}
}

func TestTokenStream_Position(t *testing.T) {
	lexer := NewLexer("42")
	tokens, _ := lexer.Tokenize()
	ts := NewTokenStream(tokens)
	pos := ts.Position()
	if pos != 0 {
		t.Errorf("expected position 0, got %d", pos)
	}
}

// ============================================================
// Helpers
// ============================================================

func containsSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
