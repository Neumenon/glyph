package glyph

import (
	"strings"
	"testing"
)

// parse_patch_test.go: ParsePatch on the SPEC-CANON.md §7 wire form. The
// cases mirror py/tests/test_patch.py so the three implementations reject
// the same inputs.

func mustParsePatch(t *testing.T, input string) *Patch {
	t.Helper()
	p, err := ParsePatch(input)
	if err != nil {
		t.Fatalf("ParsePatch(%s): %v", input, err)
	}
	return p
}

func TestParsePatchHeader(t *testing.T) {
	p := mustParsePatch(t, `{"glyph_patch":1,"ops":[],"base":"abab","schema":"s1","target":"m:ARS-LIV","type":"Match"}`)
	if p.BaseFingerprint != "abab" || p.SchemaID != "s1" || p.TargetType != "Match" {
		t.Errorf("header fields: %+v", p)
	}
	if p.Target != (RefID{Prefix: "m", Value: "ARS-LIV"}) {
		t.Errorf("target: %v", p.Target)
	}
	if len(p.Ops) != 0 {
		t.Errorf("ops: want empty, got %d", len(p.Ops))
	}

	// target splits at the FIRST colon; no colon means value only.
	if p := mustParsePatch(t, `{"glyph_patch":1,"ops":[],"target":"a:b:c"}`); p.Target != (RefID{Prefix: "a", Value: "b:c"}) {
		t.Errorf("target a:b:c → %v", p.Target)
	}
	if p := mustParsePatch(t, `{"glyph_patch":1,"ops":[],"target":"solo"}`); p.Target != (RefID{Value: "solo"}) {
		t.Errorf("target solo → %v", p.Target)
	}
	// Any JSON spelling is accepted by the parser (canonical bytes are a
	// receiver concern).
	mustParsePatch(t, "{ \"ops\" : [ ] ,\n \"glyph_patch\" : 1 }")
}

func TestParsePatchOps(t *testing.T) {
	p := mustParsePatch(t, `{"glyph_patch":1,"ops":[
		{"op":"=","path":["home","score"],"value":2},
		{"op":"+","path":["events"],"value":"Goal","index":0},
		{"op":"+","path":["events"],"value":{"minute":90,"who":{"$id":["p","smith"]}}},
		{"op":"-","path":["odds"]},
		{"op":"~","path":["rating"],"value":-0.5},
		{"op":"~","path":["n"],"value":3},
		{"op":"=","path":["items",2,"name"],"value":null}
	]}`)
	if len(p.Ops) != 7 {
		t.Fatalf("ops: want 7, got %d", len(p.Ops))
	}
	set := p.Ops[0]
	if set.Op != OpSet || pathSegsStr(set.Path) != "home.score" || mustAsInt(t, set.Value) != 2 || set.Index != -1 {
		t.Errorf("set op: %+v", set)
	}
	ins := p.Ops[1]
	if ins.Op != OpAppend || ins.Index != 0 || mustAsStr(t, ins.Value) != "Goal" {
		t.Errorf("insert op: %+v", ins)
	}
	app := p.Ops[2]
	if app.Op != OpAppend || app.Index != -1 {
		t.Errorf("append op: %+v", app)
	}
	if who := app.Value.Get("who"); who == nil || who.Type() != TypeID || who.idVal != (RefID{Prefix: "p", Value: "smith"}) {
		t.Errorf("append value $id not decoded: %v", who)
	}
	del := p.Ops[3]
	if del.Op != OpDelete || del.Value != nil {
		t.Errorf("delete op: %+v", del)
	}
	if d := p.Ops[4]; d.Op != OpDelta || mustAsFloat(t, d.Value) != -0.5 {
		t.Errorf("delta op: %+v", d)
	}
	if d := p.Ops[5]; d.Op != OpDelta || mustAsFloat(t, d.Value) != 3 {
		t.Errorf("integral delta op: %+v", d)
	}
	path := p.Ops[6].Path
	if len(path) != 3 || path[0].Kind != PathSegField || path[1].Kind != PathSegListIdx || path[1].ListIdx != 2 || path[2].Field != "name" {
		t.Errorf("mixed path: %+v", path)
	}
	if !p.Ops[6].Value.IsNull() {
		t.Errorf("null value: %v", p.Ops[6].Value)
	}
}

func TestParsePatchRejects(t *testing.T) {
	cases := []struct{ name, input string }{
		{"not json", `not json`},
		{"empty", ``},
		{"array root", `[]`},
		{"string root", `"x"`},
		{"trailing garbage", `{"glyph_patch":1,"ops":[]} x`},
		{"missing glyph_patch", `{"ops":[]}`},
		{"glyph_patch 2", `{"glyph_patch":2,"ops":[]}`},
		{"glyph_patch true", `{"glyph_patch":true,"ops":[]}`},
		{"glyph_patch string", `{"glyph_patch":"1","ops":[]}`},
		{"glyph_patch float", `{"glyph_patch":1.0,"ops":[]}`},
		{"missing ops", `{"glyph_patch":1}`},
		{"ops null", `{"glyph_patch":1,"ops":null}`},
		{"ops object", `{"glyph_patch":1,"ops":{}}`},
		{"extra header key", `{"glyph_patch":1,"ops":[],"extra":1}`},
		{"base not string", `{"glyph_patch":1,"ops":[],"base":7}`},
		{"schema not string", `{"glyph_patch":1,"ops":[],"schema":null}`},
		{"target not string", `{"glyph_patch":1,"ops":[],"target":["m","1"]}`},
		{"type not string", `{"glyph_patch":1,"ops":[],"type":1}`},
		{"op not object", `{"glyph_patch":1,"ops":[1]}`},
		{"op unknown", `{"glyph_patch":1,"ops":[{"op":"?","path":["a"],"value":1}]}`},
		{"op missing", `{"glyph_patch":1,"ops":[{"path":["a"],"value":1}]}`},
		{"op not string", `{"glyph_patch":1,"ops":[{"op":1,"path":["a"],"value":1}]}`},
		{"path missing", `{"glyph_patch":1,"ops":[{"op":"=","value":1}]}`},
		{"path string", `{"glyph_patch":1,"ops":[{"op":"=","path":"a","value":1}]}`},
		{"seg negative", `{"glyph_patch":1,"ops":[{"op":"=","path":[-1],"value":1}]}`},
		{"seg float", `{"glyph_patch":1,"ops":[{"op":"=","path":[1.5],"value":1}]}`},
		{"seg bool", `{"glyph_patch":1,"ops":[{"op":"=","path":[true],"value":1}]}`},
		{"seg null", `{"glyph_patch":1,"ops":[{"op":"=","path":[null],"value":1}]}`},
		{"seg array", `{"glyph_patch":1,"ops":[{"op":"=","path":[["x"]],"value":1}]}`},
		{"set missing value", `{"glyph_patch":1,"ops":[{"op":"=","path":["a"]}]}`},
		{"append missing value", `{"glyph_patch":1,"ops":[{"op":"+","path":["a"]}]}`},
		{"delta missing value", `{"glyph_patch":1,"ops":[{"op":"~","path":["a"]}]}`},
		{"delete with value", `{"glyph_patch":1,"ops":[{"op":"-","path":["a"],"value":1}]}`},
		{"delta string", `{"glyph_patch":1,"ops":[{"op":"~","path":["a"],"value":"1"}]}`},
		{"delta bool", `{"glyph_patch":1,"ops":[{"op":"~","path":["a"],"value":true}]}`},
		{"delta null", `{"glyph_patch":1,"ops":[{"op":"~","path":["a"],"value":null}]}`},
		{"index on set", `{"glyph_patch":1,"ops":[{"op":"=","path":["a"],"value":1,"index":0}]}`},
		{"index on delete", `{"glyph_patch":1,"ops":[{"op":"-","path":["a"],"index":0}]}`},
		{"index negative", `{"glyph_patch":1,"ops":[{"op":"+","path":["a"],"value":1,"index":-1}]}`},
		{"index string", `{"glyph_patch":1,"ops":[{"op":"+","path":["a"],"value":1,"index":"abc"}]}`},
		{"index float", `{"glyph_patch":1,"ops":[{"op":"+","path":["a"],"value":1,"index":1.5}]}`},
		{"extra op key", `{"glyph_patch":1,"ops":[{"op":"=","path":["a"],"value":1,"extra":1}]}`},
		{"malformed $bytes", `{"glyph_patch":1,"ops":[{"op":"=","path":["a"],"value":{"$bytes":"!!"}}]}`},
		{"malformed $id", `{"glyph_patch":1,"ops":[{"op":"=","path":["a"],"value":{"$id":["p"]}}]}`},
		{"malformed $time", `{"glyph_patch":1,"ops":[{"op":"=","path":["a"],"value":{"$time":"yesterday"}}]}`},
	}
	for _, tc := range cases {
		if _, err := ParsePatch(tc.input); err == nil {
			t.Errorf("%s: expected error for %s", tc.name, tc.input)
		}
	}
}

// TestParsePatchRoundTripStable: parse(emit(parse(x))) emits the same bytes,
// and a non-canonical spelling canonicalizes on re-emit.
func TestParsePatchRoundTripStable(t *testing.T) {
	loose := `{ "ops": [ {"value": 2.0, "path": ["n"], "op": "~"}, {"op":"=", "path":["a"], "value": {"z":1, "y":[1.0, "x"]}} ], "glyph_patch": 1, "target": "m:1" }`
	first, err := EmitPatch(mustParsePatch(t, loose))
	if err != nil {
		t.Fatalf("EmitPatch: %v", err)
	}
	want := `{"glyph_patch":1,"ops":[{"op":"=","path":["a"],"value":{"y":[1,"x"],"z":1}},{"op":"~","path":["n"],"value":2}],"target":"m:1"}`
	if first != want {
		t.Errorf("canonicalized\n got: %s\nwant: %s", first, want)
	}
	second, err := EmitPatch(mustParsePatch(t, first))
	if err != nil {
		t.Fatalf("EmitPatch: %v", err)
	}
	if second != first {
		t.Errorf("unstable re-emit\n1: %s\n2: %s", first, second)
	}
}

// TestParsePatchMapKeyAndFieldOneKind: the wire has one string segment kind,
// so a MapKeySeg emitted by Diff and a FieldSeg spelled by hand parse to the
// same bytes and both apply to a map.
func TestParsePatchMapKeyAndFieldOneKind(t *testing.T) {
	base := Map(MapEntry{Key: "cfg", Value: Map(MapEntry{Key: "odd key", Value: Int(1)})})
	next := Map(MapEntry{Key: "cfg", Value: Map(MapEntry{Key: "odd key", Value: Int(2)})})
	diff := mustDiff(base, next, "")
	diff.BaseFingerprint = "" // compare ops only
	viaDiff, err := EmitPatch(diff)
	if err != nil {
		t.Fatalf("EmitPatch: %v", err)
	}
	hand := NewPatch(RefID{}, "")
	hand.Ops = []*PatchOp{{Op: OpSet, Path: []PathSeg{FieldSeg("cfg", 0), FieldSeg("odd key", 0)}, Value: Int(2)}}
	viaHand, err := EmitPatch(hand)
	if err != nil {
		t.Fatalf("EmitPatch: %v", err)
	}
	if viaDiff != viaHand {
		t.Errorf("map key vs field differ on the wire\n diff: %s\n hand: %s", viaDiff, viaHand)
	}
	got, err := ApplyPatch(base, mustParsePatch(t, viaDiff))
	if err != nil {
		t.Fatalf("ApplyPatch: %v", err)
	}
	if !patchEqual(got, next) {
		t.Errorf("apply: got %s want %s", Emit(got), Emit(next))
	}
}

func TestParsePatchErrorMentionsOpIndex(t *testing.T) {
	_, err := ParsePatch(`{"glyph_patch":1,"ops":[{"op":"=","path":["a"],"value":1},{"op":"-","path":["b"],"value":1}]}`)
	if err == nil || !strings.Contains(err.Error(), "ops[1]") {
		t.Errorf("expected ops[1] in error, got %v", err)
	}
}
