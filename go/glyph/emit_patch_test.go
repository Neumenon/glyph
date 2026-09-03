package glyph

import (
	"strings"
	"testing"
)

// ============================================================
// Patch Encoding Tests (SPEC-CANON.md §7 wire form)
// ============================================================

func makeMatchForPatch() *GValue {
	return Struct("Match",
		FieldVal("id", ID("m", "ARS-LIV")),
		FieldVal("home", Struct("Team",
			FieldVal("id", ID("t", "ARS")),
			FieldVal("name", Str("Arsenal")),
			FieldVal("rating", Float(1850.5)),
		)),
		FieldVal("away", Struct("Team",
			FieldVal("id", ID("t", "LIV")),
			FieldVal("name", Str("Liverpool")),
			FieldVal("rating", Float(1890.0)),
		)),
		FieldVal("events", List()),
	)
}

func mustEmitPatch(t *testing.T, p *Patch) string {
	t.Helper()
	got, err := EmitPatch(p)
	if err != nil {
		t.Fatalf("EmitPatch error: %v", err)
	}
	return got
}

func TestPatchBasic(t *testing.T) {
	patch := NewPatch(RefID{Prefix: "m", Value: "ARS-LIV"}, "abc123").
		Set("home.ft_h", Int(2)).
		Set("away.ft_a", Int(1))

	got := mustEmitPatch(t, patch)
	want := `{"glyph_patch":1,"ops":[{"op":"=","path":["away","ft_a"],"value":1},{"op":"=","path":["home","ft_h"],"value":2}],"schema":"abc123","target":"m:ARS-LIV"}`
	if got != want {
		t.Errorf("EmitPatch\n got: %s\nwant: %s", got, want)
	}
}

// TestPatchEmitCanonicalAndSorted pins the two wire guarantees: the bytes are
// canonical JSON (IsCanonical) and ops are ordered by (canon_json(path), op),
// independent of insertion order. Both are what make a patch diffed in any
// language hash the same.
func TestPatchEmitCanonicalAndSorted(t *testing.T) {
	patch := NewPatch(RefID{Prefix: "m", Value: "1"}, "")
	patch.Ops = []*PatchOp{
		{Op: OpSet, Path: []PathSeg{FieldSeg("z", 0)}, Value: Int(1)},
		{Op: OpSet, Path: []PathSeg{FieldSeg("a", 0)}, Value: Null()},
		{Op: OpDelete, Path: []PathSeg{FieldSeg("a", 0)}},
		{Op: OpSet, Path: []PathSeg{FieldSeg("a", 0), ListIdxSeg(2)}, Value: Int(3)},
		{Op: OpSet, Path: []PathSeg{FieldSeg("a", 0), ListIdxSeg(10)}, Value: Int(4)},
	}
	got := mustEmitPatch(t, patch)
	// The key is the canonical path bytes, not a structural compare: ["a",10]
	// sorts before ["a",2] (digit order) and both before ["a"] because "," <
	// "]"; on the same path "-" (0x2d) sorts before "=" (0x3d).
	want := `{"glyph_patch":1,"ops":[` +
		`{"op":"=","path":["a",10],"value":4},` +
		`{"op":"=","path":["a",2],"value":3},` +
		`{"op":"-","path":["a"]},` +
		`{"op":"=","path":["a"],"value":null},` +
		`{"op":"=","path":["z"],"value":1}],"target":"m:1"}`
	if got != want {
		t.Errorf("EmitPatch\n got: %s\nwant: %s", got, want)
	}
	if !IsCanonical([]byte(got)) {
		t.Errorf("EmitPatch output is not canonical JSON: %s", got)
	}
}

func TestPatchAllOperations(t *testing.T) {
	patch := NewPatch(RefID{Prefix: "m", Value: "123"}, "").
		Set("score", Int(5)).
		Append("events", Str("Goal!")).
		Delete("odds").
		Delta("home.rating", 0.15)

	got := mustEmitPatch(t, patch)
	want := `{"glyph_patch":1,"ops":[` +
		`{"op":"+","path":["events"],"value":"Goal!"},` +
		`{"op":"~","path":["home","rating"],"value":0.15},` +
		`{"op":"-","path":["odds"]},` +
		`{"op":"=","path":["score"],"value":5}],"target":"m:123"}`
	if got != want {
		t.Errorf("EmitPatch\n got: %s\nwant: %s", got, want)
	}
}

func TestPatchDeltaAndIndex(t *testing.T) {
	patch := NewPatch(RefID{}, "").
		Delta("score", -3).
		InsertAt("l", 0, Int(1)).
		Delta("n", 2.5)

	got := mustEmitPatch(t, patch)
	// Integral float deltas collapse to integer digits (SPEC-CANON.md §2);
	// index rides only on "+".
	want := `{"glyph_patch":1,"ops":[{"index":0,"op":"+","path":["l"],"value":1},{"op":"~","path":["n"],"value":2.5},{"op":"~","path":["score"],"value":-3}]}`
	if got != want {
		t.Errorf("EmitPatch\n got: %s\nwant: %s", got, want)
	}
}

// TestPatchReservedValues: typed scalars inside a patch value ride as §3
// objects and come back typed, so a patch cannot silently downgrade an id or
// bytes to a string.
func TestPatchReservedValues(t *testing.T) {
	patch := NewPatch(RefID{}, "").
		Set("player", ID("p", "smith")).
		Set("blob", Bytes([]byte{0, 1, 2})).
		Append("events", Struct("Event",
			FieldVal("minute", Int(90)),
			FieldVal("who", ID("", "anon")),
		))

	got := mustEmitPatch(t, patch)
	want := `{"glyph_patch":1,"ops":[` +
		`{"op":"=","path":["blob"],"value":{"$bytes":"AAEC"}},` +
		`{"op":"+","path":["events"],"value":{"minute":90,"who":{"$id":["","anon"]}}},` +
		`{"op":"=","path":["player"],"value":{"$id":["p","smith"]}}]}`
	if got != want {
		t.Errorf("EmitPatch\n got: %s\nwant: %s", got, want)
	}

	parsed, err := ParsePatch(got)
	if err != nil {
		t.Fatalf("ParsePatch: %v", err)
	}
	if v := parsed.Ops[0].Value; v.Type() != TypeBytes || string(v.bytesVal) != "\x00\x01\x02" {
		t.Errorf("blob: want bytes 000102, got %v", v)
	}
	if v := parsed.Ops[1].Value.Get("who"); v == nil || v.Type() != TypeID || v.idVal != (RefID{Value: "anon"}) {
		t.Errorf("events.who: want id ^anon, got %v", v)
	}
	if v := parsed.Ops[2].Value; v.Type() != TypeID || v.idVal != (RefID{Prefix: "p", Value: "smith"}) {
		t.Errorf("player: want id ^p:smith, got %v", v)
	}
	if again := mustEmitPatch(t, parsed); again != got {
		t.Errorf("re-emit drifted\n got: %s\nwant: %s", again, got)
	}
}

func TestPatchEmitErrors(t *testing.T) {
	if _, err := EmitPatch(nil); err == nil {
		t.Error("nil patch: expected error")
	}
	bad := NewPatch(RefID{}, "")
	bad.Ops = []*PatchOp{{Op: OpDelta, Path: []PathSeg{FieldSeg("n", 0)}, Value: Str("x")}}
	if _, err := EmitPatch(bad); err == nil {
		t.Error("non-numeric delta: expected error")
	}
	fid := NewPatch(RefID{}, "")
	fid.Ops = []*PatchOp{{Op: OpSet, Path: []PathSeg{{Kind: PathSegField, FID: 3}}, Value: Int(1)}}
	if _, err := EmitPatch(fid); err == nil || !strings.Contains(err.Error(), "unresolved FID") {
		t.Errorf("unresolved FID: expected error, got %v", err)
	}
}

func TestPatchBuilder(t *testing.T) {
	patch := NewPatchBuilder(RefID{Prefix: "m", Value: "ARS-LIV"}).
		WithSchemaID("schema123").
		Set("home.ft_h", Int(2)).
		Append("events", Str("HT")).
		Delete("odds.pre").
		Delta("home.rating", 15.5).
		Build()

	if patch.SchemaID != "schema123" {
		t.Errorf("Expected schema ID schema123, got: %s", patch.SchemaID)
	}
	if len(patch.Ops) != 4 {
		t.Errorf("Expected 4 operations, got: %d", len(patch.Ops))
	}
}

func TestPatchApply(t *testing.T) {
	match := makeMatchForPatch()

	patch := NewPatch(RefID{}, "").
		Set("home.ft_h", Int(2)).
		Set("away.ft_a", Int(1))

	result, err := ApplyPatch(match, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}

	// Verify the changes
	home := result.Get("home")
	if home == nil {
		t.Fatal("home field missing")
	}
	ftH := home.Get("ft_h")
	if ftH == nil || mustAsInt(t, ftH) != 2 {
		t.Errorf("Expected home.ft_h = 2, got: %v", ftH)
	}

	away := result.Get("away")
	if away == nil {
		t.Fatal("away field missing")
	}
	ftA := away.Get("ft_a")
	if ftA == nil || mustAsInt(t, ftA) != 1 {
		t.Errorf("Expected away.ft_a = 1, got: %v", ftA)
	}

	// Verify original is unchanged (immutable)
	origHome := match.Get("home")
	if origHome.Get("ft_h") != nil {
		t.Error("Original should not be modified")
	}
}

func TestPatchApplyAppend(t *testing.T) {
	match := makeMatchForPatch()

	patch := NewPatch(RefID{}, "").
		Append("events", Str("Kickoff")).
		Append("events", Str("Goal!"))

	result, err := ApplyPatch(match, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}

	events := result.Get("events")
	if events == nil || events.Len() != 2 {
		t.Errorf("Expected 2 events, got: %v", events)
	}
	idx0, err := events.Index(0)
	if err != nil {
		t.Fatalf("Index(0) failed: %v", err)
	}
	if mustAsStr(t, idx0) != "Kickoff" {
		t.Errorf("Expected first event = Kickoff, got: %s", mustAsStr(t, idx0))
	}
}

func TestPatchApplyDelete(t *testing.T) {
	match := makeMatchForPatch()

	patch := NewPatch(RefID{}, "").
		Delete("events")

	result, err := ApplyPatch(match, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}

	events := result.Get("events")
	if events != nil {
		t.Errorf("Expected events to be deleted, got: %v", events)
	}
}

func TestPatchApplyDelta(t *testing.T) {
	match := makeMatchForPatch()

	patch := NewPatch(RefID{}, "").
		Delta("home.rating", 50.5)

	result, err := ApplyPatch(match, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}

	home := result.Get("home")
	rating := home.Get("rating")
	expected := 1850.5 + 50.5
	if mustAsFloat(t, rating) != expected {
		t.Errorf("Expected rating = %f, got: %f", expected, mustAsFloat(t, rating))
	}
}

// TestPatchApplyFieldSegIntoMap: wire paths are plain strings, so a parsed
// patch navigates maps with FieldSeg (Diff emits MapKeySeg for the same
// value). Both must reach the nested map entry.
func TestPatchApplyFieldSegIntoMap(t *testing.T) {
	doc := Map(MapEntry{Key: "cfg", Value: Map(MapEntry{Key: "inner", Value: Map(MapEntry{Key: "n", Value: Int(1)})})})
	patch := NewPatch(RefID{}, "")
	patch.Ops = []*PatchOp{
		{Op: OpSet, Path: []PathSeg{FieldSeg("cfg", 0), FieldSeg("inner", 0), FieldSeg("n", 0)}, Value: Int(2)},
		{Op: OpSet, Path: []PathSeg{FieldSeg("cfg", 0), MapKeySeg("inner"), FieldSeg("m", 0)}, Value: Int(3)},
	}
	result, err := ApplyPatch(doc, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}
	inner := result.Get("cfg").Get("inner")
	if mustAsInt(t, inner.Get("n")) != 2 || mustAsInt(t, inner.Get("m")) != 3 {
		t.Errorf("expected inner {n=2 m=3}, got %s", Emit(inner))
	}
}

func TestDiff(t *testing.T) {
	from := Struct("Match",
		FieldVal("id", ID("m", "123")),
		FieldVal("score", Int(0)),
		FieldVal("status", Str("pending")),
	)

	to := Struct("Match",
		FieldVal("id", ID("m", "123")),
		FieldVal("score", Int(3)),
		FieldVal("status", Str("finished")),
		FieldVal("winner", Str("home")),
	)

	patch := mustDiff(from, to, "Match")

	// Should have: score change, status change, winner added
	if len(patch.Ops) < 3 {
		t.Errorf("Expected at least 3 operations, got: %d", len(patch.Ops))
	}

	// Verify operations exist
	hasScore := false
	hasStatus := false
	hasWinner := false

	for _, op := range patch.Ops {
		pathStr := pathSegsStr(op.Path)
		if pathStr == "score" {
			hasScore = true
		}
		if pathStr == "status" {
			hasStatus = true
		}
		if pathStr == "winner" {
			hasWinner = true
		}
	}

	if !hasScore {
		t.Error("Missing score change")
	}
	if !hasStatus {
		t.Error("Missing status change")
	}
	if !hasWinner {
		t.Error("Missing winner addition")
	}

	t.Logf("Diff generated %d operations", len(patch.Ops))
}

func TestDiffWithDeletion(t *testing.T) {
	from := Struct("Match",
		FieldVal("id", ID("m", "123")),
		FieldVal("odds", Float(1.5)),
		FieldVal("pred", Str("home")),
	)

	to := Struct("Match",
		FieldVal("id", ID("m", "123")),
		// odds and pred removed
	)

	patch := mustDiff(from, to, "Match")

	// Should have deletions for odds and pred
	deleteCount := 0
	for _, op := range patch.Ops {
		if op.Op == OpDelete {
			deleteCount++
		}
	}

	if deleteCount != 2 {
		t.Errorf("Expected 2 deletions, got: %d", deleteCount)
	}
}

func TestPathParsing(t *testing.T) {
	tests := []struct {
		input    string
		expected []string
	}{
		{"home.ft_h", []string{"home", "ft_h"}},
		{"a.b.c.d", []string{"a", "b", "c", "d"}},
		{"single", []string{"single"}},
		{"", nil},
	}

	for _, tc := range tests {
		got := parsePathToSegs(tc.input)
		if len(got) != len(tc.expected) {
			t.Errorf("parsePathToSegs(%q): expected %d segs, got %d", tc.input, len(tc.expected), len(got))
			continue
		}
		for i := range got {
			if got[i].Field != tc.expected[i] {
				t.Errorf("parsePathToSegs(%q)[%d]: expected %q, got %q", tc.input, i, tc.expected[i], got[i].Field)
			}
		}
	}
}

func TestPathFIDParsing(t *testing.T) {
	tests := []struct {
		input       string
		expectedFID []int
	}{
		{"#3.#2", []int{3, 2}},
		{"#1", []int{1}},
		{"home.#2", []int{0, 2}}, // home has no FID, #2 has FID=2
		{"#3.name", []int{3, 0}}, // #3 has FID=3, name has no FID
	}

	for _, tc := range tests {
		got := parsePathToSegs(tc.input)
		if len(got) != len(tc.expectedFID) {
			t.Errorf("parsePathToSegs(%q): expected %d segs, got %d", tc.input, len(tc.expectedFID), len(got))
			continue
		}
		for i := range got {
			if got[i].FID != tc.expectedFID[i] {
				t.Errorf("parsePathToSegs(%q)[%d]: expected FID=%d, got FID=%d", tc.input, i, tc.expectedFID[i], got[i].FID)
			}
		}
	}
}

func TestDeepCopy(t *testing.T) {
	original := Struct("Test",
		FieldVal("num", Int(42)),
		FieldVal("str", Str("hello")),
		FieldVal("list", List(Int(1), Int(2), Int(3))),
		FieldVal("nested", Struct("Inner",
			FieldVal("x", Float(3.14)),
		)),
	)

	copied := deepCopy(original)

	// Modify the copy
	copied.Get("num").intVal = 100
	copied.Get("str").strVal = "modified"
	copied.Get("list").listVal[0].intVal = 999
	copied.Get("nested").Get("x").floatVal = 9.99

	// Verify original is unchanged
	if mustAsInt(t, original.Get("num")) != 42 {
		t.Error("Original num was modified")
	}
	if mustAsStr(t, original.Get("str")) != "hello" {
		t.Error("Original str was modified")
	}
	idx0, err := original.Get("list").Index(0)
	if err != nil {
		t.Fatalf("Index(0) failed: %v", err)
	}
	if mustAsInt(t, idx0) != 1 {
		t.Error("Original list was modified")
	}
	if mustAsFloat(t, original.Get("nested").Get("x")) != 3.14 {
		t.Error("Original nested was modified")
	}
}

// ============================================================
// Base Fingerprint Tests (SPEC-CANON.md §5)
// ============================================================

func TestPatchWithBaseFingerprint(t *testing.T) {
	baseState := Map(
		MapEntry{Key: "score", Value: Int(0)},
		MapEntry{Key: "status", Value: Str("pending")},
	)

	patch := NewPatchBuilder(RefID{Prefix: "m", Value: "123"}).
		WithBaseValue(baseState).
		Set("score", Int(5)).
		Build()

	got := mustEmitPatch(t, patch)

	if patch.BaseFingerprint == "" || len(patch.BaseFingerprint) != 64 {
		t.Errorf("Expected 64-char fingerprint, got: %q", patch.BaseFingerprint)
	}
	if !strings.HasPrefix(got, `{"base":"`+patch.BaseFingerprint+`",`) {
		t.Errorf("Expected base in wire form, got: %s", got)
	}
}

func TestPatchBaseFingerprint_Parse(t *testing.T) {
	input := `{"glyph_patch":1,"ops":[{"op":"=","path":["score"],"value":5}],"schema":"abc123","target":"m:123","base":"1234567890abcdef"}`

	patch, err := ParsePatch(input)
	if err != nil {
		t.Fatalf("ParsePatch error: %v", err)
	}

	if patch.BaseFingerprint != "1234567890abcdef" {
		t.Errorf("Expected base fingerprint '1234567890abcdef', got: %q", patch.BaseFingerprint)
	}
	if patch.SchemaID != "abc123" {
		t.Errorf("Expected schema abc123, got %q", patch.SchemaID)
	}
	if patch.Target != (RefID{Prefix: "m", Value: "123"}) {
		t.Errorf("Expected target m:123, got %v", patch.Target)
	}
}

func TestPatchBaseFingerprint_Roundtrip(t *testing.T) {
	baseState := Map(
		MapEntry{Key: "x", Value: Int(10)},
		MapEntry{Key: "y", Value: Int(20)},
	)

	originalPatch := NewPatchBuilder(RefID{Prefix: "m", Value: "test"}).
		WithBaseValue(baseState).
		Set("x", Int(100)).
		Build()

	patchText := mustEmitPatch(t, originalPatch)
	parsedPatch, err := ParsePatch(patchText)
	if err != nil {
		t.Fatalf("ParsePatch error: %v", err)
	}

	if originalPatch.BaseFingerprint != parsedPatch.BaseFingerprint {
		t.Errorf("Fingerprint mismatch:\nOriginal: %s\nParsed: %s",
			originalPatch.BaseFingerprint, parsedPatch.BaseFingerprint)
	}
}

func TestPatchWithExplicitFingerprint(t *testing.T) {
	patch := NewPatchBuilder(RefID{Prefix: "m", Value: "123"}).
		WithBaseFingerprint("abcdef0123456789").
		Set("value", Int(42)).
		Build()

	got := mustEmitPatch(t, patch)
	if !strings.Contains(got, `"base":"abcdef0123456789"`) {
		t.Errorf("Expected explicit base fingerprint, got: %s", got)
	}
}
