"""Golden corpus tests: Python vs Go canonical output.

Reads JSON inputs from go/glyph/testdata/loose_json/cases/ and compares
the output of from_json_loose -> canonicalize_loose_no_tabular against
the corresponding .want golden file in go/glyph/testdata/loose_json/golden/.

Every case must match Go byte-for-byte. The JSON-number typing is unified
across Go/JS/Python: GLYPH-Loose uses JSON-domain (IEEE-754 double) semantics,
so integer-valued floats collapse to integer literals (1e3 -> "1000"), -0.0 ->
"0", and integers outside the safe window (|n| > 2^53-1) canonicalize as
float64 (9007199254740993 -> "9.007199254740992e+15"). See
py/glyph/loose.py:from_json_loose and docs/LOOSE_MODE_SPEC.md.
"""

from __future__ import annotations

import json
import os
import glob
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from glyph import from_json_loose, canonicalize_loose_no_tabular

# Locate the Go testdata directory relative to this file.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_CASES_DIR = os.path.join(_REPO_ROOT, "go", "glyph", "testdata", "loose_json", "cases")
_GOLDEN_DIR = os.path.join(_REPO_ROOT, "go", "glyph", "testdata", "loose_json", "golden")

def _collect_cases():
    """Yield (case_name, case_path, want_path) tuples for every golden case."""
    if not os.path.isdir(_CASES_DIR):
        pytest.skip(f"Go testdata directory not found: {_CASES_DIR}")

    for case_path in sorted(glob.glob(os.path.join(_CASES_DIR, "*.json"))):
        name = os.path.basename(case_path)[:-5]  # strip .json
        want_path = os.path.join(_GOLDEN_DIR, name + ".want")
        if not os.path.exists(want_path):
            # No golden file for this case; skip it (e.g. 050_dynamic_keys_metadata).
            continue
        yield pytest.param(name, case_path, want_path, id=name)


@pytest.mark.parametrize("name,case_path,want_path", _collect_cases())
def test_golden_corpus(name, case_path, want_path):
    """Each Go golden case must match Python's canonicalize_loose_no_tabular output."""
    with open(case_path, encoding="utf-8") as f:
        data = json.load(f)

    with open(want_path, encoding="utf-8") as f:
        want = f.read().strip()

    gv = from_json_loose(data)
    got = canonicalize_loose_no_tabular(gv)

    assert got == want, (
        f"Golden mismatch for {name!r}\n"
        f"  Python: {got!r}\n"
        f"  Go:     {want!r}"
    )
