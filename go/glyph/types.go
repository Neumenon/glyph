package glyph

import (
	"fmt"
	"time"
)

// GType represents GLYPH value types.
type GType uint8

const (
	TypeNull GType = iota
	TypeBool
	TypeInt
	TypeFloat
	TypeStr
	TypeBytes
	TypeTime
	TypeID // Reference ID: ^prefix:value
	TypeList
	TypeMap
	TypeStruct // Typed struct: Type{...}
	TypeSum    // Tagged union: Tag(value) or Tag{...}
)

// String returns the type name.
func (t GType) String() string {
	switch t {
	case TypeNull:
		return "null"
	case TypeBool:
		return "bool"
	case TypeInt:
		return "int"
	case TypeFloat:
		return "float"
	case TypeStr:
		return "str"
	case TypeBytes:
		return "bytes"
	case TypeTime:
		return "time"
	case TypeID:
		return "id"
	case TypeList:
		return "list"
	case TypeMap:
		return "map"
	case TypeStruct:
		return "struct"
	case TypeSum:
		return "sum"
	case TypeBlob:
		return "blob"
	case TypePoolRef:
		return "poolref"
	default:
		return "unknown"
	}
}

// GValue represents a GLYPH value.
type GValue struct {
	typ GType

	// Scalar values (only one valid based on typ)
	boolVal  bool
	intVal   int64
	floatVal float64
	strVal   string
	bytesVal []byte
	timeVal  time.Time
	idVal    RefID

	// Container values
	listVal   []*GValue
	mapVal    []MapEntry
	structVal *StructValue

	// Sum type
	sumVal *SumValue

	// Blob reference
	blobVal *BlobRef

	// Pool reference
	poolRef *PoolRef

	// Source location for error reporting
	pos Position
}

// RefID represents a reference identifier (^prefix:value).
type RefID struct {
	Prefix string // e.g., "m" for match, "t" for team
	Value  string // The actual ID value
}

// String returns the full ref ID string.
func (r RefID) String() string {
	if r.Prefix == "" {
		return "^" + r.Value
	}
	return "^" + r.Prefix + ":" + r.Value
}

// MapEntry represents a key-value pair in a map.
type MapEntry struct {
	Key   string
	Value *GValue
}

// StructValue represents a typed struct.
type StructValue struct {
	TypeName string     // The struct type name (e.g., "Match", "Team")
	Fields   []MapEntry // Field name → value pairs
}

// SumValue represents a tagged union value.
type SumValue struct {
	Tag   string  // The variant tag
	Value *GValue // The wrapped value
}

// Position represents a source location.
type Position struct {
	Line   int
	Column int
	Offset int
}

// String returns position as "line:column".
func (p Position) String() string {
	return fmt.Sprintf("%d:%d", p.Line, p.Column)
}

// ============================================================
// Constructors
// ============================================================

// Null creates a null value.
func Null() *GValue {
	return &GValue{typ: TypeNull}
}

// Bool creates a boolean value.
func Bool(v bool) *GValue {
	return &GValue{typ: TypeBool, boolVal: v}
}

// Int creates an integer value.
func Int(v int64) *GValue {
	return &GValue{typ: TypeInt, intVal: v}
}

// Float creates a float value.
func Float(v float64) *GValue {
	return &GValue{typ: TypeFloat, floatVal: v}
}

// Str creates a string value.
func Str(v string) *GValue {
	return &GValue{typ: TypeStr, strVal: v}
}

// Bytes creates a bytes value.
func Bytes(v []byte) *GValue {
	return &GValue{typ: TypeBytes, bytesVal: v}
}

// Time creates a time value.
func Time(v time.Time) *GValue {
	return &GValue{typ: TypeTime, timeVal: v}
}

// ID creates a reference ID value.
func ID(prefix, value string) *GValue {
	return &GValue{typ: TypeID, idVal: RefID{Prefix: prefix, Value: value}}
}

// IDFromRef creates a reference ID from a RefID.
func IDFromRef(ref RefID) *GValue {
	return &GValue{typ: TypeID, idVal: ref}
}

// List creates a list value.
func List(values ...*GValue) *GValue {
	return &GValue{typ: TypeList, listVal: values}
}

// Map creates a map value from key-value pairs.
func Map(entries ...MapEntry) *GValue {
	return &GValue{typ: TypeMap, mapVal: entries}
}

// Struct creates a typed struct value.
func Struct(typeName string, fields ...MapEntry) *GValue {
	return &GValue{
		typ: TypeStruct,
		structVal: &StructValue{
			TypeName: typeName,
			Fields:   fields,
		},
	}
}

// Sum creates a tagged union value.
func Sum(tag string, value *GValue) *GValue {
	return &GValue{
		typ: TypeSum,
		sumVal: &SumValue{
			Tag:   tag,
			Value: value,
		},
	}
}

// ============================================================
// Accessors
// ============================================================

// Type returns the value type.
func (v *GValue) Type() GType {
	if v == nil {
		return TypeNull
	}
	return v.typ
}

// IsNull returns true if this is a null value.
func (v *GValue) IsNull() bool {
	return v == nil || v.typ == TypeNull
}

// AsBool returns the boolean value. Panics if not a bool.
func (v *GValue) AsBool() bool {
	if v.typ != TypeBool {
		panic("glyph: not a bool")
	}
	return v.boolVal
}

// AsInt returns the integer value. Panics if not an int.
func (v *GValue) AsInt() int64 {
	if v.typ != TypeInt {
		panic("glyph: not an int")
	}
	return v.intVal
}

// AsFloat returns the float value. Panics if not a float.
func (v *GValue) AsFloat() float64 {
	if v.typ != TypeFloat {
		panic("glyph: not a float")
	}
	return v.floatVal
}

// AsStr returns the string value. Panics if not a string.
func (v *GValue) AsStr() string {
	if v.typ != TypeStr {
		panic("glyph: not a str")
	}
	return v.strVal
}

// AsBytes returns the bytes value. Panics if not bytes.
func (v *GValue) AsBytes() []byte {
	if v.typ != TypeBytes {
		panic("glyph: not bytes")
	}
	return v.bytesVal
}

// AsTime returns the time value. Panics if not a time.
func (v *GValue) AsTime() time.Time {
	if v.typ != TypeTime {
		panic("glyph: not a time")
	}
	return v.timeVal
}

// AsID returns the reference ID. Panics if not an ID.
func (v *GValue) AsID() RefID {
	if v.typ != TypeID {
		panic("glyph: not an id")
	}
	return v.idVal
}

// AsList returns the list elements. Panics if not a list.
func (v *GValue) AsList() []*GValue {
	if v.typ != TypeList {
		panic("glyph: not a list")
	}
	return v.listVal
}

// AsMap returns the map entries. Panics if not a map.
func (v *GValue) AsMap() []MapEntry {
	if v.typ != TypeMap {
		panic("glyph: not a map")
	}
	return v.mapVal
}

// AsStruct returns the struct value. Panics if not a struct.
func (v *GValue) AsStruct() *StructValue {
	if v.typ != TypeStruct {
		panic("glyph: not a struct")
	}
	return v.structVal
}

// AsSum returns the sum value. Panics if not a sum.
func (v *GValue) AsSum() *SumValue {
	if v.typ != TypeSum {
		panic("glyph: not a sum")
	}
	return v.sumVal
}

// Len returns the length of a list, map, or struct.
func (v *GValue) Len() int {
	switch v.typ {
	case TypeList:
		return len(v.listVal)
	case TypeMap:
		return len(v.mapVal)
	case TypeStruct:
		return len(v.structVal.Fields)
	default:
		return 0
	}
}

// Get returns a field value by key from a map or struct.
func (v *GValue) Get(key string) *GValue {
	switch v.typ {
	case TypeMap:
		for _, e := range v.mapVal {
			if e.Key == key {
				return e.Value
			}
		}
	case TypeStruct:
		for _, e := range v.structVal.Fields {
			if e.Key == key {
				return e.Value
			}
		}
	}
	return nil
}

// Index returns the i-th element of a list.
func (v *GValue) Index(i int) *GValue {
	if v.typ != TypeList {
		panic("glyph: not a list")
	}
	if i < 0 || i >= len(v.listVal) {
		panic("glyph: index out of bounds")
	}
	return v.listVal[i]
}

// Pos returns the source position of this value.
func (v *GValue) Pos() Position {
	if v == nil {
		return Position{}
	}
	return v.pos
}

// SetPos sets the source position.
func (v *GValue) SetPos(pos Position) {
	v.pos = pos
}

// ============================================================
// Mutators
// ============================================================

// Set sets a field value on a map or struct.
func (v *GValue) Set(key string, val *GValue) {
	switch v.typ {
	case TypeMap:
		for i := range v.mapVal {
			if v.mapVal[i].Key == key {
				v.mapVal[i].Value = val
				return
			}
		}
		v.mapVal = append(v.mapVal, MapEntry{Key: key, Value: val})
	case TypeStruct:
		for i := range v.structVal.Fields {
			if v.structVal.Fields[i].Key == key {
				v.structVal.Fields[i].Value = val
				return
			}
		}
		v.structVal.Fields = append(v.structVal.Fields, MapEntry{Key: key, Value: val})
	default:
		panic("glyph: cannot set on non-map/struct")
	}
}

// Append adds a value to a list.
func (v *GValue) Append(val *GValue) {
	if v.typ != TypeList {
		panic("glyph: cannot append to non-list")
	}
	v.listVal = append(v.listVal, val)
}

// FieldVal creates a MapEntry for use in Struct construction.
func FieldVal(key string, value *GValue) MapEntry {
	return MapEntry{Key: key, Value: value}
}

// ============================================================
// Numeric Coercion Helpers
// ============================================================

// Number returns a numeric value as float64 if int or float.
func (v *GValue) Number() (float64, bool) {
	switch v.typ {
	case TypeInt:
		return float64(v.intVal), true
	case TypeFloat:
		return v.floatVal, true
	default:
		return 0, false
	}
}

// IsNumeric returns true if int or float.
func (v *GValue) IsNumeric() bool {
	return v.typ == TypeInt || v.typ == TypeFloat
}
