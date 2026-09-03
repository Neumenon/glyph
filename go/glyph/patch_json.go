package glyph

import (
	"bytes"
	"encoding/json"
	"fmt"
	"sort"
)

// ============================================================
// Patch wire form (SPEC-CANON.md §7)
// ============================================================
//
//	{"glyph_patch":1,"ops":[op,…],"base":"<64 hex>"?,"target":"prefix:value"?,
//	 "schema":"<id>"?,"type":"<TypeName>"?}
//	op  := {"op":"="|"+"|"-"|"~","path":[seg,…],"value":<v>?,"index":<n>?}
//	seg := <string> (struct field or map key) | <integer ≥ 0> (list index)
//
// EmitPatch produces canonical JSON bytes (CanonJSON) with ops sorted by
// (canon_json(path), op); ParsePatch accepts any JSON spelling.

// PatchWireVersion is the only accepted value of the "glyph_patch" key.
const PatchWireVersion = 1

// EmitPatch encodes p as canonical JSON (SPEC-CANON.md §7).
func EmitPatch(p *Patch) (string, error) {
	if p == nil {
		return "", fmt.Errorf("glyph: nil patch")
	}
	type keyed struct {
		key []byte
		gv  *GValue
	}
	ops := make([]keyed, 0, len(p.Ops))
	for _, op := range p.Ops {
		gv, err := opGV(op)
		if err != nil {
			return "", err
		}
		key, err := CanonJSON(pathGV(op.Path))
		if err != nil {
			return "", err
		}
		ops = append(ops, keyed{key, gv})
	}
	sort.SliceStable(ops, func(i, j int) bool {
		if c := bytes.Compare(ops[i].key, ops[j].key); c != 0 {
			return c < 0
		}
		return ops[i].gv.Get("op").strVal < ops[j].gv.Get("op").strVal
	})
	opVals := make([]*GValue, len(ops))
	for i, k := range ops {
		opVals[i] = k.gv
	}

	entries := []MapEntry{
		{Key: "glyph_patch", Value: Int(PatchWireVersion)},
		{Key: "ops", Value: List(opVals...)},
	}
	if p.BaseFingerprint != "" {
		entries = append(entries, MapEntry{Key: "base", Value: Str(p.BaseFingerprint)})
	}
	if p.SchemaID != "" {
		entries = append(entries, MapEntry{Key: "schema", Value: Str(p.SchemaID)})
	}
	if target := p.Target.String()[1:]; target != "" {
		entries = append(entries, MapEntry{Key: "target", Value: Str(target)})
	}
	if p.TargetType != "" {
		entries = append(entries, MapEntry{Key: "type", Value: Str(p.TargetType)})
	}
	out, err := CanonJSON(Map(entries...))
	if err != nil {
		return "", err
	}
	return string(out), nil
}

func pathGV(path []PathSeg) *GValue {
	segs := make([]*GValue, len(path))
	for i, s := range path {
		switch s.Kind {
		case PathSegListIdx:
			segs[i] = Int(int64(s.ListIdx))
		case PathSegMapKey:
			segs[i] = Str(s.MapKey)
		default:
			segs[i] = Str(s.Field)
		}
	}
	return List(segs...)
}

func opGV(op *PatchOp) (*GValue, error) {
	for _, s := range op.Path {
		if s.Kind == PathSegField && s.Field == "" && s.FID > 0 {
			return nil, fmt.Errorf("glyph: patch path has unresolved FID #%d; call ResolveFIDs first", s.FID)
		}
	}
	entries := []MapEntry{
		{Key: "op", Value: Str(string(op.Op))},
		{Key: "path", Value: pathGV(op.Path)},
	}
	switch op.Op {
	case OpDelete:
	case OpDelta:
		if op.Value == nil || !op.Value.IsNumeric() {
			return nil, fmt.Errorf("glyph: delta op at %s requires a numeric value", pathSegsStr(op.Path))
		}
		entries = append(entries, MapEntry{Key: "value", Value: op.Value})
	case OpSet, OpAppend:
		v := op.Value
		if v == nil {
			v = Null()
		}
		entries = append(entries, MapEntry{Key: "value", Value: v})
		if op.Op == OpAppend && op.Index >= 0 {
			entries = append(entries, MapEntry{Key: "index", Value: Int(int64(op.Index))})
		}
	default:
		return nil, fmt.Errorf("glyph: unknown patch op %q", string(op.Op))
	}
	return Map(entries...), nil
}

// ParsePatch decodes the SPEC-CANON.md §7 wire form. It accepts any JSON
// spelling; canonical bytes are enforced by receivers (IsCanonical).
// Path strings become FieldSeg (FID unresolved); call ResolveFIDs or
// ApplyPatchWithSchema when FIDs matter.
func ParsePatch(input string) (*Patch, error) {
	raw := []byte(input)
	if jsonKind(raw) != '{' {
		return nil, fmt.Errorf("glyph: patch must be a JSON object")
	}
	var top map[string]json.RawMessage
	if err := json.Unmarshal(raw, &top); err != nil {
		return nil, fmt.Errorf("glyph: patch: %w", err)
	}
	for k := range top {
		switch k {
		case "glyph_patch", "ops", "base", "schema", "target", "type":
		default:
			return nil, fmt.Errorf("glyph: patch: unknown key %q", k)
		}
	}
	ver, ok := top["glyph_patch"]
	if !ok {
		return nil, fmt.Errorf("glyph: patch: missing glyph_patch")
	}
	if n, err := jsonInt(ver); err != nil || n != PatchWireVersion {
		return nil, fmt.Errorf("glyph: patch: glyph_patch must be %d", PatchWireVersion)
	}
	opsRaw, ok := top["ops"]
	if !ok || jsonKind(opsRaw) != '[' {
		return nil, fmt.Errorf("glyph: patch: ops must be an array")
	}
	var opsList []json.RawMessage
	if err := json.Unmarshal(opsRaw, &opsList); err != nil {
		return nil, fmt.Errorf("glyph: patch: ops: %w", err)
	}

	p := &Patch{}
	str := func(key string) (string, error) {
		r, ok := top[key]
		if !ok {
			return "", nil
		}
		var s string
		if jsonKind(r) != '"' || json.Unmarshal(r, &s) != nil {
			return "", fmt.Errorf("glyph: patch: %s must be a string", key)
		}
		return s, nil
	}
	var err error
	if p.BaseFingerprint, err = str("base"); err != nil {
		return nil, err
	}
	if p.SchemaID, err = str("schema"); err != nil {
		return nil, err
	}
	target, err := str("target")
	if err != nil {
		return nil, err
	}
	p.Target = parseRefIDFromTarget(target)
	if p.TargetType, err = str("type"); err != nil {
		return nil, err
	}

	p.Ops = make([]*PatchOp, 0, len(opsList))
	for i, r := range opsList {
		op, err := parseWireOp(r)
		if err != nil {
			return nil, fmt.Errorf("glyph: patch: ops[%d]: %w", i, err)
		}
		p.Ops = append(p.Ops, op)
	}
	return p, nil
}

func parseWireOp(raw json.RawMessage) (*PatchOp, error) {
	if jsonKind(raw) != '{' {
		return nil, fmt.Errorf("op must be an object")
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(raw, &m); err != nil {
		return nil, err
	}
	for k := range m {
		switch k {
		case "op", "path", "value", "index":
		default:
			return nil, fmt.Errorf("unknown key %q", k)
		}
	}

	var opStr string
	if r, ok := m["op"]; !ok || jsonKind(r) != '"' || json.Unmarshal(r, &opStr) != nil {
		return nil, fmt.Errorf("op must be a string")
	}
	var kind PatchOpKind
	switch opStr {
	case "=":
		kind = OpSet
	case "+":
		kind = OpAppend
	case "-":
		kind = OpDelete
	case "~":
		kind = OpDelta
	default:
		return nil, fmt.Errorf("unknown op %q", opStr)
	}

	pathRaw, ok := m["path"]
	if !ok || jsonKind(pathRaw) != '[' {
		return nil, fmt.Errorf("path must be an array")
	}
	var segs []json.RawMessage
	if err := json.Unmarshal(pathRaw, &segs); err != nil {
		return nil, err
	}
	path := make([]PathSeg, len(segs))
	for i, s := range segs {
		if jsonKind(s) == '"' {
			var f string
			if err := json.Unmarshal(s, &f); err != nil {
				return nil, err
			}
			path[i] = FieldSeg(f, 0)
			continue
		}
		n, err := jsonInt(s)
		if err != nil || n < 0 {
			return nil, fmt.Errorf("path[%d] must be a string or non-negative integer", i)
		}
		path[i] = ListIdxSeg(int(n))
	}

	op := &PatchOp{Op: kind, Path: path, Index: -1}
	valRaw, hasVal := m["value"]
	switch kind {
	case OpDelete:
		if hasVal {
			return nil, fmt.Errorf("delete op must not have a value")
		}
	case OpDelta:
		if !hasVal {
			return nil, fmt.Errorf("delta op requires a value")
		}
		var f float64
		if k := jsonKind(valRaw); (k != '-' && (k < '0' || k > '9')) || json.Unmarshal(valRaw, &f) != nil {
			return nil, fmt.Errorf("delta value must be a number")
		}
		op.Value = Float(f)
	default:
		if !hasVal {
			return nil, fmt.Errorf("%s op requires a value", opStr)
		}
		v, err := FromJSONLoose(valRaw)
		if err != nil {
			return nil, fmt.Errorf("value: %w", err)
		}
		op.Value = v
	}
	if idxRaw, ok := m["index"]; ok {
		if kind != OpAppend {
			return nil, fmt.Errorf("index is only allowed on append")
		}
		n, err := jsonInt(idxRaw)
		if err != nil || n < 0 {
			return nil, fmt.Errorf("index must be a non-negative integer")
		}
		op.Index = int(n)
	}
	return op, nil
}

// jsonKind returns the first non-space byte of a JSON value (0 if empty).
func jsonKind(raw []byte) byte {
	raw = bytes.TrimSpace(raw)
	if len(raw) == 0 {
		return 0
	}
	return raw[0]
}

// jsonInt decodes an integer literal; strings, bools, null and "1.0" fail.
func jsonInt(raw []byte) (int64, error) {
	if k := jsonKind(raw); k != '-' && (k < '0' || k > '9') {
		return 0, fmt.Errorf("not an integer")
	}
	var n json.Number
	if err := json.Unmarshal(raw, &n); err != nil {
		return 0, err
	}
	return n.Int64()
}
