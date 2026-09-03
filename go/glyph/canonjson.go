package glyph

// Canonical JSON profile glyph-canon-json-1.0.0 (see SPEC-CANON.md).
//
// The only byte form GLYPH hashes. Fingerprint, the patch base and the GS1
// state hash are all sha256(CanonJSON(v)). GLYPH text is a renderer and is
// never hashed.

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"math"
	"sort"
	"strconv"
)

// CanonMaxDepth is the deepest container nesting CanonJSON accepts.
const CanonMaxDepth = 1000

const canonMaxSafeInt = 1<<53 - 1

var (
	ErrIntegerRange = errors.New("canon: integer outside ±(2^53-1)")
	ErrNonFinite    = errors.New("canon: non-finite float")
	ErrDuplicateKey = errors.New("canon: duplicate key")
	ErrDepth        = errors.New("canon: nesting depth exceeds 1000")
)

// CanonJSON returns the canonical JSON bytes of v (SPEC-CANON.md §1-§3).
func CanonJSON(v *GValue) ([]byte, error) {
	var b bytes.Buffer
	if err := canonJSON(&b, v, 0); err != nil {
		return nil, err
	}
	return b.Bytes(), nil
}

// Fingerprint is the one digest: 64 lowercase hex of sha256(CanonJSON(v))
// (SPEC-CANON.md §5).
func Fingerprint(v *GValue) (string, error) {
	c, err := CanonJSON(v)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(c)
	return hex.EncodeToString(sum[:]), nil
}

// IsCanonical reports whether b is exactly the canonical JSON of the value it
// encodes. Receivers at trust boundaries (patch ingest, GS1 state frames)
// reject bytes that fail this.
func IsCanonical(b []byte) bool {
	v, err := FromJSONLoose(b)
	if err != nil {
		return false
	}
	c, err := CanonJSON(v)
	return err == nil && bytes.Equal(c, b)
}

func canonJSON(b *bytes.Buffer, v *GValue, depth int) error {
	if v == nil {
		b.WriteString("null")
		return nil
	}
	switch v.typ {
	case TypeNull:
		b.WriteString("null")
	case TypeBool:
		if v.boolVal {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case TypeInt:
		if v.intVal > canonMaxSafeInt || v.intVal < -canonMaxSafeInt {
			return fmt.Errorf("%w: %d", ErrIntegerRange, v.intVal)
		}
		b.WriteString(strconv.FormatInt(v.intVal, 10))
	case TypeFloat:
		f := v.floatVal
		if math.IsNaN(f) || math.IsInf(f, 0) {
			return ErrNonFinite
		}
		if f == math.Trunc(f) && math.Abs(f) <= canonMaxSafeInt {
			b.WriteString(strconv.FormatInt(int64(f), 10)) // 1.0 -> 1, -0.0 -> 0
		} else {
			b.WriteString(canonFloat(f))
		}
	case TypeStr:
		writeJSONString(b, v.strVal)
	case TypeBytes:
		b.WriteString(`{"$bytes":`)
		writeJSONString(b, base64.StdEncoding.EncodeToString(v.bytesVal))
		b.WriteByte('}')
	case TypeTime:
		b.WriteString(`{"$time":"`)
		b.WriteString(canonTime(v.timeVal))
		b.WriteString(`"}`)
	case TypeID:
		b.WriteString(`{"$id":[`)
		writeJSONString(b, v.idVal.Prefix)
		b.WriteByte(',')
		writeJSONString(b, v.idVal.Value)
		b.WriteString("]}")
	case TypeList:
		if depth >= CanonMaxDepth {
			return ErrDepth
		}
		b.WriteByte('[')
		for i, x := range v.listVal {
			if i > 0 {
				b.WriteByte(',')
			}
			if err := canonJSON(b, x, depth+1); err != nil {
				return err
			}
		}
		b.WriteByte(']')
	case TypeMap:
		return canonObject(b, v.mapVal, depth)
	case TypeStruct:
		var fields []MapEntry
		if v.structVal != nil {
			fields = v.structVal.Fields
		}
		return canonObject(b, fields, depth)
	case TypeSum:
		if depth >= CanonMaxDepth {
			return ErrDepth
		}
		var tag string
		var inner *GValue
		if v.sumVal != nil {
			tag, inner = v.sumVal.Tag, v.sumVal.Value
		}
		b.WriteByte('{')
		writeJSONString(b, tag)
		b.WriteByte(':')
		if err := canonJSON(b, inner, depth+1); err != nil {
			return err
		}
		b.WriteByte('}')
	default:
		return fmt.Errorf("canon: unsupported type %v", v.typ)
	}
	return nil
}

func canonObject(b *bytes.Buffer, entries []MapEntry, depth int) error {
	if depth >= CanonMaxDepth {
		return ErrDepth
	}
	sorted := make([]MapEntry, len(entries))
	copy(sorted, entries)
	// Go string order is UTF-8 byte order == code point order.
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].Key < sorted[j].Key })
	b.WriteByte('{')
	for i, e := range sorted {
		if i > 0 {
			if e.Key == sorted[i-1].Key {
				return fmt.Errorf("%w: %q", ErrDuplicateKey, e.Key)
			}
			b.WriteByte(',')
		}
		writeJSONString(b, e.Key)
		b.WriteByte(':')
		if err := canonJSON(b, e.Value, depth+1); err != nil {
			return err
		}
	}
	b.WriteByte('}')
	return nil
}

// writeJSONString escapes per RFC 8785 §3.2.2.2: the short forms for
// " \ \b \f \n \r \t, \u00xx for other controls, raw UTF-8 otherwise.
func writeJSONString(b *bytes.Buffer, s string) {
	b.WriteByte('"')
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch c {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		default:
			if c < 0x20 {
				fmt.Fprintf(b, `\u%04x`, c)
			} else {
				b.WriteByte(c)
			}
		}
	}
	b.WriteByte('"')
}
