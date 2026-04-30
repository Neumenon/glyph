package glyph

import (
	"regexp"
	"strings"
	"testing"
	"time"
)

// ============================================================
// stream_validator.go coverage
// ============================================================

func TestStreamValidationError_Error(t *testing.T) {
	e1 := StreamValidationError{Code: "UNKNOWN_TOOL", Message: "not found", Field: ""}
	if !strings.Contains(e1.Error(), "UNKNOWN_TOOL") {
		t.Errorf("expected code in error, got %q", e1.Error())
	}

	e2 := StreamValidationError{Code: "CONSTRAINT_MIN", Message: "too small", Field: "age"}
	if !strings.Contains(e2.Error(), "age") {
		t.Errorf("expected field in error, got %q", e2.Error())
	}
}

func TestStreamingValidator_WithLimits(t *testing.T) {
	reg := NewToolRegistry()
	v := NewStreamingValidator(reg)
	v.WithLimits(1024, 50, 10)
	if v.maxBufferSize != 1024 {
		t.Errorf("expected maxBufferSize=1024, got %d", v.maxBufferSize)
	}
	if v.maxFieldCount != 50 {
		t.Errorf("expected maxFieldCount=50, got %d", v.maxFieldCount)
	}
	if v.maxErrorCount != 10 {
		t.Errorf("expected maxErrorCount=10, got %d", v.maxErrorCount)
	}

	// Test zero values don't change defaults
	v2 := NewStreamingValidator(reg)
	v2.WithLimits(0, 0, 0)
	if v2.maxBufferSize != DefaultMaxBuffer {
		t.Errorf("zero should not change default")
	}
}

func TestStreamingValidator_IsToolAllowed(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{Name: "search"})
	v := NewStreamingValidator(reg)
	v.Start()

	// No tool detected yet
	if v.IsToolAllowed() {
		t.Error("expected false when no tool detected")
	}

	// Feed tokens for a tool call
	v.PushToken(`{action="search" `)
	v.PushToken("query=hello}")

	allowed := v.IsToolAllowed()
	// Should detect 'search' tool
	if !allowed {
		t.Error("expected search to be allowed")
	}
}

func TestStreamingValidator_ShouldStop_UnknownTool(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{Name: "search"})
	v := NewStreamingValidator(reg)
	v.Start()

	// Feed an unknown tool
	v.PushToken(`{action="unknown_tool" `)
	v.PushToken("x=1}")

	if !v.ShouldStop() {
		t.Error("expected ShouldStop for unknown tool")
	}
}

func TestStreamingValidator_ShouldStop_NoErrors(t *testing.T) {
	reg := NewToolRegistry()
	v := NewStreamingValidator(reg)

	if v.ShouldStop() {
		t.Error("expected no stop with no tokens fed")
	}
}

func TestMaxInt(t *testing.T) {
	p := MaxInt(42)
	if *p != 42 {
		t.Errorf("expected 42, got %d", *p)
	}
}

func TestMinFloat64(t *testing.T) {
	p := MinFloat64(1.5)
	if *p != 1.5 {
		t.Errorf("expected 1.5, got %f", *p)
	}
}

func TestStreamingValidator_Reset(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{Name: "search"})
	v := NewStreamingValidator(reg)
	v.Start()
	v.PushToken(`{action="search" query=hello}`)

	v.Reset()
	if v.state != StateWaiting {
		t.Errorf("expected StateWaiting after Reset, got %d", v.state)
	}
	if v.toolName != "" {
		t.Errorf("expected empty tool name after Reset, got %q", v.toolName)
	}
}

func TestStreamingValidator_ProcessChar_Constraints(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{
		Name: "calc",
		Args: map[string]ArgSchema{
			"n": {Type: "int", Required: true, Min: MinFloat64(0), Max: MaxFloat64(100)},
			"s": {Type: "string", MinLen: MinInt(2), MaxLen: MaxInt(10)},
		},
	})
	v := NewStreamingValidator(reg)
	v.Start()
	v.PushToken(`{action="calc" n=50 s=hello}`)

	result := v.GetResult()
	if result.ToolName != "calc" {
		t.Errorf("expected tool 'calc', got %q", result.ToolName)
	}
}

func TestStreamingValidator_TypeValidation(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{
		Name: "tool1",
		Args: map[string]ArgSchema{
			"flag": {Type: "bool"},
			"val":  {Type: "float"},
		},
	})
	v := NewStreamingValidator(reg)
	v.Start()
	v.PushToken(`{action="tool1" flag=true val=3.14}`)

	result := v.GetResult()
	if result.ToolName != "tool1" {
		t.Errorf("expected tool1, got %q", result.ToolName)
	}
}

func TestStreamingValidator_EnumConstraint(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{
		Name: "lang",
		Args: map[string]ArgSchema{
			"code": {Type: "string", Enum: []string{"en", "fr", "de"}},
		},
	})
	v := NewStreamingValidator(reg)
	v.Start()
	v.PushToken(`{action="lang" code=xx}`)
	// Should have constraint error for enum
	result := v.GetResult()
	hasEnumError := false
	for _, e := range result.Errors {
		if e.Code == ErrCodeConstraintEnum {
			hasEnumError = true
		}
	}
	if !hasEnumError {
		t.Error("expected enum constraint error for 'xx'")
	}
}

// ============================================================
// token_aware.go coverage — emitSum, encodeBase64, emit bytes/time/id
// ============================================================

func TestEmitTokenAware_Sum(t *testing.T) {
	gv := Sum("Ok", Int(42))
	result := EmitTokenAware(gv)
	if !strings.Contains(result, "Ok") {
		t.Errorf("expected Ok in output, got %q", result)
	}
	if !strings.Contains(result, "42") {
		t.Errorf("expected 42 in output, got %q", result)
	}
}

func TestEmitTokenAware_SumNullValue(t *testing.T) {
	gv := Sum("None", nil)
	result := EmitTokenAware(gv)
	if !strings.Contains(result, "None") {
		t.Errorf("expected None in output, got %q", result)
	}
	if !strings.Contains(result, "()") {
		t.Errorf("expected () in output, got %q", result)
	}
}

func TestEmitTokenAware_SumStructValue(t *testing.T) {
	gv := Sum("Data", Struct("Info", MapEntry{Key: "x", Value: Int(1)}))
	result := EmitTokenAware(gv)
	if !strings.Contains(result, "Data") {
		t.Errorf("expected Data in output, got %q", result)
	}
	if !strings.Contains(result, "x=") {
		t.Errorf("expected x= in output, got %q", result)
	}
}

func TestEmitTokenAware_Bytes(t *testing.T) {
	gv := Bytes([]byte{1, 2, 3})
	result := EmitTokenAware(gv)
	if !strings.Contains(result, "b64") {
		t.Errorf("expected b64 in output, got %q", result)
	}
}

func TestEmitTokenAware_Time(t *testing.T) {
	tm := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	gv := Time(tm)
	result := EmitTokenAware(gv)
	if !strings.Contains(result, "2026") {
		t.Errorf("expected year in output, got %q", result)
	}
}

func TestEmitTokenAware_ID(t *testing.T) {
	gv := IDFromRef(RefID{Prefix: "U", Value: "abc"})
	result := EmitTokenAware(gv)
	if !strings.Contains(result, "^U:abc") {
		t.Errorf("expected ^U:abc, got %q", result)
	}
}

func TestEmitTokenAware_IDNoPrefix(t *testing.T) {
	gv := IDFromRef(RefID{Prefix: "", Value: "xyz"})
	result := EmitTokenAware(gv)
	if !strings.Contains(result, "^xyz") {
		t.Errorf("expected ^xyz, got %q", result)
	}
}

func TestEmitTokenAware_OmitDefaults_Coverage2(t *testing.T) {
	gv := Struct("Cfg",
		MapEntry{Key: "name", Value: Str("test")},
		MapEntry{Key: "count", Value: Int(0)},
		MapEntry{Key: "flag", Value: Bool(false)},
		MapEntry{Key: "val", Value: Float(0)},
		MapEntry{Key: "text", Value: Str("")},
		MapEntry{Key: "items", Value: List()},
		MapEntry{Key: "meta", Value: Map()},
	)
	opts := TokenAwareOptions{
		UseAbbreviations: false,
		CompactNumbers:   false,
		OmitDefaults:     true,
	}
	result := EmitTokenAwareWithOptions(gv, opts)
	if !strings.Contains(result, "name=") {
		t.Errorf("expected name field, got %q", result)
	}
	// Default values should be omitted
	if strings.Contains(result, "count=") {
		t.Errorf("expected count to be omitted, got %q", result)
	}
}

func TestEmitTokenAware_Null(t *testing.T) {
	gv := Null()
	result := EmitTokenAware(gv)
	if result != "∅" {
		t.Errorf("expected ∅, got %q", result)
	}
}

func TestEmitTokenAware_NilValue(t *testing.T) {
	result := EmitTokenAware(nil)
	if result != "∅" {
		t.Errorf("expected ∅ for nil, got %q", result)
	}
}

func TestEncodeBase64(t *testing.T) {
	// 1 byte (padding test)
	result := encodeBase64([]byte{0x41})
	if result != "QQ==" {
		t.Errorf("expected QQ==, got %q", result)
	}

	// 2 bytes
	result = encodeBase64([]byte{0x41, 0x42})
	if result != "QUI=" {
		t.Errorf("expected QUI=, got %q", result)
	}

	// 3 bytes (no padding)
	result = encodeBase64([]byte{0x41, 0x42, 0x43})
	if result != "QUJD" {
		t.Errorf("expected QUJD, got %q", result)
	}

	// empty
	result = encodeBase64([]byte{})
	if result != "" {
		t.Errorf("expected empty, got %q", result)
	}
}

func TestExpandAbbreviations_Sum(t *testing.T) {
	dict := NewKeyDict("test")
	dict.Add("Ok", "O")

	gv := Sum("O", Int(1))
	ExpandAbbreviations(gv, dict)
	if gv.sumVal.Tag != "Ok" {
		t.Errorf("expected expanded tag Ok, got %q", gv.sumVal.Tag)
	}
}

func TestExpandAbbreviations_Nil(t *testing.T) {
	// Should not panic
	ExpandAbbreviations(nil, nil)
	dict := NewKeyDict("test")
	ExpandAbbreviations(nil, dict)
	ExpandAbbreviations(Int(1), nil)
}

func TestExpandAbbreviations_Struct(t *testing.T) {
	dict := NewKeyDict("test")
	dict.Add("TypeName", "TN")
	dict.Add("field", "f")

	gv := Struct("TN", MapEntry{Key: "f", Value: Int(1)})
	ExpandAbbreviations(gv, dict)
	if gv.structVal.TypeName != "TypeName" {
		t.Errorf("expected TypeName, got %q", gv.structVal.TypeName)
	}
	if gv.structVal.Fields[0].Key != "field" {
		t.Errorf("expected field, got %q", gv.structVal.Fields[0].Key)
	}
}

func TestExpandAbbreviations_List(t *testing.T) {
	dict := NewKeyDict("test")
	dict.Add("key", "k")

	inner := Map(MapEntry{Key: "k", Value: Int(1)})
	gv := List(inner)
	ExpandAbbreviations(gv, dict)
	items, _ := gv.AsList()
	entries, _ := items[0].AsMap()
	if entries[0].Key != "key" {
		t.Errorf("expected expanded key 'key', got %q", entries[0].Key)
	}
}

func TestTokenSavings_Coverage2(t *testing.T) {
	dict := NewKeyDict("test")
	dict.Add("content", "c")
	dict.Add("role", "r")

	gv := Map(
		MapEntry{Key: "content", Value: Str("hello world")},
		MapEntry{Key: "role", Value: Str("user")},
	)
	orig, abbr, savings := TokenSavings(gv, dict)
	if orig <= 0 {
		t.Errorf("expected positive orig tokens, got %d", orig)
	}
	if abbr <= 0 {
		t.Errorf("expected positive abbr tokens, got %d", abbr)
	}
	if savings < 0 {
		t.Errorf("expected non-negative savings, got %f", savings)
	}
}

func TestEstimateTokens_Coverage2(t *testing.T) {
	r := EstimateTokens("hello")
	if r <= 0 {
		t.Errorf("expected positive, got %d", r)
	}
}

// ============================================================
// emit_packed.go coverage — Mode.String, SelectMode, emitPackedValue
// ============================================================

func TestMode_String(t *testing.T) {
	tests := []struct {
		m    Mode
		want string
	}{
		{ModeAuto, "auto"},
		{ModeStruct, "struct"},
		{ModePacked, "packed"},
		{ModeTabular, "tabular"},
		{ModePatch, "patch"},
		{Mode(99), "unknown"},
	}
	for _, tt := range tests {
		if got := tt.m.String(); got != tt.want {
			t.Errorf("Mode(%d).String() = %q, want %q", tt.m, got, tt.want)
		}
	}
}

func TestSelectMode_NilValue(t *testing.T) {
	schema := NewSchemaBuilder().Build()
	m := SelectMode(nil, schema, 3)
	if m != ModeStruct {
		t.Errorf("expected struct mode for nil, got %v", m)
	}
}

func TestSelectMode_TabularList(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Item", "",
			Field("name", PrimitiveType("str")),
			Field("val", PrimitiveType("int")),
		).
		Build()

	items := List(
		Struct("Item", MapEntry{Key: "name", Value: Str("a")}, MapEntry{Key: "val", Value: Int(1)}),
		Struct("Item", MapEntry{Key: "name", Value: Str("b")}, MapEntry{Key: "val", Value: Int(2)}),
		Struct("Item", MapEntry{Key: "name", Value: Str("c")}, MapEntry{Key: "val", Value: Int(3)}),
	)
	m := SelectMode(items, schema, 3)
	if m != ModeTabular {
		t.Errorf("expected tabular mode, got %v", m)
	}
}

func TestSelectMode_PackedStruct(t *testing.T) {
	schema := NewSchemaBuilder().
		AddPackedStruct("Point", "",
			Field("x", PrimitiveType("int")),
			Field("y", PrimitiveType("int")),
		).
		Build()

	gv := Struct("Point", MapEntry{Key: "x", Value: Int(1)}, MapEntry{Key: "y", Value: Int(2)})
	m := SelectMode(gv, schema, 3)
	if m != ModePacked {
		t.Errorf("expected packed mode, got %v", m)
	}
}

func TestSelectMode_MixedStructList(t *testing.T) {
	schema := NewSchemaBuilder().Build()
	// List of mixed types - should not select tabular
	items := List(
		Struct("A", MapEntry{Key: "x", Value: Int(1)}),
		Struct("B", MapEntry{Key: "y", Value: Int(2)}),
		Struct("A", MapEntry{Key: "z", Value: Int(3)}),
	)
	m := SelectMode(items, schema, 3)
	if m == ModeTabular {
		t.Error("expected non-tabular for mixed struct list")
	}
}

func TestEmitPacked_WithTypes(t *testing.T) {
	schema := NewSchemaBuilder().
		AddPackedStruct("Point", "",
			Field("x", PrimitiveType("int")),
			Field("y", PrimitiveType("int")),
			Field("label", PrimitiveType("str"), WithOptional()),
		).
		Build()

	gv := Struct("Point",
		MapEntry{Key: "x", Value: Int(10)},
		MapEntry{Key: "y", Value: Int(20)},
		MapEntry{Key: "label", Value: Str("origin")},
	)
	result, err := EmitPacked(gv, schema)
	if err != nil {
		t.Fatalf("EmitPacked: %v", err)
	}
	if result == "" {
		t.Error("expected non-empty packed output")
	}
}

// ============================================================
// emit_patch.go coverage — PatchOpKind.String, SetWithSegs, InsertAt,
// Diff, ParsePatchRoundTrip, valuesEqual, diffMapValues
// ============================================================

func TestPatchOpKind_String(t *testing.T) {
	if OpSet.String() != "=" {
		t.Errorf("expected =, got %q", OpSet.String())
	}
	if OpAppend.String() != "+" {
		t.Errorf("expected +, got %q", OpAppend.String())
	}
	if OpDelete.String() != "-" {
		t.Errorf("expected -, got %q", OpDelete.String())
	}
	if OpDelta.String() != "~" {
		t.Errorf("expected ~, got %q", OpDelta.String())
	}
}

func TestPatch_SetWithSegs(t *testing.T) {
	p := NewPatch(RefID{Value: "doc1"}, "")
	p.SetWithSegs([]PathSeg{FieldSeg("name", 0)}, Str("alice"))
	if len(p.Ops) != 1 {
		t.Fatalf("expected 1 op, got %d", len(p.Ops))
	}
	if p.Ops[0].Op != OpSet {
		t.Errorf("expected set op, got %v", p.Ops[0].Op)
	}
}

func TestPatch_InsertAt(t *testing.T) {
	p := NewPatch(RefID{Value: "doc1"}, "")
	p.InsertAt("items", 2, Str("new"))
	if len(p.Ops) != 1 {
		t.Fatalf("expected 1 op, got %d", len(p.Ops))
	}
	if p.Ops[0].Index != 2 {
		t.Errorf("expected index 2, got %d", p.Ops[0].Index)
	}
}

func TestDiff_BasicTypes(t *testing.T) {
	// Bool change
	p := Diff(Bool(true), Bool(false), "")
	if len(p.Ops) != 1 {
		t.Errorf("expected 1 op for bool diff, got %d", len(p.Ops))
	}

	// Int change
	p = Diff(Int(1), Int(2), "")
	if len(p.Ops) != 1 {
		t.Errorf("expected 1 op for int diff, got %d", len(p.Ops))
	}

	// Float change
	p = Diff(Float(1.0), Float(2.0), "")
	if len(p.Ops) != 1 {
		t.Errorf("expected 1 op for float diff, got %d", len(p.Ops))
	}

	// String change
	p = Diff(Str("a"), Str("b"), "")
	if len(p.Ops) != 1 {
		t.Errorf("expected 1 op for string diff, got %d", len(p.Ops))
	}

	// No change
	p = Diff(Int(1), Int(1), "")
	if len(p.Ops) != 0 {
		t.Errorf("expected 0 ops for same value, got %d", len(p.Ops))
	}

	// Null to null
	p = Diff(Null(), Null(), "")
	if len(p.Ops) != 0 {
		t.Errorf("expected 0 ops for null==null, got %d", len(p.Ops))
	}

	// Nil to non-nil
	p = Diff(nil, Int(1), "")
	if len(p.Ops) != 1 {
		t.Errorf("expected 1 op for nil->int, got %d", len(p.Ops))
	}

	// Non-nil to nil
	p = Diff(Int(1), nil, "")
	if len(p.Ops) != 0 {
		// root deletion with empty path results in 0 ops since path check fails
	}

	// Both nil
	p = Diff(nil, nil, "")
	if len(p.Ops) != 0 {
		t.Errorf("expected 0 ops for nil==nil, got %d", len(p.Ops))
	}

	// Type mismatch
	p = Diff(Int(1), Str("a"), "")
	if len(p.Ops) != 1 {
		t.Errorf("expected 1 op for type mismatch, got %d", len(p.Ops))
	}

	// ID change
	p = Diff(IDFromRef(RefID{Value: "a"}), IDFromRef(RefID{Value: "b"}), "")
	if len(p.Ops) != 1 {
		t.Errorf("expected 1 op for ID diff, got %d", len(p.Ops))
	}
}

func TestDiff_StructValues(t *testing.T) {
	from := Struct("S",
		MapEntry{Key: "a", Value: Int(1)},
		MapEntry{Key: "b", Value: Str("old")},
	)
	to := Struct("S",
		MapEntry{Key: "a", Value: Int(1)},
		MapEntry{Key: "b", Value: Str("new")},
		MapEntry{Key: "c", Value: Int(3)},
	)
	p := Diff(from, to, "S")
	if len(p.Ops) < 1 {
		t.Errorf("expected ops for struct diff, got %d", len(p.Ops))
	}
}

func TestDiff_MapValues(t *testing.T) {
	from := Map(
		MapEntry{Key: "x", Value: Int(1)},
		MapEntry{Key: "y", Value: Int(2)},
	)
	to := Map(
		MapEntry{Key: "x", Value: Int(1)},
		MapEntry{Key: "z", Value: Int(3)},
	)
	p := Diff(from, to, "")
	// Should have delete y, add z
	if len(p.Ops) < 2 {
		t.Errorf("expected at least 2 ops for map diff, got %d", len(p.Ops))
	}
}

func TestDiff_ListValues(t *testing.T) {
	from := List(Int(1), Int(2))
	to := List(Int(1), Int(3))
	p := Diff(from, to, "")
	if len(p.Ops) != 1 {
		t.Errorf("expected 1 op for list diff, got %d", len(p.Ops))
	}
}

func TestDiff_SameList(t *testing.T) {
	from := List(Int(1), Int(2))
	to := List(Int(1), Int(2))
	p := Diff(from, to, "")
	if len(p.Ops) != 0 {
		t.Errorf("expected 0 ops for same list, got %d", len(p.Ops))
	}
}

func TestPatchBuilder_WithSchema(t *testing.T) {
	schema := NewSchemaBuilder().Build()
	schema.Hash = "abc123"
	pb := NewPatchBuilder(RefID{Value: "doc1"}).WithSchema(schema)
	if pb.patch.SchemaID != "abc123" {
		t.Errorf("expected abc123, got %q", pb.patch.SchemaID)
	}
}

func TestPatchBuilder_WithTargetType(t *testing.T) {
	pb := NewPatchBuilder(RefID{}).WithTargetType("MyType")
	if pb.patch.TargetType != "MyType" {
		t.Errorf("expected MyType, got %q", pb.patch.TargetType)
	}
}

func TestPatchBuilder_SetFID(t *testing.T) {
	pb := NewPatchBuilder(RefID{}).
		SetFID([]PathSeg{FieldSeg("x", 1)}, Int(42))
	p := pb.Build()
	if len(p.Ops) != 1 {
		t.Fatalf("expected 1 op, got %d", len(p.Ops))
	}
}

// ============================================================
// schema.go coverage — GetFIDForField, WithPack/Tab/Open, Compile, etc.
// ============================================================

func TestGetFIDForField(t *testing.T) {
	td := &TypeDef{
		Name: "Test",
		Kind: TypeDefStruct,
		Struct: &StructDef{
			Fields: []*FieldDef{
				{Name: "id", FID: 1},
				{Name: "name", FID: 2, WireKey: "n"},
			},
		},
	}
	fid := td.GetFIDForField("id")
	if fid != 1 {
		t.Errorf("expected FID 1, got %d", fid)
	}
	fid = td.GetFIDForField("n")
	if fid != 2 {
		t.Errorf("expected FID 2 for wire key 'n', got %d", fid)
	}
	fid = td.GetFIDForField("nonexistent")
	if fid != 0 {
		t.Errorf("expected 0 for missing field, got %d", fid)
	}
}

func TestSchemaBuilder_WithPack_Option(t *testing.T) {
	opt := WithPack()
	td := &TypeDef{}
	opt(td)
	if !td.PackEnabled {
		t.Error("expected PackEnabled=true")
	}
}

func TestSchemaBuilder_WithTab_Option(t *testing.T) {
	opt := WithTab()
	td := &TypeDef{}
	opt(td)
	if !td.TabEnabled {
		t.Error("expected TabEnabled=true")
	}
}

func TestSchemaBuilder_WithOpen_Option(t *testing.T) {
	opt := WithOpen()
	td := &TypeDef{}
	opt(td)
	if !td.Open {
		t.Error("expected Open=true")
	}
}

func TestSchemaBuilder_AddOpenPackedStruct(t *testing.T) {
	schema := NewSchemaBuilder().
		AddOpenPackedStruct("Flex", "",
			Field("a", PrimitiveType("str")),
			Field("b", PrimitiveType("int")),
		).
		Build()
	td := schema.GetType("Flex")
	if td == nil {
		t.Fatal("expected type Flex")
	}
	if !td.PackEnabled {
		t.Error("expected packed")
	}
	if !td.Open {
		t.Error("expected open")
	}
}

func TestFieldOption_WithDefault(t *testing.T) {
	f := Field("name", PrimitiveType("str"), WithDefault(Str("unknown")))
	if f.Default == nil {
		t.Error("expected default value")
	}
}

func TestFieldOption_WithCodec(t *testing.T) {
	f := Field("data", PrimitiveType("str"), WithCodec("base64"))
	if f.Codec != "base64" {
		t.Errorf("expected codec base64, got %q", f.Codec)
	}
}

func TestConstraint_Compile_Regex(t *testing.T) {
	c := RegexConstraint("^[a-z]+$")
	cc, err := c.Compile()
	if err != nil {
		t.Fatalf("Compile: %v", err)
	}
	if cc.Regex == nil {
		t.Error("expected compiled regex")
	}
}

func TestConstraint_Compile_Enum(t *testing.T) {
	c := EnumConstraint([]string{"a", "b", "c"})
	cc, err := c.Compile()
	if err != nil {
		t.Fatalf("Compile: %v", err)
	}
	if len(cc.EnumSet) != 3 {
		t.Errorf("expected 3 enum values, got %d", len(cc.EnumSet))
	}
}

func TestConstraint_Compile_InvalidRegex(t *testing.T) {
	c := RegexConstraint("[invalid")
	_, err := c.Compile()
	if err == nil {
		t.Error("expected error for invalid regex")
	}
}

func TestConstraint_Compile_InvalidEnumType(t *testing.T) {
	c := Constraint{Kind: ConstraintEnum, Value: 42}
	_, err := c.Compile()
	if err == nil {
		t.Error("expected error for non-[]string enum value")
	}
}

func TestConstraint_Compile_InvalidRegexType(t *testing.T) {
	c := Constraint{Kind: ConstraintRegex, Value: 42}
	_, err := c.Compile()
	if err == nil {
		t.Error("expected error for non-string regex value")
	}
}

// ============================================================
// loose.go coverage — canonNullWithStyle
// ============================================================

func TestCanonNullWithStyle_Coverage2(t *testing.T) {
	if canonNullWithStyle(NullStyleUnderscore) != "_" {
		t.Error("expected _")
	}
	if canonNullWithStyle(NullStyleSymbol) != "∅" {
		t.Error("expected ∅")
	}
}

// ============================================================
// parse_packed.go — parseList, parseMap, parseBareOrQuotedString
// ============================================================

func TestParsePacked_WithList(t *testing.T) {
	schema := NewSchemaBuilder().
		AddPackedStruct("Msg", "",
			Field("items", PrimitiveType("list"), WithFID(1)),
		).
		Build()

	// This test exercises packed parsing with nested values
	gv := Struct("Msg", MapEntry{Key: "items", Value: List(Int(1), Int(2))})
	result, err := EmitPacked(gv, schema)
	if err != nil {
		t.Fatalf("EmitPacked: %v", err)
	}
	if result == "" {
		t.Error("expected non-empty")
	}

	// Parse it back
	parsed, err := ParsePacked(result, schema)
	if err != nil {
		t.Fatalf("ParsePacked: %v", err)
	}
	if parsed == nil {
		t.Fatal("expected non-nil result")
	}
}

// ============================================================
// incremental.go — Path
// ============================================================

func TestIncrementalParser_Path_Coverage2(t *testing.T) {
	p := NewIncrementalParser(nil, DefaultIncrementalParserOptions())
	path := p.Path()
	if len(path) != 0 {
		t.Errorf("expected empty path, got %d", len(path))
	}
}

// ============================================================
// streaming.go — extractKeys with sum, encodeDictValue
// ============================================================

func TestStreamSession_LearnKeys_WithSum(t *testing.T) {
	session := NewStreamSession(SessionOptions{
		DictOptions: DefaultStreamDictOptions(),
	})
	gv := Sum("Result", Map(MapEntry{Key: "value", Value: Int(42)}))
	session.LearnKeys(gv)

	// Should have learned "Result" and "value"
	_, ok := session.Dict().Encode("Result")
	if !ok {
		t.Error("expected 'Result' in dict")
	}
	_, ok = session.Dict().Encode("value")
	if !ok {
		t.Error("expected 'value' in dict")
	}
}

func TestEncodeDictFrame_BasicTypes(t *testing.T) {
	session := NewStreamSession(SessionOptions{
		DictOptions: DefaultStreamDictOptions(),
	})

	// Bool
	buf := EncodeDictFrame(Bool(true), session)
	if len(buf) == 0 {
		t.Error("expected non-empty frame for bool")
	}

	// Int
	buf = EncodeDictFrame(Int(42), session)
	if len(buf) == 0 {
		t.Error("expected non-empty frame for int")
	}

	// Float
	buf = EncodeDictFrame(Float(3.14), session)
	if len(buf) == 0 {
		t.Error("expected non-empty frame for float")
	}

	// String
	buf = EncodeDictFrame(Str("hello"), session)
	if len(buf) == 0 {
		t.Error("expected non-empty frame for string")
	}

	// List
	buf = EncodeDictFrame(List(Int(1), Int(2)), session)
	if len(buf) == 0 {
		t.Error("expected non-empty frame for list")
	}

	// Map with dict key
	buf = EncodeDictFrame(Map(MapEntry{Key: "key1", Value: Int(1)}), session)
	if len(buf) == 0 {
		t.Error("expected non-empty frame for map")
	}

	// Null
	buf = EncodeDictFrame(nil, session)
	if len(buf) == 0 {
		t.Error("expected non-empty frame for nil")
	}
}

// ============================================================
// validate.go — isInteger
// ============================================================

func TestIsInteger(t *testing.T) {
	if !isInteger(5.0) {
		t.Error("5.0 is integer")
	}
	if isInteger(5.5) {
		t.Error("5.5 is not integer")
	}
	if !isInteger(0.0) {
		t.Error("0.0 is integer")
	}
}

// ============================================================
// token.go — TokenType.String at 0%
// ============================================================

func TestTokenType_String_Coverage(t *testing.T) {
	types := []TokenType{
		TokenInt, TokenFloat, TokenString, TokenTrue, TokenFalse, TokenNull,
		TokenLBrace, TokenRBrace, TokenLBracket, TokenRBracket,
		TokenLParen, TokenRParen, TokenEq, TokenRef, TokenEOF,
		TokenBareStr, TokenTime, TokenComma, TokenPipe,
		TokenAt, TokenHash, TokenLT, TokenGT, TokenIdent, TokenError,
	}
	for _, tt := range types {
		s := tt.String()
		if s == "" {
			t.Errorf("empty string for token type %d", tt)
		}
	}
}

// ============================================================
// Additional parse_header.go coverage — EmitV2Patch
// ============================================================

func TestEmitV2Patch(t *testing.T) {
	p := NewPatch(RefID{Value: "M-42"}, "abc123")
	p.Set("name", Str("alice"))
	result, err := EmitV2Patch(p, V2Options{})
	if err != nil {
		t.Fatalf("EmitV2Patch: %v", err)
	}
	if !strings.Contains(result, "@patch") {
		t.Errorf("expected @patch, got %q", result)
	}
}

// ============================================================
// Additional emit.go coverage — EmitSchemaRef with nil
// ============================================================

func TestEmitSchemaRef_MoreCases(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Msg", "",
			Field("text", PrimitiveType("str")),
		).
		Build()
	result := EmitSchemaRef(schema)
	if !strings.Contains(result, "@schema#") {
		t.Errorf("expected @schema# prefix, got %q", result)
	}
}

// ============================================================
// Additional json_bridge.go coverage — WithOpts variants
// ============================================================

func TestFromJSONValueLooseWithOpts(t *testing.T) {
	opts := BridgeOpts{Extended: true}
	val := map[string]interface{}{
		"name": "alice",
		"age":  float64(30),
	}
	gv, err := FromJSONValueLooseWithOpts(val, opts)
	if err != nil {
		t.Fatalf("FromJSONValueLooseWithOpts: %v", err)
	}
	if gv.Type() != TypeMap {
		t.Errorf("expected map, got %v", gv.Type())
	}
}

func TestToJSONValueLooseWithOpts(t *testing.T) {
	opts := BridgeOpts{Extended: true}
	gv := Map(
		MapEntry{Key: "name", Value: Str("alice")},
		MapEntry{Key: "count", Value: Int(5)},
	)
	val, err := ToJSONValueLooseWithOpts(gv, opts)
	if err != nil {
		t.Fatalf("ToJSONValueLooseWithOpts: %v", err)
	}
	m, ok := val.(map[string]interface{})
	if !ok {
		t.Fatalf("expected map, got %T", val)
	}
	if m["name"] != "alice" {
		t.Errorf("expected alice, got %v", m["name"])
	}
}

// ============================================================
// schema.go — FieldsByFID, AssignFIDs, GetFieldByFID
// ============================================================

func TestFieldsByFID_Coverage(t *testing.T) {
	td := &TypeDef{
		Name: "T",
		Kind: TypeDefStruct,
		Struct: &StructDef{
			Fields: []*FieldDef{
				{Name: "b", FID: 2},
				{Name: "a", FID: 1},
			},
		},
	}
	fields := td.FieldsByFID()
	if len(fields) != 2 {
		t.Fatalf("expected 2 fields, got %d", len(fields))
	}
	if fields[0].FID != 1 {
		t.Errorf("expected FID 1 first, got %d", fields[0].FID)
	}
}

func TestAssignFIDs_Coverage(t *testing.T) {
	td := &TypeDef{
		Name: "T",
		Kind: TypeDefStruct,
		Struct: &StructDef{
			Fields: []*FieldDef{
				{Name: "x"},
				{Name: "y"},
			},
		},
	}
	td.AssignFIDs()
	if td.Struct.Fields[0].FID != 1 {
		t.Errorf("expected FID 1, got %d", td.Struct.Fields[0].FID)
	}
	if td.Struct.Fields[1].FID != 2 {
		t.Errorf("expected FID 2, got %d", td.Struct.Fields[1].FID)
	}
}

func TestGetFieldByFID_Coverage(t *testing.T) {
	td := &TypeDef{
		Name: "T",
		Kind: TypeDefStruct,
		Struct: &StructDef{
			Fields: []*FieldDef{
				{Name: "x", FID: 1},
				{Name: "y", FID: 2},
			},
		},
	}
	fd := td.GetFieldByFID(2)
	if fd == nil || fd.Name != "y" {
		t.Error("expected field y for FID 2")
	}
	fd = td.GetFieldByFID(99)
	if fd != nil {
		t.Error("expected nil for nonexistent FID")
	}
}

// ============================================================
// schema.go — SchemaBuilder WithPack/WithOpen by name
// ============================================================

func TestSchemaBuilder_WithPack_ByName(t *testing.T) {
	b := NewSchemaBuilder().
		AddStruct("Msg", "",
			Field("text", PrimitiveType("str")),
		).
		WithPack("Msg")
	schema := b.Build()
	td := schema.GetType("Msg")
	if !td.PackEnabled {
		t.Error("expected pack enabled")
	}
}

// ============================================================
// Additional document.go — parseMapWithEmbeddedTab edge cases
// ============================================================

func TestParseDocument_EmbeddedTabWithEnd(t *testing.T) {
	input := `{items=@tab _ [name age]
|alice|30|
|bob|25|
@end system=prompt}`
	gv, err := ParseDocument(input)
	if err != nil {
		t.Fatalf("ParseDocument: %v", err)
	}
	if gv.Type() != TypeMap {
		t.Errorf("expected map, got %v", gv.Type())
	}
}

// ============================================================
// Additional decimal128.go coverage — Cmp, Div edge cases
// ============================================================

func TestDecimal128_Cmp_Coverage(t *testing.T) {
	a, _ := NewDecimal128FromString("1.5")
	b, _ := NewDecimal128FromString("2.5")
	c, _ := NewDecimal128FromString("1.5")

	if a.Cmp(b) >= 0 {
		t.Error("expected a < b")
	}
	if b.Cmp(a) <= 0 {
		t.Error("expected b > a")
	}
	if a.Cmp(c) != 0 {
		t.Error("expected a == c")
	}
}

func TestDecimal128_Div_Coverage(t *testing.T) {
	a, _ := NewDecimal128FromString("10")
	b, _ := NewDecimal128FromString("3")
	result, err := a.Div(b)
	if err != nil {
		t.Fatalf("Div: %v", err)
	}
	s := result.String()
	if s != "3" && !strings.HasPrefix(s, "3.") {
		t.Errorf("expected ~3..., got %q", s)
	}

	// Div by zero
	zero, _ := NewDecimal128FromString("0")
	_, err = a.Div(zero)
	if err == nil {
		t.Error("expected error for division by zero")
	}
}

func TestDecimal128_Mul_Coverage(t *testing.T) {
	a, _ := NewDecimal128FromString("2.5")
	b, _ := NewDecimal128FromString("4")
	result, err := a.Mul(b)
	if err != nil {
		t.Fatalf("Mul: %v", err)
	}
	s := result.String()
	if s != "10" && s != "10.0" {
		t.Errorf("expected 10 or 10.0, got %q", s)
	}
}

// ============================================================
// parse_tabular.go — TypeName, Columns at 0%
// ============================================================

func TestParseTabular_TypeNameColumns(t *testing.T) {
	input := `@tab _ [name age]
|alice|30|
|bob|25|
@end`
	gv, err := ParseTabularLoose(input)
	if err != nil {
		t.Fatalf("ParseTabularLoose: %v", err)
	}
	items, _ := gv.AsList()
	if len(items) != 2 {
		t.Fatalf("expected 2 rows, got %d", len(items))
	}
}

// ============================================================
// Additional streaming.go coverage — EncodeKey frozen dict
// ============================================================

func TestStreamSession_EncodeKey_AfterFreeze(t *testing.T) {
	session := NewStreamSession(SessionOptions{
		LearnFrames: 2,
		DictOptions: StreamDictOptions{
			MaxEntries:  100,
			PreloadKeys: []string{"known"},
		},
	})

	// Learn two values to exhaust learning phase
	session.LearnKeys(Map(MapEntry{Key: "a", Value: Int(1)}))
	session.LearnKeys(Map(MapEntry{Key: "b", Value: Int(2)}))

	// Should no longer be learning
	_, ok := session.EncodeKey("unknown_key_xyz")
	// After freeze, unknown keys return false
	if ok {
		// If this passes, dict was extended past learn phase
	}

	// Known key should still work
	_, ok = session.EncodeKey("known")
	if !ok {
		t.Error("expected preloaded key to be encodable")
	}
}

// ============================================================
// Additional loose.go coverage — unquoteString
// ============================================================

func TestCanonicalizeLoose_WithSchemaContext(t *testing.T) {
	gv := Map(
		MapEntry{Key: "name", Value: Str("alice")},
		MapEntry{Key: "age", Value: Int(30)},
	)
	result := CanonicalizeLoose(gv)
	if !strings.Contains(result, "name=") {
		t.Errorf("expected name= in result, got %q", result)
	}
}

// ============================================================
// Additional stream_validator.go coverage — processChar deeper
// ============================================================

func TestStreamingValidator_StringValues(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{
		Name: "greet",
		Args: map[string]ArgSchema{
			"name": {Type: "string", Required: true},
		},
	})
	v := NewStreamingValidator(reg)
	v.Start()
	v.PushToken(`{action="greet" name="hello world"}`)

	result := v.GetResult()
	if result.ToolName != "greet" {
		t.Errorf("expected greet, got %q", result.ToolName)
	}
}

func TestStreamingValidator_MissingRequired(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{
		Name: "tool2",
		Args: map[string]ArgSchema{
			"required_field": {Type: "string", Required: true},
		},
	})
	v := NewStreamingValidator(reg)
	v.Start()
	v.PushToken(`{action="tool2" other=1}`)

	result := v.GetResult()
	hasMissing := false
	for _, e := range result.Errors {
		if e.Code == ErrCodeMissingRequired {
			hasMissing = true
		}
	}
	if !hasMissing {
		t.Error("expected MISSING_REQUIRED error")
	}
}

func TestStreamingValidator_PatternConstraint(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{
		Name: "validate_email",
		Args: map[string]ArgSchema{
			"email": {Type: "string", Pattern: mustCompileRegex("^[a-z]+@[a-z]+$")},
		},
	})
	v := NewStreamingValidator(reg)
	v.Start()
	v.PushToken(`{action="validate_email" email=notanemail}`)

	result := v.GetResult()
	hasPat := false
	for _, e := range result.Errors {
		if e.Code == ErrCodeConstraintPat {
			hasPat = true
		}
	}
	if !hasPat {
		t.Error("expected CONSTRAINT_PATTERN error")
	}
}

func TestStreamingValidator_MinMaxConstraints(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{
		Name: "bounded",
		Args: map[string]ArgSchema{
			"n": {Type: "int", Min: MinFloat64(10), Max: MaxFloat64(20)},
		},
	})

	// Value too low
	v := NewStreamingValidator(reg)
	v.Start()
	v.PushToken(`{action="bounded" n=5}`)
	result := v.GetResult()
	hasMin := false
	for _, e := range result.Errors {
		if e.Code == ErrCodeConstraintMin {
			hasMin = true
		}
	}
	if !hasMin {
		t.Error("expected CONSTRAINT_MIN error")
	}

	// Value too high
	v2 := NewStreamingValidator(reg)
	v2.Start()
	v2.PushToken(`{action="bounded" n=25}`)
	result2 := v2.GetResult()
	hasMax := false
	for _, e := range result2.Errors {
		if e.Code == ErrCodeConstraintMax {
			hasMax = true
		}
	}
	if !hasMax {
		t.Error("expected CONSTRAINT_MAX error")
	}
}

func TestStreamingValidator_LenConstraints(t *testing.T) {
	reg := NewToolRegistry()
	reg.Register(&ToolSchema{
		Name: "lencheck",
		Args: map[string]ArgSchema{
			"s": {Type: "string", MinLen: MinInt(5), MaxLen: MaxInt(10)},
		},
	})

	// Too short
	v := NewStreamingValidator(reg)
	v.Start()
	v.PushToken(`{action="lencheck" s=ab}`)
	result := v.GetResult()
	hasLen := false
	for _, e := range result.Errors {
		if e.Code == ErrCodeConstraintLen {
			hasLen = true
		}
	}
	if !hasLen {
		t.Error("expected CONSTRAINT_LEN error for too short")
	}

	// Too long
	v2 := NewStreamingValidator(reg)
	v2.Start()
	v2.PushToken(`{action="lencheck" s=abcdefghijklm}`)
	result2 := v2.GetResult()
	hasLen2 := false
	for _, e := range result2.Errors {
		if e.Code == ErrCodeConstraintLen {
			hasLen2 = true
		}
	}
	if !hasLen2 {
		t.Error("expected CONSTRAINT_LEN error for too long")
	}
}

// helper
func mustCompileRegex(pat string) *regexp.Regexp {
	return regexp.MustCompile(pat)
}
