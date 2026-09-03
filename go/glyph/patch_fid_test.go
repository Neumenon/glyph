package glyph

import (
	"strings"
	"testing"
)

// ============================================================
// FID Path Tests
// ============================================================

// makePatchTestSchema creates a schema for FID path testing.
func makePatchTestSchema() *Schema {
	return NewSchemaBuilder().
		AddPackedStruct("Match", "v2",
			Field("id", PrimitiveType("id"), WithFID(1), WithWireKey("m")),
			Field("status", PrimitiveType("str"), WithFID(2), WithWireKey("s")),
			Field("home", RefType("Team"), WithFID(3), WithWireKey("H")),
			Field("away", RefType("Team"), WithFID(4), WithWireKey("A")),
			Field("pred", RefType("Pred"), WithFID(5), WithWireKey("P"), WithOptional()),
			Field("events", ListType(PrimitiveType("str")), WithFID(6), WithWireKey("e"), WithOptional()),
		).
		AddPackedStruct("Team", "v2",
			Field("id", PrimitiveType("id"), WithFID(1), WithWireKey("t")),
			Field("name", PrimitiveType("str"), WithFID(2), WithWireKey("n")),
			Field("score", PrimitiveType("int"), WithFID(3), WithWireKey("sc"), WithOptional()),
		).
		AddPackedStruct("Pred", "v2",
			Field("ph", PrimitiveType("float"), WithFID(1)),
			Field("pd", PrimitiveType("float"), WithFID(2)),
			Field("pa", PrimitiveType("float"), WithFID(3)),
			Field("xh", PrimitiveType("float"), WithFID(4)),
			Field("xa", PrimitiveType("float"), WithFID(5)),
		).
		Build()
}

// Test 2: Decode FID paths
func TestDecodeFIDPaths(t *testing.T) {
	schema := makePatchTestSchema()

	// Parse a path like .#5.#4 (pred.xh in Match)
	path := parsePathToSegs("#5.#4")

	// Resolve FIDs to field names
	err := ResolvePathFIDs(path, "Match", schema)
	if err != nil {
		t.Fatalf("ResolvePathFIDs error: %v", err)
	}

	// Should resolve to pred.xh
	if len(path) != 2 {
		t.Fatalf("Expected 2 segments, got %d", len(path))
	}

	if path[0].Field != "pred" {
		t.Errorf("Expected path[0].Field = 'pred', got %q", path[0].Field)
	}
	if path[0].FID != 5 {
		t.Errorf("Expected path[0].FID = 5, got %d", path[0].FID)
	}

	if path[1].Field != "xh" {
		t.Errorf("Expected path[1].Field = 'xh', got %q", path[1].Field)
	}
	if path[1].FID != 4 {
		t.Errorf("Expected path[1].FID = 4, got %d", path[1].FID)
	}
}

// Test 3: Mixed decode (FID + name in same path)
func TestMixedFIDPaths(t *testing.T) {
	schema := makePatchTestSchema()

	// Parse mixed path: .#5.xh (FID for pred, name for xh)
	path := parsePathToSegs("#5.xh")

	err := ResolvePathFIDs(path, "Match", schema)
	if err != nil {
		t.Fatalf("ResolvePathFIDs error: %v", err)
	}

	// Both should be fully resolved
	if path[0].Field != "pred" || path[0].FID != 5 {
		t.Errorf("path[0] not resolved: %+v", path[0])
	}
	if path[1].Field != "xh" || path[1].FID != 4 {
		t.Errorf("path[1] not resolved: %+v", path[1])
	}

	// Now test the reverse: .P.#4 (wire key for pred, FID for xh)
	path2 := parsePathToSegs("P.#4")
	err = ResolvePathFIDs(path2, "Match", schema)
	if err != nil {
		t.Fatalf("ResolvePathFIDs (P.#4) error: %v", err)
	}

	if path2[0].Field != "pred" || path2[0].FID != 5 {
		t.Errorf("path2[0] not resolved: %+v", path2[0])
	}
	if path2[1].Field != "xh" || path2[1].FID != 4 {
		t.Errorf("path2[1] not resolved: %+v", path2[1])
	}
}

// Test 4: Unknown FID should error
func TestUnknownFIDError(t *testing.T) {
	schema := makePatchTestSchema()

	// Parse path with non-existent FID
	path := parsePathToSegs("#999")

	err := ResolvePathFIDs(path, "Match", schema)
	if err == nil {
		t.Error("Expected error for unknown FID #999, got nil")
	} else if !strings.Contains(err.Error(), "unknown field") {
		t.Errorf("Expected 'unknown field' error, got: %v", err)
	}
}

// Test 5: Rename safety - FID patches survive field renames
func TestFIDRenameSafety(t *testing.T) {
	// Create original schema
	schemaV1 := NewSchemaBuilder().
		AddPackedStruct("Team", "v1",
			Field("team_id", PrimitiveType("id"), WithFID(1)),
			Field("team_name", PrimitiveType("str"), WithFID(2)),
			Field("team_score", PrimitiveType("int"), WithFID(3)),
		).
		Build()

	// Create a patch using FIDs
	patch := NewPatch(RefID{Prefix: "t", Value: "ARS"}, schemaV1.Hash)
	patch.TargetType = "Team"
	patch.Ops = append(patch.Ops, &PatchOp{
		Op: OpSet,
		Path: []PathSeg{
			{Kind: PathSegField, Field: "team_score", FID: 3},
		},
		Value: Int(2),
	})

	// Create "renamed" schema - field names changed but FIDs same
	schemaV2 := NewSchemaBuilder().
		AddPackedStruct("Team", "v2",
			Field("id", PrimitiveType("id"), WithFID(1)),     // renamed from team_id
			Field("name", PrimitiveType("str"), WithFID(2)),  // renamed from team_name
			Field("score", PrimitiveType("int"), WithFID(3)), // renamed from team_score
		).
		Build()

	// The FID path should still resolve with new schema
	path := []PathSeg{{Kind: PathSegField, FID: 3}} // FID 3 = score in v2
	err := ResolvePathFIDs(path, "Team", schemaV2)
	if err != nil {
		t.Fatalf("ResolvePathFIDs error: %v", err)
	}

	// Should resolve to new name "score"
	if path[0].Field != "score" {
		t.Errorf("Expected field 'score', got %q", path[0].Field)
	}

	// Now apply the patch to a v2 struct
	team := Struct("Team",
		MapEntry{Key: "id", Value: ID("t", "ARS")},
		MapEntry{Key: "name", Value: Str("Arsenal")},
		MapEntry{Key: "score", Value: Int(0)},
	)

	// Update the patch's path to use resolved names for application
	patch.Ops[0].Path[0].Field = "score"

	result, err := ApplyPatch(team, patch)
	if err != nil {
		t.Fatalf("ApplyPatch error: %v", err)
	}

	score := result.Get("score")
	if score == nil || mustAsInt(t, score) != 2 {
		t.Errorf("Expected score = 2, got %v", score)
	}
}
