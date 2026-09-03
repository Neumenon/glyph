package glyph

import (
	"errors"
	"math"
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

// Boundary cases shared with the py/js ports (deep-review fix list h).
func TestCanonJSONFloatExponentBoundaries(t *testing.T) {
	// 'g' switches between decimal and exponent form at E=-4/-5 and E=5/6;
	// all four cases below are non-integral so no int-collapse applies.
	cases := []struct {
		v    *GValue
		want string
	}{
		{Float(123456.7), "123456.7"},       // E=5 stays decimal
		{Float(1234567.8), "1.2345678e+06"}, // E=6 switches to exponent
		{Float(0.00015), "0.00015"},         // E=-4 stays decimal
		{Float(0.000015), "1.5e-05"},        // E=-5 switches to exponent
	}
	for _, tc := range cases {
		got, err := CanonJSON(tc.v)
		if err != nil || string(got) != tc.want {
			t.Errorf("CanonJSON(%v) = %s, %v; want %s", tc.v.floatVal, got, err, tc.want)
		}
	}
}

func TestCanonJSONNonBMPKeyOrder(t *testing.T) {
	// Go byte order == code point order: U+E000 (EE 80 80) sorts before
	// U+10000 (F0 90 80 80).
	v := Map(MapEntry{Key: "\U00010000", Value: Int(2)}, MapEntry{Key: "\ue000", Value: Int(1)})
	got, err := CanonJSON(v)
	if err != nil {
		t.Fatal(err)
	}
	if want := "{\"\ue000\":1,\"\U00010000\":2}"; string(got) != want {
		t.Errorf("got %s, want %s", got, want)
	}
}

func TestCanonJSONInfiniteErrors(t *testing.T) {
	for _, f := range []float64{math.Inf(1), math.Inf(-1)} {
		if _, err := CanonJSON(Float(f)); !errors.Is(err, ErrNonFinite) {
			t.Errorf("CanonJSON(%v): err = %v, want ErrNonFinite", f, err)
		}
	}
}

func TestBridgeDepthLimit(t *testing.T) {
	nest := func(n int) []byte {
		s := "1"
		for i := 0; i < n; i++ {
			s = "[" + s + "]"
		}
		return []byte(s)
	}
	// 128 levels decode at depth 128 and pass; 129 exceeds bridgeMaxDepth.
	if _, err := FromJSONLoose(nest(128)); err != nil {
		t.Errorf("depth 128 should pass: %v", err)
	}
	if _, err := FromJSONLoose(nest(129)); err == nil || !strings.Contains(err.Error(), "depth") {
		t.Errorf("depth 129: expected depth error, got %v", err)
	}
	deep := nest(200)
	if _, err := FromJSONLoose(deep); err == nil {
		t.Error("depth 200 should be rejected")
	}
	if IsCanonical(deep) {
		t.Error("depth 200 must not be canonical")
	}
}

func TestCanonTimeTruncatesToMilliseconds(t *testing.T) {
	cases := []struct {
		ns   int
		want string
	}{
		{500_123_456, `{"$time":"2025-01-13T12:34:56.5Z"}`}, // sub-ms truncated, not rounded
		{1_234_567, `{"$time":"2025-01-13T12:34:56.001Z"}`},
		{123_456, `{"$time":"2025-01-13T12:34:56Z"}`}, // sub-ms-only fraction vanishes
		{0, `{"$time":"2025-01-13T12:34:56Z"}`},
	}
	for _, tc := range cases {
		got, err := CanonJSON(Time(time.Date(2025, 1, 13, 12, 34, 56, tc.ns, time.UTC)))
		if err != nil || string(got) != tc.want {
			t.Errorf("ns=%d: got %s, %v; want %s", tc.ns, got, err, tc.want)
		}
	}
	// Identity comes from the truncated form: same ms, different sub-ms.
	a, _ := CanonJSON(Time(time.Date(2025, 1, 13, 12, 34, 56, 500_000_000, time.UTC)))
	b, _ := CanonJSON(Time(time.Date(2025, 1, 13, 12, 34, 56, 500_999_999, time.UTC)))
	if string(a) != string(b) {
		t.Errorf("sub-ms must not affect identity: %s vs %s", a, b)
	}
}

func TestBridgeRejectsFractionalTensorDims(t *testing.T) {
	zeros := strings.Repeat("0", 64)
	mk := func(shape string) []byte {
		return []byte(`{"$tensor":{"dtype":"float32","shape":` + shape + `,"sha256":"` + zeros + `"}}`)
	}
	if _, err := FromJSONLoose(mk(`[1]`)); err != nil {
		t.Errorf("integer dim should pass: %v", err)
	}
	for _, shape := range []string{`[1.0]`, `[1e3]`, `[1.5]`, `[-1]`, `[9007199254740992]`} {
		if _, err := FromJSONLoose(mk(shape)); err == nil {
			t.Errorf("shape %s should be rejected", shape)
		}
	}
}

func TestTensorRefRejectsNonZeroPadding(t *testing.T) {
	// qint4 shape [3] = 12 bits in 2 bytes; top nibble of the last byte pads.
	if _, err := TensorRef("qint4", []int{3}, []byte{0x21, 0x03}); err != nil {
		t.Errorf("zero padding should pass: %v", err)
	}
	if _, err := TensorRef("qint4", []int{3}, []byte{0x21, 0x30}); err == nil {
		t.Error("non-zero padding bits should be rejected")
	}
	// binary shape [9] = 9 bits in 2 bytes; top 7 bits of last byte pad.
	if _, err := TensorRef("binary", []int{9}, []byte{0xff, 0x01}); err != nil {
		t.Errorf("zero padding should pass: %v", err)
	}
	if _, err := TensorRef("binary", []int{9}, []byte{0xff, 0x02}); err == nil {
		t.Error("non-zero padding bits should be rejected")
	}
	// Byte-aligned dtypes have no padding: high bits are data.
	if _, err := TensorRef("int8", []int{1}, []byte{0xff}); err != nil {
		t.Errorf("int8 0xff should pass: %v", err)
	}
}
