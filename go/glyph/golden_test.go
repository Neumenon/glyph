package glyph

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

// TestGoldenCrossLanguage ensures Go produces identical output to the golden fixtures.
// These same fixtures are tested by JavaScript and Python implementations.
func TestGoldenCrossLanguage(t *testing.T) {
	casesDir := filepath.Join("testdata", "loose_json", "cases")
	goldenDir := filepath.Join("testdata", "loose_json", "golden")

	entries, err := os.ReadDir(goldenDir)
	if err != nil {
		t.Fatalf("failed to read golden dir: %v", err)
	}

	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".want") {
			continue
		}

		name := strings.TrimSuffix(entry.Name(), ".want")
		t.Run(name, func(t *testing.T) {
			jsonPath := filepath.Join(casesDir, name+".json")
			wantPath := filepath.Join(goldenDir, name+".want")

			// Read input JSON
			jsonBytes, err := os.ReadFile(jsonPath)
			if err != nil {
				t.Fatalf("failed to read JSON: %v", err)
			}

			// Read expected GLYPH output
			wantBytes, err := os.ReadFile(wantPath)
			if err != nil {
				t.Fatalf("failed to read expected GLYPH: %v", err)
			}
			expected := strings.TrimSpace(string(wantBytes))

			// Convert JSON to GValue
			gval, err := FromJSONLoose(jsonBytes)
			if err != nil {
				t.Fatalf("FromJSONLoose failed: %v", err)
			}

			// Convert to GLYPH canonical form (v2.2.x: no tabular, ∅ null)
			got := CanonicalizeLooseNoTabular(gval)

			if got != expected {
				t.Errorf("output mismatch\n  got:      %s\n  expected: %s", got, expected)
			}

			// Round-trip: parse GLYPH back to value
			parsed, _, err := ParseLoosePayload(got, nil)
			if err != nil {
				t.Fatalf("ParseLoosePayload failed: %v", err)
			}

			// Re-emit and verify determinism
			reemit := CanonicalizeLooseNoTabular(parsed)
			if reemit != got {
				t.Errorf("non-deterministic output\n  first:  %s\n  second: %s", got, reemit)
			}
		})
	}
}

// TestGoldenRoundTrip verifies JSON → GLYPH → JSON round-trip preserves data.
func TestGoldenRoundTrip(t *testing.T) {
	casesDir := filepath.Join("testdata", "loose_json", "cases")

	entries, err := os.ReadDir(casesDir)
	if err != nil {
		t.Fatalf("failed to read cases dir: %v", err)
	}

	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}

		name := strings.TrimSuffix(entry.Name(), ".json")
		t.Run(name, func(t *testing.T) {
			jsonPath := filepath.Join(casesDir, name+".json")

			jsonBytes, err := os.ReadFile(jsonPath)
			if err != nil {
				t.Fatalf("failed to read JSON: %v", err)
			}

			var originalAny any
			if err := json.Unmarshal(jsonBytes, &originalAny); err != nil {
				t.Fatalf("json unmarshal failed: %v", err)
			}

			// JSON → GValue
			original, err := FromJSONLoose(jsonBytes)
			if err != nil {
				t.Fatalf("FromJSONLoose failed: %v", err)
			}

			// GValue → GLYPH string
			glyphStr := CanonicalizeLooseNoTabular(original)

			// GLYPH → parsed GValue
			parsed, _, err := ParseLoosePayload(glyphStr, nil)
			if err != nil {
				t.Fatalf("ParseLoosePayload failed: %v", err)
			}

			// Parsed GValue → JSON value
			roundTripAny, err := ToJSONValueLoose(parsed)
			if err != nil {
				t.Fatalf("ToJSONValueLoose failed: %v", err)
			}

			// Compare semantic JSON structures.
			if !deepEqualJSON(originalAny, roundTripAny) {
				origBytes, _ := json.Marshal(originalAny)
				rtBytes, _ := json.Marshal(roundTripAny)
				t.Errorf("JSON round-trip mismatch\n  original: %s\n  roundtrip: %s", string(origBytes), string(rtBytes))
			}
		})
	}
}

// deepEqualJSON compares JSON-like values with a small amount of normalization.
func deepEqualJSON(a, b any) bool {
	return reflect.DeepEqual(a, b)
}
