package glyph

import (
	"bytes"
	"math"
	"testing"
)

// patch_listops_test.go covers P2 patch correctness: list-index leaf operations
// (set/delete/insert) and root-list operations in ApplyPatch, the FID-resolution
// pre-pass, and the end-to-end invariant
//
//	ApplyPatch(base, ParsePatch(EmitPatch(Diff(base, next)))) == next
//
// including list-index cases.

// patchEqual is a semantic deep-equality used by these tests. Struct/map fields
// compare by key (order-independent) because patch application and Diff iterate
// fields in non-deterministic map order.
func patchEqual(a, b *GValue) bool {
	if a.IsNull() || b.IsNull() {
		return a.IsNull() && b.IsNull()
	}
	if a.Type() != b.Type() {
		return false
	}
	switch a.Type() {
	case TypeBool:
		return a.boolVal == b.boolVal
	case TypeInt:
		return a.intVal == b.intVal
	case TypeFloat:
		if math.IsNaN(a.floatVal) || math.IsNaN(b.floatVal) {
			return math.IsNaN(a.floatVal) && math.IsNaN(b.floatVal)
		}
		return a.floatVal == b.floatVal
	case TypeStr:
		return a.strVal == b.strVal
	case TypeBytes:
		return bytes.Equal(a.bytesVal, b.bytesVal)
	case TypeTime:
		return a.timeVal.Equal(b.timeVal)
	case TypeID:
		return a.idVal == b.idVal
	case TypeList:
		if len(a.listVal) != len(b.listVal) {
			return false
		}
		for i := range a.listVal {
			if !patchEqual(a.listVal[i], b.listVal[i]) {
				return false
			}
		}
		return true
	case TypeMap:
		return patchEntriesEqual(a.mapVal, b.mapVal)
	case TypeStruct:
		if a.structVal.TypeName != b.structVal.TypeName {
			return false
		}
		return patchEntriesEqual(a.structVal.Fields, b.structVal.Fields)
	case TypeSum:
		return a.sumVal.Tag == b.sumVal.Tag && patchEqual(a.sumVal.Value, b.sumVal.Value)
	}
	return false
}

func patchEntriesEqual(a, b []MapEntry) bool {
	if len(a) != len(b) {
		return false
	}
	bm := make(map[string]*GValue, len(b))
	for _, e := range b {
		bm[e.Key] = e.Value
	}
	for _, e := range a {
		bv, ok := bm[e.Key]
		if !ok || !patchEqual(e.Value, bv) {
			return false
		}
	}
	return true
}

// ---- list-index leaf operations -------------------------------------------

func TestApplyListIndexLeafSet(t *testing.T) {
	doc := Struct("X", FieldVal("items", List(Str("old0"), Str("old1"))))
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpSet,
		Path:  []PathSeg{FieldSeg("items", 0), ListIdxSeg(0)},
		Value: Str("new0"),
	})

	result, err := ApplyPatch(doc, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}
	first, _ := result.Get("items").Index(0)
	if first == nil || first.strVal != "new0" {
		t.Errorf("expected items[0]='new0', got %v", first)
	}
	// The original document must be untouched (ApplyPatch deep-copies).
	orig0, _ := doc.Get("items").Index(0)
	if orig0.strVal != "old0" {
		t.Errorf("ApplyPatch mutated the input document: %v", orig0)
	}
}

func TestApplyListIndexLeafDelete(t *testing.T) {
	doc := Struct("X", FieldVal("items", List(Str("a"), Str("b"), Str("c"))))
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:   OpDelete,
		Path: []PathSeg{FieldSeg("items", 0), ListIdxSeg(1)},
	})

	result, err := ApplyPatch(doc, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}
	want := List(Str("a"), Str("c"))
	if !patchEqual(result.Get("items"), want) {
		t.Errorf("expected [a c] after delete, got %v", result.Get("items"))
	}
}

func TestApplyListIndexLeafInsert(t *testing.T) {
	doc := Struct("X", FieldVal("items", List(Str("a"), Str("c"))))
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpAppend,
		Path:  []PathSeg{FieldSeg("items", 0), ListIdxSeg(1)},
		Value: Str("b"),
	})

	result, err := ApplyPatch(doc, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}
	want := List(Str("a"), Str("b"), Str("c"))
	if !patchEqual(result.Get("items"), want) {
		t.Errorf("expected [a b c] after insert, got %v", result.Get("items"))
	}
}

func TestApplyListIndexLeafDelta(t *testing.T) {
	doc := Struct("X", FieldVal("scores", List(Int(10), Int(20))))
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpDelta,
		Path:  []PathSeg{FieldSeg("scores", 0), ListIdxSeg(1)},
		Value: Int(5),
	})

	result, err := ApplyPatch(doc, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}
	got, _ := result.Get("scores").Index(1)
	if got.intVal != 25 {
		t.Errorf("expected scores[1]=25 after delta, got %v", got)
	}
}

func TestApplyListIndexOutOfBounds(t *testing.T) {
	doc := Struct("X", FieldVal("items", List(Str("a"))))
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpSet,
		Path:  []PathSeg{FieldSeg("items", 0), ListIdxSeg(5)},
		Value: Str("z"),
	})
	if _, err := ApplyPatch(doc, patch); err == nil {
		t.Error("expected out-of-bounds error, got nil")
	}
}

// ---- root-list operations --------------------------------------------------

func TestApplyRootListSet(t *testing.T) {
	doc := List(Str("a"), Str("b"))
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpSet,
		Path:  []PathSeg{ListIdxSeg(0)},
		Value: Str("new"),
	})
	result, err := ApplyPatch(doc, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}
	if !patchEqual(result, List(Str("new"), Str("b"))) {
		t.Errorf("expected [new b], got %v", result)
	}
}

func TestApplyRootListDeleteAndInsert(t *testing.T) {
	doc := List(Int(1), Int(2), Int(3))

	del := NewPatch(RefID{}, "")
	del.Ops = append(del.Ops, &PatchOp{Op: OpDelete, Path: []PathSeg{ListIdxSeg(0)}})
	afterDel, err := ApplyPatch(doc, del)
	if err != nil {
		t.Fatalf("delete error: %v", err)
	}
	if !patchEqual(afterDel, List(Int(2), Int(3))) {
		t.Errorf("expected [2 3] after root delete, got %v", afterDel)
	}

	ins := NewPatch(RefID{}, "")
	ins.Ops = append(ins.Ops, &PatchOp{Op: OpAppend, Path: []PathSeg{ListIdxSeg(2)}, Value: Int(4)})
	afterIns, err := ApplyPatch(afterDel, ins)
	if err != nil {
		t.Fatalf("insert error: %v", err)
	}
	if !patchEqual(afterIns, List(Int(2), Int(3), Int(4))) {
		t.Errorf("expected [2 3 4] after root insert at end, got %v", afterIns)
	}
}

// TestApplyListIndexThroughEmitParse proves the list-index path survives
// EmitPatch -> ParsePatch and still applies correctly.
func TestApplyListIndexThroughEmitParse(t *testing.T) {
	doc := Struct("X", FieldVal("items", List(Str("a"), Str("b"), Str("c"))))
	patch := NewPatch(RefID{Prefix: "x", Value: "1"}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpSet,
		Path:  []PathSeg{FieldSeg("items", 0), ListIdxSeg(2)},
		Value: Str("C"),
	})

	emitted, err := EmitPatch(patch, nil)
	if err != nil {
		t.Fatalf("EmitPatch error: %v", err)
	}
	parsed, err := ParsePatch(emitted, nil)
	if err != nil {
		t.Fatalf("ParsePatch error: %v (emitted: %q)", err, emitted)
	}
	result, err := ApplyPatch(doc, parsed)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v (emitted: %q)", err, emitted)
	}
	if !patchEqual(result.Get("items"), List(Str("a"), Str("b"), Str("C"))) {
		t.Errorf("expected [a b C], got %v (emitted: %q)", result.Get("items"), emitted)
	}
}

// ---- Diff/Apply round-trip invariant --------------------------------------

func TestDiffApplyRoundTripInvariant(t *testing.T) {
	cases := []struct {
		name       string
		base, next *GValue
	}{
		{
			"scalar-change",
			Struct("M", FieldVal("a", Int(1)), FieldVal("b", Str("x"))),
			Struct("M", FieldVal("a", Int(2)), FieldVal("b", Str("x"))),
		},
		{
			"add-and-delete-field",
			Struct("M", FieldVal("a", Int(1)), FieldVal("gone", Str("bye"))),
			Struct("M", FieldVal("a", Int(1)), FieldVal("added", Bool(true))),
		},
		{
			"nested-struct-change",
			Struct("M", FieldVal("inner", Struct("N", FieldVal("x", Int(1)), FieldVal("y", Int(2))))),
			Struct("M", FieldVal("inner", Struct("N", FieldVal("x", Int(9)), FieldVal("y", Int(2))))),
		},
		{
			"list-replace",
			Struct("M", FieldVal("items", List(Int(1), Int(2), Int(3)))),
			Struct("M", FieldVal("items", List(Int(1), Int(9), Int(3), Int(4)))),
		},
		{
			"map-change",
			Struct("M", FieldVal("m", Map(FieldVal("k1", Int(1)), FieldVal("k2", Int(2))))),
			Struct("M", FieldVal("m", Map(FieldVal("k1", Int(1)), FieldVal("k2", Int(20)), FieldVal("k3", Int(3))))),
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			diff := Diff(tc.base, tc.next, "M")
			emitted, err := EmitPatch(diff, nil)
			if err != nil {
				t.Fatalf("EmitPatch error: %v", err)
			}
			parsed, err := ParsePatch(emitted, nil)
			if err != nil {
				t.Fatalf("ParsePatch error: %v\npatch:\n%s", err, emitted)
			}
			result, err := ApplyPatch(tc.base, parsed)
			if err != nil {
				t.Fatalf("ApplyPatch error: %v\npatch:\n%s", err, emitted)
			}
			if !patchEqual(result, tc.next) {
				t.Errorf("round-trip mismatch\n  base:  %s\n  next:  %s\n  got:   %s\n  patch:\n%s",
					Emit(tc.base), Emit(tc.next), Emit(result), emitted)
			}
		})
	}
}

// TestDiffApplyRoundTripListIndex covers the explicit list-index leaf path
// through the full Diff-less build -> Emit -> Parse -> Apply pipeline (Diff
// replaces whole lists, so list-index ops are exercised via a hand-built patch).
func TestDiffApplyRoundTripListIndex(t *testing.T) {
	base := Struct("M", FieldVal("items", List(Str("a"), Str("b"), Str("c"))))
	next := Struct("M", FieldVal("items", List(Str("a"), Str("B"), Str("c"))))

	patch := NewPatch(RefID{Prefix: "m", Value: "1"}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpSet,
		Path:  []PathSeg{FieldSeg("items", 0), ListIdxSeg(1)},
		Value: Str("B"),
	})

	emitted, err := EmitPatch(patch, nil)
	if err != nil {
		t.Fatalf("EmitPatch error: %v", err)
	}
	parsed, err := ParsePatch(emitted, nil)
	if err != nil {
		t.Fatalf("ParsePatch error: %v", err)
	}
	result, err := ApplyPatch(base, parsed)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}
	if !patchEqual(result, next) {
		t.Errorf("list-index round-trip mismatch: got %s want %s", Emit(result), Emit(next))
	}
}

// ---- FID-resolution pre-pass ----------------------------------------------

// TestFIDModeApplyRoundTrip proves the required FID-resolution pre-pass: a
// FID-mode patch emitted with only #fid path segments parses back with empty
// Field names and must be resolved (via ApplyPatchWithSchema) before it applies.
func TestFIDModeApplyRoundTrip(t *testing.T) {
	schema := makePatchTestSchema()
	base := Struct("Match",
		FieldVal("id", ID("m", "ARS-LIV")),
		FieldVal("status", Str("pre")),
		FieldVal("home", Struct("Team",
			FieldVal("id", ID("t", "ARS")),
			FieldVal("name", Str("Arsenal")),
			FieldVal("score", Int(0)),
		)),
	)

	patch := NewPatch(RefID{Prefix: "m", Value: "ARS-LIV"}, schema.Hash)
	patch.TargetType = "Match"
	// FID-only segments (no field names).
	patch.SetWithSegs([]PathSeg{{Kind: PathSegField, FID: 2}}, Str("live"))           // status
	patch.SetWithSegs([]PathSeg{{Kind: PathSegField, FID: 3}, {Kind: PathSegField, FID: 3}}, Int(2)) // home.score

	emitted, err := EmitPatchWithOptions(patch, PatchOptions{Schema: schema, KeyMode: KeyModeFID, SortOps: true})
	if err != nil {
		t.Fatalf("EmitPatch error: %v", err)
	}

	parsed, err := ParsePatch(emitted, schema)
	if err != nil {
		t.Fatalf("ParsePatch error: %v\n%s", err, emitted)
	}
	// Parsed FID paths have empty Field — plain ApplyPatch must refuse them.
	if _, err := ApplyPatch(base, parsed); err == nil {
		t.Errorf("expected ApplyPatch to refuse unresolved FID path")
	}

	// ApplyPatchWithSchema runs the resolution pre-pass (root type derived from
	// the base struct) and applies.
	result, err := ApplyPatchWithSchema(base, parsed, schema)
	if err != nil {
		t.Fatalf("ApplyPatchWithSchema error: %v\n%s", err, emitted)
	}
	if s := result.Get("status"); s == nil || s.strVal != "live" {
		t.Errorf("expected status=live, got %v", s)
	}
	score := result.Get("home").Get("score")
	if score == nil || score.intVal != 2 {
		t.Errorf("expected home.score=2, got %v", score)
	}
}

// ---- panic-free error paths -----------------------------------------------

// TestApplySetOnNonStructParent verifies applyToParentSeg returns a clean error
// (not panic) when the parent value is not a map or struct.
func TestApplySetOnNonStructParent(t *testing.T) {
	// A document where "count" is an int. A patch tries to set count.sub = 1,
	// which would navigate to count (int) and then try to Set "sub" on it.
	doc := Struct("X", FieldVal("count", Int(5)))
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpSet,
		Path:  []PathSeg{FieldSeg("count", 0), FieldSeg("sub", 0)},
		Value: Int(1),
	})
	_, err := ApplyPatch(doc, patch)
	if err == nil {
		t.Error("expected error when setting field on int parent, got nil")
	}
}

// TestApplySetRootIntParent verifies that a FieldSeg on a root int returns an
// error rather than panicking via GValue.Set.
func TestApplySetRootIntParent(t *testing.T) {
	doc := Int(42)
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpSet,
		Path:  []PathSeg{FieldSeg("foo", 0)},
		Value: Int(1),
	})
	_, err := ApplyPatch(doc, patch)
	if err == nil {
		t.Error("expected error when setting field on int root, got nil")
	}
}

// TestApplyDeltaIntTruncation verifies that a float delta that would truncate
// when applied to an int field returns an error.
func TestApplyDeltaIntTruncation(t *testing.T) {
	doc := Struct("X", FieldVal("n", Int(10)))
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpDelta,
		Path:  []PathSeg{FieldSeg("n", 0)},
		Value: Float(1.5), // fractional — would silently truncate to 1 without guard
	})
	_, err := ApplyPatch(doc, patch)
	if err == nil {
		t.Error("expected error for float delta 1.5 on int field, got nil")
	}
}

// TestApplyDeltaIntegerFloat verifies that a float delta that is a whole number
// (e.g. 5.0) is accepted for an int field without error.
func TestApplyDeltaIntegerFloat(t *testing.T) {
	doc := Struct("X", FieldVal("n", Int(10)))
	patch := NewPatch(RefID{}, "")
	patch.Ops = append(patch.Ops, &PatchOp{
		Op:    OpDelta,
		Path:  []PathSeg{FieldSeg("n", 0)},
		Value: Float(5.0), // integer-valued float — must apply cleanly
	})
	result, err := ApplyPatch(doc, patch)
	if err != nil {
		t.Fatalf("unexpected error for whole-number float delta: %v", err)
	}
	if result.Get("n").intVal != 15 {
		t.Errorf("expected n=15, got %d", result.Get("n").intVal)
	}
}
