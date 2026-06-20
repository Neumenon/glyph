package glyph

import "testing"

// ============================================================
// @open Struct Tests
// ============================================================

func TestOpenStruct_AcceptsUnknownFields(t *testing.T) {
	schema := NewSchemaBuilder().
		AddOpenStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
			Field("port", PrimitiveType("int")),
		).
		Build()

	// Value with known + unknown fields
	value := Struct("Config",
		MapEntry{Key: "name", Value: Str("myapp")},
		MapEntry{Key: "port", Value: Int(8080)},
		MapEntry{Key: "debug", Value: Bool(true)}, // unknown
		MapEntry{Key: "timeout", Value: Int(30)},  // unknown
	)

	result := ValidateWithSchema(value, schema)

	// Should pass validation
	if !result.Valid {
		t.Errorf("Expected valid, got errors: %v", result.Errors)
	}

	// Should have warnings for unknown fields
	if len(result.Warnings) != 2 {
		t.Errorf("Expected 2 warnings for unknown fields, got %d: %v", len(result.Warnings), result.Warnings)
	}
}

func TestClosedStruct_RejectsUnknownFields(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
			Field("port", PrimitiveType("int")),
		).
		Build()

	// Value with unknown field
	value := Struct("Config",
		MapEntry{Key: "name", Value: Str("myapp")},
		MapEntry{Key: "port", Value: Int(8080)},
		MapEntry{Key: "debug", Value: Bool(true)}, // unknown - should fail
	)

	result := ValidateWithSchema(value, schema)

	// Should fail validation
	if result.Valid {
		t.Error("Expected validation to fail for unknown field in closed struct")
	}

	// Should have error for unknown field
	found := false
	for _, err := range result.Errors {
		if err.Code == "unknown_field" {
			found = true
			break
		}
	}
	if !found {
		t.Error("Expected unknown_field error")
	}
}

func TestStrictValidation_RejectsEvenOpenStruct(t *testing.T) {
	schema := NewSchemaBuilder().
		AddOpenStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
		).
		Build()

	value := Struct("Config",
		MapEntry{Key: "name", Value: Str("myapp")},
		MapEntry{Key: "extra", Value: Bool(true)}, // unknown
	)

	// Normal validation should pass
	normalResult := ValidateWithSchema(value, schema)
	if !normalResult.Valid {
		t.Errorf("Normal validation should pass for @open struct")
	}

	// Strict validation should fail
	strictResult := ValidateStrict(value, schema)
	if strictResult.Valid {
		t.Error("Strict validation should fail even for @open struct")
	}
}

// ============================================================
// map<str,T> Validation Tests
// ============================================================

func TestMapStrInt_AcceptsValidValues(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
			Field("settings", MapType(PrimitiveType("str"), PrimitiveType("int"))),
		).
		Build()

	// Map with all int values - should pass
	value := Struct("Config",
		MapEntry{Key: "name", Value: Str("myapp")},
		MapEntry{Key: "settings", Value: Map(
			MapEntry{Key: "timeout", Value: Int(30)},
			MapEntry{Key: "retries", Value: Int(3)},
			MapEntry{Key: "port", Value: Int(8080)},
		)},
	)

	result := ValidateWithSchema(value, schema)
	if !result.Valid {
		t.Errorf("Expected valid, got errors: %v", result.Errors)
	}
}

func TestMapStrInt_RejectsInvalidValues(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
			Field("settings", MapType(PrimitiveType("str"), PrimitiveType("int"))),
		).
		Build()

	// Map with string value where int expected - should fail
	value := Struct("Config",
		MapEntry{Key: "name", Value: Str("myapp")},
		MapEntry{Key: "settings", Value: Map(
			MapEntry{Key: "timeout", Value: Int(30)},
			MapEntry{Key: "name", Value: Str("invalid")}, // wrong type!
			MapEntry{Key: "port", Value: Int(8080)},
		)},
	)

	result := ValidateWithSchema(value, schema)
	if result.Valid {
		t.Error("Expected validation to fail for string in map<str,int>")
	}

	// Should have type_mismatch error for the invalid value
	found := false
	for _, err := range result.Errors {
		if err.Code == "type_mismatch" && err.Path == "settings.name" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("Expected type_mismatch error at settings.name, got: %v", result.Errors)
	}
}

func TestMapStrStr_AcceptsValidValues(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Metadata", "v1",
			Field("labels", MapType(PrimitiveType("str"), PrimitiveType("str"))),
		).
		Build()

	value := Struct("Metadata",
		MapEntry{Key: "labels", Value: Map(
			MapEntry{Key: "app", Value: Str("frontend")},
			MapEntry{Key: "env", Value: Str("production")},
		)},
	)

	result := ValidateWithSchema(value, schema)
	if !result.Valid {
		t.Errorf("Expected valid, got errors: %v", result.Errors)
	}
}

func TestMapStrRef_ValidatesNestedTypes(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Address", "v1",
			Field("host", PrimitiveType("str")),
			Field("port", PrimitiveType("int")),
		).
		AddStruct("Registry", "v1",
			Field("services", MapType(PrimitiveType("str"), RefType("Address"))),
		).
		Build()

	// Valid: map values are valid Address structs
	validValue := Struct("Registry",
		MapEntry{Key: "services", Value: Map(
			MapEntry{Key: "api", Value: Struct("Address",
				MapEntry{Key: "host", Value: Str("localhost")},
				MapEntry{Key: "port", Value: Int(8080)},
			)},
			MapEntry{Key: "db", Value: Struct("Address",
				MapEntry{Key: "host", Value: Str("db.local")},
				MapEntry{Key: "port", Value: Int(5432)},
			)},
		)},
	)

	result := ValidateWithSchema(validValue, schema)
	if !result.Valid {
		t.Errorf("Expected valid, got errors: %v", result.Errors)
	}

	// Invalid: map value is missing required field
	invalidValue := Struct("Registry",
		MapEntry{Key: "services", Value: Map(
			MapEntry{Key: "api", Value: Struct("Address",
				MapEntry{Key: "host", Value: Str("localhost")},
				// port is missing!
			)},
		)},
	)

	result = ValidateWithSchema(invalidValue, schema)
	if result.Valid {
		t.Error("Expected validation to fail for missing required field in nested struct")
	}

	// Should have required_field error
	found := false
	for _, err := range result.Errors {
		if err.Code == "required_field" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("Expected required_field error, got: %v", result.Errors)
	}
}

// ============================================================
// Required-null Tests
// ============================================================

func TestRequiredFieldNull_IsError(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
		).
		Build()

	value := Struct("Config",
		MapEntry{Key: "name", Value: Null()}, // required field present but null
	)

	result := ValidateWithSchema(value, schema)
	if result.Valid {
		t.Error("Expected validation to fail when required field is null")
	}
	found := false
	for _, err := range result.Errors {
		if err.Code == "required_field_null" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("Expected required_field_null error, got: %v", result.Errors)
	}
}

func TestOptionalFieldNull_IsAllowed(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Config", "v1",
			Field("name", PrimitiveType("str"), WithOptional()),
		).
		Build()

	value := Struct("Config",
		MapEntry{Key: "name", Value: Null()}, // optional field present as null — allowed
	)

	result := ValidateWithSchema(value, schema)
	if !result.Valid {
		t.Errorf("Expected optional null to be valid, got errors: %v", result.Errors)
	}
}

// ============================================================
// ApplyDefaults / Normalize Tests
// ============================================================

func TestApplyDefaults_FillsAbsentOptionalFields(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
			Field("port", PrimitiveType("int"), WithOptional(), WithDefault(Int(8080))),
			Field("debug", PrimitiveType("bool"), WithOptional(), WithDefault(Bool(false))),
		).
		Build()

	// Value without optional fields
	value := Struct("Config",
		MapEntry{Key: "name", Value: Str("myapp")},
	)

	result := ApplyDefaults(schema, "Config", value)
	if result == nil {
		t.Fatal("ApplyDefaults returned nil")
	}

	// Find port and debug fields in result
	var portVal, debugVal *GValue
	for _, f := range result.structVal.Fields {
		switch f.Key {
		case "port":
			portVal = f.Value
		case "debug":
			debugVal = f.Value
		}
	}

	if portVal == nil {
		t.Error("default for port not injected")
	} else if v, _ := portVal.AsInt(); v != 8080 {
		t.Errorf("port default wrong: got %d", v)
	}

	if debugVal == nil {
		t.Error("default for debug not injected")
	} else if v, _ := debugVal.AsBool(); v != false {
		t.Errorf("debug default wrong: got %v", v)
	}
}

func TestApplyDefaults_DoesNotOverwritePresentField(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Config", "v1",
			Field("port", PrimitiveType("int"), WithOptional(), WithDefault(Int(8080))),
		).
		Build()

	// Value already has port set to 9090
	value := Struct("Config",
		MapEntry{Key: "port", Value: Int(9090)},
	)

	result := ApplyDefaults(schema, "Config", value)

	var portVal *GValue
	for _, f := range result.structVal.Fields {
		if f.Key == "port" {
			portVal = f.Value
		}
	}

	if portVal == nil {
		t.Fatal("port field missing after ApplyDefaults")
	}
	if v, _ := portVal.AsInt(); v != 9090 {
		t.Errorf("ApplyDefaults overwrote existing field: got %d, want 9090", v)
	}
}

func TestApplyDefaults_DoesNotFillRequiredFields(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Config", "v1",
			Field("name", PrimitiveType("str")), // required, no default
		).
		Build()

	value := Struct("Config") // missing required field

	result := ApplyDefaults(schema, "Config", value)
	// Required field should NOT be injected
	for _, f := range result.structVal.Fields {
		if f.Key == "name" {
			t.Error("ApplyDefaults injected value for required field that has no Default")
		}
	}
}

func TestValidator_Normalize_ThenValidate(t *testing.T) {
	schema := NewSchemaBuilder().
		AddStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
			Field("port", PrimitiveType("int"), WithOptional(), WithDefault(Int(8080))),
		).
		Build()

	v := NewValidator(schema)
	value := Struct("Config", MapEntry{Key: "name", Value: Str("myapp")})

	normalized := v.Normalize(value, "Config")
	result := v.ValidateAs(normalized, "Config")
	if !result.Valid {
		t.Errorf("Expected valid after Normalize+Validate, got: %v", result.Errors)
	}

	// Confirm port default was applied
	var portVal *GValue
	for _, f := range normalized.structVal.Fields {
		if f.Key == "port" {
			portVal = f.Value
		}
	}
	if portVal == nil {
		t.Error("port default not applied by Normalize")
	}
}

// ============================================================
// @open Capture / @unknown Bucket Tests
// ============================================================

func TestOpenStruct_CapturesUnknownInBucket(t *testing.T) {
	schema := NewSchemaBuilder().
		AddOpenStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
		).
		Build()

	value := Struct("Config",
		MapEntry{Key: "name", Value: Str("myapp")},
		MapEntry{Key: "extra", Value: Int(42)}, // unknown
	)

	result := ValidateWithSchema(value, schema)
	if !result.Valid {
		t.Errorf("Expected valid for @open struct, got: %v", result.Errors)
	}

	// @unknown bucket should be present in the value's fields after validation
	var bucket *GValue
	for _, f := range value.structVal.Fields {
		if f.Key == "@unknown" {
			bucket = f.Value
			break
		}
	}
	if bucket == nil {
		t.Fatal("@unknown bucket not inserted by validateStruct")
	}
	if bucket.typ != TypeMap {
		t.Errorf("@unknown bucket should be TypeMap, got %s", bucket.typ)
	}
	// Should contain "extra"
	found := false
	for _, e := range bucket.mapVal {
		if e.Key == "extra" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("@unknown bucket should contain 'extra' field, got: %v", bucket.mapVal)
	}
}

func TestStrictValidator_OpenStruct_NoCapture(t *testing.T) {
	schema := NewSchemaBuilder().
		AddOpenStruct("Config", "v1",
			Field("name", PrimitiveType("str")),
		).
		Build()

	value := Struct("Config",
		MapEntry{Key: "name", Value: Str("myapp")},
		MapEntry{Key: "extra", Value: Int(42)},
	)

	// Strict mode: @open behaves as closed — unknown fields are errors, no capture
	result := NewStrictValidator(schema).ValidateAs(value, "Config")
	if result.Valid {
		t.Error("Strict validator should reject unknown fields even in @open struct")
	}
	found := false
	for _, e := range result.Errors {
		if e.Code == "unknown_field" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("Expected unknown_field error from strict validator, got: %v", result.Errors)
	}
}
