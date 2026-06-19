# GLYPH — Deep Review (2026-06-19)

Produced by a 22-agent workflow (10 audit dimensions → adversarial verification → synthesis),
then put through **two independent meta-review layers**: an internal critic agent, and a separate
`claude -p` process with read-only code access. Read Section 0 first — it reconciles the layers.

---

## 0. Meta-Review Reconciliation (read this first)

The base review (Sections 1–9 below) is **substantially accurate and safe to act on**. Three
independent passes confirmed all five highest-severity findings against the actual source. The
corrections below are the *net* result after the internal critic and the independent `claude -p`
pass disagreed and were adjudicated.

**Corrections to the base review:**

1. **`all_impl_parity_test.py` (Action #6) — BOTH bugs are real. Keep both fixes.**
   The internal critic claimed the package-name issue (`glyph-codec` vs crate `glyph-rs`) was a
   non-bug ("Cargo keys are free aliases"). The independent `claude -p` pass **overturned that**:
   for a *path* dependency, the dependency key must equal the crate name unless a `package = "…"`
   rename is given — so `glyph-codec = { path = … }` is rejected at resolution. AND line ~133 uses
   `canonicalize_loose(&v)` (returns `Result`) in `print!` without `.unwrap()`. Fix *both*.

2. **Python NullStyle divergence (Critical #1 / Action #1) — correct, but scope it.**
   The divergence is isolated to the **fingerprint / no-tabular path**. Go's `DefaultLooseCanonOpts()`
   (loose.go:344) uses `NullStyleUnderscore` too; only `NoTabularLooseCanonOpts()` / `FingerprintLoose`
   fall through to the zero-value `NullStyleSymbol` (∅). The one-line Python fix is still the highest-
   leverage change — just don't describe it as "all Go canonicalization uses ∅."

3. **Python DOES ship a real GLYPH text parser.** `py/glyph/__init__.py` exports `parse` / `parse_loose`
   (parse.py:714,720). The real weakness is narrower: the hypothesis property test (test_hypothesis.py:70)
   calls `from_json_loose` instead of `parse`, so it never exercises the parser. One-line test fix.

4. **`streaming.go:619` float fix stands**, but the "canon.go:41 does the same operation" citation is
   imprecise — canon.go:41 uses `Float64bits` for negative-zero *detection*, not byte-encoding. The fix
   (`uint64(f)` → `math.Float64bits(f)`) is correct.

**Two findings BOTH the review and the internal critic missed (surfaced by `claude -p`):**

5. **[High] Go's patch `BaseFingerprint` is itself malformed.** `WithBaseValue` (emit_patch.go:903-908)
   hashes the **with-tabular** canonical form truncated to **16 hex**, while `FingerprintLoose`
   (loose.go:128-130) hashes the **no-tabular** form to **64 hex**. So even if `ApplyPatch` *did* enforce
   the base, it could never match — the exact dual bug flagged for Rust `hash_loose`, present in Go too.

6. **[Medium] `all_impl_parity_test.py` cannot fail by construction.** `main()` only prints; there are no
   asserts, no `sys.exit(1)` on mismatch, and no `test_*` for pytest to collect. The "0/21" is non-failing
   regardless — and it uses *default* (underscore) opts, so it would not surface the fingerprint divergence
   even after the Rust build is fixed.

**Overreach to soften (don't over-apply the base review):**

- **Don't archive all six `docs/reports/*`.** Add pool-parked disclaimers to the three that reference
  GLYPH+Pool; keep the `reports/` index. (`reports/README.md` already labels them as dated snapshots.)
- **Rust is not strictly "emit-only."** It has a real `stream_validator.rs` (625+ lines) and
  `schema_evolution.rs`. It is *incomplete for conformance* (no parser/patch/GS1/pack) — say that, not "emit-only."
- **`py/glyph/decimal.py`: park/deprecate, not hard-drop** — direct importers (`from glyph.decimal import …`)
  may exist; absence from `__init__.py` alone doesn't justify deletion.

---

(Base review follows verbatim — apply the Section 0 corrections on top of it.)

# GLYPH Codebase — Definitive Deep Review

---

## 1. Executive Summary

GLYPH is a technically ambitious project with a genuinely strong core: the Go implementation is production-grade, the Go–JS golden-corpus conformance suite (50 cases, byte-for-byte) is the strongest cross-language correctness signal in the codebase, and the overall design — canonical form, fingerprint, patch, GS1 streaming — is coherent and well-motivated. The single biggest strength is the Go implementation itself: zero TODO/FIXME in production code, industrial safety tests, performance cliff guards, and a streaming proof test that encodes a real product claim.

The single biggest risk is that the README's three headline invariants are all partially false in practice. "Conformance impls agree byte-for-byte" is only true for Go and JS; Python diverges on 5 of 50 corpus cases. "fingerprint(x) = SHA256(canonical_no_tabular_bytes(x)) for Go/Python/JS" is false for any null-containing value (Python uses NullStyle.UNDERSCORE in no-tabular opts while Go/JS use NullStyleSymbol, producing different SHA-256 digests). "patch applies iff current\_fingerprint == patch.base" is false for every implementation — ApplyPatch in Go, JS, and Python ignores BaseFingerprint entirely at apply time; Python's Patch dataclass has no such field at all.

The headline "what to drop" decision: **remove js/dist/ from git tracking** (72 tracked-while-gitignored files, 527 KB); **drop or park the C port as a published surface** (no GLYPH text parser, SHA-256 documented but djb2 implemented, u128\_mul10 carry bug, tabular format differs from Python); and **strongly consider parking the Rust port** from the conformance surface (no parser, fingerprint\_loose returns canonical string not hash, hash\_loose truncates to 16 hex chars and hashes the wrong canonical variant, float formatting diverges for repeating decimals, not published on crates.io). The 5-language parity claim costs more credibility than it earns when two of those five ports cannot participate in cross-language conformance testing at all.

---

## 2. Per-Language Verdict Table

| Language | Maturity | Feature completeness vs README | Test quality | Verdict |
|---|---|---|---|---|
| **Go** | Reference | Full surface: loose, pack, patch, GS1 stream, schema, schema\_evolution, streaming validator | 528 pass / 7 skip; industrial safety + fuzz + perf cliff tests; two large coverage-boost files inflate numbers but real assertions exist | **Keep** — reference implementation; fix float-truncation bug in streaming.go:619, add depth guard to batch parser |
| **Python** | Solid | Missing: Pack/packed layer, GS1 framing. Present: loose, patch (no @base enforcement), schema, schema\_evolution, streaming validator | 375 pass, 88% overall; hypothesis test calls wrong function; no golden corpus cross-check | **Keep-but-fix** — fix null NullStyle in no\_tabular opts, add float canon parity, wire into golden corpus |
| **JS/TS** | Solid | Full surface except SchemaContext; has GS1 stream, patch (@base not enforced at apply), schema\_evolution (zero tests), streaming validator | 477 pass; 50 golden-file cross-checks vs Go corpus; schema\_evolution untested; estimateTokens broken | **Keep-but-fix** — fix canonTime regex in emit.ts:32, fix schema hash (djb2 vs SHA-256[:16]), remove dist/ from git, add schema\_evolution tests |
| **Rust** | Partial | Loose emit only; no parser, no patch, no GS1, no pack. fingerprint\_loose returns canonical string; hash\_loose returns 16-char truncated SHA-256 of wrong canonical variant; float formatting diverges at 15th decimal digit. Not published on crates.io | 167 pass (154 unit + 12 truth table + 1 doctest); all\_impl\_parity\_test.py broken for Rust (wrong package name) | **Consider dropping** from published surface — re-scope as internal emit-only utility if kept |
| **C** | Partial | Loose emit only; no GLYPH text parser; no patch, no GS1, no pack. glyph\_hash\_loose documents SHA-256, implements djb2. u128\_mul10 carry bug for >19-digit decimals. gmtime() NULL-deref on out-of-range times. int64\_t formatted with %ld. Not a published package | 192 pass; truth\_table test file exists but not wired into Makefile; no cross-language corpus | **Consider dropping** from published surface — narrowly useful as emit-only embedder but cannot participate in conformance |

---

## 3. What Is STRONG

**Go–JS golden corpus parity (50 cases).** `js/src/glyph.test.ts:919-944` reads `go/glyph/testdata/loose_json/` directly and asserts byte-for-byte canonical equality against the `.want` golden files. All 50 cases pass. This is the only real cross-language conformance evidence in the codebase and it is strong.

**Go industrial safety tests.** `go/glyph/industrial_safety_test.go` covers parser bombs (5000-deep nested maps/lists/structs), 10 MB strings, 50 MB lists, 100K-key maps, unterminated structure recovery, Unicode/UTF-8 edge cases, and `FuzzParse`/`FuzzFromJSONLoose` targets with seed corpus. All pass. The `mustNotPanic` wrapper catches crashes; the test suite is genuinely adversarial.

**Go streaming proof test.** `go/glyph/streaming_proof_test.go:198-205` demonstrates and asserts that tolerant GLYPH parsing extracts named fields from partial streaming input 4 chunks earlier than `json.Unmarshal`. The assertion would fail on parser regression. This is a test that encodes a product claim.

**Go performance cliff detection.** `go/glyph/perf_cliff_test.go:25` uses wall-clock ratio guards (>20x slowdown on depth doubling fails the test) and 5-second absolute ceilings for wide maps and large lists. Algorithmic regressions are caught automatically.

**Go `sync.Pool` hot-path optimization.** `go/glyph/loose.go:39-73` uses three pools (map entries, column slices, strings.Builder with 64 KB cap guard) to reduce GC pressure in the canonical/fingerprint hot path. The design is correct and non-trivial.

**Go GS1 stream as a fully decoupled package.** `go/stream/` implements complete GS1-T framing (reader/writer/CRC-32/SHA-256 state hash/cursor/types) without importing the `glyph` core package. Users can take the codec without the framing layer; the dependency direction is clean.

**Zero TODO/FIXME in Go production code.** Grep of all non-test `.go` files for `TODO|FIXME|HACK|XXX` returns zero hits. The one known stub (`@schema#hash` lookup in `parse.go:471`) is marked with an explicit warning comment, not silently skipped.

**JS GS1 stream implementation.** `js/src/stream/` (~1140 source lines) is a complete, independent implementation of GS1-T framing. Go and JS independently enforce CRC-32 IEEE and SEQ monotonicity. These two ports alone provide cross-language GS1 interop.

**Go blob/pool decoupling is complete.** Commit `b14f5e9` cleanly removed all blob/pool types from `go/glyph/`. Grep for `TypeBlob|TypePoolRef|blobVal|poolRef` in `go/glyph/*.go` returns zero hits.

---

## 4. What Is WEAK

### Critical

**Python NullStyle in no-tabular opts differs from Go/JS.**
`py/glyph/loose.py:70-72` creates `LooseCanonOpts(auto_tabular=False)` which inherits the dataclass default `null_style: NullStyle = NullStyle.UNDERSCORE` (line 54). Go's `NoTabularLooseCanonOpts()` at `go/glyph/loose.go:375-381` leaves NullStyle unset, inheriting the zero-value `NullStyleSymbol` (∅). JS's `noTabularLooseCanonOpts()` at `js/src/loose.ts:135-141` explicitly sets `nullStyle: 'symbol'`. Result: `FingerprintLoose({a:1, b:null})` = `cde00fb3...` in Go/JS, `9202d6f0...` in Python. README line 116 claims "byte-identical across Go, Python, and JavaScript." This claim is false for any null-containing value.
**Fix:** Set `null_style=NullStyle.SYMBOL` explicitly in `no_tabular_loose_canon_opts()` at `py/glyph/loose.py:70`.

**C glyph\_hash\_loose implements djb2, documented as SHA-256.**
`c/glyph-codec/src/json.c:598-617` implements a djb2 hash (seed 5381). The source comment says "Simple hash for demonstration (not cryptographic!)." The public header `c/glyph-codec/include/glyph.h:222` documents it as "Get SHA-256 hash (first 16 hex chars)." The test at `test_glyph.c:518-525` only checks `strlen(h) == 16`. A C-generated patch base fingerprint will never match a Go/JS/Python fingerprint.
**Fix:** Implement real SHA-256 (link libcrypto or vendor a single-file implementation) or rename to `glyph_hash_djb2_loose()` and remove the SHA-256 claim from the header.

### High

**float truncation bug in Go streaming.go.**
`go/glyph/streaming.go:619` encodes a float64 as `binary.LittleEndian.PutUint64(tmp[:], uint64(f))`. The cast `uint64(f)` is a numeric truncation (3.14 → 3), not a bit-reinterpretation. The correct call is `math.Float64bits(f)`. `go/glyph/canon.go:41` uses `math.Float64bits` correctly for the same operation. Every non-integer float encoded through `EncodeDictFrame` is silently corrupted.
**Fix:** Replace `uint64(f)` with `math.Float64bits(f)` at `streaming.go:619`.

**Rust fingerprint\_loose returns canonical string, not SHA-256.**
`rust/glyph-codec/src/loose.rs:98-100`: `fingerprint_loose` is a direct alias for `canonicalize_loose`, returning the canonical GLYPH string. `hash_loose` at lines 105-111 does compute SHA-256 but truncates to first 8 bytes (16 hex chars) AND hashes the with-tabular canonical form — doubly wrong relative to Go/Python/JS (which use no-tabular form and full 64 hex chars). Any caller expecting a hex fingerprint gets raw GLYPH text from `fingerprint_loose`.
**Fix:** Implement `fingerprint_loose` as `sha256(canonicalize_loose_no_tabular(v))` returning 64 hex chars, matching Go/JS/Python semantics.

**Python float canonicalization divergence from Go/JS.**
Python's `from_json_loose` does not promote integer-valued floats to Int type (`json.loads('1e3')` yields Python float 1000.0, stored as `GValue.float_`), while Go's `fromJSONValue` explicitly checks and promotes integer-valued floats within `[-2^53, 2^53]` to Int. This causes type-level divergence, not just format divergence. Additionally, `py/tests/test_truth_table.py:58-60` explicitly acknowledges that Python's `canon_float` preserves `.0` suffix unlike Go, calling both "acceptable canonical forms" — directly contradicting the README's cross-impl parity claim.

**Go batch parser has no depth guard.**
`go/glyph/parse.go`'s `parseValue`/`parseList`/`parseMap`/`parseStruct`/`parseSum` are mutually recursive with no depth counter. The only `depth` variable in `parse.go` is inside `skipSchemaBlock` (lines 489-496), an iterative helper. At depth 100,000, goroutine stack grows to ~62 MB. `industrial_safety_test.go:36-91` uses `mustNotPanic` at depth 5000 — the test passes because Go doesn't crash, not because there is a limit.
**Fix:** Add a depth counter to the Parser struct (as in the incremental parser at `go/glyph/incremental.go:699`) and reject at 128.

**ApplyPatch ignores BaseFingerprint in all three implementing ports.**
README line 150: "A receiver applies the patch only if its current state's fingerprint matches base." This is false for every implementation: `go/glyph/emit_patch.go:603-621` applies ops unconditionally; `js/src/patch.ts:782-790` applies unconditionally; `py/glyph/patch.py:59-63` has no `base_fingerprint` field in the Patch dataclass at all and `parse_patch()` at `py/glyph/patch.py:83-90` has no `@base=` branch. The only base check anywhere is in the GS1 stream layer (`go/stream/cursor.go:102`).

**Cross-impl tests in Go skip in a clean checkout.**
`go/glyph/cross_impl_test.go:60` checks for `../js/dist/index.js` which resolves to `go/js/dist/index.js` — a path that does not exist. Seven top-level cross-impl tests (`TestCrossImplTeamRoundtrip`, `TestCrossImplMatchRoundtrip`, `TestCrossImplBitmapRoundtrip`, `TestCrossImplPatchRoundtrip`, `TestCrossImplPatchParseApply`, `TestCrossImplTabularParse`, `TestCrossImplVersion`) permanently skip in a clean checkout. The actual dist is at `js/dist/index.js` (two levels up, not one).

**25 Go `TestTripleImpl` subtests permanently skip.**
`go/glyph/test/py/canon.py` does not exist; only `test/js/canon.mjs` exists. All `TestTripleImpl_CanonicalizeLoose` subtests skip with "stat test/py/canon.py: no such file or directory." (`go/glyph/loose_test.go:1573`, confirmed).

**u128\_mul10 carry calculation wrong in C.**
`c/glyph-codec/src/decimal128.c:53-68`: for `l = UINT64_MAX`, the function returns `high=24` where the correct value is 9 (verified with `__uint128_t` cross-check). For `l = 9999999999999999999ULL`, returns `high=14` vs correct `high=5`. Any decimal128 value with more than 19 significant digits is silently corrupted.

**GS1 v==1 MUST requirement not enforced.**
`docs/GS1_SPEC.md` section 3.1: "v MUST be 1; reject frames with v != 1." `go/stream/gs1t_reader.go:131-137` parses `v` into `frame.Version` but has no enforcement check. JS `gs1t.ts` is the same.

**GS1 frame reader has unbounded header read (DoS vector).**
`go/stream/gs1t_reader.go:39` uses `bufio.NewReader` with the default 4096-byte buffer. Line 53 calls `ReadString('\n')` which grows the buffer without limit when the header line exceeds 4096 bytes. `MaxPayload` (line 69) only gates the body, not the header. A sender sending a malformed headerline with no newline causes unbounded allocation.

**Stream validator depth gap (Go, JS, Python, Rust).**
Only the C stream validator has a hard 128-depth cap (`c/glyph-codec/src/stream_validator.c:19`, enforced at line 865). Go's `stream_validator.go:147` has a `depth` field but no comparison against any limit. Rust, JS, and Python stream validators have no depth cap at all. The audit originally claimed all five ports enforce depth limits — this is false for four of them.

### Medium

**JS canonTime bug in emit.ts.**
`js/src/emit.ts:32` uses `.replace('.000Z', 'Z')` which only strips milliseconds when they are exactly `.000`. `js/src/loose.ts:242` correctly uses `.replace(/\\.\\d{3}Z$/, 'Z')`. Any `Date` with non-zero milliseconds (e.g. `2025-01-01T12:00:00.123Z`) emitted through the packed/emit path retains the `.123Z` suffix, diverging from Go and Python which always truncate to seconds. All existing tests use zero-ms dates, so this is uncaught.
**Fix:** Change `emit.ts:32` to `.replace(/\\.\\d{3}Z$/, 'Z')`.

**JS Schema hash algorithm mismatch with Go.**
`js/src/schema.ts:108-117` uses a 32-bit djb2-like hash producing 8 hex chars. `go/glyph/schema.go:238-242` uses SHA-256 truncated to first 16 bytes (32 hex chars). @schema# hashes in patch headers will never match between a JS PatchBuilder and a Go receiver.
**Fix:** Replace JS `schema.computeHash` with SHA-256[:16] using Node's crypto module (already imported in `loose.ts`).

**Go has two hash functions with similar names.**
`CanonicalHash` at `go/glyph/emit.go:369-386` uses FNV-1a and returns 16 hex chars. `FingerprintLoose` at `go/glyph/loose.go:127-131` uses SHA-256 and returns 64 hex chars. Both are exported and both accept `*GValue`. `CanonicalHash` is called only in `glyph_test.go:639-640` — it has no production callers. The name implies it is the canonical fingerprint; it is not.

**Go `escapeString` vs `quoteString` diverge on control characters.**
`escapeString` at `go/glyph/emit.go:322-342` (used by `Emit()`) passes control chars below 0x20 through raw. `quoteString` at `go/glyph/canon.go:155-190` (used by `CanonicalizeLoose()`) emits `\u00XX` for the same bytes. `Emit(Str("\x01"))` and `CanonicalizeLoose(Str("\x01"))` produce different wire bytes.

**Python hypothesis test calls wrong function.**
`py/tests/test_hypothesis.py:70` calls `from_json_loose(text)` on arbitrary text, not `parse(text)`. `from_json_loose` on a string simply wraps it in `GValue.str_()` — it cannot crash regardless of input. The property test does not exercise the GLYPH parser at all.

**Rust bare-safe allows `@` and `:` as identifier characters.**
`rust/glyph-codec/src/loose.rs:219` includes `@` and `:` in the safe-char set. LOOSE\_MODE\_SPEC.md defines bare-safe as `[a-zA-Z0-9._-]` only. Go/JS/Python enforce this correctly. Values like `@frame` or `a:b` would be emitted unquoted by Rust and then parsed differently in other ports.

**Rust and C missing `none` and `nil` from reserved words.**
`rust/glyph-codec/src/loose.rs:212` reserved array contains only `["t","f","true","false","null","_"]`. `c/glyph-codec/src/glyph.c:406-408` similarly omits `none` and `nil`. Go's `canon.go:93` and JS both include all 9 reserved bare values. Strings whose content is `none` or `nil` would be emitted unquoted by Rust/C and then parsed as bare tokens by Go/JS/Python.

**Rust and C default max\_cols is 64, not 20.**
LOOSE\_MODE\_SPEC.md specifies `max_cols=20`. Go (`loose.go:345`), Python (`loose.py:56`), and JS (`loose.ts:123`) all use 20. Rust (`loose.rs:42`) and C (`glyph.c:366`) use 64. Tables with 21–64 columns are tabular in Rust/C but flat maps in Go/Python/JS.

**`all_impl_parity_test.py` always reports 0/21 due to Rust build bugs.**
`tests/all_impl_parity_test.py:119` uses package name `glyph-codec` (wrong; actual crate name is `glyph-rs` per `rust/glyph-codec/Cargo.toml:2`). Additionally the generated Rust code calls `canonicalize_loose(&v)` as if it returns `String`, but it returns `Result<String, GlyphError>`. Both bugs cause Rust compilation to fail before tests run, making the harness report 0/21 despite Go/Python/JS/C agreeing on all 21 cases.

**Python `schema_evolution.py` and `decimal.py` not integrated with GValue.**
Both modules operate on raw Python dicts and are not exported from `py/glyph/__init__.py`. Neither is reachable from any codec path. The Go equivalents are similarly dict-based (`schema_evolution.go` operates on `map[string]interface{}`), so this is a shared limitation, not a Python-specific gap.

**`gmtime()` NULL dereference in C on out-of-range GLYPH\_TIME values.**
`c/glyph-codec/src/glyph.c:773-774` and `c/glyph-codec/src/json.c:575-576` use the return of `gmtime()` directly in `strftime()` without a NULL check. No `glyph_time()` constructor exists in `glyph.h` and no tests cover `GLYPH_TIME`, so the bug is latent but reachable if `time_val` is set directly.

### Low

**Python bare-safe adds NaN and Inf as extra reserved words.**
`py/glyph/loose.py:88` includes `NaN` and `Inf` in `RESERVED_WORDS`. The spec does not list them. Go/JS would emit strings `NaN`/`Inf` bare while Python quotes them, causing parse divergence.

**Go `coverage_boost_test.go` files inflate coverage without reliable assertions.**
`go/glyph/coverage_boost_test.go:36` uses `_ = canonValue(tt.val)` — a discard pattern with no assertion. The files do contain real `t.Errorf` assertions elsewhere (confirmed: 150 and 147 respectively), but the named "coverage boost" sections exist specifically to exercise code without verifying output correctness. These slow the test run and misrepresent coverage quality.

**3 Go equivalence class subtests are stubs.**
`testdata/equivalence_classes.json` entries for `whitespace_variants`, `key_order_invariance`, and `escape_variants_string` have zero inputs or empty canonical fields. At runtime these emit "unhandled equivalence class type" and skip.

**Python negative-zero branch is unreachable.**
`py/glyph/loose.py:118-119`: the `if math.copysign(1.0, f) < 0 and f == 0` branch is dead because `if f == 0` at line 115 already catches both `0.0` and `-0.0` in Python (`-0.0 == 0` is `True`).

**`@schema#hash` lookup is silently unresolved in Go.**
`go/glyph/parse.go:471` emits a warning and then silently continues. The `@schema#hash` annotation is consumed without resolution. This also affects the `parse(emit(x)) = x` roundtrip claim for values containing schema annotations.

**`parse.go:115,120` silently discard parse errors.**
`strconv.ParseInt` and `strconv.ParseFloat` errors are discarded with `_`. Overflow of a 19+-digit integer produces a silently wrong value.

---

## 5. Spec ↔ Code Drift — Ranked

**1. README fingerprint parity claim is false.** Line 116: "The same input produces the same 64-char hex digest in the Go, Python, and JavaScript / TypeScript implementations." False for any null-containing value due to Python NullStyle default mismatch. False for floats in the 1e12–1e14 range where Go's `strconv.FormatFloat('g',-1,64)` and JS/Python's exp-threshold rule diverge (divergence begins at 1e12, not 1e13 as previously stated).

**2. README patch base enforcement claim is false for all ports.** Lines 150, 190: "patch applies iff current\_fingerprint == patch.base." No implementation enforces this at apply time. Python lacks the field entirely.

**3. LOOSE\_MODE\_SPEC.md float rule is internally contradictory.** Line 29: "Shortest roundtrip, e (not E)." Line 36: "Use exponential when exp < -4 or exp >= 15." These rules differ for 1e12–1e14. SPECIFICATIONS.md example "100000000000000 → 1e+14" only makes sense under shortest-roundtrip semantics, not the threshold rule. Three implementations use the threshold rule; one (Go) uses shortest-roundtrip.

**4. LOOSE\_MODE\_SPEC.md documents Python APIs that do not exist.** The Python section documents `new_schema_context()`, `SchemaRegistry`, `parse_loose_payload()`, and `PatchBuilder.with_base_value()`. None of these exist in `py/glyph/`.

**5. GS1 framing claimed as a product layer, only in Go and JS.** The README layers table and API\_REFERENCE.md present GS1 as a uniform cross-language layer. Python, Rust, and C have zero GS1 implementation. API\_REFERENCE.md says GS1 streaming is something "every implementation revolves around."

**6. GS1\_SPEC.md v==1 MUST requirement is unenforced.** Section 3.1 says "v MUST be 1; reject frames with v != 1." Neither Go's `gs1t_reader.go` nor JS's `gs1t.ts` reject non-1 version values.

**7. Python tabular header omits rows/cols; Go/JS/Rust/C include them.** LOOSE\_MODE\_SPEC.md says rows/cols "can be added" (optional). Python emits `@tab _ [col1 col2]`; Go/JS/Rust/C emit `@tab _ rows=N cols=M [col1 col2]`. This produces byte-for-byte divergence on the 50-case corpus (`044_array_of_objects.json`). Python is spec-compliant but the corpus treats Go/JS as canonical.

**8. `cargo add glyph-rs` is unexecutable.** `rust/glyph-codec/Cargo.toml` has no `publish = false` but glyph-rs is not published on crates.io. The README install matrix presents this as a working command.

**9. Rust max\_cols default is 64, spec says 20.** Covered under weaknesses; spec divergence on a concrete default value.

**10. Go `Parse('_')` returns `Str('_')`, not `Null()`.** `token.go:487` classifies `_` as `isIdentStart`. `parseValue` falls through to `Str(name)`. Only `ParseLoosePayload` (via `parseLooseValue`) correctly handles `_` → `Null()`. The roundtrip `parse(emit(null))` fails when going through `Parse()`.

---

## 6. Documentation — Per-File Table

| Path | Status | Action |
|---|---|---|
| `README.md` | Partially outdated — fingerprint parity and patch enforcement claims are false | **Refresh** — scope fingerprint claim, qualify patch claim, note Rust/C are not conformance ports |
| `docs/QUICKSTART.md` | Accurate, examples verified runnable | **Keep** |
| `docs/LOOSE_MODE_SPEC.md` | Float rule self-contradicts; Python API section documents nonexistent functions | **Refresh** — pick one float rule, remove nonexistent Python API section |
| `docs/SPECIFICATIONS.md` | Float example contradicts body text; cross-impl parity claim overstated | **Refresh** — align float example, scope parity claim |
| `docs/GS1_SPEC.md` | Date field "2025-06-20" predates first commit (2026-01-13); v==1 enforcement not called out as missing | **Refresh** — fix date, note v==1 not yet enforced |
| `docs/API_REFERENCE.md` | GS1 streaming listed as cross-language; Rust/C fingerprint deviation understated | **Refresh** — add language-scope annotations to GS1 and fingerprint sections |
| `docs/GLYPH_FILE_FORMAT.md` | Orphaned — zero inbound links from any active doc; Shard v2 context has no implementation | **Refresh** — add to `docs/README.md` index, or add "Status: Not implemented" to Shard v2 section |
| `docs/GUIDE.md` | Links to `docs/archive/COOKBOOK.md` at line 594 — that file uses stale API | **Keep** — update the linked archive COOKBOOK or note link is to historical reference |
| `docs/COOKBOOK.md` | Active; mostly current but `model='your-model'` placeholder at line 69 | **Refresh** — replace placeholder with current model name or doc link |
| `docs/README.md` | Says "DEMO\_README.md / DEMO\_QUICK\_REFERENCE.md — legacy demo material (removed)" but they exist in `attic/agents/` | **Refresh** — change "removed" to "moved to attic/" |
| `docs/archive/COOKBOOK.md` | 68-line diff from active COOKBOOK; uses stale `registry.register` API; linked from `docs/GUIDE.md:594` | **Refresh** — add header banner noting stale API, or replace link in GUIDE.md with note about historical API |
| `docs/archive/README.md:66` | Broken link to `../AGENTS.md` — file is at `attic/docs/AGENTS.md` | **Refresh** — fix link or remove line |
| `docs/archive/BLOB_POOL_SPEC.md` | Spec for parked pool subsystem; already in archive | **Archive** — no action needed, already scoped correctly |
| `docs/archive/SUBSTRATE_COMPARISON.md` | Pool-centric benchmark; pool is parked | **Archive** — no action needed |
| `docs/reports/BENCHMARK_INDEX.md` | Three broken links (SUBSTRATE\_COMPARISON.md in wrong dir, GLYPH\_VALUE\_REPORT.html nonexistent, `benchmark/` dir nonexistent); sjson/ running instructions for nonexistent dir; pool headline numbers lack disclaimer | **Delete** — `docs/reports/README.md` covers the same ground; broken links add noise |
| `docs/reports/README.md` | Already self-labels reports as "dated research snapshots"; adequate disclaimer | **Keep** — add one-sentence note that pool results use parked subsystem |
| `docs/reports/CODEC_BENCHMARK_REPORT.md` | Recommends "Use GLYPH+Pool" (parked); dated "December 25, 2024" predating first commit | **Archive** — move to `docs/archive/` |
| `docs/reports/BENCH_2025-12-20.md` | Frozen snapshot; not indexed in `docs/reports/README.md` | **Archive** — add to index or move to `docs/archive/` |
| `docs/reports/LLM_ACCURACY_REPORT.md` | Dated "December 25, 2024"; compares against ZON/TOON formats not in this repo | **Archive** — move to `docs/archive/` |
| `docs/reports/OPTIMIZATION_REPORT.md`, `STREAMING_VALIDATION_REPORT.md`, `TOOL_CALL_REPORT.md` | Dated snapshots; pool references without disclaimer | **Archive** or add disclaimer |
| `explainer.html` (repo root) | @pool presented as a live core feature with full usage section; no disclaimer; gitignored correctly (not tracked) | **Not a git concern** — file is gitignored; if it surfaces publicly, add pool-parked disclaimer |
| `docs/visual-guide.html` | Tracked, actively linked; not gitignored (unlike `explainer.html`); intentionally maintained | **Keep** — consistent policy with explainer.html would mean gitignoring it, but it is clearly intentionally tracked |
| `js/STREAMING_VALIDATOR_PARITY.md:124` | Imports from `'glyph-codec'` (old npm name); current name is `cowrie-glyph` | **Refresh** — one-line fix |
| `js/STREAMING_VALIDATOR_PARITY.md:236` | Says "59 tests"; actual count is 63 | **Refresh** — update count or remove specific number |
| `go/glyph/loose.go:122` | Doc comment claims "byte-identical across Go, Python, and JS" for fingerprint | **Refresh** — scope to "non-null values" until Python NullStyle fix is deployed |
| `rust/glyph-codec/README.md` | Install snippet implies crate is on crates.io; caveat buried at end | **Refresh** — move caveat before install block, add git-dependency syntax |
| `c/glyph-codec/include/glyph.h:222` | Documents djb2 as SHA-256 | **Refresh** — correct the comment |
| `WORKLOG.md` (repo root) | Sprint plan for completed/parked pool-parsing work; no inbound references | **Delete** — sprint history belongs in commit messages and issues |

---

## 7. Formats & Artifacts to Drop

### Git: Remove from tracking

```bash
# 72 tracked-while-gitignored compiled JS files (527 KB)
git rm -r --cached js/dist/
# Root .gitignore already has 'dist/' at line 5 — no .gitignore change needed
```

Risk: npm consumers install from the registry where `dist/` is included via `package.json` `"files": ["dist"]`. The `prepublishOnly` hook (`npm run clean && npm run build && npm run test`) rebuilds dist/ before every publish, so removing from git does not affect publishing. Any consumer who clones and directly requires `dist/` without installing would break — but that usage pattern is already wrong.

```bash
# Sprint plan for parked work, no inbound references
git rm WORKLOG.md
```

### .gitignore additions

```
*.tsbuildinfo
js/coverage/
```

(Note: `js/coverage/` is already excluded by the existing `coverage/` entry, but making it explicit is cleaner. `*.tsbuildinfo` is not yet on disk but is a TypeScript incremental build cache that should not be committed.)

### Docs to delete (git rm)

```bash
git rm docs/reports/BENCHMARK_INDEX.md     # three broken links, superseded by reports/README.md
```

### Docs to archive (git mv to docs/archive/)

```bash
git mv docs/reports/CODEC_BENCHMARK_REPORT.md docs/archive/
git mv docs/reports/BENCH_2025-12-20.md docs/archive/
git mv docs/reports/LLM_ACCURACY_REPORT.md docs/archive/
git mv docs/reports/OPTIMIZATION_REPORT.md docs/archive/
git mv docs/reports/STREAMING_VALIDATION_REPORT.md docs/archive/
git mv docs/reports/TOOL_CALL_REPORT.md docs/archive/
```

Then add a one-sentence note to `docs/reports/README.md`: "Historical benchmark snapshots have been moved to `docs/archive/`; reports referencing GLYPH+Pool use the blob/pool subsystem parked on 2026-04-30."

### Language ports — dropping/parking recommendation

**Rust (`rust/glyph-codec/`):** Recommend removing from the conformance surface and install matrix. The Rust port cannot participate in cross-language conformance testing (no parser, no golden corpus wiring). Its published install command (`cargo add glyph-rs`) fails. Its fingerprint API is semantically incompatible with every other port. It is missing patch, GS1, and pack. If kept, park it explicitly as "emit-only, not a conformance port" in the README and Rust README, add `publish = false` to `Cargo.toml` until it is actually published, and fix `hash_loose` to use the no-tabular canonical form and return 64 hex chars.

Risk of dropping: low — not published on crates.io, no known downstream consumers.

**C (`c/glyph-codec/`):** Recommend removing from the conformance surface. No GLYPH text parser exists, so `parse(emit(x)) = x` is untestable. The `glyph_hash_loose` SHA-256 claim is false. `u128_mul10` has a verified carry bug for >19-digit decimals. Tabular format includes `rows=/cols=` that Python omits. Pattern validation in stream\_validator is a silent no-op. If kept as an embed-only emitter (legitimate use case), scope it explicitly in the README as "emit-only, no parser, no conformance testing" and fix the hash claim and `u128_mul10`.

Risk of dropping from the install matrix: zero — C is "build-from-source" with no published package to deprecate.

### Features to park or remove

| What | Where | Action | Risk |
|---|---|---|---|
| `CanonicalHash` | `go/glyph/emit.go:369-386` | Drop — FNV-1a, zero production callers, misleading name | Zero callers outside `glyph_test.go` |
| `estimateTokens` / `compareTokens` | `js/src/index.ts:251-271` | Drop — whitespace-split tokenizer produces -733.3% savings in own tests | Low; remove from public API |
| `schema_evolution.ts` (JS) | `js/src/schema_evolution.ts` | Archive (demote from public API) — 528 lines, zero tests, exported in index.ts | Callers using VersionedSchema would break |
| `EncodeDictFrame` / `StreamDict` / `StreamSession` | `go/glyph/streaming.go` | Archive — undocumented, no spec, no other-language equivalent; float truncation bug | No production callers; used in benchmark/tests only |
| `EmitTokenAware` / GLYPH-T format | `go/glyph/token_aware.go` | Archive — no spec, no cross-language equivalent, zero production callers (only test files) | Safe |
| `GLYPH_FILE_FORMAT.md` Shard v2 context | `docs/GLYPH_FILE_FORMAT.md` | Mark "Status: Not implemented" — no implementation in any port | No callers |
| `attic/agents/` demo files | `attic/agents/DEMO_README.md`, `DEMO_QUICK_REFERENCE.md`, `agent-showcase.html`, `demo-ui.html` | Drop from attic — explicitly marked "legacy demo material (removed)" in docs/README.md | None; git history preserves |
| `docs/archive/COOKBOOK.md` stale API | `docs/archive/COOKBOOK.md` | Add header banner noting stale API and rename link target in GUIDE.md | GUIDE.md:594 links to it; do not delete without updating that link |
| `py/glyph/decimal.py` | `py/glyph/decimal.py` | Archive — not in `__init__.py` exports, not reachable from any codec path | Low; any `from glyph.decimal import Decimal128` callers break |
| `coverage_boost_test.go`, `coverage_boost2_test.go` | `go/glyph/` | Consider dropping named "coverage boost" discard sections — keep real assertion sections | Coverage percentage will drop; no correctness risk |

---

## 8. Prioritized Action Plan

**1. Fix Python NullStyle default in `no_tabular_loose_canon_opts()`.** One-line fix at `py/glyph/loose.py:70`: `LooseCanonOpts(auto_tabular=False, null_style=NullStyle.SYMBOL)`. This restores the cross-lang fingerprint claim for null-containing values and is the highest-leverage single fix in the codebase.

**2. Remove `js/dist/` from git tracking.** `git rm -r --cached js/dist/`. The CI publish step already rebuilds from source. Zero functional risk. Removes 72 tracked-while-gitignored files and ends the stale-build-artifact problem permanently.

**3. Fix float-truncation bug in `go/glyph/streaming.go:619`.** Replace `uint64(f)` with `math.Float64bits(f)`. One character change; verified regression by comparison with `canon.go:41`.

**4. Fix `go/glyph/cross_impl_test.go:60` jsDistPath.** Change `filepath.Join("..", "js", "dist", "index.js")` to `filepath.Join("..", "..", "js", "dist", "index.js")`. This unblocks the 7 permanently-skipping Go cross-impl tests.

**5. Create `go/glyph/test/py/canon.py`.** Wire the 25 `TestTripleImpl_CanonicalizeLoose` subtests that currently skip. The `canon.mjs` at `go/glyph/test/js/canon.mjs:30` provides the template — mirror it in Python using `subprocess`.

**6. Fix `all_impl_parity_test.py` Rust package name and function signature.** At `tests/all_impl_parity_test.py:119`, change `glyph-codec` to `glyph-rs`. At line 130, change `canonicalize_loose(&v)` to `canonicalize_loose(&v).unwrap()`. This makes the 0/21 harness actually test Go/Python/JS/C parity.

**7. Wire Python into the golden corpus.** Add a pytest parameterized test that reads `go/glyph/testdata/loose_json/cases/*.json`, converts via `from_json_loose`, and compares `canonicalize_loose_no_tabular` output against `golden/*.want` files. The float `.0` and null NullStyle bugs (items 1 above and float alignment below) would immediately surface as explicit failures rather than silent divergences.

**8. Resolve the float canonicalization rule.** Pick one: shortest-roundtrip (`'g'` format, matches Go and the SPECIFICATIONS.md example) or threshold (exp < -4 or >= 15, matches Python and JS). Update LOOSE\_MODE\_SPEC.md to remove the self-contradiction. Update the non-conforming implementations. Add a golden test covering values in the 1e12–1e14 range.

**9. Fix JS canonTime regex in `emit.ts:32`.** Change `.replace('.000Z', 'Z')` to `.replace(/\\.\\d{3}Z$/, 'Z')`. Add a test with a non-zero-ms Date.

**10. Add depth guard to Go batch parser.** Add a `depth int` field to the Parser struct; increment on every recursive call; reject at 128 with a parse error. Mirror the existing pattern in `go/glyph/incremental.go:699`.

**11. Fix GS1 v==1 enforcement in Go and JS.** After parsing the `v` field in `go/stream/gs1t_reader.go:131` and `js/src/stream/gs1t.ts`, add a check that returns a parse error when `v != 1`.

**12. Add GS1 header line-length cap.** In `go/stream/gs1t_reader.go:39`, replace `bufio.NewReader(r)` with `bufio.NewReaderSize(r, MaxHeaderSize)` where `MaxHeaderSize` is a configurable constant (suggest 64 KB). This closes the DoS vector on untrusted GS1 streams.

**13. Fix Rust `hash_loose` to use no-tabular canonical form and return 64 hex chars.** `rust/glyph-codec/src/loose.rs:105-111`: change to hash `canonicalize_loose_no_tabular(v)` and return `hex::encode(&result[..])` (all 32 bytes = 64 chars). Add `hex` to `Cargo.toml` dependencies to remove the private inline module.

**14. Fix missing reserved words in Rust and C.** Add `"none"` and `"nil"` to Rust's `RESERVED` array at `loose.rs:212`. Add them to C's `is_reserved` check at `glyph.c:406-408`. Remove `@` and `:` from Rust's bare-safe char set at `loose.rs:219` (and C equivalent). Change Rust and C default `max_cols` from 64 to 20.

**15. Fix C `u128_mul10` carry calculation.** Replace the bit-manipulation carry at `decimal128.c:53-68` with a `__uint128_t`-based implementation (matching the `decimal128_mul` pattern already used at `decimal128.c:425`). Add a test for the carry case.

**16. Document GS1 as Go-and-JS-only in all spec docs.** Update `docs/API_REFERENCE.md`, `docs/SPECIFICATIONS.md`, and the README layers table to scope GS1 framing to "(Go and JS only)." Add "(Go, Python, JS)" for streaming validator.

**17. Fix JS schema hash algorithm.** Replace `schema.ts:108-117` djb2 with SHA-256[:16] using Node's `crypto` module (already imported in `loose.ts`).

**18. Qualify or implement the ApplyPatch base fingerprint check.** Either implement enforcement in Go, JS, and Python, or change README lines 150/190 to "the base fingerprint is recorded for audit; enforcement is the caller's responsibility." Document that only the GS1 stream layer (`go/stream/cursor.go:102`) enforces this automatically.

**19. Clean repo of stale artifacts.** `git rm WORKLOG.md`. `git rm docs/reports/BENCHMARK_INDEX.md`. `git mv docs/reports/*.md docs/archive/` (all but README.md). Add header banners to `docs/archive/COOKBOOK.md` and `docs/archive/README.md` noting stale links. Fix broken link `docs/archive/README.md:66` to `attic/docs/AGENTS.md`. Fix import in `js/STREAMING_VALIDATOR_PARITY.md:124` from `'glyph-codec'` to `'cowrie-glyph'`.

**20. Decide fate of Rust and C ports; update README install matrix accordingly.** If dropping from the conformance surface: remove `cargo add glyph-rs` and the C build-from-source entry from the install matrix, or add explicit "(emit-only, not a conformance port)" footnotes. Add `publish = false` to `rust/glyph-codec/Cargo.toml` until the port is actually published.

---

## 9. Open Questions / Things Not Verified

**Float rule decision is unresolved.** The spec contradicts itself and three implementations follow one rule while one (Go) follows another. Which rule is canonical is a product decision, not a technical one. The answer determines who changes.

**Which null char for FingerprintLoose — ∅ or \_?** Go/JS use ∅ in the no-tabular context; Python's dataclass default is \_. Choosing Go/JS (∅) as canonical is consistent with the symbol being visually distinct in LLM output, but stored fingerprints on the Python side would change if Python is updated.

**Is the Rust port intended for revival or permanent parking?** The attic commit message series (`G3+G4 — park blob/pool, decouple core`) suggests a deliberate scope reduction. Whether Rust is meant to reach parser+patch+GS1 parity, or to remain an emit-only embedder, is not documented.

**Does EncodeDictFrame's float truncation bug affect any real downstream consumer?** There is no Go decoder for its output in this repo. If any external system consumes the binary frame format produced by `EncodeDictFrame`, the bug is critical for interop. If it is prototype/unused externally, it is medium. This was not verified.

**Has the fuzz corpus been exercised for a meaningful duration?** `FuzzParse` and `FuzzFromJSONLoose` targets exist with seed corpus. Whether they have been run for hours (not just short CI passes) is unknown. The seeds cover truncated inputs; extended fuzzing may find new crashes in the batch parser's recursive structure.

**Was glyph-rs 0.1.0 ever published to crates.io under the MIT license?** The local `target/package/` contains a `glyph-rs-0.1.0.crate` with MIT license. The current `Cargo.toml` declares Apache-2.0 at 1.0.0. If 0.1.0 was published before the license change, downstream users pinned to 0.1.0 under MIT terms need to be informed of the relicensing.

**Is Go's `Parse('_')` → `Str('_')` behavior intentional?** This means `parse(emit(null))` fails for values going through the batch `Parse()` rather than `ParseLoosePayload()`. It is unclear whether the batch parser is documented as not handling null values, or whether this is an unintentional parsing gap.

**GS1_SPEC.md Date "2025-06-20" — typo or deliberate?** Given today is 2026-06-19, this could be a typo for 2026-06-20 (tomorrow), or a deliberate retroactive version date. The same backfill pattern appears across `docs/reports/` (dates of December 2024 predating the first commit). The project's internal dating convention is not documented anywhere.

**The `C test_truth_table.c` file is wired to nothing.** `c/glyph-codec/test/test_truth_table.c` has 12 hardcoded cross-language conformance test cases but is not referenced in the Makefile and never executed by `make test`. Go, JS, and Rust have equivalent truth\_table test files integrated into their build systems. Whether the C version is meant to be wired in was not resolved.

**The stream validator depth gap in Go, JS, Python, and Rust.** Only the C stream validator has a hard 128-depth cap. Whether the other four validators are intentionally depth-unlimited (on the theory that the streaming validator only sees flat tool-call payloads) or whether this is an oversight was not verified against the product intent.
---

## Appendix A — Internal critic (review-the-review, layer 1)

```json
{
  "verdict": "Substantially trustworthy on the major technical claims, but contains one clear inaccuracy in the all_impl_parity_test.py diagnosis, one misattributed quote from API_REFERENCE.md, one misleading statement about how the Go float bug relates to canon.go, and a subtle overreach on C-port dropping that ignores the truth_table.c value. The core findings — Python NullStyle mismatch, streaming.go float truncation bug, Rust fingerprint_loose returning canonical text, C djb2-as-SHA-256, patch base not enforced anywhere, cross_impl_test.go wrong dist path, 25 TestTripleImpl subtests permanently skipping, u128_mul10 carry bug, and js/dist tracked in git — are all verified accurate against the actual code. The priority fixes and the \"consider dropping Rust/C from conformance surface\" recommendations are well-supported by the evidence. The review is actionable and can be trusted for the top-10 items with only the corrections noted below.",
  "gaps": [
    "The review does not check whether py/glyph/parse.py exists and exports parse() and parse_loose() — it does (py/glyph/__init__.py lines 44-45 export both). This matters because the hypothesis test at test_hypothesis.py:70 could have used the real GLYPH parser instead of from_json_loose, making the gap more clearly fixable with a one-line import change.",
    "The review does not note that Go's DefaultLooseCanonOpts() (loose.go:344) explicitly sets NullStyle: NullStyleUnderscore, not NullStyleSymbol — only NoTabularLooseCanonOpts() uses the zero-value (Symbol). This means FingerprintLoose in Go uses ∅ but any tabular canonicalization in Go uses _. The null-style divergence is thus specific to the no-tabular/fingerprint path, not all Go canonicalization.",
    "The review does not check whether the go/js/ directory is intentionally empty or a placeholder — it is a completely empty directory with no .gitkeep. This is either dead structure or an artifact, and either way should be cleaned up.",
    "The review does not examine whether any externally documented API (npm cowrie-glyph, PyPI glyph-py) is actually published with the current package names — it only notes the Rust cargo add fails. Verifying published package states for npm and PyPI was not done.",
    "The review mentions 'Go has two hash functions with similar names' (CanonicalHash vs FingerprintLoose) but does not note that CanonicalHash uses FNV-1a (not SHA-256) and produces only 16 hex chars, making it semantically incompatible with the fingerprint contract even for callers who read the source carefully.",
    "The review does not examine whether the c/glyph-codec/test/test_truth_table.c actually compiles correctly or contains any cross-language reference values that could be wired in quickly."
  ],
  "inaccuracies": [
    {
      "claim": "all_impl_parity_test.py:119 uses package name 'glyph-codec' (wrong; actual crate name is 'glyph-rs')",
      "issue": "This is not an error. In Cargo.toml [dependencies], the key is an alias chosen by the consumer — 'glyph-codec = { path = ... }' is valid regardless of the crate's internal name 'glyph-rs'. The use glyph_codec::... in the generated Rust source is correct for that alias. The actual build failure is caused entirely by line 133 calling print!(\"{}\", canonicalize_loose(&v)) without unwrapping the Result<String, GlyphError>. The package-name diagnosis is wrong; the Result-unwrap diagnosis is correct."
    },
    {
      "claim": "Go's NoTabularLooseCanonOpts() leaves NullStyle unset, inheriting the zero-value NullStyleSymbol (∅)",
      "issue": "Technically accurate as stated, but the review also implies the Go fingerprint path always uses Symbol while all Go canonicalization does not. DefaultLooseCanonOpts() (loose.go:344) sets NullStyle: NullStyleUnderscore, so ordinary canonicalize calls in Go use underscore. Only FingerprintLoose and NoTabularLooseCanonOpts() use the zero-value Symbol. The review's fingerprint divergence claim remains correct, but the framing that Go 'uses NullStyleSymbol' without qualification is misleading for non-fingerprint paths."
    },
    {
      "claim": "go/glyph/canon.go:41 uses math.Float64bits correctly 'for the same operation' as streaming.go:619",
      "issue": "canon.go:41 uses math.Float64bits(f) == 0x8000000000000000 to detect negative zero — it is not performing the same binary-encoding operation as streaming.go:619. There is no other use of math.Float64bits for float-to-bytes encoding in the codebase. The fix recommendation (use math.Float64bits(f)) is correct, but the cited comparison to canon.go is imprecise."
    },
    {
      "claim": "API_REFERENCE.md says GS1 streaming is something 'every implementation revolves around'",
      "issue": "The actual text (line 19) says 'Every implementation revolves around the same layers' and then lists four layers including streaming — it does not specifically say every implementation has GS1 streaming. The overall point (GS1 is presented without language-scope qualification) is valid, but the specific quote attribution misrepresents the document's phrasing. Notably, API_REFERENCE.md lines 32-33 already add a Rust/C caveat for the fingerprint section, just not for GS1."
    }
  ],
  "overreach": [
    "The recommendation to drop all docs/reports/*.md to docs/archive/ (six files) is too broad. docs/reports/README.md explicitly labels these as 'dated research snapshots' and is itself recommended to Keep. The reports contain benchmark methodology that may still be referenced by developers even if outdated. Archiving all of them loses the reports/ index structure. A more proportionate action is adding pool-parked disclaimers to the three that reference GLYPH+Pool rather than moving all six.",
    "The recommendation to 'Consider dropping' the Rust port from the published surface does not acknowledge that it has a working stream_validator (stream_validator.rs, 625+ lines) and schema_evolution (schema_evolution.rs) that are more complete than implied by 'emit-only.' The stream_validator is a non-trivial feature that other ports also implement. The port is genuinely incomplete for conformance (no parser, no patch, no GS1) but 'emit-only' understates what exists.",
    "The recommendation to drop py/glyph/decimal.py as 'not reachable from any codec path' is overly aggressive without checking whether it is used in tests or via direct import. Users may import it directly as 'from glyph.decimal import Decimal128'. Parking or deprecating it is reasonable, but 'drop' is not justified purely by absence from __init__.py exports."
  ],
  "priorityCorrections": [
    "The all_impl_parity_test.py Rust build failure diagnosis is wrong: the issue is not 'wrong package name glyph-codec' (that alias is valid Rust Cargo syntax) but rather that canonicalize_loose(&v) returns Result<String, GlyphError> and the generated main.rs uses it directly in print!() without .unwrap(). The fix is one character: print!(\"{}\", canonicalize_loose(&v).unwrap()). This changes the remediation from 'fix the package name' to 'fix the Result handling' and affects priority action item #6.",
    "The review presents the Python NullStyle mismatch as producing different fingerprints for 'any null-containing value,' which is accurate, but omits that Go's DefaultLooseCanonOpts() also uses NullStyleUnderscore (_). The fingerprint divergence is isolated to the no-tabular/FingerprintLoose path. Fixing py/glyph/loose.py:72 to set null_style=NullStyle.SYMBOL would align fingerprints but would diverge from ordinary Python canonicalization (which uses _). The fix is correct but the scope of the divergence (fingerprint path only, not all canonicalization) should be stated to avoid over-correcting.",
    "The cross_impl_test.go path diagnosis ('wrong by one directory level') is correct, but the tests do not fail — they skip gracefully with a t.Skip() message. The go/js/ directory also appears to be an empty placeholder, which may explain the path: perhaps the intent was to have a local js symlink or copy under go/. This context changes the recommendation from 'fix the path' to 'decide whether go/js/ is meant to be a symlink target or whether the path should be updated to ../../js/dist/index.js.'",
    "The review does not note that Python's glyph package exports a real GLYPH text parser (py/glyph/parse.py with parse() and parse_loose() at lines 714 and 720, exported in __init__.py). This means the hypothesis test fix is trivial (change from_json_loose to parse in the import list), and also means the review's characterization of Python as 'missing a GLYPH parser' needs qualification — Python has a parser, just the hypothesis test doesn't use it."
  ]
}```
