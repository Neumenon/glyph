package glyph

import (
	"testing"
)

// patch_roundtrip_test.go contains the round-trip invariant property test:
//
//	ApplyPatch(base, ParsePatch(EmitPatch(Diff(base, next)))) == next
//
// It also tests the VerifyPatchBase API and the escaped map-key path cases.

// ---- Subcase helpers -------------------------------------------------------

func runRoundTrip(t *testing.T, base, next *GValue, typeName string) *GValue {
	t.Helper()
	diff := Diff(base, next, typeName)
	emitted, err := EmitPatch(diff, nil)
	if err != nil {
		t.Fatalf("EmitPatch: %v", err)
	}
	parsed, err := ParsePatch(emitted, nil)
	if err != nil {
		t.Fatalf("ParsePatch: %v\npatch:\n%s", err, emitted)
	}
	result, err := ApplyPatch(base, parsed)
	if err != nil {
		t.Fatalf("ApplyPatch: %v\npatch:\n%s", err, emitted)
	}
	if !patchEqual(result, next) {
		t.Errorf("round-trip mismatch\n  base: %s\n  next: %s\n  got:  %s\n  patch:\n%s",
			Emit(base), Emit(next), Emit(result), emitted)
	}
	return result
}

// ---- TestPatchRoundTripProperty -------------------------------------------

func TestPatchRoundTripProperty(t *testing.T) {
	t.Run("scalar-fields", func(t *testing.T) {
		// Subcase 1: scalar field changes (bool/int/float/str/id).
		base := Struct("M",
			FieldVal("ok", Bool(false)),
			FieldVal("count", Int(10)),
			FieldVal("rate", Float(1.5)),
			FieldVal("label", Str("old")),
		)
		next := Struct("M",
			FieldVal("ok", Bool(true)),
			FieldVal("count", Int(42)),
			FieldVal("rate", Float(3.14)),
			FieldVal("label", Str("new")),
		)
		runRoundTrip(t, base, next, "M")
	})

	t.Run("nested-struct", func(t *testing.T) {
		// Subcase 2: nested struct change.
		base := Struct("M",
			FieldVal("outer", Struct("N",
				FieldVal("inner", Struct("O", FieldVal("x", Int(1)))),
			)),
		)
		next := Struct("M",
			FieldVal("outer", Struct("N",
				FieldVal("inner", Struct("O", FieldVal("x", Int(99)))),
			)),
		)
		runRoundTrip(t, base, next, "M")
	})

	t.Run("map-keys-simple", func(t *testing.T) {
		// Subcase 3: map keys, no escapes (Diff-driven).
		base := Struct("M",
			FieldVal("cfg", Map(
				FieldVal("timeout", Int(5000)),
				FieldVal("retries", Int(3)),
			)),
		)
		next := Struct("M",
			FieldVal("cfg", Map(
				FieldVal("timeout", Int(10000)),
				FieldVal("retries", Int(5)),
				FieldVal("host", Str("example.com")),
			)),
		)
		runRoundTrip(t, base, next, "M")
	})

	t.Run("map-key-escaped-roundtrip", func(t *testing.T) {
		// Subcase 4: map key with escape sequences — hand-built patch, not via
		// Diff, to directly exercise the GAP 1 fix (map key quoting/unquoting).
		escapedKeys := []string{
			`a\b`,         // backslash
			`k"ey`,        // double-quote
			"nl\nkey",     // newline
			"tab\tkey",    // tab
			`normal/slash`, // no escaping needed but explicit check
		}

		for _, key := range escapedKeys {
			key := key // capture
			t.Run("key="+key, func(t *testing.T) {
				base := Struct("M",
					FieldVal("cfg", Map(FieldVal(key, Int(0)))),
				)
				patch := NewPatch(RefID{Prefix: "x", Value: "1"}, "")
				patch.Ops = append(patch.Ops, &PatchOp{
					Op:    OpSet,
					Path:  []PathSeg{FieldSeg("cfg", 0), MapKeySeg(key)},
					Value: Int(99),
				})
				emitted, err := EmitPatch(patch, nil)
				if err != nil {
					t.Fatalf("EmitPatch: %v", err)
				}
				parsed, err := ParsePatch(emitted, nil)
				if err != nil {
					t.Fatalf("ParsePatch: %v (emitted: %q)", err, emitted)
				}
				result, err := ApplyPatch(base, parsed)
				if err != nil {
					t.Fatalf("ApplyPatch: %v (emitted: %q)", err, emitted)
				}
				v := result.Get("cfg")
				if v == nil {
					t.Fatal("cfg missing in result")
				}
				// Find the entry by key.
				var got *GValue
				for _, e := range v.mapVal {
					if e.Key == key {
						got = e.Value
						break
					}
				}
				if got == nil || got.intVal != 99 {
					t.Errorf("key %q: got %v, want 99 (emitted: %q)", key, got, emitted)
				}
			})
		}
	})

	t.Run("list-replace-via-diff", func(t *testing.T) {
		// Subcase 5: Diff replaces whole lists with OpSet.
		base := Struct("M", FieldVal("items", List(Int(1), Int(2), Int(3))))
		next := Struct("M", FieldVal("items", List(Int(1), Int(9), Int(3), Int(4))))
		runRoundTrip(t, base, next, "M")
	})

	t.Run("list-index-set", func(t *testing.T) {
		// Subcase 6: hand-built list-index set, multi-index.
		base := Struct("M", FieldVal("items", List(Str("a"), Str("b"), Str("c"), Str("d"))))
		patch := NewPatch(RefID{Prefix: "m", Value: "1"}, "")
		patch.Ops = append(patch.Ops,
			&PatchOp{Op: OpSet, Path: []PathSeg{FieldSeg("items", 0), ListIdxSeg(1)}, Value: Str("B")},
			&PatchOp{Op: OpSet, Path: []PathSeg{FieldSeg("items", 0), ListIdxSeg(3)}, Value: Str("D")},
		)
		emitted, err := EmitPatch(patch, nil)
		if err != nil {
			t.Fatalf("EmitPatch: %v", err)
		}
		parsed, err := ParsePatch(emitted, nil)
		if err != nil {
			t.Fatalf("ParsePatch: %v", err)
		}
		result, err := ApplyPatch(base, parsed)
		if err != nil {
			t.Fatalf("ApplyPatch: %v", err)
		}
		want := Struct("M", FieldVal("items", List(Str("a"), Str("B"), Str("c"), Str("D"))))
		if !patchEqual(result, want) {
			t.Errorf("got %s, want %s", Emit(result), Emit(want))
		}
	})

	t.Run("list-index-delete-and-insert", func(t *testing.T) {
		// Subcase 7: list-index delete then insert.
		base := Struct("M", FieldVal("items", List(Str("a"), Str("b"), Str("c"))))

		// Delete index 1 ("b").
		del := NewPatch(RefID{Prefix: "m", Value: "1"}, "")
		del.Ops = append(del.Ops, &PatchOp{
			Op:   OpDelete,
			Path: []PathSeg{FieldSeg("items", 0), ListIdxSeg(1)},
		})
		emDel, err := EmitPatch(del, nil)
		if err != nil {
			t.Fatalf("EmitPatch del: %v", err)
		}
		pDel, err := ParsePatch(emDel, nil)
		if err != nil {
			t.Fatalf("ParsePatch del: %v", err)
		}
		afterDel, err := ApplyPatch(base, pDel)
		if err != nil {
			t.Fatalf("ApplyPatch del: %v", err)
		}
		wantDel := Struct("M", FieldVal("items", List(Str("a"), Str("c"))))
		if !patchEqual(afterDel, wantDel) {
			t.Fatalf("after delete: got %s, want %s", Emit(afterDel), Emit(wantDel))
		}

		// Insert "B" at index 1.
		ins := NewPatch(RefID{Prefix: "m", Value: "1"}, "")
		ins.Ops = append(ins.Ops, &PatchOp{
			Op:    OpAppend,
			Path:  []PathSeg{FieldSeg("items", 0), ListIdxSeg(1)},
			Value: Str("B"),
		})
		emIns, err := EmitPatch(ins, nil)
		if err != nil {
			t.Fatalf("EmitPatch ins: %v", err)
		}
		pIns, err := ParsePatch(emIns, nil)
		if err != nil {
			t.Fatalf("ParsePatch ins: %v", err)
		}
		afterIns, err := ApplyPatch(afterDel, pIns)
		if err != nil {
			t.Fatalf("ApplyPatch ins: %v", err)
		}
		wantIns := Struct("M", FieldVal("items", List(Str("a"), Str("B"), Str("c"))))
		if !patchEqual(afterIns, wantIns) {
			t.Errorf("after insert: got %s, want %s", Emit(afterIns), Emit(wantIns))
		}
	})

	t.Run("fid-paths", func(t *testing.T) {
		// Subcase 8: FID paths require ApplyPatchWithSchema.
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
		// FID 2 = status, FID 3 = home, FID 3.FID3 = home.score
		patch.SetWithSegs([]PathSeg{{Kind: PathSegField, FID: 2}}, Str("live"))
		patch.SetWithSegs([]PathSeg{{Kind: PathSegField, FID: 3}, {Kind: PathSegField, FID: 3}}, Int(2))

		emitted, err := EmitPatchWithOptions(patch, PatchOptions{Schema: schema, KeyMode: KeyModeFID, SortOps: true})
		if err != nil {
			t.Fatalf("EmitPatch: %v", err)
		}
		parsed, err := ParsePatch(emitted, schema)
		if err != nil {
			t.Fatalf("ParsePatch: %v\n%s", err, emitted)
		}
		// Plain ApplyPatch must refuse unresolved FIDs.
		if _, err := ApplyPatch(base, parsed); err == nil {
			t.Error("expected ApplyPatch to refuse unresolved FID path")
		}
		// ApplyPatchWithSchema must succeed.
		result, err := ApplyPatchWithSchema(base, parsed, schema)
		if err != nil {
			t.Fatalf("ApplyPatchWithSchema: %v\n%s", err, emitted)
		}
		if s := result.Get("status"); s == nil || s.strVal != "live" {
			t.Errorf("expected status=live, got %v", s)
		}
		score := result.Get("home").Get("score")
		if score == nil || score.intVal != 2 {
			t.Errorf("expected home.score=2, got %v", score)
		}
	})

	t.Run("int-delta-no-truncation", func(t *testing.T) {
		// Subcase 9a: integer delta applies cleanly.
		base := Struct("M", FieldVal("n", Int(10)))
		patch := NewPatch(RefID{}, "")
		patch.Ops = append(patch.Ops, &PatchOp{
			Op:    OpDelta,
			Path:  []PathSeg{FieldSeg("n", 0)},
			Value: Int(5),
		})
		emitted, err := EmitPatch(patch, nil)
		if err != nil {
			t.Fatalf("EmitPatch: %v", err)
		}
		parsed, err := ParsePatch(emitted, nil)
		if err != nil {
			t.Fatalf("ParsePatch: %v", err)
		}
		result, err := ApplyPatch(base, parsed)
		if err != nil {
			t.Fatalf("ApplyPatch: %v", err)
		}
		if result.Get("n").intVal != 15 {
			t.Errorf("expected n=15, got %d", result.Get("n").intVal)
		}

		// Subcase 9b: fractional float delta on int field is rejected.
		patch2 := NewPatch(RefID{}, "")
		patch2.Ops = append(patch2.Ops, &PatchOp{
			Op:    OpDelta,
			Path:  []PathSeg{FieldSeg("n", 0)},
			Value: Float(1.5),
		})
		if _, err := ApplyPatch(base, patch2); err == nil {
			t.Error("expected error for float delta 1.5 on int field")
		}
	})

	t.Run("base-fingerprint-verify", func(t *testing.T) {
		// Subcase 10: VerifyPatchBase API.
		base := Struct("M", FieldVal("x", Int(1)))
		pb := NewPatchBuilder(RefID{}).WithBaseValue(base)
		pb.Set("x", Int(2))
		patch := pb.Build()

		// Matching base: must return nil.
		if err := VerifyPatchBase(base, patch); err != nil {
			t.Errorf("VerifyPatchBase on matching base: %v", err)
		}

		// Mutated base: must return FingerprintMismatch.
		other := Struct("M", FieldVal("x", Int(99)))
		err := VerifyPatchBase(other, patch)
		if err == nil {
			t.Error("expected FingerprintMismatch for mismatched base, got nil")
		}
		if _, ok := err.(*FingerprintMismatch); !ok {
			t.Errorf("expected *FingerprintMismatch, got %T: %v", err, err)
		}

		// No fingerprint: must return nil regardless.
		bare := NewPatch(RefID{}, "")
		bare.Ops = append(bare.Ops, &PatchOp{Op: OpSet, Path: []PathSeg{FieldSeg("x", 0)}, Value: Int(2)})
		if err := VerifyPatchBase(base, bare); err != nil {
			t.Errorf("VerifyPatchBase with no fingerprint: %v", err)
		}
	})

	t.Run("apply-enforces-base-by-default", func(t *testing.T) {
		// Subcase 11: ApplyPatch itself must verify a recorded base fingerprint
		// (not just VerifyPatchBase, which callers had to remember to invoke
		// separately) and must fail loudly, without applying any operation, on
		// a stale base.
		base := Struct("M", FieldVal("x", Int(1)))
		pb := NewPatchBuilder(RefID{}).WithBaseValue(base)
		pb.Set("x", Int(2))
		patch := pb.Build()

		// Matching base: applies normally.
		result, err := ApplyPatch(base, patch)
		if err != nil {
			t.Fatalf("ApplyPatch on matching base: %v", err)
		}
		if result.Get("x").intVal != 2 {
			t.Errorf("expected x=2, got %d", result.Get("x").intVal)
		}

		// Stale/mutated base: ApplyPatch must reject before applying, with a
		// typed *PatchBaseMismatch (alias of *FingerprintMismatch).
		stale := Struct("M", FieldVal("x", Int(99)))
		_, err = ApplyPatch(stale, patch)
		if err == nil {
			t.Fatal("expected ApplyPatch to reject a stale base, got nil error")
		}
		mismatch, ok := err.(*PatchBaseMismatch)
		if !ok {
			t.Fatalf("expected *PatchBaseMismatch, got %T: %v", err, err)
		}
		if mismatch.Want != patch.BaseFingerprint {
			t.Errorf("expected mismatch.Want = %q, got %q", patch.BaseFingerprint, mismatch.Want)
		}

		// The stale value itself must be untouched (ApplyPatch never mutates
		// its input, but this also guards against a check that runs too late).
		if stale.Get("x").intVal != 99 {
			t.Errorf("stale base was mutated: x = %d", stale.Get("x").intVal)
		}

		// No base fingerprint recorded: applies unconditionally, as before.
		bare := NewPatch(RefID{}, "")
		bare.Ops = append(bare.Ops, &PatchOp{Op: OpSet, Path: []PathSeg{FieldSeg("x", 0)}, Value: Int(3)})
		result, err = ApplyPatch(stale, bare)
		if err != nil {
			t.Fatalf("ApplyPatch with no base fingerprint: %v", err)
		}
		if result.Get("x").intVal != 3 {
			t.Errorf("expected x=3, got %d", result.Get("x").intVal)
		}
	})

	t.Run("apply-unchecked-skips-base-verification", func(t *testing.T) {
		// Subcase 12: ApplyPatchUnchecked is the explicit opt-out — it must
		// apply successfully even against a base that does not match the
		// patch's recorded fingerprint.
		base := Struct("M", FieldVal("x", Int(1)))
		pb := NewPatchBuilder(RefID{}).WithBaseValue(base)
		pb.Set("x", Int(2))
		patch := pb.Build()

		stale := Struct("M", FieldVal("x", Int(99)))

		// Sanity: the checked path rejects this combination.
		if _, err := ApplyPatch(stale, patch); err == nil {
			t.Fatal("expected ApplyPatch to reject stale base (sanity check)")
		}

		// ApplyPatchUnchecked applies regardless.
		result, err := ApplyPatchUnchecked(stale, patch)
		if err != nil {
			t.Fatalf("ApplyPatchUnchecked: %v", err)
		}
		if result.Get("x").intVal != 2 {
			t.Errorf("expected x=2, got %d", result.Get("x").intVal)
		}
	})
}

// TestDiffEmitCrossLanguageGolden pins the exact bytes Diff+EmitPatch produce
// for a fixed from/to pair. Go is the reference implementation for this
// string: the Python (py/tests/test_patch.py TestDiffEmitCrossLanguageGolden)
// and JS (js/src/glyph.test.ts) ports assert the identical literal, so this
// test fails loudly if Go's own output ever drifts out from under them.
func TestDiffEmitCrossLanguageGolden(t *testing.T) {
	from := Struct("M",
		FieldVal("count", Int(10)),
		FieldVal("label", Str("old")),
		FieldVal("rate", Float(1.5)),
		FieldVal("active", Bool(false)),
	)
	to := Struct("M",
		FieldVal("count", Int(42)),
		FieldVal("label", Str("new")),
		FieldVal("rate", Float(1.5)),
		FieldVal("extra", Str("added")),
	)

	patch := Diff(from, to, "M")
	patch.Target = RefID{Prefix: "m", Value: "123"}

	got, err := EmitPatch(patch, nil)
	if err != nil {
		t.Fatalf("EmitPatch: %v", err)
	}

	want := "@patch @keys=wire @target=m:123 @base=4f9708ac7bbe01e1\n" +
		"- active\n" +
		"= count 42\n" +
		"= extra added\n" +
		"= label new\n" +
		"@end"

	if got != want {
		t.Errorf("cross-language golden mismatch\nwant:\n%s\ngot:\n%s", want, got)
	}
}
