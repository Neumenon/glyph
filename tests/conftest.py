"""Pytest configuration for the repo-level cross-implementation harness.

The ``*_test.py`` files in this directory are **standalone scripts**, not pytest
modules. Each has a ``__main__`` / ``sys.exit`` entry point and shells out to the
Go / JS (and parked Rust / C) builds to check cross-language parity. Pytest's
default glob (``*_test.py``) happens to match their names, which previously caused
fixture-injection errors (``test_roundtrip(name, data)``) and
``PytestReturnNotNoneWarning`` (functions that ``return`` a bool).

Run them directly instead::

    python tests/all_impl_parity_test.py      # the cross-impl parity gate
    python tests/roundtrip_stress_test.py
    python tests/cross_impl_parity_test.py

``collect_ignore`` keeps ``pytest tests/`` free of errors and warnings without
renaming the scripts or touching their call sites. The language-specific pytest
suites live under ``py/tests/`` and are unaffected.
"""

collect_ignore = [
    "all_impl_parity_test.py",
    "cross_impl_parity_test.py",
    "roundtrip_stress_test.py",
]
