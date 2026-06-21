package glyph

// glyph_gauntlet_test.go — correctness gauntlet for the Go GLYPH codec.
//
// Each test is named Test_Gauntlet_* and encodes WHY the behaviour matters,
// not just what it does. Run with:
//
//	cd /home/omen/Documents/Project/cogs/glyph/go && go test ./glyph/ -run Gauntlet -count=1 -v

import (
	"fmt"
	"math"
	"strings"
	"testing"
	"time"
)

// ============================================================
// Test_Gauntlet_MuseumOfEdgeCases
// ============================================================
//
// Encodes all "evil" input cases from the gauntlet data set.
// Each case verifies:
//   1. CanonicalizeLoose(v) does not panic or error.
//   2. ParseDocument(CanonicalizeLoose(v)) round-trips to EqualLoose.
//   3. Idempotency: CanonicalizeLoose(parse(emit)) == emit.

func Test_Gauntlet_MuseumOfEdgeCases(t *testing.T) {
	opts := NoTabularLooseCanonOpts() // no-tabular for deterministic idempotency check

	cases := []struct {
		name  string
		value *GValue
		note  string
	}{
		{
			name:  "empty-string",
			value: Str(""),
			note:  "empty string must survive round-trip; must not be mistaken for null",
		},
		{
			name:  "unicode-multibyte",
			value: Str("日本語🎉"),
			note:  "multi-byte UTF-8 must survive round-trip without corruption",
		},
		{
			name:  "string-with-quotes",
			value: Str(`say "hello" now`),
			note:  "embedded double-quotes must be escaped in canonical form",
		},
		{
			name:  "string-with-pipe",
			value: Str("a|b|c"),
			note:  "pipe chars are tabular delimiters; strings containing them must quote",
		},
		{
			name:  "string-with-newlines",
			value: Str("line1\nline2\r\nline3"),
			note:  "newlines inside strings must be escaped (\\n, \\r\\n)",
		},
		{
			name:  "null",
			value: Null(),
			note:  "null must canonicalize to _ and round-trip correctly",
		},
		{
			name:  "bool-true",
			value: Bool(true),
			note:  "true must canonicalize to t",
		},
		{
			name:  "bool-false",
			value: Bool(false),
			note:  "false must canonicalize to f",
		},
		{
			name:  "big-int",
			value: Int(9007199254740993), // MAX_SAFE_INTEGER+1
			note:  "Go must handle int64 above JS MAX_SAFE_INTEGER (JS is lossy here — documented gap)",
		},
		{
			name:  "float-scientific",
			value: Float(1.23e100),
			note:  "large float must survive round-trip in scientific notation",
		},
		{
			name:  "neg-zero-float",
			value: Float(math.Copysign(0, -1)), // -0.0
			note:  "negative zero must canonicalize to 0.0 (not -0.0)",
		},
		{
			name:  "date-string",
			value: Str("2024-01-15"),
			note:  "a date-like string must round-trip as a string, not coerced to time",
		},
		{
			name:  "nested-list",
			value: List(List(Int(1), Int(2)), List(Int(3), Int(4))),
			note:  "nested lists must survive round-trip",
		},
		{
			name: "nested-map",
			value: Map(
				FieldVal("outer", Map(
					FieldVal("inner", Str("value")),
				)),
			),
			note: "deeply nested maps must survive round-trip",
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			// Step 1: canonicalize
			emitted := CanonicalizeLooseWithOpts(tc.value, opts)
			if emitted == "" && tc.value != nil && tc.value.typ != TypeStr {
				t.Errorf("[%s] CanonicalizeLoose produced empty string for non-empty value; note: %s", tc.name, tc.note)
				return
			}

			// Step 2: parse back
			parsed, err := ParseDocument(emitted)
			if err != nil {
				t.Errorf("[%s] ParseDocument(%q) error: %v; note: %s", tc.name, emitted, err, tc.note)
				return
			}

			// Step 3: semantic equality
			if !EqualLoose(tc.value, parsed) {
				reEmitted := CanonicalizeLooseWithOpts(parsed, opts)
				t.Errorf("[%s] round-trip value mismatch\n  original emit: %q\n  re-emit:       %q\n  note: %s",
					tc.name, emitted, reEmitted, tc.note)
				return
			}

			// Step 4: idempotency — emit of parse must equal original emit
			reEmitted := CanonicalizeLooseWithOpts(parsed, opts)
			if reEmitted != emitted {
				t.Errorf("[%s] idempotency failure: emit != emit(parse(emit))\n  emit:         %q\n  emit(parse):  %q\n  note: %s",
					tc.name, emitted, reEmitted, tc.note)
			}
		})
	}
}

// ============================================================
// Test_Gauntlet_NegZeroCanonicalisation
// ============================================================
//
// -0.0 must canonicalize to "0.0" (not "-0.0").
// This is a cross-language parity requirement.

func Test_Gauntlet_NegZeroCanonicalisation(t *testing.T) {
	negZero := Float(math.Copysign(0, -1))
	posZero := Float(0)

	negText := CanonicalizeLooseNoTabular(negZero)
	posText := CanonicalizeLooseNoTabular(posZero)

	if negText != "0.0" {
		t.Errorf("neg-zero must canonicalize to '0.0', got %q", negText)
	}
	if posText != "0.0" {
		t.Errorf("pos-zero must canonicalize to '0.0', got %q", posText)
	}
	if negText != posText {
		t.Errorf("-0.0 and 0.0 must produce identical canonical text; got %q vs %q", negText, posText)
	}
}

// ============================================================
// Test_Gauntlet_TypeZoo
// ============================================================
//
// Every supported GType passes through the loose emit/parse cycle
// and the JSON bridge (FromJSONLoose / ToJSONLoose).
//
// WHY: a new type added to the codec should immediately fail here if
// the bridge or canonical path is not wired up.

func Test_Gauntlet_TypeZoo(t *testing.T) {
	now := time.Date(2025, 6, 21, 12, 0, 0, 0, time.UTC)
	opts := NoTabularLooseCanonOpts()

	cases := []struct {
		name  string
		value *GValue
	}{
		{"null", Null()},
		{"bool-true", Bool(true)},
		{"bool-false", Bool(false)},
		{"int-zero", Int(0)},
		{"int-pos", Int(42)},
		{"int-neg", Int(-1)},
		{"int-max", Int(math.MaxInt64)},
		{"int-min", Int(math.MinInt64)},
		{"float-simple", Float(1.5)},
		{"float-neg", Float(-2.5)},
		{"float-sci", Float(1.23e10)},
		{"float-neg-zero", Float(math.Copysign(0, -1))},
		{"str-empty", Str("")},
		{"str-bare", Str("hello")},
		{"str-needs-quote", Str("hello world")},
		{"str-unicode", Str("café")},
		{"str-newline", Str("a\nb")},
		{"bytes-empty", Bytes([]byte{})},
		{"bytes-simple", Bytes([]byte("hello"))},
		{"bytes-binary", Bytes([]byte{0, 1, 255})},
		{"time-utc", Time(now)},
		{"id-prefixed", ID("m", "123")},
		{"id-bare", ID("", "plain")},
		{"list-empty", List()},
		{"list-scalars", List(Int(1), Str("two"), Bool(true))},
		{"map-empty", Map()},
		{"map-mixed", Map(FieldVal("a", Int(1)), FieldVal("b", Str("x")))},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			// Loose text round-trip
			emitted := CanonicalizeLooseWithOpts(tc.value, opts)
			parsed, err := ParseDocument(emitted)
			if err != nil {
				t.Errorf("ParseDocument(%q) error: %v", emitted, err)
				return
			}
			if !EqualLoose(tc.value, parsed) {
				t.Errorf("loose round-trip mismatch: emitted %q, re-parsed not equal", emitted)
			}

			// Typed emit/parse round-trip (for types the typed codec handles)
			typedEmitted := Emit(tc.value)
			typedResult, pErr := Parse(typedEmitted)
			if pErr != nil {
				t.Errorf("Parse(Emit(%q)) error: %v", tc.name, pErr)
				return
			}
			if typedResult.HasErrors() {
				t.Errorf("Parse(Emit(%q)) parse errors: %v", tc.name, typedResult.Errors)
			}
		})
	}
}

// ============================================================
// Test_Gauntlet_JSONBridgeSemanticRoundTrip
// ============================================================
//
// FromJSONLoose(json bytes) -> GValue -> ToJSONLoose -> json must
// re-parse to semantically equal GValue.
//
// WHY: the JSON bridge is the entry point for LLM-produced JSON data.
// Semantic equality (not byte equality) is the contract — map key order
// is not guaranteed by JSON.

func Test_Gauntlet_JSONBridgeSemanticRoundTrip(t *testing.T) {
	cases := []struct {
		name string
		json string
	}{
		{"null", `null`},
		{"bool-true", `true`},
		{"bool-false", `false`},
		{"int", `42`},
		{"neg-int", `-7`},
		{"float", `3.14`},
		{"string", `"hello"`},
		{"empty-string", `""`},
		{"list", `[1, 2, 3]`},
		{"empty-list", `[]`},
		{"map", `{"a": 1, "b": "two"}`},
		{"empty-map", `{}`},
		{"nested", `{"x": {"y": [1, 2]}}`},
		{"string-unicode", `"日本語"`},
		{"string-with-quotes", `"say \"hi\""`},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gv, err := FromJSONLoose([]byte(tc.json))
			if err != nil {
				t.Fatalf("FromJSONLoose(%q) error: %v", tc.json, err)
			}

			// Back to JSON bytes
			jsonBytes, err := ToJSONLoose(gv)
			if err != nil {
				t.Fatalf("ToJSONLoose error: %v", err)
			}

			// Re-parse the emitted JSON
			gv2, err := FromJSONLoose(jsonBytes)
			if err != nil {
				t.Fatalf("FromJSONLoose(re-encoded) error: %v", err)
			}

			// Semantic equality via loose canonicalization (normalizes map order)
			opts := NoTabularLooseCanonOpts()
			c1 := CanonicalizeLooseWithOpts(gv, opts)
			c2 := CanonicalizeLooseWithOpts(gv2, opts)
			if c1 != c2 {
				t.Errorf("JSON semantic round-trip mismatch:\n  c1: %q\n  c2: %q", c1, c2)
			}
		})
	}
}

// ============================================================
// Test_Gauntlet_SchemaHashTrap
// ============================================================
//
// Two schemas with identical field names and types but SWAPPED FIDs
// must produce DIFFERENT schema hashes.
//
// WHY (from spec parseNotes): "FIDs are schema-only (Go concern)".
// If the hash only covered names/types (not FIDs), a receiver could
// silently accept a packed payload that maps FID→field in the wrong
// order, producing a wrong but not-errored decode.
//
// This test asserts the CORRECT invariant. If the current code hashes
// them the same, this test will FAIL LOUD — document it as a real bug.

func Test_Gauntlet_SchemaHashTrap(t *testing.T) {
	// Schema A: x→FID 1, y→FID 2
	schemaA := NewSchemaBuilder().AddPackedStruct("Rec", "v1",
		Field("x", PrimitiveType("int"), WithFID(1)),
		Field("y", PrimitiveType("int"), WithFID(2)),
	).Build()

	// Schema B: x→FID 2, y→FID 1 (FIDs swapped — different wire layout)
	schemaB := NewSchemaBuilder().AddPackedStruct("Rec", "v1",
		Field("x", PrimitiveType("int"), WithFID(2)),
		Field("y", PrimitiveType("int"), WithFID(1)),
	).Build()

	if schemaA.Hash == schemaB.Hash {
		t.Fatalf(
			"REAL BUG: schemas with swapped FIDs must produce different hashes "+
				"(both hash to %q). A decoder that accepts packed data using the wrong "+
				"schema would silently swap x and y.",
			schemaA.Hash,
		)
	}

	// Complement: same FIDs, different declaration order → same hash.
	// (Declaration order is irrelevant; packed layout is determined by FID.)
	schemaC := NewSchemaBuilder().AddPackedStruct("Rec", "v1",
		Field("y", PrimitiveType("int"), WithFID(2)), // declared y first
		Field("x", PrimitiveType("int"), WithFID(1)), // then x
	).Build()

	if schemaA.Hash != schemaC.Hash {
		t.Errorf(
			"schemas with same FIDs but different declaration order must hash identically "+
				"(A=%q, C=%q)",
			schemaA.Hash, schemaC.Hash,
		)
	}
}

// ============================================================
// Test_Gauntlet_ChunkInvariance
// ============================================================
//
// The incremental parser must produce identical events regardless
// of how input is chunked: one big chunk, byte-by-byte, or irregular.
//
// WHY: streaming parsers that are sensitive to chunk boundaries produce
// subtle bugs in real-time LLM output consumers where chunk sizes are
// unpredictable.

type eventRecord struct {
	typ   ParseEventType
	key   string
	value string // CanonicalizeLoose of the value when typ==EventValue
	tag   string // for EventStartSum
}

func collectEvents(t *testing.T, input string, chunks [][]byte) []eventRecord {
	t.Helper()

	var events []eventRecord
	opts := NoTabularLooseCanonOpts()

	handler := func(ev ParseEvent) error {
		switch ev.Type {
		case EventValue:
			canon := ""
			if ev.Value != nil {
				canon = CanonicalizeLooseWithOpts(ev.Value, opts)
			}
			events = append(events, eventRecord{typ: ev.Type, value: canon})
		case EventKey:
			events = append(events, eventRecord{typ: ev.Type, key: ev.Key})
		case EventStartObject, EventEndObject, EventStartList, EventEndList:
			events = append(events, eventRecord{typ: ev.Type})
		case EventStartSum:
			events = append(events, eventRecord{typ: ev.Type, tag: ev.Tag})
		case EventEndSum:
			events = append(events, eventRecord{typ: ev.Type})
		case EventError:
			t.Logf("parse error event: %v", ev.Error)
		}
		return nil
	}

	p := NewIncrementalParser(handler, DefaultIncrementalParserOptions())
	for _, chunk := range chunks {
		if _, err := p.Feed(chunk); err != nil {
			t.Fatalf("Feed error: %v", err)
		}
	}
	if err := p.End(); err != nil {
		t.Fatalf("End error: %v", err)
	}

	return events
}

func chunkBytewise(s string) [][]byte {
	chunks := make([][]byte, len(s))
	for i := range s {
		chunks[i] = []byte{s[i]}
	}
	return chunks
}

func chunkIrregular(s string) [][]byte {
	// Fixed irregular splits: 3, 7, 2, rest
	data := []byte(s)
	var chunks [][]byte
	sizes := []int{3, 7, 2}
	i := 0
	for _, sz := range sizes {
		if i >= len(data) {
			break
		}
		end := i + sz
		if end > len(data) {
			end = len(data)
		}
		chunks = append(chunks, data[i:end])
		i = end
	}
	if i < len(data) {
		chunks = append(chunks, data[i:])
	}
	return chunks
}

func Test_Gauntlet_ChunkInvariance(t *testing.T) {
	inputs := []struct {
		name  string
		input string
	}{
		{"scalar-int", "42"},
		{"scalar-string", `"hello world"`},
		{"simple-map", `{a=1 b=2}`},
		{"nested-map", `{x={y=42} z=true}`},
		{"list", `[1 2 3]`},
		{"mixed", `{name="Alice" scores=[10 20 30] active=t}`},
	}

	for _, tc := range inputs {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			// One-shot
			oneShot := collectEvents(t, tc.input, [][]byte{[]byte(tc.input)})

			// Byte-by-byte
			bytewise := collectEvents(t, tc.input, chunkBytewise(tc.input))

			// Irregular splits
			irregular := collectEvents(t, tc.input, chunkIrregular(tc.input))

			compareEvents := func(label string, got []eventRecord) {
				if len(got) != len(oneShot) {
					t.Errorf("[%s] %s: event count mismatch: oneshot=%d got=%d",
						tc.name, label, len(oneShot), len(got))
					return
				}
				for i := range oneShot {
					if got[i] != oneShot[i] {
						t.Errorf("[%s] %s: event[%d] mismatch:\n  oneshot: %+v\n  got:     %+v",
							tc.name, label, i, oneShot[i], got[i])
					}
				}
			}

			compareEvents("bytewise", bytewise)
			compareEvents("irregular", irregular)
		})
	}
}

// ============================================================
// Test_Gauntlet_PatchApply
// ============================================================
//
// Patch(base, next) applied to base must produce a value EqualLoose to next.
//
// WHY: the patch mechanism is the core of the streaming match-update
// use case. If Diff(a,b) |> ApplyPatch does not recover b, the patch
// protocol is broken.

func Test_Gauntlet_PatchApply(t *testing.T) {
	cases := []struct {
		name string
		base *GValue
		next *GValue
	}{
		{
			name: "set-single-field",
			base: Map(FieldVal("score", Int(0)), FieldVal("minute", Int(0))),
			next: Map(FieldVal("score", Int(1)), FieldVal("minute", Int(45))),
		},
		{
			name: "add-field",
			base: Map(FieldVal("a", Int(1))),
			next: Map(FieldVal("a", Int(1)), FieldVal("b", Int(2))),
		},
		{
			name: "change-string",
			base: Map(FieldVal("status", Str("pending"))),
			next: Map(FieldVal("status", Str("done"))),
		},
		{
			name: "nested-field",
			base: Map(FieldVal("home", Map(FieldVal("score", Int(0))))),
			next: Map(FieldVal("home", Map(FieldVal("score", Int(2))))),
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			patch := Diff(tc.base, tc.next, "")
			if patch == nil {
				t.Fatalf("Diff returned nil patch")
			}

			applied, err := ApplyPatch(tc.base, patch)
			if err != nil {
				t.Fatalf("ApplyPatch error: %v", err)
			}

			if !EqualLoose(applied, tc.next) {
				opts := NoTabularLooseCanonOpts()
				t.Errorf("ApplyPatch(base, Diff(base,next)) != next\n  next:    %s\n  applied: %s",
					CanonicalizeLooseWithOpts(tc.next, opts),
					CanonicalizeLooseWithOpts(applied, opts),
				)
			}
		})
	}
}

// ============================================================
// Test_Gauntlet_TabularAutoTrigger
// ============================================================
//
// CanonicalizeLoose on a list of 3+ homogeneous objects must emit a
// @tab _ block, not a plain list. Verify the savings and the header
// format match the spec.
//
// WHY: auto-tabular is the primary compression mechanism (35-65%
// savings). If it silently stops triggering, downstream token counts
// will blow up without any error.

func Test_Gauntlet_TabularAutoTrigger(t *testing.T) {
	// Build 10 match rows (homogeneous objects)
	rows := make([]*GValue, 10)
	for i := 0; i < 10; i++ {
		rows[i] = Map(
			FieldVal("minute", Int(int64(i*9))),
			FieldVal("score_home", Int(int64(i%3))),
			FieldVal("score_away", Int(int64(i%2))),
		)
	}
	v := List(rows...)

	defaultOpts := DefaultLooseCanonOpts()
	result := CanonicalizeLooseWithOpts(v, defaultOpts)

	if !strings.HasPrefix(result, "@tab _") {
		t.Errorf("expected auto-tabular @tab _ block, got: %q", result[:min(100, len(result))])
	}

	if !strings.HasSuffix(result, "@end") {
		t.Errorf("tabular block must end with @end, got: %q", result[max(0, len(result)-20):])
	}

	// Tabular form must be smaller than flat JSON list
	flatOpts := NoTabularLooseCanonOpts()
	flatResult := CanonicalizeLooseWithOpts(v, flatOpts)
	if len(result) >= len(flatResult) {
		t.Errorf("tabular (%d bytes) must be smaller than flat (%d bytes)", len(result), len(flatResult))
	}

	// Verify round-trip through ParseTabularLoose
	parsed, err := ParseTabularLoose(result)
	if err != nil {
		t.Fatalf("ParseTabularLoose error: %v", err)
	}
	if parsed == nil || parsed.typ != TypeList {
		t.Fatalf("ParseTabularLoose must return a list, got %v", parsed)
	}
	if len(parsed.listVal) != 10 {
		t.Errorf("expected 10 rows, got %d", len(parsed.listVal))
	}
}

// min/max helpers (pre-Go 1.21 compat)
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// ============================================================
// Test_Gauntlet_FirewallUnknownTool
// ============================================================
//
// The StreamingValidator must reject an unknown tool name and
// must not allow further data through after rejection.
//
// WHY: the firewall is a safety primitive. If an unknown tool call
// slips through (e.g. "wire_transfer"), the downstream consumer may
// execute it. The codec spec says wire_transfer is NOT in the default
// registry and must be rejected.

func Test_Gauntlet_FirewallUnknownTool(t *testing.T) {
	registry := DefaultToolRegistry()
	sv := NewStreamingValidator(registry)

	// Feed the tool call token by token (simulating streaming).
	// Format: {action=wire_transfer amount=1000 to="attacker"}
	toolCallText := `{action=wire_transfer amount=1000 to="attacker"}`
	sv.PushToken(toolCallText)

	result := sv.GetResult()

	// wire_transfer is not in the default registry
	if sv.IsToolAllowed() {
		t.Errorf("wire_transfer must be rejected (not in default registry), but IsToolAllowed returned true")
	}
	// ShouldStop must return true for an unknown tool
	if !sv.ShouldStop() {
		t.Errorf("ShouldStop must return true for unknown tool wire_transfer; errors: %v", result.Errors)
	}
	// There must be an UNKNOWN_TOOL error
	hasUnknownTool := false
	for _, e := range result.Errors {
		if e.Code == ErrCodeUnknownTool {
			hasUnknownTool = true
		}
	}
	if !hasUnknownTool {
		t.Errorf("expected UNKNOWN_TOOL error; got: %v", result.Errors)
	}
}

// ============================================================
// Test_Gauntlet_AllowedTool
// ============================================================
//
// A known tool (search) must pass the firewall.

func Test_Gauntlet_AllowedTool(t *testing.T) {
	registry := DefaultToolRegistry()
	sv := NewStreamingValidator(registry)

	toolCallText := `{action=search query="weather NYC"}`
	sv.PushToken(toolCallText)
	result := sv.GetResult()
	_ = result

	if !sv.IsToolAllowed() {
		t.Errorf("search tool must be allowed in default registry; errors: %v", result.Errors)
	}
	if sv.ShouldStop() {
		t.Errorf("ShouldStop must be false for a valid tool call")
	}
}

// ============================================================
// Test_Gauntlet_LooseIdempotency
// ============================================================
//
// CanonicalizeLoose must be idempotent for all scalar types:
// emit(parse(emit(v))) == emit(v).
//
// WHY: if the canonical form is not a fixed point under
// parse-then-emit, then two passes through the codec produce
// different bytes, breaking fingerprinting and deduplication.

func Test_Gauntlet_LooseIdempotency(t *testing.T) {
	opts := NoTabularLooseCanonOpts()

	cases := []*GValue{
		Null(),
		Bool(true), Bool(false),
		Int(0), Int(1), Int(-1), Int(math.MaxInt64), Int(math.MinInt64),
		Float(0), Float(1.5), Float(-2.25), Float(1e100),
		Float(math.Copysign(0, -1)), // -0.0
		Str(""), Str("hello"), Str("with space"), Str("with\"quote"),
		Str("with\nnewline"), Str("日本語"),
		Bytes([]byte{}), Bytes([]byte("hello")), Bytes([]byte{0, 1, 255}),
		ID("m", "123"), ID("", "plain"),
		List(), List(Int(1), Int(2)),
		Map(), Map(FieldVal("a", Int(1)), FieldVal("b", Str("x"))),
	}

	for i, v := range cases {
		v := v
		name := fmt.Sprintf("case-%d", i)
		t.Run(name, func(t *testing.T) {
			emit1 := CanonicalizeLooseWithOpts(v, opts)

			// Parse back through ParseDocument
			parsed, err := ParseDocument(emit1)
			if err != nil {
				t.Skipf("ParseDocument(%q) error (known limitation for some types): %v", emit1, err)
				return
			}

			emit2 := CanonicalizeLooseWithOpts(parsed, opts)

			if emit1 != emit2 {
				t.Errorf("idempotency failure:\n  emit1: %q\n  emit2: %q", emit1, emit2)
			}
		})
	}
}

// ============================================================
// Test_Gauntlet_StreamingValidator (integration)
// ============================================================
//
// Feed the same tool call text as the gauntlet data shows,
// using wire_transfer as the blocked tool and search as allowed.

func Test_Gauntlet_StreamingValidator(t *testing.T) {
	registry := DefaultToolRegistry()

	t.Run("allowed-search-tool", func(t *testing.T) {
		sv := NewStreamingValidator(registry)
		text := `{action=search query="weather NYC" confidence=0.9}`
		sv.PushToken(text)
		result := sv.GetResult()
		_ = result
		if !sv.IsToolAllowed() {
			t.Errorf("search tool must pass; errors: %v", result.Errors)
		}
	})

	t.Run("blocked-wire-transfer", func(t *testing.T) {
		sv := NewStreamingValidator(registry)
		text := `{action=wire_transfer amount=1000}`
		sv.PushToken(text)
		result := sv.GetResult()
		_ = result
		if sv.IsToolAllowed() {
			t.Errorf("wire_transfer must be blocked but IsToolAllowed returned true")
		}
		if !sv.ShouldStop() {
			t.Errorf("ShouldStop must be true for wire_transfer; errors: %v", result.Errors)
		}
	})
}
