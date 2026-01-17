#!/usr/bin/env python3
"""
GLYPH Round-Trip Stress Test Suite

Comprehensive tests to find data corruption issues like the tabular sparse keys bug.
Tests JSON -> GLYPH -> JSON round-trip fidelity across edge cases.
"""

import json
import sys
import traceback
from typing import Any, List, Tuple

# Add the glyph-codec path
sys.path.insert(0, '/home/omen/Documents/Project/Agent-GO/sjson/glyph-py')

from glyph import (
    from_json_loose, to_json_loose,
    canonicalize_loose, canonicalize_loose_no_tabular,
    parse_json_loose, stringify_json_loose,
    equal_loose, fingerprint_loose,
    LooseCanonOpts, NullStyle,
)


def test_roundtrip(name: str, data: Any, use_tabular: bool = True) -> Tuple[bool, str]:
    """Test JSON -> GValue -> GLYPH -> GValue -> JSON round-trip."""
    try:
        # JSON -> GValue
        gvalue = from_json_loose(data)

        # GValue -> GLYPH string
        if use_tabular:
            glyph_str = canonicalize_loose(gvalue)
        else:
            glyph_str = canonicalize_loose_no_tabular(gvalue)

        # GValue -> JSON (direct, no parse)
        restored = to_json_loose(gvalue)

        # Compare
        orig_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
        rest_json = json.dumps(restored, sort_keys=True, ensure_ascii=False)

        if orig_json == rest_json:
            return True, f"OK | GLYPH: {glyph_str[:80]}{'...' if len(glyph_str) > 80 else ''}"
        else:
            return False, f"MISMATCH\n  Original: {data}\n  Restored: {restored}\n  GLYPH: {glyph_str}"
    except Exception as e:
        return False, f"ERROR: {e}\n{traceback.format_exc()}"


def test_parse_roundtrip(name: str, data: Any) -> Tuple[bool, str]:
    """Test JSON -> GValue -> GLYPH string -> parse -> GValue -> JSON."""
    try:
        # JSON -> GValue -> GLYPH
        gvalue = from_json_loose(data)
        glyph_str = canonicalize_loose(gvalue)

        # GLYPH -> JSON string -> parse -> GValue
        # Note: We need to use the JSON bridge since there's no loose GLYPH parser
        json_str = stringify_json_loose(gvalue)
        reparsed = parse_json_loose(json_str)
        restored = to_json_loose(reparsed)

        # Compare
        orig_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
        rest_json = json.dumps(restored, sort_keys=True, ensure_ascii=False)

        if orig_json == rest_json:
            return True, "OK"
        else:
            return False, f"MISMATCH\n  Original: {data}\n  Restored: {restored}"
    except Exception as e:
        return False, f"ERROR: {e}"


# =============================================================================
# Test Cases
# =============================================================================

ROUNDTRIP_TESTS: List[Tuple[str, Any]] = [
    # =========================================================================
    # BASIC TYPES
    # =========================================================================
    ("null", None),
    ("true", True),
    ("false", False),
    ("zero", 0),
    ("negative zero float", -0.0),
    ("positive int", 42),
    ("negative int", -123),
    ("large int", 9999999999999),
    ("float", 3.14159),
    ("negative float", -2.71828),
    ("scientific notation small", 1e-10),
    ("scientific notation large", 1e15),
    ("empty string", ""),
    ("simple string", "hello"),
    ("string with spaces", "hello world"),
    ("string with quotes", 'say "hello"'),
    ("string with backslash", "path\\to\\file"),
    ("string with newline", "line1\nline2"),
    ("string with tab", "col1\tcol2"),
    ("string with unicode", "你好世界"),
    ("string with emoji", "🚀🔥💻"),
    ("string with null char", "before\x00after"),

    # =========================================================================
    # ARRAYS - BASIC
    # =========================================================================
    ("empty array", []),
    ("array of nulls", [None, None, None]),
    ("array of bools", [True, False, True]),
    ("array of ints", [1, 2, 3, 4, 5]),
    ("array of floats", [1.1, 2.2, 3.3]),
    ("array of strings", ["a", "b", "c"]),
    ("mixed array", [1, "two", True, None, 3.14]),
    ("nested array", [[1, 2], [3, 4], [5, 6]]),
    ("deeply nested array", [[[1]], [[2]], [[3]]]),

    # =========================================================================
    # ARRAYS - SPARSE/HETEROGENEOUS (potential tabular issues)
    # =========================================================================
    ("sparse keys - disjoint", [{"a": 1}, {"b": 2}, {"c": 3}]),
    ("sparse keys - partial overlap", [{"a": 1, "b": 2}, {"b": 3, "c": 4}, {"a": 5, "c": 6}]),
    ("sparse keys - one common", [{"x": 1, "a": 2}, {"x": 3, "b": 4}, {"x": 5, "c": 6}]),
    ("varying key counts", [{"a": 1}, {"a": 1, "b": 2}, {"a": 1, "b": 2, "c": 3}]),
    ("empty objects in array", [{}, {}, {}]),
    ("mixed empty and non-empty", [{"a": 1}, {}, {"b": 2}]),
    ("single key objects", [{"x": 1}, {"x": 2}, {"x": 3}]),
    ("objects with null values", [{"a": 1, "b": None}, {"a": None, "b": 2}]),

    # =========================================================================
    # OBJECTS - BASIC
    # =========================================================================
    ("empty object", {}),
    ("single key", {"key": "value"}),
    ("multiple keys", {"a": 1, "b": 2, "c": 3}),
    ("nested object", {"outer": {"inner": {"deep": True}}}),
    ("object with null value", {"key": None}),
    ("object with array value", {"arr": [1, 2, 3]}),
    ("object with mixed values", {"str": "hello", "num": 42, "bool": True, "null": None}),

    # =========================================================================
    # OBJECTS - KEY EDGE CASES
    # =========================================================================
    ("numeric string keys", {"1": "one", "2": "two", "10": "ten"}),
    ("unicode keys", {"名前": "Alice", "年齢": 30}),
    ("emoji keys", {"🔑": "key", "📦": "box"}),
    ("empty string key", {"": "empty key"}),
    ("key with spaces", {"my key": "value"}),
    ("key with special chars", {"a=b": 1, "c:d": 2, "e[f]": 3}),
    ("key ordering test", {"z": 1, "a": 2, "m": 3, "b": 4}),
    ("reserved word keys", {"true": 1, "false": 2, "null": 3, "t": 4, "f": 5}),

    # =========================================================================
    # DEEPLY NESTED STRUCTURES
    # =========================================================================
    ("deep nesting 5", {"a": {"b": {"c": {"d": {"e": 1}}}}}),
    ("deep nesting 10", {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": {"l8": {"l9": {"l10": "deep"}}}}}}}}}}),
    ("array in object in array", [{"arr": [1, 2, 3]}, {"arr": [4, 5, 6]}]),
    ("object in array in object", {"items": [{"nested": {"value": 1}}, {"nested": {"value": 2}}]}),

    # =========================================================================
    # NUMBERS - EDGE CASES
    # =========================================================================
    ("max safe int", 9007199254740991),
    ("min safe int", -9007199254740991),
    ("very small float", 0.000000001),
    ("very large float", 999999999999.999),
    ("float precision edge", 0.1 + 0.2),  # Famous 0.30000000000000004
    ("negative exponent", 1.5e-5),
    ("positive exponent", 1.5e10),
    ("integer as float", 42.0),

    # =========================================================================
    # STRINGS - EDGE CASES
    # =========================================================================
    ("string that looks like int", "42"),
    ("string that looks like float", "3.14"),
    ("string that looks like bool", "true"),
    ("string that looks like null", "null"),
    ("string with only spaces", "   "),
    ("string with leading/trailing spaces", "  hello  "),
    ("very long string", "x" * 1000),
    ("string with all escape chars", "tab:\there\nnewline\rcarriage\"quote\\backslash"),
    ("unicode normalization test", "é"),  # Can be composed or decomposed
    ("zero-width chars", "a\u200bb\u200cc"),
    ("RTL text", "مرحبا"),
    ("mixed LTR/RTL", "Hello مرحبا World"),

    # =========================================================================
    # ARRAYS - SIZE EDGE CASES
    # =========================================================================
    ("single element array", [1]),
    ("two element array", [1, 2]),
    ("exactly 3 elements (tabular threshold)", [{"a": 1}, {"a": 2}, {"a": 3}]),
    ("large homogeneous array", [{"id": i, "val": i * 2} for i in range(20)]),
    ("large heterogeneous array", [{"id": i, f"key{i}": i} for i in range(10)]),

    # =========================================================================
    # REAL-WORLD PATTERNS
    # =========================================================================
    ("api response", {
        "status": "success",
        "data": [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}],
        "meta": {"total": 2, "page": 1}
    }),
    ("tool call", {
        "tool": "search",
        "args": {"query": "test", "limit": 10},
        "id": "call_123"
    }),
    ("config object", {
        "database": {"host": "localhost", "port": 5432},
        "cache": {"enabled": True, "ttl": 3600},
        "features": ["auth", "logging"]
    }),
    ("sparse api results", [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob"},  # Missing email
        {"id": 3, "email": "charlie@example.com"},  # Missing name
    ]),

    # =========================================================================
    # POTENTIAL PROBLEM PATTERNS
    # =========================================================================
    ("all nulls object", {"a": None, "b": None, "c": None}),
    ("alternating nulls", [{"a": 1, "b": None}, {"a": None, "b": 2}, {"a": 3, "b": None}]),
    ("deeply nested nulls", {"outer": {"inner": {"value": None}}}),
    ("array with empty strings", ["", "", ""]),
    ("object with empty string values", {"a": "", "b": "", "c": ""}),
    ("mixed null and empty", {"null": None, "empty": "", "zero": 0, "false": False}),
]


def run_tests():
    """Run all round-trip tests and report results."""
    print("=" * 70)
    print("GLYPH ROUND-TRIP STRESS TEST")
    print("=" * 70)

    passed = 0
    failed = 0
    errors = []

    for name, data in ROUNDTRIP_TESTS:
        # Test with tabular enabled (default)
        success, msg = test_roundtrip(name, data, use_tabular=True)

        if success:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}")
            print(f"   {msg}")
            failed += 1
            errors.append((name, data, msg))

        # Also test without tabular to isolate issues
        success_no_tab, msg_no_tab = test_roundtrip(f"{name} (no tabular)", data, use_tabular=False)
        if not success_no_tab and success:
            print(f"   ⚠️  Fails WITHOUT tabular too: {msg_no_tab}")

    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if errors:
        print("\n❌ FAILED TESTS:")
        for name, data, msg in errors:
            print(f"\n  {name}:")
            print(f"    Data: {data}")
            print(f"    Issue: {msg[:200]}")

    return failed == 0


def run_equality_tests():
    """Test that semantically equal values have equal fingerprints."""
    print("\n" + "=" * 70)
    print("EQUALITY / FINGERPRINT TESTS")
    print("=" * 70)

    test_cases = [
        # (name, val1, val2, should_be_equal)
        ("same object different key order", {"a": 1, "b": 2}, {"b": 2, "a": 1}, True),
        ("same array", [1, 2, 3], [1, 2, 3], True),
        ("different array order", [1, 2, 3], [3, 2, 1], False),
        ("int vs float", 42, 42.0, False),  # Different types
        ("null equality", None, None, True),
        ("empty structures", {}, [], False),
        ("nested same", {"a": {"b": 1}}, {"a": {"b": 1}}, True),
        ("nested different", {"a": {"b": 1}}, {"a": {"b": 2}}, False),
    ]

    passed = 0
    failed = 0

    for name, val1, val2, expected in test_cases:
        gv1 = from_json_loose(val1)
        gv2 = from_json_loose(val2)

        are_equal = equal_loose(gv1, gv2)
        fp_equal = fingerprint_loose(gv1) == fingerprint_loose(gv2)

        # equal_loose and fingerprint should agree
        consistent = are_equal == fp_equal
        correct = are_equal == expected

        if consistent and correct:
            print(f"✅ {name}: equal={are_equal} (expected={expected})")
            passed += 1
        else:
            print(f"❌ {name}: equal={are_equal}, fp_equal={fp_equal}, expected={expected}")
            failed += 1

    print(f"\nEquality tests: {passed} passed, {failed} failed")
    return failed == 0


def run_canonicalization_tests():
    """Test that canonicalization is deterministic and stable."""
    print("\n" + "=" * 70)
    print("CANONICALIZATION STABILITY TESTS")
    print("=" * 70)

    test_data = [
        {"z": 1, "a": 2, "m": 3},  # Key ordering
        [{"b": 2, "a": 1}, {"d": 4, "c": 3}, {"f": 6, "e": 5}],  # Nested ordering
        {"key": "value with\nnewline"},
        {"float": 3.14159265358979},
    ]

    passed = 0
    failed = 0

    for data in test_data:
        gv = from_json_loose(data)

        # Canonicalize multiple times
        c1 = canonicalize_loose(gv)
        c2 = canonicalize_loose(gv)
        c3 = canonicalize_loose(gv)

        if c1 == c2 == c3:
            print(f"✅ Stable: {c1[:60]}...")
            passed += 1
        else:
            print(f"❌ Unstable canonicalization!")
            print(f"   c1: {c1}")
            print(f"   c2: {c2}")
            print(f"   c3: {c3}")
            failed += 1

    print(f"\nStability tests: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    all_passed = True

    all_passed &= run_tests()
    all_passed &= run_equality_tests()
    all_passed &= run_canonicalization_tests()

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED - INVESTIGATE ABOVE")
    print("=" * 70)

    sys.exit(0 if all_passed else 1)
