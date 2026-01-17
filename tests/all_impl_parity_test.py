#!/usr/bin/env python3
"""
Cross-implementation parity test for ALL GLYPH implementations:
Python, Go, JavaScript, Rust, and C
"""

import subprocess
import json
import sys
import os

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

def get_python_output(json_str):
    """Get GLYPH output from Python implementation"""
    sys.path.insert(0, '/home/omen/Documents/Project/Agent-GO/sjson/glyph-py')
    from glyph import from_json_loose, canonicalize_loose
    v = from_json_loose(json_str)
    return canonicalize_loose(v)

def get_go_output(json_str):
    """Get GLYPH output from Go implementation"""
    go_code = f'''
package main

import (
    "fmt"
    glyph "/home/omen/Documents/Project/glyph/go/glyph"
)

func main() {{
    v, _ := glyph.FromJSON([]byte(`{json_str}`))
    fmt.Print(glyph.CanonicalizeLoose(v))
}}
'''
    result = subprocess.run(
        ['go', 'run', '-'],
        input=go_code,
        capture_output=True,
        text=True,
        cwd='/home/omen/Documents/Project/glyph/go'
    )
    if result.returncode != 0:
        return f"ERROR: {result.stderr}"
    return result.stdout

def get_js_output(json_str):
    """Get GLYPH output from JavaScript implementation"""
    js_code = f'''
const {{ GValue }} = require('/home/omen/Documents/Project/glyph/js/dist/index.js');
const v = GValue.fromJSON({json_str});
console.log(v.canonicalizeLoose());
'''
    result = subprocess.run(
        ['node', '-e', js_code],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return f"ERROR: {result.stderr}"
    return result.stdout.strip()

def get_rust_output(json_str):
    """Get GLYPH output from Rust implementation"""
    # Create a temporary test
    rust_code = f'''
use glyph_codec::{{from_json, canonicalize_loose}};
fn main() {{
    let v = from_json(r#"{json_str}"#).unwrap();
    print!("{{}}", canonicalize_loose(&v));
}}
'''
    # Write temp main.rs
    temp_dir = '/tmp/glyph_rust_test'
    os.makedirs(temp_dir, exist_ok=True)

    with open(f'{temp_dir}/Cargo.toml', 'w') as f:
        f.write('''[package]
name = "test"
version = "0.1.0"
edition = "2021"

[dependencies]
glyph-codec = { path = "/home/omen/Documents/Project/glyph/rust/glyph-codec" }
''')

    os.makedirs(f'{temp_dir}/src', exist_ok=True)
    with open(f'{temp_dir}/src/main.rs', 'w') as f:
        f.write(rust_code)

    result = subprocess.run(
        ['cargo', 'run', '-q'],
        capture_output=True,
        text=True,
        cwd=temp_dir
    )
    if result.returncode != 0:
        return f"ERROR: {result.stderr}"
    return result.stdout

def get_c_output(json_str):
    """Get GLYPH output from C implementation"""
    c_code = f'''
#include "glyph.h"
#include <stdio.h>
#include <stdlib.h>

int main(void) {{
    const char *json = {repr(json_str)};
    glyph_value_t *v = glyph_from_json(json);
    if (v) {{
        char *canon = glyph_canonicalize_loose(v);
        printf("%s", canon);
        glyph_free(canon);
        glyph_value_free(v);
    }}
    return 0;
}}
'''
    # Write and compile
    temp_dir = '/tmp/glyph_c_test'
    os.makedirs(temp_dir, exist_ok=True)

    with open(f'{temp_dir}/test.c', 'w') as f:
        f.write(c_code)

    c_dir = '/home/omen/Documents/Project/glyph/c/glyph-codec'
    compile_result = subprocess.run(
        ['gcc', '-o', f'{temp_dir}/test', f'{temp_dir}/test.c',
         f'-I{c_dir}/include', f'-L{c_dir}/build', '-lglyph', '-lm'],
        capture_output=True,
        text=True
    )
    if compile_result.returncode != 0:
        return f"COMPILE ERROR: {compile_result.stderr}"

    run_result = subprocess.run(
        [f'{temp_dir}/test'],
        capture_output=True,
        text=True,
        env={**os.environ, 'LD_LIBRARY_PATH': f'{c_dir}/build'}
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
    print("=" * 70)

    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
