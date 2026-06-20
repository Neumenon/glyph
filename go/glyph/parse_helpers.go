package glyph

import (
	"fmt"
	"time"
	"unicode/utf8"
)

// ============================================================
// Shared parse helpers used by multiple codec modes.
// ============================================================

// parseTimeLiteralStr parses a pre-scanned time string (already extracted by the
// caller's boundary loop) using a canonical ordered set of formats.  It tries
// more formats than any individual parser did before, ensuring parity across
// packed, tabular, and loose.
//
// Formats attempted (in order):
//   1. 2006-01-02T15:04:05Z          (UTC, no fractional seconds)
//   2. time.RFC3339Nano              (UTC or offset, with fractional seconds)
//   3. time.RFC3339                  (UTC or offset, no fractional seconds)
//   4. 2006-01-02T15:04:05.000Z      (UTC, milliseconds)
//   5. 2006-01-02                    (date only)
func parseTimeLiteralStr(s string) (*GValue, error) {
	for _, layout := range []string{
		"2006-01-02T15:04:05Z",
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02T15:04:05.000Z",
		"2006-01-02",
	} {
		if t, err := time.Parse(layout, s); err == nil {
			return Time(t), nil
		}
	}
	return nil, fmt.Errorf("invalid time format: %s", s)
}

// decodeUnicodeEscape reads exactly 4 hex digits starting at s[pos] and returns
// the decoded rune and the new position. ok is false if fewer than 4 hex digits
// are available or any character is not a hex digit.
func decodeUnicodeEscape(s string, pos int) (r rune, newPos int, ok bool) {
	if pos+4 > len(s) {
		return 0, pos, false
	}
	var code rune
	for i := 0; i < 4; i++ {
		ch := s[pos+i]
		var d rune
		switch {
		case ch >= '0' && ch <= '9':
			d = rune(ch - '0')
		case ch >= 'a' && ch <= 'f':
			d = rune(ch-'a') + 10
		case ch >= 'A' && ch <= 'F':
			d = rune(ch-'A') + 10
		default:
			return 0, pos, false
		}
		code = code<<4 | d
	}
	return code, pos + 4, true
}

// parseQuotedStringShared scans a quoted string from input starting at pos
// (which must point at the opening '"'). It handles the standard GLYPH escape
// sequences including \uXXXX. It returns the unquoted string and the position
// after the closing '"', or an error.
func parseQuotedStringShared(input string, pos int) (string, int, error) {
	if pos >= len(input) || input[pos] != '"' {
		return "", pos, fmt.Errorf("expected '\"'")
	}
	pos++ // skip opening quote

	var sb []byte
	for pos < len(input) {
		c := input[pos]
		if c == '"' {
			pos++ // skip closing quote
			str := string(sb)
			if !utf8.ValidString(str) {
				str = replaceInvalidUTF8(str)
			}
			return str, pos, nil
		}
		if c == '\\' {
			pos++
			if pos >= len(input) {
				return "", pos, fmt.Errorf("unterminated escape in string")
			}
			switch input[pos] {
			case 'n':
				sb = append(sb, '\n')
			case 'r':
				sb = append(sb, '\r')
			case 't':
				sb = append(sb, '\t')
			case '\\':
				sb = append(sb, '\\')
			case '"':
				sb = append(sb, '"')
			case 'u':
				pos++ // skip 'u'
				r, newPos, ok := decodeUnicodeEscape(input, pos)
				if !ok {
					return "", pos, fmt.Errorf("invalid \\u escape in string")
				}
				var buf [4]byte
				n := utf8.EncodeRune(buf[:], r)
				sb = append(sb, buf[:n]...)
				pos = newPos
				continue
			default:
				sb = append(sb, input[pos])
			}
			pos++
		} else {
			sb = append(sb, c)
			pos++
		}
	}
	return "", pos, fmt.Errorf("unterminated string")
}

// replaceInvalidUTF8 replaces invalid UTF-8 sequences with U+FFFD, mirroring
// the typed lexer's behaviour.
func replaceInvalidUTF8(s string) string {
	const replacement = "�"
	var out []byte
	for i := 0; i < len(s); {
		r, size := utf8.DecodeRuneInString(s[i:])
		if r == utf8.RuneError && size == 1 {
			out = append(out, []byte(replacement)...)
		} else {
			out = append(out, s[i:i+size]...)
		}
		i += size
	}
	return string(out)
}
