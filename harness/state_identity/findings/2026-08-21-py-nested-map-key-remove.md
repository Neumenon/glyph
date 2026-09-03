# Finding: Python `apply_patch` rejects valid nested-remove patches

> **STATUS: FIXED 2026-08-21** (same day). The defect was wider than first
> filed — three coupled bugs in `py/glyph/patch.py`:
>
> 1. `_apply_op` navigated only `FIELD` segments on maps; `diff()` emits
>    `MAP_KEY` → every depth ≥2 map path failed (sets too, not just removals).
> 2. `_parse_path` could not read the `["key"]` bracket wire syntax at all
>    (treated contents as list indices) — py couldn't parse Go/JS-emitted
>    patches, or even its own emitted text.
> 3. `_split_path_value` split op lines at the first space, truncating paths
>    whose quoted keys contain spaces.
>
> Fixes: MAP navigation accepts both segment kinds; path parser rewritten as
> a scanner honoring quoted keys + escape_string escapes; splitter is
> quote-aware. Regression tests in `py/tests/test_patch.py`
> (`TestNestedMapKeyRegression`, `TestBracketPathParsing`). Gauntlet S5
> extended with depth-2 bracket paths + space-containing key via
> `gen_inputs.py`; 8/8 scenarios pass across Go/Py/JS.
> Post-fix harness re-run: sanity trips 46 → 0; glyph-default 3000/3000
> detected, zero errors. Original analysis below preserved for record.

**Discovered by:** state_identity harness S1 sanity check (`s1_stale_patch_race.py`)
**Date:** 2026-08-21 · **Affected:** `glyph/py` 1.1.0 (`py/glyph/patch.py`)
**Scope:** Python only. Go and JS apply identical patches correctly.
**Severity:** High for py users of diff→apply round-trips; does not affect
conformance corpus (nested map-key *removal* is evidently not covered there).

## Repro (minimal)

```python
import glyph
base = {"x": {"a": 1, "b": 2}}
tgt  = {"x": {"a": 1}}                      # remove nested key "x.b" only
P = glyph.diff(glyph.from_json_loose(base), glyph.from_json_loose(tgt))
glyph.apply_patch(glyph.from_json_loose(base), P, verify_base=True)
# ValueError: cannot navigate map_key in map
```

Also reproduces when a subtree is emptied entirely:

```python
P = glyph.diff(glyph.from_json_loose({"x": {"a": 1}}),
               glyph.from_json_loose({"x": {}}))
# patch text: @patch @keys=wire @target= @base=…
# - ["x"]["a"]
# @end   → same ValueError on apply against its own true base
```

Root-level removals work (`diff({"a":1,"b":2} → {})` applies fine).

## Cross-language comparison

| impl | Diff emits | ApplyPatch(base, patch) |
|---|---|---|
| Go (`ApplyPatch`) | 1 op | **OK**, result `{"x":{"a":1}}` |
| JS (`applyPatch`) | — | **OK**, result `{"x":{"a":1}}` |
| Py (`apply_patch`) | wire-equivalent ops | **ValueError: cannot navigate map_key in map** |

## Impact in this harness

S1 sanity check ("every diff must re-apply cleanly on its true base") tripped
on 23/3000 seeded trials before any race injection — i.e. ~0.8% of random
state pairs hit this path via nested removals. These trials are counted in an
isolated `sanity-apply-on-true-base` bucket and do not affect detection/corruption rates.

## Suggested next step

Fix `_apply_op` / path navigation in `py/glyph/patch.py` for nested `-`
(map-key) ops; add conformance cases for nested removal + subtree-emptying so
the corpus closes the gap. Harness deliberately does not patch glyph itself.
