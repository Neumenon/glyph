package glyph

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

// Suite 3: Canonicalization Equivalence Classes
// Groups of semantically equivalent inputs must produce identical canonical output.

type equivClass struct {
	ID           string   `json:"id"`
	Description  string   `json:"description"`
	InputsJSON   []any    `json:"inputs_json"`
	CanonicalVal string   `json:"canonical_value"`
	Canonical    string   `json:"canonical"`
	TestStrings  []string `json:"test_strings"`
	ExpectBare   *bool    `json:"expect_bare"`
}

type equivManifest struct {
	Classes []equivClass `json:"classes"`
}

func equivTestdataDir() string {
	_, filename, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(filename), "testdata")
}

func TestEquivalenceClasses(t *testing.T) {
	data, err := os.ReadFile(filepath.Join(equivTestdataDir(), "equivalence_classes.json"))
	if err != nil {
		t.Fatalf("failed to read equivalence_classes.json: %v", err)
	}

	var manifest equivManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		t.Fatalf("failed to parse manifest: %v", err)
	}

	opts := LLMLooseCanonOpts()

	for _, cls := range manifest.Classes {
		t.Run(cls.ID, func(t *testing.T) {
			switch {
			case cls.TestStrings != nil && cls.ExpectBare != nil:
				testStringBareSafety(t, cls)
			case len(cls.InputsJSON) > 0 && cls.CanonicalVal != "":
				testNumericEquivalence(t, cls, opts)
			case len(cls.InputsJSON) > 1 && cls.Canonical != "":
				testObjectEquivalence(t, cls, opts)
			case cls.CanonicalVal != "" && len(cls.InputsJSON) == 1:
				testSingleCanon(t, cls, opts)
			default:
				t.Skipf("unhandled equivalence class type: %s", cls.ID)
			}
		})
	}
}

func testNumericEquivalence(t *testing.T, cls equivClass, opts LooseCanonOpts) {
	t.Helper()
	for _, input := range cls.InputsJSON {
		gv := equivJsonToGValue(input)
		canonical := CanonicalizeLooseWithOpts(gv, opts)
		if canonical != cls.CanonicalVal {
			t.Errorf("input %v: got %q, want %q", input, canonical, cls.CanonicalVal)
		}
	}
}

func testObjectEquivalence(t *testing.T, cls equivClass, opts LooseCanonOpts) {
	t.Helper()
	var results []string
	for _, input := range cls.InputsJSON {
		gv := equivJsonToGValue(input)
		canonical := CanonicalizeLooseWithOpts(gv, opts)
		results = append(results, canonical)
	}

	for i := 1; i < len(results); i++ {
		if results[i] != results[0] {
			t.Errorf("input[%d] produced %q, but input[0] produced %q", i, results[i], results[0])
		}
	}

	if cls.Canonical != "" && results[0] != cls.Canonical {
		t.Errorf("canonical mismatch: got %q, want %q", results[0], cls.Canonical)
	}
}

func testSingleCanon(t *testing.T, cls equivClass, opts LooseCanonOpts) {
	t.Helper()
	for _, input := range cls.InputsJSON {
		gv := equivJsonToGValue(input)
		canonical := CanonicalizeLooseWithOpts(gv, opts)
		if canonical != cls.CanonicalVal {
			t.Errorf("input %v: got %q, want %q", input, canonical, cls.CanonicalVal)
		}
	}
}

func testStringBareSafety(t *testing.T, cls equivClass) {
	t.Helper()
	for _, s := range cls.TestStrings {
		safe := isBareSafeV2(s)
		if *cls.ExpectBare && !safe {
			t.Errorf("expected %q to be bare-safe, but it was not", s)
		} else if !*cls.ExpectBare && safe {
			t.Errorf("expected %q to NOT be bare-safe, but it was", s)
		}
	}
}

// equivJsonToGValue converts a JSON-decoded any value to a GValue.
func equivJsonToGValue(v any) *GValue {
	switch val := v.(type) {
	case nil:
		return Null()
	case bool:
		return Bool(val)
	case float64:
		if val == math.Trunc(val) && math.Abs(val) < 1e15 {
			return Int(int64(val))
		}
		return Float(val)
	case string:
		return Str(val)
	case []any:
		items := make([]*GValue, len(val))
		for i, item := range val {
			items[i] = equivJsonToGValue(item)
		}
		return List(items...)
	case map[string]any:
		entries := make([]MapEntry, 0, len(val))
		for k, v := range val {
			entries = append(entries, MapEntry{Key: k, Value: equivJsonToGValue(v)})
		}
		return Map(entries...)
	default:
		return Null()
	}
}
