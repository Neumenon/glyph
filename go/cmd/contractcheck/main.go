// Command contractcheck is a memory-light, library-only verifier for the W2
// canonical-scalar contract. It compiles only the glyph package (NOT the heavy
// go/glyph test binary), so it runs under tight memory caps where `go test
// ./glyph/` is OOM-killed. Run: go run ./cmd/contractcheck
package main

import (
	"fmt"
	"math"
	"os"
	"time"

	"github.com/Neumenon/glyph/glyph"
)

var fails, total int

func check(name, got, want string) {
	total++
	if got != want {
		fails++
		fmt.Printf("FAIL %-28s got %q  want %q\n", name, got, want)
	}
}

// rt asserts Parse(Emit(v)) round-trips back to an equal value.
func rt(name string, v *glyph.GValue) {
	total++
	typed := glyph.Emit(v)
	pr, err := glyph.Parse(typed)
	if err != nil || pr == nil || len(pr.Errors) > 0 || !glyph.EqualLoose(pr.Value, v) {
		fails++
		fmt.Printf("FAIL rt %-25s typed=%q err=%v errs=%v\n", name, typed, err, errsOf(pr))
	}
}

func errsOf(pr *glyph.ParseResult) []glyph.ParseError {
	if pr == nil {
		return nil
	}
	return pr.Errors
}

// wantParseErr asserts that parsing input is a hard error (D6 invalid base64,
// int overflow, etc.).
func wantParseErr(name, input string) {
	total++
	pr, err := glyph.Parse(input)
	if err == nil && (pr == nil || len(pr.Errors) == 0) {
		fails++
		got := ""
		if pr != nil && pr.Value != nil {
			got = glyph.Emit(pr.Value)
		}
		fmt.Printf("FAIL parseErr %-20s input=%q parsed-ok-as %q (expected error)\n", name, input, got)
	}
}

// wantLooseErr asserts CanonicalizeLooseErr rejects v (D3 NaN/Inf in Loose).
func wantLooseErr(name string, v *glyph.GValue) {
	total++
	if _, err := glyph.CanonicalizeLooseErr(v, glyph.DefaultLooseCanonOpts()); err == nil {
		fails++
		fmt.Printf("FAIL looseErr %-20s expected D3 error, got none\n", name)
	}
}

// scalar runs the full typed + loose + round-trip triad for one value.
func scalar(name string, v *glyph.GValue, wantTyped, wantLoose string) {
	check(name+":typed", glyph.Emit(v), wantTyped)
	check(name+":loose", glyph.CanonicalizeLoose(v), wantLoose)
	rt(name, v)
}

func main() {
	// --- null / bool / int ---
	scalar("null", glyph.Null(), "∅", "_")
	scalar("bool-true", glyph.Bool(true), "t", "t")
	scalar("bool-false", glyph.Bool(false), "f", "f")
	scalar("int-42", glyph.Int(42), "42", "42")
	scalar("int-neg", glyph.Int(-100), "-100", "-100")
	scalar("int-max", glyph.Int(math.MaxInt64), "9223372036854775807", "9223372036854775807")
	scalar("int-min", glyph.Int(math.MinInt64), "-9223372036854775808", "-9223372036854775808")

	// --- float (D4: shortest + always a decimal point; -0 -> 0.0) ---
	scalar("float-1", glyph.Float(1.0), "1.0", "1.0")
	scalar("float-0", glyph.Float(0.0), "0.0", "0.0")
	scalar("float-neg0", glyph.Float(math.Copysign(0, -1)), "0.0", "0.0")
	scalar("float-0.1", glyph.Float(0.1), "0.1", "0.1")
	scalar("float-3.0", glyph.Float(3.0), "3.0", "3.0")
	scalar("float-1e21", glyph.Float(1e21), "1e+21", "1e+21")

	// --- float NaN/Inf: Typed tokens, Loose hard error (D3) ---
	check("nan:typed", glyph.Emit(glyph.Float(math.NaN())), "NaN")
	check("inf:typed", glyph.Emit(glyph.Float(math.Inf(1))), "Inf")
	check("ninf:typed", glyph.Emit(glyph.Float(math.Inf(-1))), "-Inf")
	wantLooseErr("nan", glyph.Float(math.NaN()))
	wantLooseErr("inf", glyph.Float(math.Inf(1)))

	// --- strings: conservative quoting (D8) ---
	scalar("str-bare", glyph.Str("hello"), "hello", "hello")
	scalar("str-space", glyph.Str("hello world"), `"hello world"`, `"hello world"`)
	scalar("str-kw-true", glyph.Str("true"), `"true"`, `"true"`)
	scalar("str-unicode", glyph.Str("café"), `"café"`, `"café"`)
	scalar("str-slash", glyph.Str("a/b"), `"a/b"`, `"a/b"`)
	scalar("str-dash", glyph.Str("a-b"), `"a-b"`, `"a-b"`)
	scalar("str-caret", glyph.Str("^x"), `"^x"`, `"^x"`)
	scalar("str-underscore", glyph.Str("_"), `"_"`, `"_"`) // null token -> must quote
	scalar("str-null-symbol", glyph.Str("∅"), `"∅"`, `"∅"`)
	scalar("str-empty", glyph.Str(""), `""`, `""`)

	// --- bytes: b64"<std-base64>" everywhere (D6) ---
	scalar("bytes-1", glyph.Bytes([]byte{0x01}), `b64"AQ=="`, `b64"AQ=="`)
	scalar("bytes-empty", glyph.Bytes([]byte{}), `b64""`, `b64""`)
	scalar("bytes-hello", glyph.Bytes([]byte("Hello")), `b64"SGVsbG8="`, `b64"SGVsbG8="`)

	// --- time: single UTC RFC3339, trailing-zero-trimmed fraction (D2) ---
	scalar("time-whole", glyph.Time(time.Date(2026, 6, 19, 12, 0, 0, 0, time.UTC)),
		"2026-06-19T12:00:00Z", "2026-06-19T12:00:00Z")
	scalar("time-frac", glyph.Time(time.Date(2026, 6, 19, 12, 0, 0, 500000000, time.UTC)),
		"2026-06-19T12:00:00.5Z", "2026-06-19T12:00:00.5Z")
	scalar("time-offset", glyph.Time(time.Date(2026, 6, 19, 12, 0, 0, 0, time.FixedZone("x", 5*3600+1800))),
		"2026-06-19T06:30:00Z", "2026-06-19T06:30:00Z")

	// --- refs/IDs: bare when safe, quoted ^"..." when unsafe (D7/D8) ---
	scalar("id-simple", glyph.ID("p", "smith"), "^p:smith", "^p:smith")
	scalar("id-slash", glyph.ID("ns", "path/value"), `^"ns:path/value"`, `^"ns:path/value"`)
	scalar("id-colon", glyph.ID("ns", "a:b"), `^"ns:a:b"`, `^"ns:a:b"`)

	// --- containers round-trip ---
	rt("list", glyph.List(glyph.Int(1), glyph.Str("a"), glyph.Bytes([]byte{0x02})))

	// --- parse hard-errors ---
	wantParseErr("int-overflow", "9223372036854775808")
	wantParseErr("bytes-bad-b64", `b64"@@@"`)

	fmt.Printf("\ncontractcheck: %d/%d checks passed, %d failed\n", total-fails, total, fails)
	if fails > 0 {
		os.Exit(1)
	}
}
