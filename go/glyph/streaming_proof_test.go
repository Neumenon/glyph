package glyph

import (
	"encoding/json"
	"strings"
	"testing"
)

// TestStreamingParseabilityProof demonstrates the core claim:
// partial GLYPH is parseable and yields extracted values,
// while partial JSON is syntactically invalid and yields nothing.
//
// Both formats receive tokens via SSE identically. The difference
// is what you can DO with the partial text that has arrived so far.
func TestStreamingParseabilityProof(t *testing.T) {
	// Full tool call in both formats
	fullJSON := `{"name": "web_search", "arguments": {"query": "transformer attention mechanism", "max_results": 5}}`
	fullGLYPH := `tool_call { name: "web_search" arguments: {query: "transformer attention mechanism" max_results: 5} }`

	// Simulate SSE: we've received tokens up to and including the query value,
	// but the document isn't closed. Cut at a point where individual values
	// are complete but the overall structure is open.
	partialJSON := `{"name": "web_search", "arguments": {"query": "transformer attention mechanism"`
	partialGLYPH := `tool_call { name: "web_search" arguments: {query: "transformer attention mechanism"`

	t.Run("full_json_parses", func(t *testing.T) {
		var v map[string]interface{}
		if err := json.Unmarshal([]byte(fullJSON), &v); err != nil {
			t.Fatalf("full JSON should parse: %v", err)
		}
		if v["name"] != "web_search" {
			t.Fatalf("expected web_search, got %v", v["name"])
		}
	})

	t.Run("full_glyph_parses", func(t *testing.T) {
		result, err := Parse(fullGLYPH)
		if err != nil {
			t.Fatalf("full GLYPH should parse: %v", err)
		}
		name := result.Value.Get("name")
		if name == nil {
			t.Fatal("expected name field")
		}
		nameStr, nameErr := name.AsStr()
		if nameErr != nil || nameStr != "web_search" {
			t.Fatalf("expected name=web_search, got %v (err=%v)", nameStr, nameErr)
		}
		args := result.Value.Get("arguments")
		if args == nil {
			t.Fatal("expected arguments field")
		}
		maxResults := args.Get("max_results")
		if maxResults == nil {
			t.Fatal("expected max_results field")
		}
		mr, mrErr := maxResults.AsInt()
		if mrErr != nil || mr != 5 {
			t.Fatalf("expected max_results=5, got %v (err=%v)", mr, mrErr)
		}
	})

	t.Run("partial_json_fails", func(t *testing.T) {
		var v map[string]interface{}
		err := json.Unmarshal([]byte(partialJSON), &v)
		if err == nil {
			t.Fatal("partial JSON should NOT parse, but it did")
		}
		// This is the point: you received tokens via SSE, but json.Unmarshal
		// gives you NOTHING. No name, no partial arguments. Complete failure.
		t.Logf("JSON parser: %v", err)
		t.Logf("Extractable values: 0 (must buffer until closing })")
	})

	t.Run("partial_glyph_extracts_values", func(t *testing.T) {
		// GLYPH tolerant parser auto-closes unterminated structures
		// and returns whatever fields were successfully parsed.
		result, err := Parse(partialGLYPH)
		if err != nil {
			t.Fatalf("partial GLYPH should parse in tolerant mode: %v", err)
		}

		// The struct type is preserved
		if result.Value.Type() != TypeStruct {
			t.Fatalf("expected struct, got %s", result.Value.Type())
		}

		// name field is FULLY extracted despite incomplete document
		name := result.Value.Get("name")
		if name == nil {
			t.Fatal("GLYPH should extract 'name' from partial input")
		}
		nameStr, nameErr := name.AsStr()
		if nameErr != nil {
			t.Fatalf("AsStr failed: %v", nameErr)
		}
		if nameStr != "web_search" {
			t.Fatalf("expected web_search, got %s", nameStr)
		}
		t.Logf("Extracted name = %q from partial input", nameStr)

		// arguments struct is also extracted (auto-closed)
		args := result.Value.Get("arguments")
		if args == nil {
			t.Fatal("GLYPH should extract 'arguments' from partial input")
		}

		// query is a truncated string — the lexer may error on the unterminated
		// string, but in tolerant mode we still get the arguments key.
		// The point is: we have SOMETHING, not nothing.
		query := args.Get("query")
		if query != nil {
			qStr, qErr := query.AsStr()
			if qErr == nil {
				t.Logf("Extracted arguments.query = %q (truncated)", qStr)
			}
		} else {
			t.Logf("arguments.query not fully extractable (string unterminated)")
		}

		// Count what we got vs what JSON got
		extractedCount := 0
		if name != nil {
			extractedCount++
		}
		if args != nil {
			extractedCount++
		}
		t.Logf("Extractable values: %d (vs JSON: 0)", extractedCount)

		// Warnings show the auto-closing happened
		for _, w := range result.Warnings {
			t.Logf("  warning: %s", w.Message)
		}
	})

	t.Run("incremental_extraction_simulation", func(t *testing.T) {
		// Simulate token-by-token arrival. After each "chunk",
		// try both parsers. Count when each first extracts a value.
		chunks := []string{
			`tool_call { `,
			`name: "web_search" `,
			`arguments: {`,
			`query: "transformer attention mechanism" `,
			`max_results: 5`,
			`} }`,
		}

		jsonChunks := []string{
			`{"name": `,
			`"web_search", `,
			`"arguments": {`,
			`"query": "transformer attention mechanism", `,
			`"max_results": 5`,
			`}}`,
		}

		t.Log("--- Token-by-token arrival ---")

		var glyphBuf, jsonBuf strings.Builder
		glyphFirstExtract := -1
		jsonFirstExtract := -1

		for i := range chunks {
			glyphBuf.WriteString(chunks[i])
			jsonBuf.WriteString(jsonChunks[i])

			// Try GLYPH
			result, err := Parse(glyphBuf.String())
			glyphOK := err == nil && result.Value != nil && result.Value.Get("name") != nil
			if glyphOK && glyphFirstExtract < 0 {
				glyphFirstExtract = i
			}

			// Try JSON
			var v map[string]interface{}
			jsonErr := json.Unmarshal([]byte(jsonBuf.String()), &v)
			jsonOK := jsonErr == nil && v["name"] != nil
			if jsonOK && jsonFirstExtract < 0 {
				jsonFirstExtract = i
			}

			glyphStatus := "FAIL"
			if glyphOK {
				glyphStatus = "OK"
			}
			jsonStatus := "FAIL"
			if jsonOK {
				jsonStatus = "OK"
			}

			t.Logf("  chunk %d: GLYPH=%s  JSON=%s", i, glyphStatus, jsonStatus)
		}

		t.Logf("")
		t.Logf("GLYPH first extracts 'name' at chunk %d", glyphFirstExtract)
		t.Logf("JSON  first extracts 'name' at chunk %d", jsonFirstExtract)

		if glyphFirstExtract >= jsonFirstExtract {
			t.Error("Expected GLYPH to extract values before JSON")
		}

		t.Logf("")
		t.Logf("GLYPH extracts values %d chunks earlier than JSON",
			jsonFirstExtract-glyphFirstExtract)
	})
}
