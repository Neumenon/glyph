# GLYPH v1.1.0

**Tags:** `v1.1.0` (repo-wide), `go/v1.1.0` (Go module), `py/v1.1.0`, `js/v1.1.0`
**Packages:** `glyph-py` 1.1.0 (PyPI) · `cowrie-glyph` 1.1.0 (npm) ·
`github.com/Neumenon/glyph/go` (Go module proxy)

This release closes the two largest cross-language gaps that were still
open after v1.0.0 — Python had no GS1 stream implementation, and only Go had
a `Diff()` — and fixes four correctness bugs: silently divergent JSON→GLYPH
sniffing behavior in JS, unenforced patch-base checking on the standalone
apply path in all three languages, Python struct/sum canonicalization that
diverged from the spec and from Go/JS, and `diff()` output that carried no
base fingerprint at all. It also fixes the Go module so `go get` resolves it
at all. Four of these are breaking changes; each ships with a one-line
opt-out or a clear upgrade note for anyone who depended on the old behavior.

## Highlights

- **Python gets full GS1 stream framing** (`glyph.stream`) — `Writer`,
  `Reader`, `StreamCursor`, CRC, state hashing, UI event frames. Go, Python,
  and JS now all implement the same protocol against the same golden byte
  vectors.
- **`diff()` ported to Python and JS.** All three languages can now both
  produce and apply patches; previously only Go could compute a `Patch` from
  two values.
- **Patch application is now safe by default.** `ApplyPatch` /
  `apply_patch` / `applyPatch` verify a patch's recorded base fingerprint
  before applying, in all three languages, closing a gap where a
  standalone (non-streaming) caller could silently apply a patch against the
  wrong state.
- **The Go module is `go get`-able again.** `go get
  github.com/Neumenon/glyph/go@latest` now resolves cleanly; previously the
  module path didn't match its on-disk location and the request 404'd.
- **README rewritten around a verified claim, not a marketing one:** same
  value → same canonical bytes → same SHA-256, across Go/Python/JS, with
  measured (not estimated) token-savings numbers that are honest about the
  shapes where GLYPH doesn't help.

## Breaking changes

### 1. JS `fromJson` no longer type-sniffs by default

`FromJsonOptions.parseDates` and `.parseRefs` now default to `false` (were
`true`). `fromJson` no longer opportunistically parses ISO date strings as
`time` values or `^prefix:value` strings as `ref` values unless you ask for
it.

**Why this is safe to take:** the old default made `fromJson`'s output
diverge from Go's `FromJSONLoose` and Python's `from_json`, which never
sniffed. Two languages parsing the identical JSON produced *different*
canonical bytes, and therefore different `fingerprint_loose` /
`FingerprintLoose` / `fingerprintLoose` hashes for what should have been
the same value — silently breaking the one cross-language guarantee GLYPH
exists to provide. The new default restores parity. If you were relying on
the sniffing behavior for a JS-only pipeline (no cross-language fingerprint
comparison in play), the fix is one line:

```ts
fromJson(json, { parseDates: true, parseRefs: true })
```

`jsonToPacked`, `jsonToTabular`, and `jsonToLyph` (schema-driven emission)
are unaffected — they keep sniffing on by default, since schema-typed
emission was never part of the fingerprint-parity contract.

### 2. Patch application now enforces the base fingerprint by default

`ApplyPatch` (Go), `apply_patch` (Python), and `applyPatch` (JS) now check a
patch's recorded base fingerprint against the value being patched *before*
applying any operation, when the patch carries one. A mismatch raises a
typed error (`PatchBaseMismatch` in Python/JS; `*FingerprintMismatch` in Go,
aliased as `PatchBaseMismatch`) instead of silently applying the patch
anyway. A patch with no recorded base fingerprint still applies
unconditionally — nothing changes for callers who never set one.

**Why this is safe to take:** this was already the enforced behavior on the
GS1 streaming path (the cursor has always rejected a frame whose declared
base doesn't match). The standalone `ApplyPatch` path was the one place a
stale or wrong-base patch could be applied silently — arguably the more
dangerous of the two entry points, since it's the one most likely to be
called directly against agent memory or session state outside a stream. If
you intentionally force-apply patches against a base you know differs (or
you've already verified the base yourself and don't want the redundant
check), use the explicit opt-out:

- Go: `ApplyPatchUnchecked(v, p)`
- Python: `apply_patch(v, p, verify_base=False)`
- JS: `applyPatch(v, p, { verifyBase: false })`

### 3. Python struct/sum loose canonicalization aligned with the spec and Go/JS

Python's `canonicalize_loose` emitted structs as `TypeName{...}` and sums as
`Tag(value)`. Per CANONICAL_FORMS.md (G1/G2) — and per what Go and JS have
always done — Loose collapses a struct to a plain map `{field=val ...}`
(sorted keys, no TypeName) and a sum to `{tag=value}` (no-payload sums:
`{tag=_}`). Python now matches.

**Why this is safe to take:** the old Python behavior meant a struct or sum
value fingerprinted differently in Python than in Go/JS — the same class of
silent cross-language identity break as the JS `fromJson` sniffing bug.
Python-persisted fingerprints of struct/sum values will change (to the values
Go and JS always produced); JSON-domain values (maps, lists, scalars) are
completely unaffected, and all 51 conformance cases remain byte-identical.

### 4. `diff()` output now carries — and therefore enforces — a base fingerprint

Patches generated by `Diff`/`diff` now record the base fingerprint of the
`from` value, so applying one to any other state fails with
`PatchBaseMismatch` instead of silently succeeding. Combined with change 2,
the diff → send → apply workflow is now base-verified end to end by default.
Emitted patch text gains an `@base=` header (the cross-language golden test
pins the exact bytes in all three languages).

## Added

- `diff(from, to, typeName)` in Python and JS, matching Go's existing
  `Diff`. Whole-list-replace semantics (no element-wise list diffing) are
  consistent across all three.
- Python: `glyph.stream` — GS1 `Writer`, `Reader`, `StreamCursor`, CRC,
  `state_hash_loose`, UI event frame types.
- JS package root now exports `diff`, `verifyPatchBase`,
  `computeBaseFingerprint`, `PatchBaseMismatch`, `ApplyPatchOptions` (these
  existed internally but weren't reachable from `import { ... } from
  'cowrie-glyph'`).
- Cross-language doc-comment disambiguation between `fingerprint_loose`
  (64-hex, no-tabular, value-identity) and a patch's base fingerprint
  (16-hex, with-tabular, apply-time precondition) — added to Go, Python, and
  JS source, and to the README invariants table.

## Fixed

- Go module path corrected to `github.com/Neumenon/glyph/go` (was mismatched
  with its `go/` subdirectory location, so external `go get` couldn't find
  a `go.mod`). The unpublished `cowrie` dev-bridge dependency has been
  removed along with the code that used it; `go.mod` is dependency-free and
  `go mod tidy` is a no-op.
- `attic/rust/glyph-codec/README.md` and `attic/c/glyph-codec/README.md`
  corrected: the Rust crate is not published (`publish = false`, never
  pushed to crates.io — the old install snippet would not resolve); the C
  port's `glyph_fingerprint_loose` is documented as what it actually is (an
  alias for `glyph_canonicalize_loose`, not a hash) and `glyph_hash_loose`
  is documented as incompatible with the other languages'
  `fingerprint_loose` (different pre-image, different truncation).
- Stale/invalid syntax in several example-bearing docs (`docs/GUIDE.md`,
  `docs/COOKBOOK.md`, `docs/GS1_SPEC.md`, `docs/LOOSE_MODE_SPEC.md`,
  `docs/GLYPH_FILE_FORMAT.md`, `docs/SPECIFICATIONS.md`) that no longer
  parsed against the current grammar, or showed output missing the
  `rows=N cols=N` tabular header metadata the codec always emits by
  default.
- Root `README.md` rewritten around the verified fingerprint-parity claim,
  with measured (not estimated) token-savings numbers.

## Known gaps carried into this release (not fixed here)

- `py/README.md`, `js/README.md`, `docs/GS1_SPEC.md`, and
  `docs/API_REFERENCE.md` still say GS1 is "Go and JS only." This is now
  stale given the Python GS1 addition above and should be corrected in a
  fast-follow.
- A real (pre-existing, not introduced by this release) patch path-grammar
  divergence: dot-separated intermediate path segments
  (e.g. `steps[0].status`) are struct-only in Go/JS (they raise on a bare
  loose map) but Python's applier accepts them against maps too. `diff()`
  output never triggers this — it only emits single-level ops — so it's
  invisible to the conformance suite. Only relevant if you hand-write a
  multi-segment dotted patch against loose/map data; documented in the
  README as a caveat rather than silently left for someone to discover.
- `py/glyph/__init__.py`'s hand-maintained `__version__ = "1.0.1"` constant
  needs bumping to `1.1.0` before the PyPI build (tracked in the release
  checklist).

## Upgrade notes

- **If you call `fromJson` in JS and rely on cross-language fingerprints**:
  no action needed — you get the fix for free (parity restored).
- **If you call `fromJson` in JS and relied on auto-sniffing for a JS-only
  pipeline**: pass `{ parseDates: true, parseRefs: true }` explicitly.
- **If you call `ApplyPatch`/`apply_patch`/`applyPatch` and always verified
  the base yourself first, or never set a base fingerprint**: no action
  needed, behavior is identical.
- **If you call `ApplyPatch`/`apply_patch`/`applyPatch` and intentionally
  force-apply against a known-stale base**: switch to the unchecked variant
  (see above) before upgrading, or the call will start raising.

## Positioning (unchanged from README, restated here for release-note readers)

GLYPH is a content-addressed identity and verification layer for structured
AI agent state, not a compression format. The property that matters is:
same value, same canonical bytes, same SHA-256, independent of which of Go,
Python, or JavaScript produced it — checked against a shared conformance
corpus, not asserted. Patch application and GS1 streaming build enforced
preconditions on top of that identity (reject a stale base, reject a
desynced frame) rather than applying deltas silently. Token savings from
tabular packing are real but shape-dependent — roughly 40% on homogeneous
records, roughly 25% on structured traces, roughly 1-2% (and possibly
negative) on prose-heavy nested chat state. If your reason for reaching for
GLYPH is token cost, measure your own payload shape first; if your reason is
state identity or patch safety, the shape doesn't matter.

## Verification

All three test suites and the cross-language conformance corpus pass as of
this release:

- Go: `go build ./...`, `go vet ./...` clean; `go test ./... -count=1` — both
  packages `ok` (508 tests)
- Python: `pytest tests/ -q` — 551 passed
- JS: `npm test` — 8 suites / 594 tests passed
- Conformance: `bash conformance/run_conformance.sh` — 51/51 cases across
  go/py/js

See `docs/RELEASE_CHECKLIST_v1.1.0.md` for the exact commands to reproduce
this and the remaining steps to publish.
