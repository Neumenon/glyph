# GLYPH — Parity Roadmap (triage of the external review vs current `main`)

Date: 2026-06-19. Triaged by direct code probes against `main` @ `210c2ee` (the multi-agent
triage workflow kept getting torn down by session context-compaction, so this was verified directly).
Every item cites `go/glyph/...:line` evidence.

## 1. Scoreboard

The external review is **partly outdated**. Of its major claims:
- **~6 already fixed** on `main` (mostly by this session's work)
- **~5 moot / stale** (parked features, or reference code that doesn't exist here, or intentionally deferred)
- **~8 still-real** and worth doing — concentrated in **P0 round-trip correctness** (the review's own top priority)

**Bottom line:** the review's headline — *"emitter produces text the parser can't parse; enforce round-trip before adding
features"* — is **correct and still the right next move**. But blob/pool, `appendFloat64`, `ParseV2Document`, and the patch-base
critiques are already handled or moot. The real remaining core is a focused **P0 round-trip pass**, not a rewrite.

## 2. Already handled (don't redo)

| Review claim | Status | Evidence |
|---|---|---|
| `appendFloat64` encodes numeric cast not IEEE bits | ✅ fixed | `streaming.go:620` uses `math.Float64bits(f)` |
| No parser depth guard (DoS) | ✅ fixed | `parse.go` `maxParseDepth=128` |
| GS1 `v==1` MUST unenforced; header DoS | ✅ fixed | `go/stream/gs1t_reader.go` (v-check + header cap) |
| `estimateTokens` broken (JS) | ✅ deprecated | JS `index.ts` marked deprecated |
| Cross-impl parity not a real gate | ✅ fixed | `tests/all_impl_parity_test.py` exits non-zero on Go/Py/JS mismatch (21/21) |
| Python null-style fingerprint divergence | ✅ fixed | `py/glyph/loose.py` no-tabular opts → SYMBOL |

## 3. Stale / moot / wrong (no longer applies)

| Review claim | Why moot |
|---|---|
| blob/pool not integrated across emit/parse/Cowrie/deepCopy | **Parked to `attic/`** — `TypeBlob`/`TypePoolRef` ABSENT in `go/glyph`. Critique no longer applies to core. |
| `ToCowrie`/`FromCowrie` uint64→int64 overflow | `ToCowrie` **ABSENT** in `go/glyph` — no Cowrie bridge in this repo (lives in the website/cowrie project). |
| `ParseV2Document` missing / v2 not parseable | There is no `ParseV2Document` (confirmed absent). This is a **real gap** but listed here because the review treats it as a regression — it's a *never-built* parser (see P4). |
| `DecodeDictFrame` missing | **ABSENT** — `EncodeDictFrame` is emit-only (see P4: de-scope or build). |
| `ApplyPatch` doesn't enforce `BaseFingerprint` | **Intentionally deferred + documented** — GS1 cursor (`go/stream/cursor.go`) enforces base; standalone apply records-not-verifies, by design. |

## 4. Real remaining work — by priority

### P0 — Round-trip-airtight core (`Parse(Emit(v)) == v`) — the review's top ask, still valid
- **No bytes token in the parser.** `Emit(Bytes(...))` emits `b64"..."`, parser has no bytes path → fails. *(no `TypeBytes`/`b64` case in `parse.go`/`token.go`)* — **M, Go (then Py/JS).**
- **`scanString` doesn't decode `\u` escapes** while `quoteString` can emit `\u00XX` → emitted control chars don't round-trip. *(no `\u` decode in `token.go`)* — **S/M, Go.**
- **`strconv` errors silently discarded** → overflow/garbage parses to wrong value. `parse.go:129` `v, _ := strconv.ParseInt(...)`, `:134` `ParseFloat`. (Note: `:823/:830` *do* check — inconsistent.) — **S, Go.**
- **Bare-string / lexer mismatch.** `isIdentContinue = isIdentStart || isDigit` (`token.go:490`); bare-string emit allows chars (`-`, Unicode) the ASCII lexer rejects → emit-bare-then-fail-parse. Fix = **conservative quoting**: quote anything the lexer can't read back, until lexer support lands. — **M, Go (then Py/JS).**
- **Map duplicate-key policy undefined; tolerant mode coerces unknown tokens → `Null`** (dangerous for tool exec). Define + document policy; make tolerant `Null`-coercion opt-in/loud. — **S/M, Go.**
- **Deliverable:** golden `Parse(Emit(v))==v` table across every `GType` (null, bool, int incl. overflow, float incl. NaN/Inf policy, strings with spaces/quotes/control/Unicode/`-`/`.`/`/`/`|`, bytes, time, ID, list/map/struct/sum).

### P1 — Schema-hash safety + schema-text round-trip + JSON fidelity
- **Schema hash may omit decoding-relevant bits.** `Schema.ComputeHash()`/`Canonical()` exist (`schema.go:238/246`) and FID-ordering exists (`FieldsByFID` `:335`), but **confirm `Canonical()` actually serializes FID + `PackEnabled`/`TabEnabled`/`KeepNull`/`Codec`/defaults**. If not, two incompatible packed schemas can share a hash → silent mis-decode. **Ship blocker for packed mode.** — **M, Go.** *(read `Canonical()` body to confirm in/out.)*
- **`ParseSchema(EmitSchema(s))` round-trip + text syntax** for `@pack`/`@tab`/`@open`/FID/KeepNull/Codec/defaults; lexer can't tokenize `..` in `[0..10]` ranges. Schemaful packed mode is programmatic-only today. — **L, Go.**
- **JSON bridge precision:** `ToJSONLoose(TypeInt)` → `float64(v.intVal)` (`json_bridge.go:213`) loses precision >2^53; `FromJSONLoose` should use `json.Decoder.UseNumber`/`json.Number`. Struct `TypeName` loss + sum `{tag:value}` ambiguity + extended-marker collision policy. — **M, Go (+ Py/JS for parity).**

### P2 — Patch correctness
- **`PathSegListIdx` exists** (`emit_patch.go:51,61`, emitted `:447`) but confirm **`ApplyPatch` handles list-index leaf set/delete/insert + root-list ops** (review: `applyToParentSeg` covers struct/map, not list leaf). — **M, Go.**
- **FID-path resolution as a required pre-pass:** FID segments parse with empty `Field`; `ApplyPatch` uses `seg.Field` → call `ResolvePathFIDs` consistently on build/parse/apply. Resolve `KeyModeWire` wire keys. — **M, Go.**
- `SortOps` default may change list semantics; int-delta silently truncates float deltas. — **S, Go.**
- **Deliverable:** `ApplyPatch(base, ParsePatch(EmitPatch(Diff(base,next)))) == next`.

### P3 — Incremental / streaming chunk-invariance
- **Close-token stall + early emit.** `incremental.go` `stateAfterValue` (`:304`) with `return 0` paths (`:262,287`) → `Feed()` treats `consumed==0` as `EventNeedMore`, so `{a=1}` can stall at `}`; partial idents/keywords may emit too early; path stack not popped → sibling paths accumulate. — **M/L, Go.**
- **Deliverable:** property test `events(feed_all(x)) == events(feed_one_byte_at_a_time(x))` over scalars, nested structs, malformed input, split at every byte.

### P4 — Scope cleanup (shrink the public surface)
- **Decimal128 is standalone/unreachable** — NOT referenced in `parse.go`/`emit.go`/`types.go`/`token.go`. Plus the review's correctness bugs (scale int8 overflow, `ToInt64` returns raw coefficient, negative-scale `String()` panic). → **de-scope to experimental or remove from the feature list** until integrated + tested. — Go/Py.
- **`EmitV2` with no `ParseV2Document`** → emit-only, can't round-trip. Either build the authoritative v2 document parser or mark v2 experimental.
- **`EncodeDictFrame` with no `DecodeDictFrame`** → de-scope or add decoder + round-trip test.
- **Too many emitters** (`Emit`/`EmitCompact`/`EmitTokenAware`/`EmitV2`/`EmitPacked`/`EmitTabular`/`CanonicalizeLoose`/…): collapse to two hard layers — **Loose** (schema-free, LLM-facing) and **Typed** (schema-bound). Archive zero-caller emitters (`EmitTokenAware`, `CanonicalHash`).

## 5. Recommended execution — one workflow per phase (greenlight individually)

1. **Workflow 1 — P0 round-trip core** *(highest value).* Conservative quoting + bytes token + `\u` decode + `strconv` error checks + dup-key/tolerant policy, with the golden `Parse(Emit(v))==v` table. Go first, then mirror Py/JS.
2. **Workflow 2 — P1 schema-hash safety** (confirm + fix `Canonical()` coverage; gate packed mode) — *ship blocker, do before promoting packed.*
3. **Workflow 3 — P1 schema-text round-trip + JSON fidelity** (`UseNumber`, int64 preservation, schema text syntax).
4. **Workflow 4 — P2 patch list-leaf + FID resolution** (+ the `Diff/Apply` round-trip invariant).
5. **Workflow 5 — P3 incremental chunk-invariance** (+ the byte-split property test).
6. **Workflow 6 — P4 scope cleanup** (de-scope Decimal128/EmitV2/dict-frames behind experimental; collapse emitters to Loose/Typed).

## 6. Open decisions for the maintainer (genuine forks)
- **Does Loose preserve types or intentionally collapse to JSON-like?** (Determines whether time/ID/bytes round-trip through Loose or only through Typed.) — *biggest fork; decide first, it shapes P0.*
- **Keep or drop Decimal128 and EmitV2** as advertised features, or move both behind experimental?
- **`@lyph` vs `@glyph`** header spelling — parser accepts both (`parse_header.go:38`); pick one canonical for the emitter.
- **Float rule** (already-open) — shortest-roundtrip (Go) vs threshold (Py/JS); unify or keep documented-divergent.
