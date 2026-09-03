// Go subject runner — state identity harness.
// Same I/O contract as subjects/runner.py.
//
// Numbers are decoded with json.Number (UseNumber) so integers beyond float64
// survive parsing — matching Python's arbitrary-precision ints. This is a
// documented choice: the default encoding/json behavior (float64) would lose
// precision at parse time, which the harness reports separately as parse-layer
// divergence rather than canonicalization divergence.
package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"
	"strings"

	jsoncanonicalizer "github.com/cyberphone/json-canonicalization/go/src/webpki.org/jsoncanonicalizer"
	glyph "github.com/Neumenon/glyph/go/glyph"
)

type outRow struct {
	ID      string `json:"id"`
	Subject string `json:"subject"`
	Hash    string `json:"hash"`
	Error   *string `json:"error"`
}

func errRow(id, subject, msg string) outRow {
	return outRow{ID: id, Subject: subject, Hash: "", Error: &msg}
}

func sha(b []byte) string { return fmt.Sprintf("%x", sha256.Sum256(b)) }

func runFixture(id, raw string) []outRow {
	var v interface{}
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&v); err != nil {
		msg := fmt.Sprintf("parse: %v", err)
		return []outRow{
			errRow(id, "naive", msg), errRow(id, "minified", msg),
			errRow(id, "jcs", msg), errRow(id, "glyph", msg), errRow(id, "canon_json", msg),
		}
	}
	// Strictness parity with FromJSONLoose (json.Unmarshal rejects trailing
	// garbage): a second Decode must hit io.EOF, otherwise naive/minified
	// would hash a prefix while glyph/jcs refuse the whole input.
	trailing := false
	var extra interface{}
	if err := dec.Decode(&extra); err != io.EOF {
		trailing = true
	}

	rows := make([]outRow, 0, 5)

	// naive/minified: re-marshal (encoding/json sorts map keys; output is compact).
	if trailing {
		msg := "trailing data after top-level JSON value"
		rows = append(rows, errRow(id, "naive", msg), errRow(id, "minified", msg))
	} else if norm, err := json.Marshal(v); err != nil {
		msg := fmt.Sprintf("marshal: %v", err)
		rows = append(rows, errRow(id, "naive", msg), errRow(id, "minified", msg))
	} else {
		rows = append(rows,
			outRow{ID: id, Subject: "naive", Hash: sha(norm)},
			outRow{ID: id, Subject: "minified", Hash: sha(norm)})
	}

	// jcs: canonicalize the original bytes (the realistic usage path).
	if canon, cerr := jsoncanonicalizer.Transform([]byte(raw)); cerr != nil {
		msg := fmt.Sprintf("jcs: %v", cerr)
		rows = append(rows, errRow(id, "jcs", msg))
	} else {
		rows = append(rows, outRow{ID: id, Subject: "jcs", Hash: sha(canon)})
	}

	// glyph: bridge parses JSON bytes itself (float64-domain semantics by design).
	gv, gerr := glyph.FromJSONLoose([]byte(raw))
	if gerr != nil {
		msg := fmt.Sprintf("glyph: %v", gerr)
		return append(rows, errRow(id, "glyph", msg), errRow(id, "canon_json", msg))
	}
	if fp, ferr := glyph.Fingerprint(gv); ferr != nil {
		rows = append(rows, errRow(id, "glyph", fmt.Sprintf("glyph: %v", ferr)))
	} else {
		rows = append(rows, outRow{ID: id, Subject: "glyph", Hash: fp})
	}
	// canon_json: the canonical bytes themselves + the idempotence check (SPEC-CANON.md §7).
	if c, cerr := glyph.CanonJSON(gv); cerr != nil {
		rows = append(rows, errRow(id, "canon_json", fmt.Sprintf("canon: %v", cerr)))
	} else if !glyph.IsCanonical(c) {
		rows = append(rows, errRow(id, "canon_json", "idempotence: re-canonicalization differs"))
	} else {
		rows = append(rows, outRow{ID: id, Subject: "canon_json", Hash: sha(c)})
	}
	return rows
}

func selftest(vectorsDir string) int {
	entries, _ := os.ReadDir(vectorsDir)
	total, failures := 0, 0
	for _, e := range entries {
		name := e.Name()
		if !strings.HasSuffix(name, ".input.json") {
			continue
		}
		rawBytes, _ := os.ReadFile(filepath.Join(vectorsDir, name))
		expBytes, _ := os.ReadFile(filepath.Join(vectorsDir, strings.TrimSuffix(name, ".input.json")+".expected.json"))
		canon, err := jsoncanonicalizer.Transform(rawBytes)
		total++
		if err != nil || strings.TrimSpace(string(canon)) != strings.TrimSpace(string(expBytes)) {
			failures++
			fmt.Fprintf(os.Stderr, "JCS VECTOR FAIL: %s (%v)\n", name, err)
		}
	}
	fmt.Printf("go/json-canonicalization selftest: %d/%d vectors pass\n", total-failures, total)
	if failures > 0 {
		return 1
	}
	return 0
}

func gtextMode() int {
	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1024*1024), 32*1024*1024)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var fx struct {
			ID   string `json:"id"`
			Text string `json:"text"`
		}
		if err := json.Unmarshal([]byte(line), &fx); err != nil {
			continue
		}
		gv, err := glyph.ParseDocument(fx.Text)
		var fp string
		if err == nil {
			fp, err = glyph.Fingerprint(gv)
		}
		if err != nil {
			msg := fmt.Sprintf("glyph: %v", err)
			b, _ := json.Marshal(outRow{ID: fx.ID, Subject: "glyph", Hash: "", Error: &msg})
			w.Write(b)
		} else {
			b, _ := json.Marshal(outRow{ID: fx.ID, Subject: "glyph", Hash: fp})
			w.Write(b)
		}
		w.WriteByte('\n')
	}
	return 0
}

func benchMode(payloadsPath string) int {
	const iters = 300
	raw, err := os.ReadFile(payloadsPath)
	if err != nil {
		return 1
	}
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	for _, line := range strings.Split(string(raw), "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		var p struct {
			ID   string `json:"id"`
			JSON string `json:"json"`
		}
		if err := json.Unmarshal([]byte(line), &p); err != nil {
			continue
		}
		var v interface{}
		dec := json.NewDecoder(strings.NewReader(p.JSON))
		dec.UseNumber()
		if err := dec.Decode(&v); err != nil {
			continue
		}
		row := map[string]interface{}{"id": p.ID, "iters": iters}

		t0 := time.Now()
		for i := 0; i < iters; i++ {
			norm, _ := json.Marshal(v)
			sha(norm)
		}
		row["naive_ns"] = time.Since(t0).Nanoseconds() / iters

		gv, err := glyph.FromJSONLoose([]byte(p.JSON))
		if err == nil {
			t0 = time.Now()
			for i := 0; i < iters; i++ {
				glyph.Fingerprint(gv)
			}
			row["glyph_ns"] = time.Since(t0).Nanoseconds() / iters
		}

		t0 = time.Now()
		for i := 0; i < iters; i++ {
			if canon, cerr := jsoncanonicalizer.Transform([]byte(p.JSON)); cerr == nil {
				sha(canon)
			}
		}
		row["jcs_ns"] = time.Since(t0).Nanoseconds() / iters

		b, _ := json.Marshal(row)
		w.Write(b)
		w.WriteByte('\n')
	}
	return 0
}

func main() {
	args := os.Args[1:]
	if len(args) == 2 && args[0] == "--selftest" {
		os.Exit(selftest(args[1]))
	}
	if len(args) == 2 && args[0] == "--mode" && args[1] == "gtext" {
		os.Exit(gtextMode())
	}
	if len(args) == 3 && args[0] == "--mode" && args[1] == "bench" {
		os.Exit(benchMode(args[2]))
	}

	sc := bufio.NewScanner(os.Stdin)
	sc.Buffer(make([]byte, 1024*1024), 32*1024*1024)
	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var fx struct {
			ID   string `json:"id"`
			JSON string `json:"json"`
		}
		if err := json.Unmarshal([]byte(line), &fx); err != nil {
			fmt.Fprintf(os.Stderr, "bad envelope line: %v\n", err)
			continue
		}
		for _, row := range runFixture(fx.ID, fx.JSON) {
			b, _ := json.Marshal(row)
			w.Write(b)
			w.WriteByte('\n')
		}
	}
}
