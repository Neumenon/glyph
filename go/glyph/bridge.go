//go:build cogs

package glyph

import (
	"fmt"
	"time"

	cowrie "github.com/Neumenon/cowrie/go/v2"
)

// ============================================================
// Cowrie / SJSON Bridge
// ============================================================
//
// Converts between GValue and cowrie.Value for binary-protocol usage.
//
// Two modes — controlled by BridgeOpts (shared with json_bridge.go):
//
//   Strict (default, Extended=false):
//     Intentionally lossy, like json_bridge strict mode.
//     - TypeID  → cowrie.String("^prefix:val")   — decoded back as plain Str
//     - TypeStruct → cowrie.Object (fields only, TypeName dropped)
//     - TypeSum    → cowrie.Object{tag: value}    (plain map on decode)
//     - "_type", "_tag", "^"-prefix strings are NOT reinterpreted on decode.
//     - cowrie.TypeDatetime64 and cowrie.TypeBytes are native, already lossless.
//
//   Extended (Extended=true):
//     Lossless via "$glyph" marker objects, mirroring json_bridge extended mode.
//     - TypeID  → {$glyph:"id",  value:"^prefix:val"}
//     - TypeStruct → {$glyph:"struct", type:"T", fields:{...}}
//     - TypeSum    → {$glyph:"sum",    tag:"T",  value:...}
//     - TypeBytes  and TypeTime use native cowrie types — no marker needed.
//     - "$glyph" key in user maps/struct-fields/sum-tags → hard error on emit.
//     - On decode, only exactly-shaped marker objects are interpreted; any extra
//       or missing key causes a loud error rather than silent misinterpretation.

// cowrieMarkerKey is the reserved cowrie object key for extended-mode markers.
// Mirrors glyphMarkerKey ("$glyph") in json_bridge.go. Dollar-prefix is not a
// valid GLYPH identifier so accidental collision with application keys is
// structurally impossible.
const cowrieMarkerKey = "$glyph"

// guardCowrieKey rejects user data that collides with cowrieMarkerKey in
// extended mode. In strict mode the key passes through as ordinary data.
func guardCowrieKey(key string, opts BridgeOpts) error {
	if opts.Extended && key == cowrieMarkerKey {
		return fmt.Errorf("cowrie bridge: key %q collides with reserved %s marker in extended mode", key, cowrieMarkerKey)
	}
	return nil
}

// ============================================================
// ToSJSON / ToSJSONWithOpts
// ============================================================

// ToSJSON converts a GValue to a cowrie.Value in strict (lossy) mode.
// Struct TypeName and Sum structure are not preserved. "_type", "_tag", and
// "^"-prefix strings are NOT given special meaning on decode in strict mode.
func ToSJSON(v *GValue) *cowrie.Value {
	cv, _ := toSJSONValue(v, BridgeOpts{Extended: false})
	return cv
}

// ToSJSONWithOpts converts a GValue to a cowrie.Value with mode control.
// Extended mode emits $glyph marker objects and errors on reserved-key
// collision. Strict mode is intentionally lossy (documented above).
func ToSJSONWithOpts(v *GValue, opts BridgeOpts) (*cowrie.Value, error) {
	return toSJSONValue(v, opts)
}

func toSJSONValue(v *GValue, opts BridgeOpts) (*cowrie.Value, error) {
	if v == nil {
		return cowrie.Null(), nil
	}

	switch v.typ {
	case TypeNull:
		return cowrie.Null(), nil

	case TypeBool:
		return cowrie.Bool(v.boolVal), nil

	case TypeInt:
		return cowrie.Int64(v.intVal), nil

	case TypeFloat:
		return cowrie.Float64(v.floatVal), nil

	case TypeStr:
		return cowrie.String(v.strVal), nil

	case TypeBytes:
		// cowrie.TypeBytes is a native wire type — lossless in both modes.
		return cowrie.Bytes(v.bytesVal), nil

	case TypeTime:
		// cowrie.TypeDatetime64 is a native nanosecond wire type — lossless.
		return cowrie.Datetime64(v.timeVal.UnixNano()), nil

	case TypeID:
		if opts.Extended {
			// Lossless: store the raw RefID string form ("^prefix:val" — never
			// quoted, unlike canonRef which may add GLYPH text quoting). The
			// cowrie wire layer is binary, so text quoting is not needed and
			// would prevent a clean colon-split on decode.
			rawIDStr := v.idVal.String() // e.g. "^ns:path/value" — unquoted
			return cowrie.Object(
				cowrie.Member{Key: cowrieMarkerKey, Value: cowrie.String("id")},
				cowrie.Member{Key: "value", Value: cowrie.String(rawIDStr)},
			), nil
		}
		// Strict: emit as a plain canonRef string. Lossy — decoded back as Str.
		return cowrie.String(canonRef(v.idVal)), nil

	case TypeList:
		items := make([]*cowrie.Value, len(v.listVal))
		for i, elem := range v.listVal {
			cv, err := toSJSONValue(elem, opts)
			if err != nil {
				return nil, fmt.Errorf("list[%d]: %w", i, err)
			}
			items[i] = cv
		}
		return cowrie.Array(items...), nil

	case TypeMap:
		members := make([]cowrie.Member, 0, len(v.mapVal))
		for _, entry := range v.mapVal {
			if err := guardCowrieKey(entry.Key, opts); err != nil {
				return nil, err
			}
			cv, err := toSJSONValue(entry.Value, opts)
			if err != nil {
				return nil, fmt.Errorf("map[%q]: %w", entry.Key, err)
			}
			members = append(members, cowrie.Member{Key: entry.Key, Value: cv})
		}
		return cowrie.Object(members...), nil

	case TypeStruct:
		if opts.Extended {
			// Lossless: emit as $glyph struct marker.
			fieldMembers := make([]cowrie.Member, 0, len(v.structVal.Fields))
			for _, field := range v.structVal.Fields {
				if err := guardCowrieKey(field.Key, opts); err != nil {
					return nil, err
				}
				cv, err := toSJSONValue(field.Value, opts)
				if err != nil {
					return nil, fmt.Errorf("struct[%q]: %w", field.Key, err)
				}
				fieldMembers = append(fieldMembers, cowrie.Member{Key: field.Key, Value: cv})
			}
			return cowrie.Object(
				cowrie.Member{Key: cowrieMarkerKey, Value: cowrie.String("struct")},
				cowrie.Member{Key: "type", Value: cowrie.String(v.structVal.TypeName)},
				cowrie.Member{Key: "fields", Value: cowrie.Object(fieldMembers...)},
			), nil
		}
		// Strict: emit fields only; TypeName is dropped (intentionally lossy).
		members := make([]cowrie.Member, 0, len(v.structVal.Fields))
		for _, field := range v.structVal.Fields {
			cv, err := toSJSONValue(field.Value, opts)
			if err != nil {
				return nil, fmt.Errorf("struct[%q]: %w", field.Key, err)
			}
			members = append(members, cowrie.Member{Key: field.Key, Value: cv})
		}
		return cowrie.Object(members...), nil

	case TypeSum:
		if opts.Extended {
			// Lossless: emit as $glyph sum marker.
			if err := guardCowrieKey(v.sumVal.Tag, opts); err != nil {
				return nil, err
			}
			cv, err := toSJSONValue(v.sumVal.Value, opts)
			if err != nil {
				return nil, fmt.Errorf("sum value: %w", err)
			}
			return cowrie.Object(
				cowrie.Member{Key: cowrieMarkerKey, Value: cowrie.String("sum")},
				cowrie.Member{Key: "tag", Value: cowrie.String(v.sumVal.Tag)},
				cowrie.Member{Key: "value", Value: cv},
			), nil
		}
		// Strict: emit as {tag: value} plain object. Lossy — decoded back as Map.
		cv, err := toSJSONValue(v.sumVal.Value, opts)
		if err != nil {
			return nil, fmt.Errorf("sum value: %w", err)
		}
		return cowrie.Object(
			cowrie.Member{Key: v.sumVal.Tag, Value: cv},
		), nil

	default:
		return cowrie.Null(), nil
	}
}

// ============================================================
// FromSJSON / FromSJSONWithOpts
// ============================================================

// FromSJSON converts a cowrie.Value to a GValue in strict mode.
//
// In strict mode:
//   - cowrie.TypeString is decoded as Str regardless of "^" prefix. The caret
//     is meaningful only in the GLYPH text format, not in the cowrie wire layer.
//   - cowrie.TypeObject is decoded as Map always — "_type" and "_tag" keys carry
//     no special meaning and do NOT trigger struct/sum reconstruction.
//   - TypeStruct and TypeSum are not recoverable in strict mode (lossy by design).
func FromSJSON(v *cowrie.Value) *GValue {
	gv, _ := fromSJSONValue(v, BridgeOpts{Extended: false})
	return gv
}

// FromSJSONWithOpts converts a cowrie.Value to a GValue with mode control.
// Extended mode interprets $glyph marker objects for lossless round-trip.
// Returns an error if a marker object is malformed (wrong shape).
func FromSJSONWithOpts(v *cowrie.Value, opts BridgeOpts) (*GValue, error) {
	return fromSJSONValue(v, opts)
}

func fromSJSONValue(v *cowrie.Value, opts BridgeOpts) (*GValue, error) {
	if v == nil || v.IsNull() {
		return Null(), nil
	}

	switch v.Type() {
	case cowrie.TypeNull:
		return Null(), nil

	case cowrie.TypeBool:
		return Bool(v.Bool()), nil

	case cowrie.TypeInt64:
		return Int(v.Int64()), nil

	case cowrie.TypeUint64:
		return Int(int64(v.Uint64())), nil

	case cowrie.TypeFloat64:
		return Float(v.Float64()), nil

	case cowrie.TypeString:
		// Strict: always decode as Str. The "^" prefix is a GLYPH text-format
		// convention, not a cowrie wire convention. In strict mode we do not
		// reinterpret it (that was the collision bug).
		return Str(v.String()), nil

	case cowrie.TypeBytes:
		return Bytes(v.Bytes()), nil

	case cowrie.TypeDatetime64:
		return Time(time.Unix(0, v.Datetime64())), nil

	case cowrie.TypeArray:
		items := v.Array()
		elements := make([]*GValue, len(items))
		for i, item := range items {
			gv, err := fromSJSONValue(item, opts)
			if err != nil {
				return nil, fmt.Errorf("array[%d]: %w", i, err)
			}
			elements[i] = gv
		}
		return List(elements...), nil

	case cowrie.TypeObject:
		if opts.Extended {
			// Check for $glyph marker. Only a TypeString value triggers dispatch;
			// if the user stored a non-string under $glyph it is decoded as a
			// plain Map (no ambiguity possible).
			markerVal := v.Get(cowrieMarkerKey)
			if markerVal != nil && markerVal.Type() == cowrie.TypeString {
				return fromCowrieMarker(markerVal.String(), v, opts)
			}
		}
		// Regular map — decode all members as entries.
		members := v.Members()
		entries := make([]MapEntry, len(members))
		for i, m := range members {
			gv, err := fromSJSONValue(m.Value, opts)
			if err != nil {
				return nil, fmt.Errorf("object[%q]: %w", m.Key, err)
			}
			entries[i] = MapEntry{Key: m.Key, Value: gv}
		}
		return Map(entries...), nil

	default:
		return Null(), nil
	}
}

// fromCowrieMarker decodes a cowrie object that carries a $glyph marker.
// It applies exact-shape validation: any unexpected or missing key causes a
// loud error rather than silent data loss or misinterpretation.
func fromCowrieMarker(markerType string, v *cowrie.Value, opts BridgeOpts) (*GValue, error) {
	members := v.Members()

	// exactKeys checks that the object has exactly the required keys and no others.
	exactKeys := func(want ...string) error {
		if len(members) != len(want) {
			return fmt.Errorf("$glyph %s marker: expected %d keys, got %d", markerType, len(want), len(members))
		}
		required := make(map[string]bool, len(want))
		for _, k := range want {
			required[k] = true
		}
		for _, m := range members {
			if !required[m.Key] {
				return fmt.Errorf("$glyph %s marker: unexpected key %q", markerType, m.Key)
			}
		}
		for _, k := range want {
			if v.Get(k) == nil {
				return fmt.Errorf("$glyph %s marker: missing key %q", markerType, k)
			}
		}
		return nil
	}

	switch markerType {
	case "id":
		// Shape: {$glyph:"id", value:"^prefix:val"}
		if err := exactKeys(cowrieMarkerKey, "value"); err != nil {
			return nil, err
		}
		valField := v.Get("value")
		if valField == nil || valField.Type() != cowrie.TypeString {
			return nil, fmt.Errorf("$glyph id marker: value must be a string")
		}
		return parseRefFromString(strings_trimLeadingCaret(valField.String())), nil

	case "struct":
		// Shape: {$glyph:"struct", type:"T", fields:{...}}
		if err := exactKeys(cowrieMarkerKey, "type", "fields"); err != nil {
			return nil, err
		}
		typeField := v.Get("type")
		if typeField == nil || typeField.Type() != cowrie.TypeString {
			return nil, fmt.Errorf("$glyph struct marker: type must be a string")
		}
		fieldsField := v.Get("fields")
		if fieldsField == nil || fieldsField.Type() != cowrie.TypeObject {
			return nil, fmt.Errorf("$glyph struct marker: fields must be an object")
		}
		fieldMembers := fieldsField.Members()
		fields := make([]MapEntry, len(fieldMembers))
		for i, m := range fieldMembers {
			gv, err := fromSJSONValue(m.Value, opts)
			if err != nil {
				return nil, fmt.Errorf("$glyph struct field %q: %w", m.Key, err)
			}
			fields[i] = MapEntry{Key: m.Key, Value: gv}
		}
		return Struct(typeField.String(), fields...), nil

	case "sum":
		// Shape: {$glyph:"sum", tag:"T", value:...}
		if err := exactKeys(cowrieMarkerKey, "tag", "value"); err != nil {
			return nil, err
		}
		tagField := v.Get("tag")
		if tagField == nil || tagField.Type() != cowrie.TypeString {
			return nil, fmt.Errorf("$glyph sum marker: tag must be a string")
		}
		valueField := v.Get("value")
		gv, err := fromSJSONValue(valueField, opts)
		if err != nil {
			return nil, fmt.Errorf("$glyph sum value: %w", err)
		}
		return Sum(tagField.String(), gv), nil

	default:
		return nil, fmt.Errorf("$glyph cowrie marker: unknown type %q", markerType)
	}
}

// strings_trimLeadingCaret removes a leading "^" from s if present.
// Used when decoding the "value" field of a $glyph id marker, which stores
// the canonRef form (e.g. "^prefix:val" or "^\"quoted\"").
func strings_trimLeadingCaret(s string) string {
	if len(s) > 0 && s[0] == '^' {
		return s[1:]
	}
	return s
}

// parseRefFromString parses a ref ID from its string representation (without
// the leading "^"). Splits on the first colon: "prefix:val" → ID(prefix,val).
func parseRefFromString(s string) *GValue {
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

// ToSJSONList converts a list of GValues to cowrie.Values (strict mode).
func ToSJSONList(values []*GValue) []*cowrie.Value {
	result := make([]*cowrie.Value, len(values))
	for i, v := range values {
		result[i] = ToSJSON(v)
	}
	return result
}

// FromSJSONList converts a list of cowrie.Values to GValues (strict mode).
func FromSJSONList(values []*cowrie.Value) []*GValue {
	result := make([]*GValue, len(values))
	for i, v := range values {
		result[i] = FromSJSON(v)
	}
	return result
}

// ============================================================
// JSON Interop
// ============================================================

// ToJSON converts a GValue to JSON bytes via cowrie (strict mode).
func ToJSON(v *GValue) ([]byte, error) {
	sv := ToSJSON(v)
	return cowrie.ToJSON(sv)
}

// FromJSON parses JSON bytes into a GValue (strict mode).
func FromJSON(data []byte) (*GValue, error) {
	sv, err := cowrie.FromJSON(data)
	if err != nil {
		return nil, err
	}
	return FromSJSON(sv), nil
}

// ToJSONString converts a GValue to a JSON string (strict mode).
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
	return cowrie.ToAny(ToSJSON(v))
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
	return FromSJSON(cowrie.FromAny(v))
}

// ============================================================
// Binary Interop (via Cowrie)
// ============================================================

// EncodeBinary encodes a GValue to Cowrie binary format (strict mode).
func EncodeBinary(v *GValue) ([]byte, error) {
	sv := ToSJSON(v)
	return cowrie.Encode(sv)
}

// DecodeBinary decodes Cowrie binary format to a GValue (strict mode).
func DecodeBinary(data []byte) (*GValue, error) {
	sv, err := cowrie.Decode(data)
	if err != nil {
		return nil, err
	}
	return FromSJSON(sv), nil
}

// ============================================================
// Round-Trip Verification
// ============================================================

// RoundTrips checks if a GValue survives round-trip through Cowrie (extended).
// Uses extended mode so Struct/Sum/ID are preserved.
func RoundTrips(v *GValue) bool {
	sv, err := ToSJSONWithOpts(v, BridgeOpts{Extended: true})
	if err != nil {
		return false
	}
	roundTripped, err := FromSJSONWithOpts(sv, BridgeOpts{Extended: true})
	if err != nil {
		return false
	}

	// Compare canonical forms
	original := Emit(v)
	afterRT := Emit(roundTripped)

	return original == afterRT
}

// ============================================================
// Type-Aware Conversion
// ============================================================

// FromSJSONWithSchema converts a cowrie.Value using schema hints.
func FromSJSONWithSchema(v *cowrie.Value, schema *Schema, typeName string) *GValue {
	if v == nil || v.IsNull() {
		return Null()
	}

	td := schema.GetType(typeName)
	if td == nil {
		return FromSJSON(v)
	}

	if td.Kind == TypeDefStruct && v.Type() == cowrie.TypeObject {
		return fromSJSONStruct(v, schema, td)
	}

	return FromSJSON(v)
}

func fromSJSONStruct(v *cowrie.Value, schema *Schema, td *TypeDef) *GValue {
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

	// A member named "type" is a marker key ONLY when this object is an extended
	// $glyph struct marker; on a plain/strict object "type" is real field data and
	// must not be dropped (would be a silent-loss bug).
	hasMarker := false
	for _, m := range members {
		if m.Key == cowrieMarkerKey {
			hasMarker = true
			break
		}
	}

	for _, m := range members {
		// Skip the $glyph marker key (always); skip the "type" marker member only
		// when this really is an extended struct marker.
		if m.Key == cowrieMarkerKey || (hasMarker && m.Key == "type") {
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
