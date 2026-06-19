# GLYPH Fix Plan (Worklog)
Date: 2026-01-27
Scope: Fix pool parsing, tabular parsing correctness/robustness, schema generic parsing, pool concurrency safety, and documentation alignment.

Principles
- Atomic, committable tasks with explicit validation.
- Each sprint ends in a runnable/demoable state and builds on prior work.
- Prefer tests; if tests are not meaningful, specify alternate validation.

---

## Sprint 1 — Pool Parsing Correctness (Full GLYPH Values)
Goal: `@pool.str` and `@pool.obj` accept full GLYPH values (including spaces, structs, lists) and validate string-pool types.
Demo: `go test ./go/glyph -run Pool`

Tickets
- S1-T1: Replace whitespace tokenization with full GLYPH parsing for pool entries.
  - Files: `glyph/go/glyph/pool.go`
  - Notes: Parse entries by wrapping in `[...]`, use `ParseWithOptions` (tolerant=false), require list result.
  - Validation: `go test ./go/glyph -run PoolParse` (add test)

- S1-T2: Enforce `@pool.str` entry types are strings; allow any value for `@pool.obj`.
  - Files: `glyph/go/glyph/pool.go`
  - Validation: `go test ./go/glyph -run PoolType`

- S1-T3: Add pool parse tests for nested structs, quoted strings with spaces, lists, and round-trip via `EmitPool`.
  - Files: `glyph/go/glyph/pool_test.go`
  - Validation: `go test ./go/glyph -run PoolRoundTrip`

- S1-T4: Add pool parse error tests (unterminated entries, invalid types for `@pool.str`).
  - Files: `glyph/go/glyph/pool_test.go`
  - Validation: `go test ./go/glyph -run PoolErrors`

---

## Sprint 2 — Tabular Parsing Correctness I (Row/Cell Semantics)
Goal: Correct row parsing, inline row splitting, and cell syntax edge cases.
Demo: `go test ./go/glyph -run Tabular`

Tickets
- S2-T1: Detect and error on extra columns (leftover non-whitespace) after expected fields.
  - Files: `glyph/go/glyph/parse_tabular.go`, `glyph/go/glyph/parse_tabular_test.go`
  - Validation: `go test ./go/glyph -run TabularExtraColumns`

- S2-T2: Treat date-only `YYYY-MM-DD` as time in tabular cells.
  - Files: `glyph/go/glyph/parse_tabular.go`, `glyph/go/glyph/parse_tabular_test.go`
  - Validation: `go test ./go/glyph -run TabularDateOnly`

- S2-T3: Accept `_` and `null` as null tokens in tabular cells (in addition to `∅`).
  - Files: `glyph/go/glyph/parse_tabular.go`, `glyph/go/glyph/parse_tabular_test.go`
  - Validation: `go test ./go/glyph -run TabularNullAliases`

- S2-T4: Allow optional commas inside nested list/map cells in tabular parsing.
  - Files: `glyph/go/glyph/parse_tabular.go`, `glyph/go/glyph/parse_tabular_test.go`
  - Validation: `go test ./go/glyph -run TabularNestedCommas`

- S2-T5: Fix inline tabular row splitting to respect quoted strings and escaped pipes.
  - Files: `glyph/go/glyph/parse_tabular.go`, `glyph/go/glyph/parse_tabular_test.go`
  - Validation: `go test ./go/glyph -run InlineTabularSplit`

---

## Sprint 3 — Tabular Parsing Robustness (Reader Limits + Schema Safety)
Goal: Improve resilience to large rows and explicit schema handling.
Demo: `go test ./go/glyph -run TabularReader`

Tickets
- S3-T1: Increase `bufio.Scanner` buffer for `TabularReader` to handle large rows (e.g., embeddings).
  - Files: `glyph/go/glyph/parse_tabular.go`
  - Validation: `go test ./go/glyph -run TabularLargeRow`

- S3-T2: Return a clear error when `TabularReader` is used with a nil schema.
  - Files: `glyph/go/glyph/parse_tabular.go`, `glyph/go/glyph/parse_tabular_test.go`
  - Validation: `go test ./go/glyph -run TabularNilSchema`

---

## Sprint 4 — Schema Parsing (Parameterized Types + Inline Structs)
Goal: Correctly parse `list<T>`, `map<K,V>`, nested generics, and inline `struct{...}` types.
Demo: `go test ./go/glyph -run ParseSchemaParameterizedTypes`

Tickets
- S4-T1: Extend lexer to tokenize `<` and `>`; update token enums and stringers.
  - Files: `glyph/go/glyph/token.go`
  - Validation: `go test ./go/glyph -run TokenizeSchemaGenerics`

- S4-T2: Implement recursive `parseTypeSpec` handling for `list<T>` and `map<K,V>` with proper error cases.
  - Files: `glyph/go/glyph/parse.go`
  - Validation: `go test ./go/glyph -run ParseSchemaParameterizedTypes`

- S4-T3: Add inline `struct{...}` parsing inside type specs (e.g., `list<struct{a:int}>`).
  - Files: `glyph/go/glyph/parse.go`, `glyph/go/glyph/schema_parse_test.go`
  - Validation: `go test ./go/glyph -run ParseSchemaParameterizedTypes`

- S4-T4: Add negative tests for malformed generic syntax (missing `>`, missing type params).
  - Files: `glyph/go/glyph/schema_parse_test.go`
  - Validation: `go test ./go/glyph -run ParseSchemaParameterizedTypesErrors`

---

## Sprint 5 — Pool Concurrency Safety
Goal: Make pool operations safe for concurrent access (AutoInterner + PoolRegistry consumers).
Demo: `go test -race ./go/glyph -run PoolConcurrent` (or `go test ./go/glyph -run PoolConcurrent` if -race unavailable)

Tickets
- S5-T1: Add locking to `Pool` for `Add`, `Get`, and `String` access to `Entries`.
  - Files: `glyph/go/glyph/pool.go`
  - Validation: `go test ./go/glyph -run PoolConcurrent`

- S5-T2: Add concurrency test that calls `AutoInterner.Process` in parallel with pool resolves.
  - Files: `glyph/go/glyph/pool_test.go`
  - Validation: `go test -race ./go/glyph -run PoolConcurrent`

---

## Sprint 6 — Documentation Alignment
Goal: Sync docs with current behavior (auto-tabular default, null style, and pool parsing capabilities).
Demo: `rg -n "auto-tabular" glyph/docs/LOOSE_MODE_SPEC.md` and read updated docs.

Tickets
- S6-T1: Update `LOOSE_MODE_SPEC.md` to reflect auto-tabular enabled by default in Go canonicalization; clarify null default `_` vs pretty `∅`.
  - Files: `glyph/docs/LOOSE_MODE_SPEC.md`
  - Validation: Manual doc review; `rg -n "Auto-tabular" glyph/docs/LOOSE_MODE_SPEC.md`

- S6-T2: Update `glyph/README.md` and `glyph/docs/README.md` examples to match defaults and pool capabilities.
  - Files: `glyph/README.md`, `glyph/docs/README.md`
  - Validation: Manual doc review

---

Subagent Review (Simulated)
- Suggest adding tests for pool parsing using `@pool.obj` with nested lists/maps and quoted strings containing spaces.
- Suggest adding inline-tabular tests with quoted values that include `|` to verify splitter logic.
- Suggest explicit error messages for nil schema to aid callers.
- Suggest docs to mention tabular reader row-size limits and new buffer behavior.

Edits incorporated into Sprint plan above.

---

## Sprint 7 — Default Policy + Parity Alignment
Goal: Align default null style to `_` across implementations and enforce 50% shared-key threshold for auto-tabular; keep parity tooling standalone and correct.
Demo: `python3 tests/all_impl_parity_test.py`

Tickets
- S7-T1: Enforce ≥50% shared-key threshold (intersection/union) for auto-tabular eligibility when missing keys are allowed; reject empty-object rows.
  - Files: `glyph/go/glyph/loose.go`, `glyph/py/glyph/loose.py`
  - Validation: `go test ./go/glyph -run AutoTabular` and `python3 -m pytest py/tests/test_glyph.py`

- S7-T2: Make underscore the default null style in Python and adjust tests to match.
  - Files: `glyph/py/glyph/loose.py`, `glyph/py/tests/test_glyph.py`
  - Validation: `python3 -m pytest py/tests/test_glyph.py`

- S7-T3: Update JS tests to expect `_` for default loose canonicalization outputs (including tabular missing values).
  - Files: `glyph/js/src/glyph.test.ts`
  - Validation: `npm test` (run in `glyph/js`)

- S7-T4: Fix cross-impl parity helpers to use correct JSON bridges and in-repo paths; build Rust offline and build C lib if missing.
  - Files: `glyph/tests/all_impl_parity_test.py`, `glyph/tests/cross_impl_parity_test.py`
  - Validation: `python3 tests/all_impl_parity_test.py`

- S7-T5: Document 50% shared-key rule in loose mode spec.
  - Files: `glyph/docs/LOOSE_MODE_SPEC.md`
  - Validation: Manual doc review
