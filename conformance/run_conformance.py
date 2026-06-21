#!/usr/bin/env python3
"""
GLYPH conformance runner.

Tests the Go, Python, and JavaScript reference implementations against the
51-case corpus in conformance/corpus/.  Exits non-zero if any required
implementation (Go/Python/JS) fails any case.

Usage:
    python conformance/run_conformance.py [--impl go|py|js]

Run from the repo root or from conformance/.
"""

import argparse
import json
import os
import subprocess
import sys

# ── paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

CORPUS_DIR = os.path.join(SCRIPT_DIR, "corpus")
CASES_DIR  = os.path.join(CORPUS_DIR, "cases")
GOLDEN_DIR = os.path.join(CORPUS_DIR, "golden")
MANIFEST   = os.path.join(CORPUS_DIR, "manifest.json")

PY_PATH  = os.path.join(REPO_ROOT, "py")
GO_DIR   = os.path.join(REPO_ROOT, "go")
JS_DIST  = os.path.join(REPO_ROOT, "js", "dist", "index.js")

# ── Go binary (built once per run) ────────────────────────────────────────────

_go_bin = None

def _ensure_go_bin():
    global _go_bin
    if _go_bin and os.path.exists(_go_bin):
        return _go_bin

    tmp = "/tmp/glyph_conformance_go"
    os.makedirs(tmp, exist_ok=True)
    main_go = os.path.join(tmp, "main.go")
    bin_path = os.path.join(tmp, "glyph_canon")

    go_src = r'''package main

import (
    "fmt"
    "io"
    "os"
    glyph "github.com/Neumenon/glyph/go/glyph"
)

func main() {
    var input []byte
    if len(os.Args) > 1 {
        input = []byte(os.Args[1])
    } else {
        data, _ := io.ReadAll(os.Stdin)
        input = data
    }
    v, err := glyph.FromJSONLoose(input)
    if err != nil {
        fmt.Fprint(os.Stderr, err)
        os.Exit(1)
    }
    // CanonicalizeLooseNoTabular matches how the golden corpus was generated:
    // auto-tabular disabled, NullStyle defaults to ∅ (NullStyleSymbol).
    fmt.Println(glyph.CanonicalizeLooseNoTabular(v))
}
'''
    with open(main_go, "w") as f:
        f.write(go_src)

    env = {**os.environ, "GOMOD": os.path.join(GO_DIR, "go.mod"), "GOCACHE": "/tmp/go-cache"}
    r = subprocess.run(
        ["go", "build", "-o", bin_path, main_go],
        capture_output=True, text=True, cwd=GO_DIR, env=env,
    )
    if r.returncode != 0:
        raise RuntimeError(f"Go build failed:\n{r.stderr}")

    _go_bin = bin_path
    return _go_bin


# ── per-impl runners ──────────────────────────────────────────────────────────

def run_go(json_bytes: bytes) -> str:
    """Return canonical output from the Go reference implementation."""
    bin_path = _ensure_go_bin()
    r = subprocess.run(
        [bin_path, json_bytes.decode()],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def run_py(json_bytes: bytes) -> str:
    """Return canonical output from the Python reference implementation.

    Uses canonicalize_loose_no_tabular to match how the golden corpus was
    generated (auto-tabular disabled, null as ∅).
    """
    sys.path.insert(0, PY_PATH)
    from glyph import from_json_loose, canonicalize_loose_no_tabular  # type: ignore
    import json as _json
    v = from_json_loose(_json.loads(json_bytes.decode()))
    return canonicalize_loose_no_tabular(v) + "\n"


def run_js(json_bytes: bytes) -> str:
    """Return canonical output from the JavaScript reference implementation.

    Uses canonicalizeLooseNoTabular to match how the golden corpus was generated
    (auto-tabular disabled, null as ∅).
    """
    import json as _json
    js_code = (
        f"const {{fromJsonLoose, canonicalizeLooseNoTabular}} = require({_json.dumps(JS_DIST)});\n"
        f"const data = JSON.parse({_json.dumps(json_bytes.decode())});\n"
        f"const v = fromJsonLoose(data);\n"
        f"console.log(canonicalizeLooseNoTabular(v));\n"
    )
    r = subprocess.run(["node", "-e", js_code], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout  # console.log already appends \n


IMPLS = {
    "go":  run_go,
    "py":  run_py,
    "js":  run_js,
}

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GLYPH conformance runner")
    parser.add_argument(
        "--impl", choices=list(IMPLS), action="append", dest="impls",
        metavar="IMPL",
        help="Which impl(s) to test (default: all). May be repeated.",
    )
    args = parser.parse_args()
    selected = args.impls or list(IMPLS)

    with open(MANIFEST) as f:
        manifest = json.load(f)

    corpus_version = manifest.get("version", "unknown")
    cases = manifest["cases"]

    print("=" * 68)
    print(f"GLYPH conformance runner  (corpus {corpus_version})")
    print(f"Implementations: {', '.join(selected)}")
    print("=" * 68)
    print()

    # Pre-flight: build Go binary once, check JS dist exists
    setup_errors = {}
    if "go" in selected:
        print("Building Go binary...", end=" ", flush=True)
        try:
            _ensure_go_bin()
            print("ok")
        except Exception as e:
            setup_errors["go"] = str(e)
            print(f"FAILED\n  {e}")

    if "js" in selected and not os.path.exists(JS_DIST):
        setup_errors["js"] = f"JS dist not found: {JS_DIST}\n  Run: npm run build  (in js/)"
        print(f"JS dist missing: {JS_DIST}")

    print()

    # Run corpus
    results = {impl: {"pass": 0, "fail": 0, "skip": False} for impl in selected}
    failures = []

    for case in cases:
        name = case["name"]
        case_file = os.path.join(CASES_DIR, os.path.basename(case["file"]))
        want_stem = os.path.splitext(os.path.basename(case["file"]))[0]
        want_file = os.path.join(GOLDEN_DIR, want_stem + ".want")

        json_bytes = open(case_file, "rb").read()
        want = open(want_file, "rb").read().decode()

        for impl in selected:
            if impl in setup_errors:
                results[impl]["skip"] = True
                continue

            fn = IMPLS[impl]
            try:
                got = fn(json_bytes)
            except Exception as e:
                got = f"ERROR: {e}"

            if got == want:
                results[impl]["pass"] += 1
            else:
                results[impl]["fail"] += 1
                failures.append((impl, name, repr(want), repr(got)))

    # Report
    print(f"{'Case':<40} " + "  ".join(f"{i:>5}" for i in selected))
    print("-" * (40 + 8 * len(selected)))

    # Per-case detail only for failures
    for impl, name, want_r, got_r in failures:
        print(f"  FAIL [{impl}] {name}")
        print(f"    want: {want_r}")
        print(f"    got:  {got_r}")

    if failures:
        print()

    print()
    print("=" * 68)
    print("SUMMARY")
    print("=" * 68)
    overall_pass = True
    for impl in selected:
        r = results[impl]
        if r["skip"]:
            print(f"  {impl:4s}  SKIP  ({setup_errors.get(impl, 'setup error')})")
        elif r["fail"] == 0:
            print(f"  {impl:4s}  PASS  {r['pass']}/{r['pass']+r['fail']} cases")
        else:
            print(f"  {impl:4s}  FAIL  {r['pass']}/{r['pass']+r['fail']} cases ({r['fail']} failures)")
            overall_pass = False

    print()
    if overall_pass:
        total = len(cases)
        print(f"ALL PASS  ({total} cases x {len(selected)} impls)")
        return 0
    else:
        print("CONFORMANCE FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
