//go:build cogs

// Command bridgecheck is a memory-light, library-only verifier for the W5
// Cowrie bridge collision-safety contract. It compiles only the glyph package
// (NOT the heavy cogs test binary), so it runs under tight memory caps where
// `go test -tags cogs ./glyph/` would OOM.
//
// Run: go run -tags cogs ./cmd/bridgecheck
//
// Checks:
//   - Strict mode: "^not-an-id" stays a Str (no ^ coercion)
//   - Strict mode: {"_type":"x","foo":1} stays a Map (no struct coercion)
//   - Strict mode: {"_tag":"ok","_value":42} stays a Map (no sum coercion)
//   - Extended mode: ID round-trips losslessly
//   - Extended mode: Struct round-trips losslessly (TypeName preserved)
//   - Extended mode: Sum round-trips losslessly
//   - Extended mode: Bytes round-trips losslessly (native cowrie type)
//   - Extended mode: Time round-trips losslessly (native cowrie type)
//   - Extended mode: nested containers round-trip
//   - Extended mode: user map with $glyph key → hard error on emit
//   - Extended mode: user sum with $glyph tag → hard error on emit
//   - Extended mode: user struct with $glyph field → hard error on emit
//   - Extended mode: malformed marker (extra key) → error on decode
//   - Strict mode: all basic scalars round-trip as expected
package main

import (
	"fmt"
	"os"
	"time"

	"github.com/Neumenon/glyph/glyph"
	cowrie "github.com/Neumenon/cowrie/go/v2"
)

var fails, total int

func pass(name string) {
	total++
	fmt.Printf("PASS %s\n", name)
}

func fail(name, msg string) {
	total++
	fails++
	fmt.Printf("FAIL %-36s %s\n", name, msg)
}

// checkType asserts gv has the expected GValue type.
func checkType(name string, gv *glyph.GValue, want glyph.GType) {
	total++
	if gv == nil {
		fails++
		fmt.Printf("FAIL %-36s got nil, want type %s\n", name, want)
		return
	}
	if gv.Type() != want {
		fails++
		fmt.Printf("FAIL %-36s got type %s, want %s\n", name, gv.Type(), want)
	}
}

// rtExtended round-trips v through ToSJSONWithOpts/FromSJSONWithOpts in
// extended mode and verifies Emit output is identical.
func rtExtended(name string, v *glyph.GValue) {
	total++
	opts := glyph.BridgeOpts{Extended: true}
	cv, err := glyph.ToSJSONWithOpts(v, opts)
	if err != nil {
		fails++
		fmt.Printf("FAIL %-36s ToSJSONWithOpts error: %v\n", name, err)
		return
	}
	back, err := glyph.FromSJSONWithOpts(cv, opts)
	if err != nil {
		fails++
		fmt.Printf("FAIL %-36s FromSJSONWithOpts error: %v\n", name, err)
		return
	}
	orig := glyph.Emit(v)
	got := glyph.Emit(back)
	if orig != got {
		fails++
		fmt.Printf("FAIL %-36s emit mismatch: want %q got %q\n", name, orig, got)
		return
	}
	fmt.Printf("PASS %s\n", name)
}

// wantEmitErr asserts ToSJSONWithOpts returns an error for v in extended mode.
func wantEmitErr(name string, v *glyph.GValue) {
	total++
	opts := glyph.BridgeOpts{Extended: true}
	_, err := glyph.ToSJSONWithOpts(v, opts)
	if err == nil {
		fails++
		fmt.Printf("FAIL %-36s expected emit error, got none\n", name)
		return
	}
	fmt.Printf("PASS %s (error: %v)\n", name, err)
}

// wantDecodeErr asserts FromSJSONWithOpts returns an error for cv in extended mode.
func wantDecodeErr(name string, cv *cowrie.Value) {
	total++
	opts := glyph.BridgeOpts{Extended: true}
	_, err := glyph.FromSJSONWithOpts(cv, opts)
	if err == nil {
		fails++
		fmt.Printf("FAIL %-36s expected decode error, got none\n", name)
		return
	}
	fmt.Printf("PASS %s (error: %v)\n", name, err)
}

func main() {
	// ============================================================
	// Collision fixes: strict mode must NOT reinterpret sentinel patterns
	// ============================================================

	fmt.Println("=== Strict mode: collision safety ===")

	// FIX 1: "^not-an-id" must survive as a plain string, not be parsed as ID.
	{
		name := "strict/^string-stays-str"
		cv := cowrie.String("^not-an-id")
		gv := glyph.FromSJSON(cv)
		checkType(name+"/type", gv, glyph.TypeStr)
		total++ // check the value content too
		if gv.Type() == glyph.TypeStr {
			s, _ := gv.AsStr()
			if s == "^not-an-id" {
				fmt.Printf("PASS %s\n", name+"/value")
			} else {
				fails++
				fmt.Printf("FAIL %-36s got %q want %q\n", name+"/value", s, "^not-an-id")
			}
		}
	}

	// FIX 2: {"_type":"x","foo":1} must stay a Map, not become Struct.
	{
		name := "strict/_type-object-stays-map"
		cv := cowrie.Object(
			cowrie.Member{Key: "_type", Value: cowrie.String("x")},
			cowrie.Member{Key: "foo", Value: cowrie.Int64(1)},
		)
		gv := glyph.FromSJSON(cv)
		checkType(name, gv, glyph.TypeMap)
	}

	// FIX 3: {"_tag":"ok","_value":42} must stay a Map, not become Sum.
	{
		name := "strict/_tag-object-stays-map"
		cv := cowrie.Object(
			cowrie.Member{Key: "_tag", Value: cowrie.String("ok")},
			cowrie.Member{Key: "_value", Value: cowrie.Int64(42)},
		)
		gv := glyph.FromSJSON(cv)
		checkType(name, gv, glyph.TypeMap)
	}

	// ============================================================
	// Extended mode: lossless round-trips
	// ============================================================

	fmt.Println("\n=== Extended mode: lossless round-trips ===")

	// ID round-trip
	rtExtended("extended/id-simple", glyph.ID("m", "ARS-LIV"))
	rtExtended("extended/id-no-prefix", glyph.ID("", "xyz"))
	rtExtended("extended/id-slash", glyph.ID("ns", "path/value"))
	rtExtended("extended/id-colon", glyph.ID("ns", "a:b"))

	// Struct round-trip (TypeName must survive)
	rtExtended("extended/struct-simple", glyph.Struct("Match",
		glyph.MapEntry{Key: "score", Value: glyph.Int(2)},
		glyph.MapEntry{Key: "home", Value: glyph.Str("Arsenal")},
	))
	rtExtended("extended/struct-empty", glyph.Struct("Empty"))
	rtExtended("extended/struct-nested", glyph.Struct("Outer",
		glyph.MapEntry{Key: "inner", Value: glyph.Struct("Inner",
			glyph.MapEntry{Key: "x", Value: glyph.Int(1)},
		)},
	))

	// Sum round-trip
	rtExtended("extended/sum-int", glyph.Sum("ok", glyph.Int(42)))
	rtExtended("extended/sum-str", glyph.Sum("err", glyph.Str("not found")))
	rtExtended("extended/sum-null", glyph.Sum("none", glyph.Null()))
	rtExtended("extended/sum-nested-struct", glyph.Sum("ok", glyph.Struct("T",
		glyph.MapEntry{Key: "v", Value: glyph.Bool(true)},
	)))

	// Bytes round-trip (native cowrie.TypeBytes — no marker needed)
	rtExtended("extended/bytes-empty", glyph.Bytes([]byte{}))
	rtExtended("extended/bytes-data", glyph.Bytes([]byte{0x01, 0x02, 0x03}))

	// Time round-trip (native cowrie.TypeDatetime64 — no marker needed)
	rtExtended("extended/time-utc", glyph.Time(time.Date(2026, 6, 20, 12, 0, 0, 0, time.UTC)))
	rtExtended("extended/time-nano", glyph.Time(time.Date(2026, 6, 20, 12, 0, 0, 500000000, time.UTC)))

	// Nested containers with mixed types
	rtExtended("extended/nested-list-struct", glyph.List(
		glyph.Struct("A", glyph.MapEntry{Key: "id", Value: glyph.ID("p", "smith")}),
		glyph.Sum("ok", glyph.Int(1)),
		glyph.Bytes([]byte("hi")),
	))

	// Map with various value types
	rtExtended("extended/map-mixed", glyph.Map(
		glyph.MapEntry{Key: "name", Value: glyph.Str("Arsenal")},
		glyph.MapEntry{Key: "rank", Value: glyph.Int(1)},
		glyph.MapEntry{Key: "id", Value: glyph.ID("t", "ARS")},
	))

	// ============================================================
	// Extended mode: guard — reserved key collisions must error loudly
	// ============================================================

	fmt.Println("\n=== Extended mode: reserved key guard ===")

	// User map with $glyph key
	wantEmitErr("extended/map-$glyph-key-guard", glyph.Map(
		glyph.MapEntry{Key: "$glyph", Value: glyph.Str("user data")},
		glyph.MapEntry{Key: "other", Value: glyph.Int(1)},
	))

	// User struct with $glyph field
	wantEmitErr("extended/struct-$glyph-field-guard", glyph.Struct("T",
		glyph.MapEntry{Key: "$glyph", Value: glyph.Str("user data")},
	))

	// Sum with $glyph tag — guardCowrieKey is called on the tag string
	wantEmitErr("extended/sum-$glyph-tag-guard", glyph.Sum("$glyph", glyph.Int(1)))

	// ============================================================
	// Extended mode: malformed marker → loud error on decode
	// ============================================================

	fmt.Println("\n=== Extended mode: malformed marker rejection ===")

	// Marker with extra key
	wantDecodeErr("extended/id-marker-extra-key", cowrie.Object(
		cowrie.Member{Key: "$glyph", Value: cowrie.String("id")},
		cowrie.Member{Key: "value", Value: cowrie.String("^p:val")},
		cowrie.Member{Key: "extra", Value: cowrie.String("boom")},
	))

	// Marker with missing key
	wantDecodeErr("extended/id-marker-missing-value", cowrie.Object(
		cowrie.Member{Key: "$glyph", Value: cowrie.String("id")},
	))

	// Struct marker with missing fields key
	wantDecodeErr("extended/struct-marker-missing-fields", cowrie.Object(
		cowrie.Member{Key: "$glyph", Value: cowrie.String("struct")},
		cowrie.Member{Key: "type", Value: cowrie.String("T")},
	))

	// Sum marker with extra key
	wantDecodeErr("extended/sum-marker-extra-key", cowrie.Object(
		cowrie.Member{Key: "$glyph", Value: cowrie.String("sum")},
		cowrie.Member{Key: "tag", Value: cowrie.String("ok")},
		cowrie.Member{Key: "value", Value: cowrie.Int64(1)},
		cowrie.Member{Key: "extra", Value: cowrie.String("boom")},
	))

	// Unknown marker type → error
	wantDecodeErr("extended/unknown-marker-type", cowrie.Object(
		cowrie.Member{Key: "$glyph", Value: cowrie.String("unknown")},
	))

	// $glyph with non-string value → decoded as plain Map (not an error)
	{
		name := "extended/$glyph-non-string-decoded-as-map"
		cv := cowrie.Object(
			cowrie.Member{Key: "$glyph", Value: cowrie.Int64(42)},
			cowrie.Member{Key: "foo", Value: cowrie.String("bar")},
		)
		opts := glyph.BridgeOpts{Extended: true}
		gv, err := glyph.FromSJSONWithOpts(cv, opts)
		if err != nil {
			fail(name, fmt.Sprintf("unexpected error: %v", err))
		} else if gv.Type() != glyph.TypeMap {
			fail(name, fmt.Sprintf("expected Map, got %s", gv.Type()))
		} else {
			pass(name)
		}
	}

	// ============================================================
	// Strict mode: basic scalars and containers are lossless
	// ============================================================

	fmt.Println("\n=== Strict mode: basic scalar fidelity ===")

	strictRT := func(name string, v *glyph.GValue) {
		total++
		cv := glyph.ToSJSON(v)
		back := glyph.FromSJSON(cv)
		orig := glyph.Emit(v)
		got := glyph.Emit(back)
		if orig != got {
			fails++
			fmt.Printf("FAIL %-36s emit mismatch: want %q got %q\n", name, orig, got)
		} else {
			fmt.Printf("PASS %s\n", name)
		}
	}

	strictRT("strict/null", glyph.Null())
	strictRT("strict/bool-true", glyph.Bool(true))
	strictRT("strict/bool-false", glyph.Bool(false))
	strictRT("strict/int-42", glyph.Int(42))
	strictRT("strict/float-3.14", glyph.Float(3.14))
	strictRT("strict/str-hello", glyph.Str("hello"))
	strictRT("strict/str-caret", glyph.Str("^not-an-id"))
	strictRT("strict/bytes", glyph.Bytes([]byte{0xDE, 0xAD}))
	strictRT("strict/time", glyph.Time(time.Date(2026, 6, 20, 0, 0, 0, 0, time.UTC)))
	strictRT("strict/list", glyph.List(glyph.Int(1), glyph.Str("a")))
	strictRT("strict/map", glyph.Map(
		glyph.MapEntry{Key: "k", Value: glyph.Int(1)},
	))

	// Strict mode: ID becomes a string (lossy), decoded back as Str
	{
		name := "strict/id-lossy-to-str"
		total++
		v := glyph.ID("p", "smith")
		cv := glyph.ToSJSON(v)
		back := glyph.FromSJSON(cv)
		if back.Type() != glyph.TypeStr {
			fails++
			fmt.Printf("FAIL %-36s expected Str (lossy), got %s\n", name, back.Type())
		} else {
			fmt.Printf("PASS %s\n", name)
		}
	}

	// Strict mode: Struct becomes a Map (TypeName lost), Sum becomes a Map
	{
		name := "strict/struct-lossy-to-map"
		total++
		v := glyph.Struct("T", glyph.MapEntry{Key: "x", Value: glyph.Int(1)})
		cv := glyph.ToSJSON(v)
		back := glyph.FromSJSON(cv)
		if back.Type() != glyph.TypeMap {
			fails++
			fmt.Printf("FAIL %-36s expected Map (lossy), got %s\n", name, back.Type())
		} else {
			fmt.Printf("PASS %s\n", name)
		}
	}
	{
		name := "strict/sum-lossy-to-map"
		total++
		v := glyph.Sum("ok", glyph.Int(1))
		cv := glyph.ToSJSON(v)
		back := glyph.FromSJSON(cv)
		if back.Type() != glyph.TypeMap {
			fails++
			fmt.Printf("FAIL %-36s expected Map (lossy), got %s\n", name, back.Type())
		} else {
			fmt.Printf("PASS %s\n", name)
		}
	}

	// ============================================================
	// Summary
	// ============================================================

	fmt.Printf("\nbridgecheck: %d/%d checks passed, %d failed\n", total-fails, total, fails)
	if fails > 0 {
		os.Exit(1)
	}
}
