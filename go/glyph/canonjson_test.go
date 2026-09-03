package glyph

import (
	"errors"
	"strings"
	"testing"
	"time"
)

// SPEC-CANON.md conformance. Every expected string here is shared verbatim with
// py/tests/test_canon.py and js/src/canon.test.ts: the one digest must be
// byte-identical across languages, so a divergence fails in all three.
func TestCanonJSON(t *testing.T) {
	m := func(entries ...MapEntry) *GValue { return Map(entries...) }
	e := func(k string, v *GValue) MapEntry { return MapEntry{Key: k, Value: v} }
	cases := []struct {
		name string
		v    *GValue
		want string
	}{
		{"scalars", m(e("b", List(Int(1), Float(2.5), Null(), Bool(true))), e("a", Str("q\"\\\n\t\x01é😀"))),
			`{"a":"q\"\\\n\t\u0001é😀","b":[1,2.5,null,true]}`},
		{"float 1.0 collapses", Float(1.0), "1"},
		{"neg zero", Float(-0.0 * 1), "0"},
		{"1e300", Float(1e300), "1e+300"},
		{"2^53 float", Float(1 << 53), "9.007199254740992e+15"},
		{"1e-7", Float(1e-7), "1e-07"},
		{"max safe int", Int(1<<53 - 1), "9007199254740991"},
		{"code point key order", m(e("😀", Int(2)), e("", Int(1))), `{"":1,"😀":2}`},
		{"bytes", Bytes([]byte{0, 0xff}), `{"$bytes":"AP8="}`},
		{"time", Time(time.Date(2025, 1, 13, 12, 34, 56, 500_000_000, time.UTC)), `{"$time":"2025-01-13T12:34:56.5Z"}`},
		{"id", IDFromRef(RefID{Prefix: "m", Value: "1"}), `{"$id":["m","1"]}`},
		{"struct drops type name", Struct("Team", e("z", Int(1)), e("a", Int(2))), `{"a":2,"z":1}`},
		{"sum", Sum("Ok", Int(1)), `{"Ok":1}`},
		{"sum nil", Sum("None", nil), `{"None":null}`},
	}
	for _, tc := range cases {
		got, err := CanonJSON(tc.v)
		if err != nil || string(got) != tc.want {
			t.Errorf("%s: got %s, %v; want %s", tc.name, got, err, tc.want)
		}
	}

	errs := []struct {
		name string
		v    *GValue
		want error
	}{
		{"int beyond safe", Int(1 << 53), ErrIntegerRange},
		{"nan", Float(nan()), ErrNonFinite},
		{"dup key", m(e("k", Int(1)), e("k", Int(2))), ErrDuplicateKey},
	}
	for _, tc := range errs {
		if _, err := CanonJSON(tc.v); !errors.Is(err, tc.want) {
			t.Errorf("%s: err = %v, want %v", tc.name, err, tc.want)
		}
	}

	deep := List()
	for i := 0; i < 999; i++ {
		deep = List(deep)
	}
	if _, err := CanonJSON(deep); err != nil {
		t.Errorf("depth 1000 should pass: %v", err)
	}
	if _, err := CanonJSON(List(deep)); !errors.Is(err, ErrDepth) {
		t.Errorf("depth 1001: err = %v", err)
	}
}

func TestFingerprintIsTheOneDigest(t *testing.T) {
	v, _ := FromJSONLoose([]byte(`{"b":[1,2.0,null],"a":"x"}`))
	fp, err := Fingerprint(v)
	if err != nil || len(fp) != 64 || strings.ToLower(fp) != fp {
		t.Fatalf("Fingerprint = %q, %v", fp, err)
	}
	p, err := Diff(v, v, "")
	if err != nil || p.BaseFingerprint != fp {
		t.Errorf("Diff base %q != fingerprint %q (%v)", p.BaseFingerprint, fp, err)
	}
	if NewPatchBuilder(RefID{}).WithBaseValue(v).Build().BaseFingerprint != fp {
		t.Error("WithBaseValue != Fingerprint")
	}
}

func TestIsCanonical(t *testing.T) {
	yes := []string{`{"a":1,"b":[true,null]}`, `"x"`, `1`}
	no := []string{`{"b":[true,null],"a":1}`, `{"a": 1}`, `{"a":1.0}`, `{"a":1,"a":2}`, `nope`}
	for _, s := range yes {
		if !IsCanonical([]byte(s)) {
			t.Errorf("%s should be canonical", s)
		}
	}
	for _, s := range no {
		if IsCanonical([]byte(s)) {
			t.Errorf("%s should not be canonical", s)
		}
	}
}

func nan() float64 {
	z := 0.0
	return z / z
}
