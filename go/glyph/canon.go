package glyph

import (
	"encoding/base64"
	"math"
	"strconv"
	"strings"
	"time"
)

// ============================================================
// Canonical Scalar Encoding (GLYPH v2)
// ============================================================

// canonTime returns the canonical time representation per D2:
// UTC, RFC3339Nano, trailing fractional zeros trimmed, always 'Z'.
func canonTime(t time.Time) string {
	s := t.UTC().Format(time.RFC3339Nano)
	if idx := strings.IndexByte(s, '.'); idx != -1 {
		end := len(s) - 1 // index of 'Z'
		i := end
		for i > idx && s[i-1] == '0' {
			i--
		}
		if i == idx+1 {
			i = idx // drop lone '.'
		}
		s = s[:i] + "Z"
	}
	return s
}

// canonNull returns the canonical null representation.
func canonNull() string {
	return "∅"
}

// canonBool returns the canonical boolean representation.
func canonBool(b bool) string {
	if b {
		return "t"
	}
	return "f"
}

// canonInt returns the canonical integer representation.
// No leading zeros, -0 → 0.
func canonInt(n int64) string {
	if n == 0 {
		return "0"
	}
	return strconv.FormatInt(n, 10)
}

// canonFloat returns the canonical float representation per D4:
// - NaN/+Inf/-Inf → bare tokens "NaN"/"Inf"/"-Inf" (Typed-mode only; Loose callers must guard separately)
// - -0.0 and 0.0 both → "0.0" (always decimal point)
// - shortest round-trip 'g'/-1 format; if no '.' or 'e' in result, append ".0" so float != int
func canonFloat(f float64) string {
	if math.IsNaN(f) {
		return "NaN"
	}
	if math.IsInf(f, 1) {
		return "Inf"
	}
	if math.IsInf(f, -1) {
		return "-Inf"
	}
	// -0.0 and 0.0 both canonicalize to "0.0"
	if math.Float64bits(f) == 0x8000000000000000 || f == 0 {
		return "0.0"
	}
	// Shortest round-trip representation
	s := strconv.FormatFloat(f, 'g', -1, 64)
	s = strings.ReplaceAll(s, "E", "e")
	// 'g' may produce a bare integer (e.g. "999999") for integral floats.
	// Append ".0" so the token is unambiguously float, not int (D4).
	if !strings.Contains(s, ".") && !strings.Contains(s, "e") {
		s += ".0"
	}
	return s
}

// canonString returns the canonical string representation.
// Uses bare form if safe per isValidBareString (strict ASCII lexer match, D8),
// otherwise quoted with minimal escapes.
func canonString(s string) string {
	if isValidBareString(s) {
		return s
	}
	return quoteString(s)
}

// canonRef returns the canonical reference representation.
// Format: ^prefix:value or ^"quoted:value" if unsafe.
func canonRef(r RefID) string {
	full := r.String()[1:] // Remove leading ^ from String()
	if isRefSafe(full) {
		return "^" + full
	}
	return "^" + quoteString(full)
}

// ============================================================
// Safety Checks
// ============================================================

// isRefSafe reports whether the full ref string (prefix:value, no leading ^)
// can be emitted as a bare ^prefix:value token. Rules per D7+D8:
//   - All chars must pass isRefChar (ASCII: [A-Za-z0-9_:-.]).
//   - '/' and all non-ASCII bytes force quoting (isRefChar rejects them).
//   - A ':' in the value part forces quoting to keep first-':' split unambiguous.
func isRefSafe(s string) bool {
	if len(s) == 0 {
		return false
	}
	colon := strings.IndexByte(s, ':')
	if colon < 0 {
		// No prefix: whole string is the value.
		for i := 0; i < len(s); i++ {
			if !isRefChar(s[i]) {
				return false
			}
		}
		return true
	}
	// Has a prefix:value separator.
	prefix, value := s[:colon], s[colon+1:]
	for i := 0; i < len(prefix); i++ {
		if !isRefChar(prefix[i]) {
			return false
		}
	}
	for i := 0; i < len(value); i++ {
		// ':' in the value forces quoting to avoid mis-split.
		if value[i] == ':' || !isRefChar(value[i]) {
			return false
		}
	}
	return true
}

// ============================================================
// String Quoting
// ============================================================

// quoteString returns a quoted string with minimal escapes.
func quoteString(s string) string {
	var b strings.Builder
	b.Grow(len(s) + 10)
	b.WriteByte('"')

	for _, r := range s {
		switch r {
		case '\\':
			b.WriteString(`\\`)
		case '"':
			b.WriteString(`\"`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		default:
			if r < 0x20 {
				// Control character: use \u00XX
				b.WriteString(`\u00`)
				hex := strconv.FormatInt(int64(r), 16)
				if len(hex) == 1 {
					b.WriteByte('0')
				}
				b.WriteString(strings.ToUpper(hex))
			} else {
				b.WriteRune(r)
			}
		}
	}

	b.WriteByte('"')
	return b.String()
}

// ============================================================
// Canonical Value Encoding
// ============================================================

// canonValue returns the canonical string representation of any GValue.
// This is used for scalar values; containers use specialized encoders.
func canonValue(v *GValue) string {
	if v == nil {
		return canonNull()
	}

	switch v.typ {
	case TypeNull:
		return canonNull()
	case TypeBool:
		return canonBool(v.boolVal)
	case TypeInt:
		return canonInt(v.intVal)
	case TypeFloat:
		return canonFloat(v.floatVal)
	case TypeStr:
		return canonString(v.strVal)
	case TypeID:
		return canonRef(v.idVal)
	case TypeTime:
		return canonTime(v.timeVal)
	case TypeBytes:
		// Base64 encoded per D6
		return "b64" + quoteString(base64.StdEncoding.EncodeToString(v.bytesVal))
	default:
		// Container types handled by specialized encoders
		return ""
	}
}

// ============================================================
// Bitmap Encoding
// ============================================================

// maskToBinary converts a boolean mask to "0bXXX" format.
// LSB = first element (lowest fid optional field).
// Returns "0b0" for empty or all-false mask.
func maskToBinary(mask []bool) string {
	// Find highest set bit
	hi := -1
	for i := len(mask) - 1; i >= 0; i-- {
		if mask[i] {
			hi = i
			break
		}
	}

	if hi == -1 {
		return "0b0"
	}

	var b strings.Builder
	b.WriteString("0b")

	// Write bits from MSB (highest index) to LSB (index 0)
	for i := hi; i >= 0; i-- {
		if mask[i] {
			b.WriteByte('1')
		} else {
			b.WriteByte('0')
		}
	}

	return b.String()
}

const maxBitmapBits = 1 << 20

// binaryToMask parses a "0bXXX" string back to a boolean mask.
func binaryToMask(s string) ([]bool, error) {
	if !strings.HasPrefix(s, "0b") {
		return nil, &ParseError{Message: "bitmap must start with 0b"}
	}

	bits := s[2:]
	if len(bits) == 0 {
		return nil, &ParseError{Message: "empty bitmap"}
	}
	if len(bits) > maxBitmapBits {
		return nil, &ParseError{Message: "bitmap too large"}
	}

	// Bits are written MSB first, so reverse to get LSB-first mask
	mask := make([]bool, len(bits))
	for i, c := range bits {
		idx := len(bits) - 1 - i // Reverse index
		switch c {
		case '1':
			mask[idx] = true
		case '0':
			mask[idx] = false
		default:
			return nil, &ParseError{Message: "invalid bitmap character"}
		}
	}

	return mask, nil
}
