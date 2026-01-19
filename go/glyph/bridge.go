package glyph

import (
	"time"

	"github.com/phenomenon0/Agent-GO/sjson"
)

// ToSJSON converts a GValue to an sjson.Value.
func ToSJSON(v *GValue) *sjson.Value {
	if v == nil {
		return sjson.Null()
	}

	switch v.typ {
	case TypeNull:
		return sjson.Null()

	case TypeBool:
		return sjson.Bool(v.boolVal)

	case TypeInt:
		return sjson.Int64(v.intVal)

	case TypeFloat:
		return sjson.Float64(v.floatVal)

	case TypeStr:
		return sjson.String(v.strVal)

	case TypeBytes:
		return sjson.Bytes(v.bytesVal)

	case TypeTime:
		return sjson.Datetime64(v.timeVal.UnixNano())

	case TypeID:
		// Represent as string with ^ prefix
		return sjson.String(v.idVal.String())

	case TypeList:
		items := make([]*sjson.Value, len(v.listVal))
		for i, elem := range v.listVal {
			items[i] = ToSJSON(elem)
		}
		return sjson.Array(items...)

	case TypeMap:
		members := make([]sjson.Member, len(v.mapVal))
		for i, entry := range v.mapVal {
			members[i] = sjson.Member{Key: entry.Key, Value: ToSJSON(entry.Value)}
		}
		return sjson.Object(members...)

	case TypeStruct:
		// Represent as object with _type field
		members := make([]sjson.Member, 0, len(v.structVal.Fields)+1)
		members = append(members, sjson.Member{Key: "_type", Value: sjson.String(v.structVal.TypeName)})
		for _, field := range v.structVal.Fields {
			members = append(members, sjson.Member{Key: field.Key, Value: ToSJSON(field.Value)})
		}
		return sjson.Object(members...)

	case TypeSum:
		// Represent as object with _tag and _value
		return sjson.Object(
			sjson.Member{Key: "_tag", Value: sjson.String(v.sumVal.Tag)},
			sjson.Member{Key: "_value", Value: ToSJSON(v.sumVal.Value)},
		)

	default:
		return sjson.Null()
	}
}

// FromSJSON converts an sjson.Value to a GValue.
func FromSJSON(v *sjson.Value) *GValue {
	if v == nil || v.IsNull() {
		return Null()
	}

	switch v.Type() {
	case sjson.TypeNull:
		return Null()

	case sjson.TypeBool:
		return Bool(v.Bool())

	case sjson.TypeInt64:
		return Int(v.Int64())

	case sjson.TypeUint64:
		return Int(int64(v.Uint64()))

	case sjson.TypeFloat64:
		return Float(v.Float64())

	case sjson.TypeString:
		s := v.String()
		// Check for ID reference
		if len(s) > 0 && s[0] == '^' {
			return parseRefFromString(s[1:])
		}
		return Str(s)

	case sjson.TypeBytes:
		return Bytes(v.Bytes())

	case sjson.TypeDatetime64:
		return Time(time.Unix(0, v.Datetime64()))

	case sjson.TypeArray:
		items := v.Array()
		elements := make([]*GValue, len(items))
		for i, item := range items {
			elements[i] = FromSJSON(item)
		}
		return List(elements...)

	case sjson.TypeObject:
		members := v.Members()

		// Check for struct marker
		typeVal := v.Get("_type")
		if typeVal != nil && typeVal.Type() == sjson.TypeString {
			typeName := typeVal.String()
			fields := make([]MapEntry, 0, len(members)-1)
			for _, m := range members {
				if m.Key == "_type" {
					continue
				}
				fields = append(fields, MapEntry{Key: m.Key, Value: FromSJSON(m.Value)})
			}
			return Struct(typeName, fields...)
		}

		// Check for sum marker
		tagVal := v.Get("_tag")
		if tagVal != nil && tagVal.Type() == sjson.TypeString {
			tag := tagVal.String()
			valueVal := v.Get("_value")
			return Sum(tag, FromSJSON(valueVal))
		}

		// Regular map
		entries := make([]MapEntry, len(members))
		for i, m := range members {
			entries[i] = MapEntry{Key: m.Key, Value: FromSJSON(m.Value)}
		}
		return Map(entries...)

	default:
		return Null()
	}
}

// parseRefFromString parses a ref ID from its string representation.
func parseRefFromString(s string) *GValue {
	// Split on first colon
	for i := 0; i < len(s); i++ {
		if s[i] == ':' {
			return ID(s[:i], s[i+1:])
		}
	}
	return ID("", s)
}

// ============================================================
// Batch Conversion
// ============================================================

// ToSJSONList converts a list of GValues to sjson.Values.
func ToSJSONList(values []*GValue) []*sjson.Value {
	result := make([]*sjson.Value, len(values))
	for i, v := range values {
		result[i] = ToSJSON(v)
	}
	return result
}

// FromSJSONList converts a list of sjson.Values to GValues.
func FromSJSONList(values []*sjson.Value) []*GValue {
	result := make([]*GValue, len(values))
	for i, v := range values {
		result[i] = FromSJSON(v)
	}
	return result
}

// ============================================================
// JSON Interop
// ============================================================

// ToJSON converts a GValue to JSON bytes via sjson.
func ToJSON(v *GValue) ([]byte, error) {
	sv := ToSJSON(v)
	return sjson.ToJSON(sv)
}

// FromJSON parses JSON bytes into a GValue.
func FromJSON(data []byte) (*GValue, error) {
	sv, err := sjson.FromJSON(data)
	if err != nil {
		return nil, err
	}
	return FromSJSON(sv), nil
}

// ToJSONString converts a GValue to a JSON string.
func ToJSONString(v *GValue) (string, error) {
	data, err := ToJSON(v)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

// ============================================================
// Go Native Interop (any)
// ============================================================

// ToAny converts a GValue to a Go any value.
// This enables direct interop with Gen1 and JSON:
//
//	gv := glyph.Parse(text)
//	data, _ := gen1.Encode(glyph.ToAny(gv))  // GLYPH → Gen1
//	jsonBytes, _ := json.Marshal(glyph.ToAny(gv))  // GLYPH → JSON
func ToAny(v *GValue) any {
	return sjson.ToAny(ToSJSON(v))
}

// FromAny converts a Go any value to a GValue.
// This enables direct interop from Gen1 and JSON:
//
//	native, _ := gen1.Decode(data)
//	gv := glyph.FromAny(native)  // Gen1 → GLYPH
//	text := glyph.Canonicalize(gv)
//
//	var obj any
//	json.Unmarshal(jsonBytes, &obj)
//	gv := glyph.FromAny(obj)  // JSON → GLYPH
func FromAny(v any) *GValue {
	return FromSJSON(sjson.FromAny(v))
}

// ============================================================
// Binary Interop (via SJSON)
// ============================================================

// EncodeBinary encodes a GValue to SJSON binary format.
func EncodeBinary(v *GValue) ([]byte, error) {
	sv := ToSJSON(v)
	return sjson.Encode(sv)
}

// DecodeBinary decodes SJSON binary format to a GValue.
func DecodeBinary(data []byte) (*GValue, error) {
	sv, err := sjson.Decode(data)
	if err != nil {
		return nil, err
	}
	return FromSJSON(sv), nil
}

// ============================================================
// Round-Trip Verification
// ============================================================

// RoundTrips checks if a GValue survives round-trip through SJSON.
func RoundTrips(v *GValue) bool {
	sv := ToSJSON(v)
	roundTripped := FromSJSON(sv)

	// Compare canonical forms
	original := Emit(v)
	afterRT := Emit(roundTripped)

	return original == afterRT
}

// ============================================================
// Type-Aware Conversion
// ============================================================

// FromSJSONWithSchema converts an sjson.Value using schema hints.
func FromSJSONWithSchema(v *sjson.Value, schema *Schema, typeName string) *GValue {
	if v == nil || v.IsNull() {
		return Null()
	}

	td := schema.GetType(typeName)
	if td == nil {
		return FromSJSON(v)
	}

	if td.Kind == TypeDefStruct && v.Type() == sjson.TypeObject {
		return fromSJSONStruct(v, schema, td)
	}

	return FromSJSON(v)
}

func fromSJSONStruct(v *sjson.Value, schema *Schema, td *TypeDef) *GValue {
	members := v.Members()
	fields := make([]MapEntry, 0, len(members))

	// Build field lookup from schema
	fieldDefs := make(map[string]*FieldDef)
	wireKeyMap := make(map[string]string) // wireKey -> fieldName
	for _, fd := range td.Struct.Fields {
		fieldDefs[fd.Name] = fd
		if fd.WireKey != "" {
			wireKeyMap[fd.WireKey] = fd.Name
		}
	}

	for _, m := range members {
		if m.Key == "_type" {
			continue
		}

		// Resolve wire key to field name
		fieldName := m.Key
		if fullName, ok := wireKeyMap[m.Key]; ok {
			fieldName = fullName
		}

		// Get field def for type-aware conversion
		fd := fieldDefs[fieldName]
		var fieldValue *GValue
		if fd != nil && fd.Type.Kind == TypeSpecRef {
			fieldValue = FromSJSONWithSchema(m.Value, schema, fd.Type.Name)
		} else {
			fieldValue = FromSJSON(m.Value)
		}

		fields = append(fields, MapEntry{Key: fieldName, Value: fieldValue})
	}

	return Struct(td.Name, fields...)
}
