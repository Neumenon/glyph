package glyph

import (
	"bufio"
	"encoding/hex"
	"encoding/json"
	"os"
	"strings"
	"testing"
)

// SPEC-CANON.md §4: a tensor is identified by sha256 of its raw element bytes.
// The fixtures are cowrie's 8 tensor cases with the bytes lifted from its golden
// encodings, so glyph and cowrie name the same tensor by the same hash.
const tensorFixtures = "../../harness/state_identity/data/tensor_refs.jsonl"

func TestTensorRefMatchesCowrieBytes(t *testing.T) {
	f, err := os.Open(tensorFixtures)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	n := 0
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1<<20), 1<<20)
	for sc.Scan() {
		var fx struct {
			ID      string `json:"id"`
			Tensors []struct {
				DType   string `json:"dtype"`
				Shape   []int  `json:"shape"`
				DataHex string `json:"data_hex"`
				SHA     string `json:"sha256"`
			} `json:"tensors"`
			JSON        string `json:"json"`
			Fingerprint string `json:"fingerprint"`
		}
		if err := json.Unmarshal(sc.Bytes(), &fx); err != nil {
			t.Fatal(err)
		}
		for _, tt := range fx.Tensors {
			data, err := hex.DecodeString(tt.DataHex)
			if err != nil {
				t.Fatal(err)
			}
			ref, err := TensorRef(tt.DType, tt.Shape, data)
			if err != nil {
				t.Fatalf("%s: %v", fx.ID, err)
			}
			got, err := CanonJSON(ref)
			if err != nil {
				t.Fatal(err)
			}
			want, _ := json.Marshal(map[string]any{"$tensor": map[string]any{
				"dtype": tt.DType, "shape": tt.Shape, "sha256": tt.SHA,
			}})
			if string(got) != string(want) {
				t.Fatalf("%s: got %s want %s", fx.ID, got, want)
			}
		}
		v, err := FromJSONLoose([]byte(fx.JSON))
		if err != nil {
			t.Fatalf("%s: %v", fx.ID, err)
		}
		c, err := CanonJSON(v)
		if err != nil || string(c) != fx.JSON {
			t.Fatalf("%s: canon %s (%v) want %s", fx.ID, c, err, fx.JSON)
		}
		fp, _ := Fingerprint(v)
		if fp != fx.Fingerprint {
			t.Fatalf("%s: fingerprint %s want %s", fx.ID, fp, fx.Fingerprint)
		}
		n++
	}
	if n != 8 {
		t.Fatalf("want 8 fixtures, got %d", n)
	}
}

func TestTensorRefRejectsWrongPackedSize(t *testing.T) {
	if _, err := TensorRef("qint4", []int{3}, []byte{0x21, 0x03}); err != nil { // 12 bits -> 2 bytes
		t.Fatal(err)
	}
	for _, c := range []struct {
		dtype string
		shape []int
		n     int
	}{
		{"qint4", []int{3}, 3},
		{"float32", []int{2}, 7},
		{"f32", []int{2}, 8}, // cowrie names only, no aliases
	} {
		if _, err := TensorRef(c.dtype, c.shape, make([]byte, c.n)); err == nil {
			t.Fatalf("%+v accepted", c)
		}
	}
}

func TestBridgeRejectsMalformedTensorRef(t *testing.T) {
	// An uppercase or short sha256 would fingerprint differently from the same
	// tensor written correctly: the bridge refuses to mint that second identity.
	zeros := strings.Repeat("0", 64)
	if _, err := FromJSONLoose([]byte(`{"$tensor":{"dtype":"float32","shape":[1],"sha256":"` + zeros + `"}}`)); err != nil {
		t.Fatal(err)
	}
	for _, bad := range []string{
		`{"dtype":"float32","shape":[1],"sha256":"` + strings.Repeat("A", 64) + `"}`,
		`{"dtype":"float32","shape":[1],"sha256":"` + zeros[:63] + `"}`,
		`{"dtype":"float32","shape":[-1],"sha256":"` + zeros + `"}`,
		`{"dtype":"float32","shape":[true],"sha256":"` + zeros + `"}`,
		`{"dtype":"f32","shape":[1],"sha256":"` + zeros + `"}`,
		`{"dtype":"float32","shape":[1]}`,
		`{"dtype":"float32","shape":[1],"sha256":"` + zeros + `","extra":1}`,
		`"x"`,
	} {
		if _, err := FromJSONLoose([]byte(`{"$tensor":` + bad + `}`)); err == nil {
			t.Fatalf("accepted %s", bad)
		}
	}
}
