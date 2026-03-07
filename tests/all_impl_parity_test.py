#!/usr/bin/env python3
"""
Cross-implementation parity test for ALL GLYPH implementations:
Python, Go, JavaScript, Rust, and C
"""

import subprocess
import json
import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY_PATH = os.path.join(REPO_ROOT, "py")
GO_DIR = os.path.join(REPO_ROOT, "go")
JS_DIST = os.path.join(REPO_ROOT, "js", "dist", "index.js")
RUST_PATH = os.path.join(REPO_ROOT, "rust", "glyph-codec")
C_DIR = os.path.join(REPO_ROOT, "c", "glyph-codec")

# Test cases: (description, json_input, expected_glyph)
TEST_CASES = [
    ("null", "null", "_"),
    ("true", "true", "t"),
    ("false", "false", "f"),
    ("int positive", "42", "42"),
    ("int negative", "-123", "-123"),
    ("int zero", "0", "0"),
    ("float", "3.14", "3.14"),
    ("string bare", '"hello"', "hello"),
    ("string quoted", '"hello world"', '"hello world"'),
    ("string digit start", '"123abc"', '"123abc"'),
    ("string empty", '""', '""'),
    ("string reserved t", '"t"', '"t"'),
    ("string reserved f", '"f"', '"f"'),
    ("list empty", "[]", "[]"),
    ("list ints", "[1, 2, 3]", "[1 2 3]"),
    ("map empty", "{}", "{}"),
    ("map single", '{"a": 1}', "{a=1}"),
    ("map sorted", '{"b": 2, "a": 1}', "{a=1 b=2}"),
    ("nested", '{"x": {"y": 1}}', "{x={y=1}}"),
    # Sparse keys - should NOT become tabular
    ("sparse keys", '[{"a": 1}, {"b": 2}, {"c": 3}]', "[{a=1} {b=2} {c=3}]"),
    # Empty objects - should NOT become tabular
    ("empty objects", "[{}, {}, {}]", "[{} {} {}]"),
]

_go_bin = None
_rust_bin = None
_c_bin = None


def ensure_go_bin():
    global _go_bin
    if _go_bin and os.path.exists(_go_bin):
        return _go_bin

    temp_dir = "/tmp/glyph_go_test"
    os.makedirs(temp_dir, exist_ok=True)
    main_path = os.path.join(temp_dir, "main.go")
    bin_path = os.path.join(temp_dir, "glyph_go_canon")

    go_code = r'''
package main

import (
    "fmt"
    "io"
    "os"
    glyph "github.com/Neumenon/glyph/glyph"
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
    fmt.Print(glyph.CanonicalizeLoose(v))
}
'''
    with open(main_path, "w") as f:
        f.write(go_code)

    env = {**os.environ, "GOMOD": os.path.join(GO_DIR, "go.mod"), "GOCACHE": "/tmp/go-cache"}
    result = subprocess.run(
        ["go", "build", "-o", bin_path, main_path],
        capture_output=True,
        text=True,
        cwd=GO_DIR,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Go build error: {result.stderr}")

    _go_bin = bin_path
    return _go_bin


def ensure_rust_bin():
    global _rust_bin
    if _rust_bin and os.path.exists(_rust_bin):
        return _rust_bin

    temp_dir = "/tmp/glyph_rust_test"
    os.makedirs(temp_dir, exist_ok=True)

    cargo_toml = f'''[package]
name = "glyph_canon"
version = "0.1.0"
edition = "2021"

[dependencies]
glyph-codec = {{ path = "{RUST_PATH}" }}
'''

    main_rs = r'''
use std::io::{self, Read};
use glyph_codec::{parse_json, canonicalize_loose};

fn main() {
    let input = std::env::args().nth(1).unwrap_or_else(|| {
        let mut s = String::new();
        io::stdin().read_to_string(&mut s).unwrap();
        s
    });
    let v = parse_json(&input).unwrap();
    print!("{}", canonicalize_loose(&v));
}
'''

    with open(os.path.join(temp_dir, "Cargo.toml"), "w") as f:
        f.write(cargo_toml)
    os.makedirs(os.path.join(temp_dir, "src"), exist_ok=True)
    with open(os.path.join(temp_dir, "src", "main.rs"), "w") as f:
        f.write(main_rs)

    result = subprocess.run(
        ["cargo", "build", "-q", "--offline"],
        capture_output=True,
        text=True,
        cwd=temp_dir,
        env={**os.environ, "CARGO_NET_OFFLINE": "true"},
    )
    if result.returncode != 0:
        raise RuntimeError(f"Rust build error: {result.stderr}")

    _rust_bin = os.path.join(temp_dir, "target", "debug", "glyph_canon")
    return _rust_bin


def ensure_c_bin():
    global _c_bin
    if _c_bin and os.path.exists(_c_bin):
        return _c_bin

    temp_dir = "/tmp/glyph_c_test"
    os.makedirs(temp_dir, exist_ok=True)

    c_code = r'''
#include "glyph.h"
#include <stdio.h>

int main(int argc, char **argv) {
    if (argc < 2) {
        return 1;
    }
    const char *json = argv[1];
    glyph_value_t *v = glyph_from_json(json);
    if (!v) {
        return 1;
    }
    char *canon = glyph_canonicalize_loose(v);
    if (canon) {
        printf("%s", canon);
        glyph_free(canon);
    }
    glyph_value_free(v);
    return 0;
}
'''

    c_path = os.path.join(temp_dir, "test.c")
    with open(c_path, "w") as f:
        f.write(c_code)

    lib_path = os.path.join(C_DIR, "build", "libglyph.a")
    if not os.path.exists(lib_path):
        build_result = subprocess.run(
            ["make"],
            capture_output=True,
            text=True,
            cwd=C_DIR,
        )
        if build_result.returncode != 0:
            raise RuntimeError(f"C build error: {build_result.stderr}")

    bin_path = os.path.join(temp_dir, "glyph_canon")
    compile_result = subprocess.run(
        [
            "gcc",
            "-o",
            bin_path,
            c_path,
            f"-I{C_DIR}/include",
            f"-L{C_DIR}/build",
            "-lglyph",
            "-lm",
        ],
        capture_output=True,
        text=True,
    )
    if compile_result.returncode != 0:
        raise RuntimeError(f"C compile error: {compile_result.stderr}")

    _c_bin = bin_path
    return _c_bin


def get_python_output(json_str):
    """Get GLYPH output from Python implementation"""
    sys.path.insert(0, PY_PATH)
    from glyph import from_json_loose, canonicalize_loose

    v = from_json_loose(json.loads(json_str))
    return canonicalize_loose(v)


def get_go_output(json_str):
    """Get GLYPH output from Go implementation"""
    try:
        bin_path = ensure_go_bin()
    except Exception as exc:
        return f"ERROR: {exc}"

    result = subprocess.run(
        [bin_path, json_str],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"ERROR: {result.stderr}"
    return result.stdout


def get_js_output(json_str):
    """Get GLYPH output from JavaScript implementation"""
    js_code = f'''
const {{ fromJsonLoose, canonicalizeLoose }} = require({json.dumps(JS_DIST)});
const data = JSON.parse({json.dumps(json_str)});
const v = fromJsonLoose(data);
console.log(canonicalizeLoose(v));
'''
    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"ERROR: {result.stderr}"
    return result.stdout.strip()


def get_rust_output(json_str):
    """Get GLYPH output from Rust implementation"""
    try:
        bin_path = ensure_rust_bin()
    except Exception as exc:
        return f"ERROR: {exc}"

    result = subprocess.run(
        [bin_path, json_str],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"ERROR: {result.stderr}"
    return result.stdout


def get_c_output(json_str):
    """Get GLYPH output from C implementation"""
    try:
        bin_path = ensure_c_bin()
    except Exception as exc:
        return f"ERROR: {exc}"

    run_result = subprocess.run(
        [bin_path, json_str],
        capture_output=True,
        text=True,
        env={**os.environ, "LD_LIBRARY_PATH": f"{C_DIR}/build"},
    )
    if run_result.returncode != 0:
        return f"RUN ERROR: {run_result.stderr}"
    return run_result.stdout


def main():
    print("=" * 70)
    print("CROSS-IMPLEMENTATION PARITY TEST (Python, Go, JS, Rust, C)")
    print("=" * 70)
    print()

    passed = 0
    failed = 0

    # Get Python output for all tests first (fastest)
    print("Getting Python outputs...")
    py_outputs = {}
    for desc, json_str, expected in TEST_CASES:
        py_outputs[desc] = get_python_output(json_str)

    print("Getting Go outputs...")
    go_outputs = {}
    for desc, json_str, expected in TEST_CASES:
        go_outputs[desc] = get_go_output(json_str)

    print("Getting JS outputs...")
    js_outputs = {}
    for desc, json_str, expected in TEST_CASES:
        js_outputs[desc] = get_js_output(json_str)

    print("Getting Rust outputs...")
    rust_outputs = {}
    for desc, json_str, expected in TEST_CASES:
        rust_outputs[desc] = get_rust_output(json_str)

    print("Getting C outputs...")
    c_outputs = {}
    for desc, json_str, expected in TEST_CASES:
        c_outputs[desc] = get_c_output(json_str)

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()

    for desc, json_str, expected in TEST_CASES:
        py = py_outputs[desc]
        go = go_outputs[desc]
        js = js_outputs[desc]
        rust = rust_outputs[desc]
        c = c_outputs[desc]

        all_match = (py == go == js == rust == c == expected)

        if all_match:
            print(f"✅ {desc}: {expected}")
            passed += 1
        else:
            print(f"❌ {desc}:")
            print(f"   Expected: {repr(expected)}")
            print(f"   Python:   {repr(py)}")
            print(f"   Go:       {repr(go)}")
            print(f"   JS:       {repr(js)}")
            print(f"   Rust:     {repr(rust)}")
            print(f"   C:        {repr(c)}")
            failed += 1

    print()
    print("=" * 70)
    if failed == 0:
        print(f"✅ ALL {passed} TESTS PASSED - FULL PARITY ACROSS ALL IMPLEMENTATIONS")
    else:
        print(f"❌ {passed} passed, {failed} failed")


if __name__ == "__main__":
    main()
