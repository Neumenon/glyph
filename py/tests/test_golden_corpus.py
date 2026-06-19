"""Golden corpus tests: Python vs Go canonical output.

Reads JSON inputs from go/glyph/testdata/loose_json/cases/ and compares
the output of from_json_loose -> canonicalize_loose_no_tabular against
the corresponding .want golden file in go/glyph/testdata/loose_json/golden/.

Cases that diverge today due to known, deferred issues are marked xfail with
an explanatory reason string. The suite is expected to produce xfail results
for those — not hard failures.

Known divergences (intentionally deferred, do NOT fix here):
- Float canonicalization rule: Go emits integer-valued floats without ".0"
  (e.g. 1e3 -> "1000"), Python's canon_float keeps the float representation
  (1000.0). This affects cases 006, 016, 034, 035.
  See: "deferred — float-.0 rule unification".
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

# Cases expected to diverge due to the float canonicalization rule (deferred).
# Python's JSON parser returns floats for 1e3/3.0e+0 (Go returns ints),
# and returns ints for 1e20/1e21 (Go returns floats). Both are correct per
# JSON spec but produce different GLYPH output until the rule is unified.
_FLOAT_RULE_XFAIL = {
    "006_exponent_numbers": (
        "deferred — float-.0 rule: JSON numbers like 1e3 and 3.0e+0 are parsed "
        "as Python float (1000.0, 3.0) but Go parses them as int (1000, 3); "
        "canon_float diverges until the float canonicalization rule is unified"
    ),
    "016_large_int_like": (
        "deferred — float rule: 9007199254740993 is parsed as Python int (emitted "
        "as-is) but Go treats it as float and emits 9.007199254740992e+15"
    ),
    "034_exp_boundary_large": (
        "deferred — float rule: 1e20/1e21 are parsed as Python int by json.loads "
        "and emitted as large ints, but Go parses them as float and emits 1e+20/1e+21"
    ),
    "035_safe_int_boundary": (
        "deferred — float rule: 9007199254740992/9007199254740993 are parsed as "
        "Python int by json.loads, but Go treats them as out-of-safe-int float and "
        "emits 9.007199254740992e+15"
    ),
}


def _collect_cases():
    """Yield (case_name, case_path, want_path, xfail_reason_or_None) tuples."""
    if not os.path.isdir(_CASES_DIR):
        pytest.skip(f"Go testdata directory not found: {_CASES_DIR}")

    for case_path in sorted(glob.glob(os.path.join(_CASES_DIR, "*.json"))):
        name = os.path.basename(case_path)[:-5]  # strip .json
        want_path = os.path.join(_GOLDEN_DIR, name + ".want")
        if not os.path.exists(want_path):
            # No golden file for this case; skip it (e.g. 050_dynamic_keys_metadata).
            continue
        xfail_reason = _FLOAT_RULE_XFAIL.get(name)
        yield pytest.param(
            name,
            case_path,
            want_path,
            xfail_reason,
            id=name,
            marks=[pytest.mark.xfail(reason=xfail_reason, strict=True)]
            if xfail_reason
            else [],
        )


@pytest.mark.parametrize("name,case_path,want_path,xfail_reason", _collect_cases())
def test_golden_corpus(name, case_path, want_path, xfail_reason):
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
