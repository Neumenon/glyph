// Command gauntletrunner is the Go scenario runner for the GLYPH cross-language
// gauntlet. It reads the shared inputs.json, runs every scenario applicable to
// the Go implementation, and prints a single JSON evidence object to stdout.
//
// It does NOT decide pass/fail — the orchestrator (gauntlet/scenarios/gauntlet.py)
// is the single evaluator, applied identically to every language.
//
// It lives inside the Go module (rather than under gauntlet/) so the local
// github.com/Neumenon/glyph/{glyph,stream} packages resolve without a separate
// module + replace directive.
//
// Applicable scenarios: S1, S2, S3, S4, S5, S6, S7.
// (S8 / streaming firewall is Py+JS in this gauntlet.)
//
// Usage:  go run ./cmd/gauntletrunner <inputs.json>
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"runtime"

	"github.com/Neumenon/glyph/glyph"
	"github.com/Neumenon/glyph/stream"
)

type result struct {
	OK       bool        `json:"ok"`
	Evidence interface{} `json:"evidence,omitempty"`
	Error    string      `json:"error,omitempty"`
}

func run(fn func() (interface{}, error)) (res result) {
	defer func() {
		if r := recover(); r != nil {
			res = result{OK: false, Error: fmt.Sprintf("panic: %v", r)}
		}
	}()
	ev, err := fn()
	if err != nil {
		return result{OK: false, Error: err.Error()}
	}
	return result{OK: true, Evidence: ev}
}

func toJSONValue(gv *glyph.GValue) interface{} {
	jb, err := glyph.ToJSONLoose(gv)
	if err != nil {
		panic(err)
	}
	var v interface{}
	if err := json.Unmarshal(jb, &v); err != nil {
		panic(err)
	}
	return v
}

func compactLen(raw json.RawMessage) int {
	var buf bytes.Buffer
	if err := json.Compact(&buf, raw); err != nil {
		panic(err)
	}
	return buf.Len()
}

func main() {
	path := "inputs.json"
	if len(os.Args) > 1 {
		path = os.Args[1]
	}
	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var root map[string]json.RawMessage
	if err := json.Unmarshal(data, &root); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	scen := map[string]result{}

	// ── S1 ────────────────────────────────────────────────────────────────
	scen["S1"] = run(func() (interface{}, error) {
		var d struct {
			Snapshot json.RawMessage `json:"snapshot"`
		}
		json.Unmarshal(root["S1_json_bridge"], &d)
		gv, err := glyph.FromJSONLoose(d.Snapshot)
		if err != nil {
			return nil, err
		}
		jb, err := glyph.ToJSONLoose(gv)
		if err != nil {
			return nil, err
		}
		eq, _ := glyph.JSONEqual(d.Snapshot, jb)
		var rt interface{}
		json.Unmarshal(jb, &rt)
		return map[string]interface{}{"roundtrip": rt, "equals_input": eq}, nil
	})

	// ── S2 ────────────────────────────────────────────────────────────────
	scen["S2"] = run(func() (interface{}, error) {
		var d struct {
			Variants   []json.RawMessage `json:"variants"`
			FloatsText []string          `json:"floats_text"`
		}
		json.Unmarshal(root["S2_canonical"], &d)
		canons := make([]string, len(d.Variants))
		for i, v := range d.Variants {
			gv, err := glyph.FromJSONLoose(v)
			if err != nil {
				return nil, err
			}
			canons[i] = glyph.CanonicalizeLoose(gv)
		}
		consistent := true
		for _, c := range canons {
			if c != canons[0] {
				consistent = false
			}
		}
		floats := map[string]string{}
		for _, t := range d.FloatsText {
			gv, err := glyph.ParseDocument(t)
			if err != nil {
				return nil, fmt.Errorf("parse float %q: %w", t, err)
			}
			floats[t] = glyph.CanonicalizeLoose(gv)
		}
		return map[string]interface{}{
			"canonical":           canons[0],
			"variants_consistent": consistent,
			"floats":              floats,
		}, nil
	})

	// ── S3 ────────────────────────────────────────────────────────────────
	scen["S3"] = run(func() (interface{}, error) {
		var d struct {
			Base    json.RawMessage `json:"base"`
			Equiv   json.RawMessage `json:"equiv"`
			Mutated json.RawMessage `json:"mutated"`
		}
		json.Unmarshal(root["S3_fingerprint"], &d)
		fp := func(raw json.RawMessage) (string, error) {
			gv, err := glyph.FromJSONLoose(raw)
			if err != nil {
				return "", err
			}
			return glyph.FingerprintLoose(gv), nil
		}
		fb, err := fp(d.Base)
		if err != nil {
			return nil, err
		}
		fe, err := fp(d.Equiv)
		if err != nil {
			return nil, err
		}
		fm, err := fp(d.Mutated)
		if err != nil {
			return nil, err
		}
		return map[string]interface{}{"fp_base": fb, "fp_equiv": fe, "fp_mutated": fm}, nil
	})

	// ── S4 ────────────────────────────────────────────────────────────────
	scen["S4"] = run(func() (interface{}, error) {
		var d struct {
			Trace json.RawMessage `json:"trace"`
		}
		json.Unmarshal(root["S4_tabular"], &d)
		gv, err := glyph.FromJSONLoose(d.Trace)
		if err != nil {
			return nil, err
		}
		tab := glyph.CanonicalizeLoose(gv)
		lst := glyph.CanonicalizeLooseNoTabular(gv)
		recovered, err := glyph.ParseDocument(tab)
		if err != nil {
			return nil, fmt.Errorf("parse tabular: %w", err)
		}
		return map[string]interface{}{
			"is_tabular":    bytes.Contains([]byte(tab), []byte("@tab")),
			"canonical_tab": tab,
			"bytes_json":    compactLen(d.Trace),
			"bytes_list":    len(lst),
			"bytes_tab":     len(tab),
			"roundtrip_ok":  glyph.EqualLoose(gv, recovered),
			"fp_recovered":  glyph.FingerprintLoose(recovered),
		}, nil
	})

	// ── S5 ────────────────────────────────────────────────────────────────
	scen["S5"] = run(func() (interface{}, error) {
		var d struct {
			Base      json.RawMessage `json:"base"`
			PatchText string          `json:"patch_text"`
		}
		json.Unmarshal(root["S5_patch_apply"], &d)
		base, err := glyph.FromJSONLoose(d.Base)
		if err != nil {
			return nil, err
		}
		before, _ := glyph.ToJSONLoose(base)
		p, err := glyph.ParsePatch(d.PatchText, nil)
		if err != nil {
			return nil, fmt.Errorf("parse patch: %w", err)
		}
		out, err := glyph.ApplyPatch(base, p)
		if err != nil {
			return nil, fmt.Errorf("apply patch: %w", err)
		}
		after, _ := glyph.ToJSONLoose(base)
		unchanged, _ := glyph.JSONEqual(before, after)
		return map[string]interface{}{
			"result":         toJSONValue(out),
			"fp_result":      glyph.FingerprintLoose(out),
			"base_unchanged": unchanged,
		}, nil
	})

	// ── S6 ────────────────────────────────────────────────────────────────
	scen["S6"] = run(func() (interface{}, error) {
		var d struct {
			State        json.RawMessage `json:"state"`
			PatchOpLines []string        `json:"patch_op_lines"`
			Target       string          `json:"target"`
			StaleBase    string          `json:"stale_base"`
		}
		json.Unmarshal(root["S6_patch_base"], &d)
		state, err := glyph.FromJSONLoose(d.State)
		if err != nil {
			return nil, err
		}
		base16 := glyph.NewPatchBuilder(glyph.RefID{}).WithBaseValue(state).Build().BaseFingerprint
		ops := ""
		for _, l := range d.PatchOpLines {
			ops += l + "\n"
		}
		happy, err := glyph.ParsePatch(fmt.Sprintf("@patch @base=%s @target=%s\n%s@end", base16, d.Target, ops), nil)
		if err != nil {
			return nil, err
		}
		stale, err := glyph.ParsePatch(fmt.Sprintf("@patch @base=%s @target=%s\n%s@end", d.StaleBase, d.Target, ops), nil)
		if err != nil {
			return nil, err
		}
		return map[string]interface{}{
			"base16":        base16,
			"verify_accept": glyph.VerifyPatchBase(state, happy) == nil,
			"verify_reject": glyph.VerifyPatchBase(state, stale) != nil,
		}, nil
	})

	// ── S7 ────────────────────────────────────────────────────────────────
	scen["S7"] = run(func() (interface{}, error) {
		var d struct {
			SID    uint64 `json:"sid"`
			Frames []struct {
				Kind    string `json:"kind"`
				Seq     uint64 `json:"seq"`
				Payload string `json:"payload"`
				Final   bool   `json:"final"`
			} `json:"frames"`
			BaseState        json.RawMessage `json:"base_state"`
			BasePatchPayload string          `json:"base_patch_payload"`
		}
		json.Unmarshal(root["S7_gs1_stream"], &d)

		var buf bytes.Buffer
		w := stream.NewWriter(&buf)
		for _, f := range d.Frames {
			kind, ok := stream.ParseKind(f.Kind)
			if !ok {
				return nil, fmt.Errorf("bad kind %q", f.Kind)
			}
			if err := w.WriteFrame(&stream.Frame{
				Version: 1, SID: d.SID, Seq: f.Seq, Kind: kind,
				Payload: []byte(f.Payload), Final: f.Final,
			}); err != nil {
				return nil, err
			}
		}
		streamBytes := buf.Bytes()
		sum := sha256.Sum256(streamBytes)

		r := stream.NewReader(bytes.NewReader(streamBytes))
		frames, err := r.ReadAll()
		if err != nil {
			return nil, fmt.Errorf("decode: %w", err)
		}
		kinds := make([]string, len(frames))
		seqs := make([]int, len(frames))
		payloadsOK := len(frames) == len(d.Frames)
		for i, fr := range frames {
			kinds[i] = fr.Kind.String()
			seqs[i] = int(fr.Seq)
			if payloadsOK && string(fr.Payload) != d.Frames[i].Payload {
				payloadsOK = false
			}
		}

		st, err := glyph.FromJSONLoose(d.BaseState)
		if err != nil {
			return nil, err
		}
		sc := stream.NewStreamCursor()
		sc.SetState(d.SID, st)
		correct := stream.StateHashLoose(st)
		acceptErr := sc.ProcessFrame(&stream.Frame{
			Version: 1, SID: d.SID, Seq: 1, Kind: stream.KindPatch,
			Payload: []byte(d.BasePatchPayload), Base: &correct,
		})
		var wrong [32]byte
		wrong[0] = 0xde
		rejectErr := sc.ProcessFrame(&stream.Frame{
			Version: 1, SID: d.SID, Seq: 2, Kind: stream.KindPatch,
			Payload: []byte(d.BasePatchPayload), Base: &wrong,
		})

		return map[string]interface{}{
			"stream_sha256": hex.EncodeToString(sum[:]),
			"stream_b64":    base64.StdEncoding.EncodeToString(streamBytes),
			"frame_count":   len(frames),
			"kinds":         kinds,
			"seqs":          seqs,
			"payloads_ok":   payloadsOK,
			"statehash_hex": stream.HashToHex(correct),
			"base_accept":   acceptErr == nil,
			"base_reject":   rejectErr != nil,
		}, nil
	})

	out := map[string]interface{}{
		"lang":      "go",
		"version":   runtime.Version(),
		"scenarios": scen,
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(out); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
