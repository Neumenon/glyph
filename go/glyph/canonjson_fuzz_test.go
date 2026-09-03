package glyph

import (
	"testing"
)

// Seed-corpus fuzz wrappers for the canonical-JSON trust boundary.
// Cheap by design: each input is parsed/emitted once with no nested loops,
// so the seed corpus runs in milliseconds under plain `go test`.

func FuzzCanonJSON(f *testing.F) {
	seeds := []string{
		`{"a":1,"b":[1,2.5,"x",null]}`,
		`{"$bytes":"AP8="}`,
		`{"$time":"2025-01-13T12:34:56.5Z"}`,
		`{"$id":["m","1"]}`,
		`{"$tensor":{"dtype":"float32","shape":[1],"sha256":"0000000000000000000000000000000000000000000000000000000000000000"}}`,
		`{"glyph_patch":1,"ops":[{"op":"=","path":["a"],"value":1}]}`,
		`[1.5e-05,1.2345678e+06]`,
		`{"":1,"😀":2}`,
	}
	for _, s := range seeds {
		f.Add(s)
	}
	f.Fuzz(func(t *testing.T, s string) {
		v, err := FromJSONLoose([]byte(s))
		if err != nil {
			return // malformed or over depth limit: not canonical, nothing to check
		}
		c, err := CanonJSON(v)
		if err != nil {
			return // uncanonicalizable (range, dup key): nothing to check
		}
		if !IsCanonical(c) {
			t.Fatalf("CanonJSON output is not canonical: %q", c)
		}
	})
}

func FuzzIsCanonical(f *testing.F) {
	seeds := []string{
		`{"a":1}`,
		`{"b":1,"a":2}`,
		`{"a": 1}`,
		`{"a":1.0}`,
		`1`,
		`"x"`,
		`nope`,
	}
	for _, s := range seeds {
		f.Add(s)
	}
	f.Fuzz(func(t *testing.T, s string) {
		b := []byte(s)
		if !IsCanonical(b) {
			return
		}
		// Canonical bytes must be a fixpoint: decode and re-encode.
		v, err := FromJSONLoose(b)
		if err != nil {
			t.Fatalf("IsCanonical true but FromJSONLoose failed: %q (%v)", s, err)
		}
		c, err := CanonJSON(v)
		if err != nil || string(c) != s {
			t.Fatalf("IsCanonical true but re-encode drifted: %q -> %q (%v)", s, c, err)
		}
	})
}

func FuzzParsePatchJSON(f *testing.F) {
	seeds := []string{
		`{"glyph_patch":1,"ops":[]}`,
		`{"glyph_patch":1,"ops":[{"op":"=","path":["a"],"value":1}]}`,
		`{"glyph_patch":1,"ops":[{"op":"+","path":["l"],"value":1,"index":0}]}`,
		`{"glyph_patch":1,"ops":[{"op":"~","path":["n"],"value":2.5}]}`,
		`{"glyph_patch":1,"ops":[{"op":"-","path":["x"]}]}`,
		`{"glyph_patch":2,"ops":[]}`,
		`not json`,
	}
	for _, s := range seeds {
		f.Add(s)
	}
	f.Fuzz(func(t *testing.T, s string) {
		p, err := ParsePatch(s)
		if err != nil {
			return
		}
		first, err := EmitPatch(p)
		if err != nil {
			return // e.g. stray Index on a non-append op: emitter rejects
		}
		again, err := ParsePatch(first)
		if err != nil {
			t.Fatalf("EmitPatch output does not parse: %q (%v)", first, err)
		}
		second, err := EmitPatch(again)
		if err != nil || second != first {
			t.Fatalf("patch re-emit unstable: %q -> %q (%v)", first, second, err)
		}
	})
}
