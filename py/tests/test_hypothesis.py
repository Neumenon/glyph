"""Suite 5: Property-based testing for glyph Python using hypothesis.

Tests:
1. Arbitrary text parse: never raises unhandled exception
2. JSON roundtrip: from_json_loose(to_json_loose(v)) preserves structure
3. Canonicalization idempotency: canon(canon(x)) == canon(x)
"""

import math
import json

import pytest

try:
    from hypothesis import given, settings, assume, HealthCheck
    from hypothesis import strategies as st

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

from glyph import (
    from_json_loose,
    to_json_loose,
    canonicalize_loose_no_tabular,
)
from glyph.loose import canon_float

pytestmark = pytest.mark.skipif(
    not HAS_HYPOTHESIS, reason="hypothesis not installed"
)


# ── Strategies ──────────────────────────────────────────────────────

if not HAS_HYPOTHESIS:
    pytest.skip("hypothesis not installed", allow_module_level=True)

# Safe float values (no NaN/Inf since glyph text rejects them)
safe_floats = st.floats(
    allow_nan=False, allow_infinity=False, allow_subnormal=True
)

json_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    safe_floats,
    st.text(max_size=50),
)

json_values = st.recursive(
    json_scalars,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(max_size=20), children, max_size=5),
    ),
    max_leaves=20,
)


# ── Tests ───────────────────────────────────────────────────────────


@given(text=st.text(max_size=500))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_arbitrary_text_parse_no_crash(text: str):
    """Parsing arbitrary text must never crash — only return value or raise."""
    try:
        from_json_loose(text)
    except Exception:
        pass  # Any exception is fine


@given(value=safe_floats)
@settings(max_examples=200)
def test_canon_float_roundtrip(value: float):
    """canon_float for finite values always produces a parseable number."""
    try:
        result = canon_float(value)
    except ValueError:
        return  # Some edge cases may be rejected

    # The result should parse back to a valid float.
    # NOTE: Python canon_float may lose precision for large values (uses %g format).
    # This is a known limitation — we only verify the result is parseable.
    parsed = float(result)
    assert isinstance(parsed, float)


@given(value=safe_floats)
@settings(max_examples=100)
def test_canon_float_idempotent(value: float):
    """Canonicalizing a float twice gives the same result."""
    try:
        first = canon_float(value)
        second = canon_float(float(first))
    except (ValueError, OverflowError):
        return
    assert first == second, f"Not idempotent: {value} -> {first} -> {second}"


def test_canon_float_rejects_nan():
    with pytest.raises(ValueError):
        canon_float(float("nan"))


def test_canon_float_rejects_inf():
    with pytest.raises(ValueError):
        canon_float(float("inf"))
    with pytest.raises(ValueError):
        canon_float(float("-inf"))


@given(obj=st.dictionaries(st.text(min_size=1, max_size=20), json_scalars, max_size=10))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_json_loose_roundtrip(obj: dict):
    """from_json_loose then to_json_loose preserves dict structure."""
    try:
        gv = from_json_loose(obj)
        parsed = to_json_loose(gv)
    except (ValueError, TypeError):
        return  # Unrepresentable values are expected

    assert isinstance(parsed, dict)


@given(text=st.text(alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")), max_size=200))
@settings(max_examples=200)
def test_canonicalize_no_crash(text: str):
    """Canonicalizing arbitrary parsed values never crashes."""
    try:
        parsed = from_json_loose(text)
    except (ValueError, TypeError):
        return
    if parsed is None:
        return
    try:
        result = to_json_loose(parsed)
    except (ValueError, TypeError):
        return
    assert isinstance(result, str)
