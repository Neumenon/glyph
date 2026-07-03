# GLYPH

**A content-addressed identity and verification layer for structured AI agent state.**

```python
>>> import glyph
>>> glyph.fingerprint_loose(glyph.parse("{a=1 b=2}"))
'f35719430d98a2fe1336b584d828e31c0e2182c1b4c8464f75a03b38418ec9a7'
```

Run that same line through the Go, Python, and JavaScript/TypeScript implementations and you get that exact 64-character hex string, every time, byte-for-byte. This holds for every value in the shared conformance corpus (`go/glyph/testdata/loose_json`), checked in CI across all three languages. That is the whole point of GLYPH: **same value → same canonical bytes → same SHA-256, independent of which language produced it.**

That property is the load-bearing one. Everything else — patch application that refuses to apply against the wrong base, a stream protocol whose cursor rejects a frame that doesn't match the state it thinks it's patching, tabular packing that happens to save tokens on repeated-shape data — is built on top of it.

## What GLYPH is

- a **canonicalization scheme** for JSON-domain values: one deterministic byte sequence per value, per language, forever (frozen for the test corpus — see [`docs/LOOSE_MODE_SPEC.md`](./docs/LOOSE_MODE_SPEC.md))
- a **content-addressed identity primitive**: `fingerprint_loose` / `FingerprintLoose` / `fingerprintLoose` — SHA-256 of the canonical form, identical across Go, Python, and JS — for state caching, deduplication, and "did this sub-agent actually see the state I think it saw"
- a **patch/delta substrate with an enforced precondition**: a patch can record the fingerprint of the state it was computed against, and applying it verifies that fingerprint first, raising a typed error on mismatch instead of silently applying a delta to the wrong base
- a **stream framing protocol (GS1)** — implemented in Go, Python, and JavaScript/TypeScript — whose cursor tracks per-stream state hashes and rejects a patch frame whose declared base doesn't match, so a desynced or replayed frame fails loud instead of corrupting state
- a **JSON bridge** in both directions, and a **packed/tabular representation** for repeated-shape records, which incidentally reduces token count — see below for honest, shape-dependent numbers
- **cross-language conformance**: Go, Python, and JavaScript/TypeScript are the three conformance-tested implementations (Rust and C are parked in `attic/`, emit-only, not part of conformance testing)

## What GLYPH is not

- **not a compression format.** It is not optimized primarily for size or token count, and it does not always win on either — see the numbers below. If your only goal is minimizing bytes or tokens on a single payload, GLYPH is the wrong tool to reach for first.
- not a replacement for JSON at public API boundaries
- not a replacement for JSON Schema or model-constrained structured output
- not a replacement for Protobuf/gRPC for typed binary RPC
- not a database format or a general document language
- not an agent framework
- not a guarantee that LLMs will *generate* GLYPH better than JSON — they generally won't, and that's fine; GLYPH targets the system side of the loop, not model output

> Models may read GLYPH. Systems generate, hash, patch, and stream it. Boundaries stay JSON.

## When to use GLYPH

Good fits — anywhere the same structured state gets hashed, compared, patched, or streamed more than once:

- state-identity caching and deduplication (has this context already been processed?)
- patch/delta application against agent memory or session state, where applying a stale patch silently would be a correctness bug, not just an inconvenience
- long-running stream protocols where you need to detect "the receiver's state has drifted from what the sender thinks it is"
- agent traces and tool-call logs with repeated shape (tabular packing helps here, and token savings are real)
- retrieval payloads re-inserted into context

Poor fits:

- public APIs where JSON is expected
- model output already constrained by JSON Schema
- binary RPC where Protobuf or gRPC already fits
- one-off payloads, or payloads dominated by long free-text content, where GLYPH's structural savings don't have much repeated structure to work against (see token numbers below)

| Use case                     |        Use JSON |    Use GLYPH |
|-------------------------------|----------------:|-------------:|
| Public REST API                |            Yes |            No |
| LLM structured output          |            Yes |    Usually no |
| Tool-call arguments             |            Yes |    Usually no |
| Canonical state identity / hash |          Weak |           Yes |
| Patch application with precondition | Weak (nothing built in) | Yes |
| Streamed agent events with drift detection | Weak | Yes, via GS1 |
| Homogeneous agent traces / eval batches | Maybe | Yes |
| Nested chat-message history | Yes | Marginal — see below |
| Binary service transport | No — use Protobuf | No |

## Token savings: shape-dependent, not a fixed number

GLYPH's compactness comes from bare keys, `=` instead of `: `, no mandatory quoting, and auto-tabular packing for lists of same-shaped records. That helps a lot on some shapes and almost nothing on others. Measured against minified JSON (`json.dumps(x, separators=(",", ":"))`) with a real tokenizer (`tiktoken`, `cl100k_base`), not a heuristic character-count estimate:

| Payload shape | Savings vs minified JSON | Why |
|---|---:|---|
| Homogeneous records — eval batches, uniform tool-call logs, tabular data | **~40%** | Auto-tabular packing emits repeated keys once; this is GLYPH's best case |
| Structured traces — step logs with nested-but-repeated fields | **~25%** | Some repeated structure, but not fully tabular |
| Nested chat-message state — multi-turn conversation history | **~1–2%** | Dominated by unique free-text content; punctuation savings apply to a small fraction of the payload |

The gradient is the honest finding: **savings shrink toward zero, and can go negative, as payload content shifts from repeated structure toward unique prose.** A toy chat transcript we measured while writing this document — mostly long assistant/user message strings, punctuated by a couple of tool calls — came out at −4% (GLYPH *larger* in tokens than minified JSON), because tabular packing had almost nothing repeated to work against and structural savings were swamped by string content. Don't take "~40%" as a blanket number; measure your own payload shape before committing to GLYPH for a token-cost reason. If your reason is state identity or patch safety, the shape doesn't matter.

## Install

| Language | Package | Docs |
|----------|---------|------|
| Python | `pip install glyph-py` | [Python README](./py/README.md) |
| Go | `go get github.com/Neumenon/glyph/go` (repo must be public; or set `GOPRIVATE`) | [Go README](./go/README.md) |
| JavaScript / TypeScript | `npm install cowrie-glyph` | [JS README](./js/README.md) |
| Rust | parked in `attic/rust/glyph-codec/` — emit-only, not published | [Rust README](./attic/rust/glyph-codec/README.md) |
| C | parked in `attic/c/glyph-codec/` — emit-only, build from source | [C README](./attic/c/glyph-codec/README.md) |

> **Rust and C** emit canonical GLYPH-Loose but are not conformance ports: no text parser, no patch, no GS1, no pack. They are not published; `cargo add glyph-rs` is not a valid install path — see the attic READMEs for what does work.
>
> **Go module path** is `github.com/Neumenon/glyph/go` (the `/go` suffix is the monorepo-subdirectory convention `go get` expects). The repo must be public — or `GOPRIVATE`/`GONOSUMCHECK` configured — for the module proxy to resolve it.

## Examples

Every example below was executed against this repository's working tree while writing this document; output shown is real, not illustrative.

### 1. JSON bridge

```python
import glyph

data = {"action": "search", "query": "glyph codec", "limit": 5}
text = glyph.json_to_glyph(data)
print(text)
# {action=search limit=5 query="glyph codec"}

value = glyph.parse(text)
back = glyph.to_json(value)
assert back == data
```

### 2. Content-addressed identity — the fingerprint

```python
import glyph

fp = glyph.fingerprint_loose(glyph.parse("{a=1 b=2}"))
print(fp)
# f35719430d98a2fe1336b584d828e31c0e2182c1b4c8464f75a03b38418ec9a7
```

The same call in Go (`glyph.FingerprintLoose(parsed.Value)`) and JavaScript (`fingerprintLoose(parseLoose("{a=1 b=2}"))`) produces the identical 64-character hex string. `fingerprint_loose` always hashes the *no-tabular* canonical form (so the digest doesn't depend on cross-language agreement about auto-tabular thresholds) — see the invariants table below for how this differs from a patch's `@base`.

### 3. Patch application with an enforced base

A patch can record the fingerprint of the state it expects to be applied to. Applying it verifies that fingerprint *before* touching any operation — this is enforced by default in all three languages, not an opt-in check the caller has to remember.

```python
import glyph

base = glyph.parse("{status=running turn=1}")
patch = glyph.parse_patch(f"""@patch @base={glyph.compute_base_fingerprint(base)}
= status done
~ turn +1
@end""")

result = glyph.apply_patch(base, patch)   # base matches -> applies
print(glyph.emit(result))
# {status=done turn=2}

stale = glyph.parse("{status=done turn=5}")
glyph.apply_patch(stale, patch)           # base does NOT match -> raises
# glyph.PatchBaseMismatch: patch base fingerprint mismatch: got '4daa8272b53b2f7e', want '2beeaacd8e079f14'
```

The same patch text, applied through `glyph.ApplyPatch` in Go and `applyPatch` in JS, produces the identical accepted result and the identical rejected-fingerprint pair above — verified directly while writing this document, not assumed from the Python behavior. `apply_patch(base, patch, verify_base=False)` (Go: `ApplyPatchUnchecked`; JS: `applyPatch(v, p, { verifyBase: false })`) is the explicit opt-out for callers who already verified the base elsewhere. `glyph.diff(from_value, to_value)` computes a `Patch` between two states in all three languages if you'd rather generate one than hand-write it.

One path-grammar caveat worth knowing before you hand-write a patch: dot-separated path segments (`.field`) are resolved as struct-field access in Go and JS — navigating a *map* (untyped `{...}` data, the common case in loose mode) through more than one dotted/indexed segment raises an error in those two languages, even though Python's applier is more permissive and accepts it. `diff()`-generated patches never hit this, because they only ever emit single-level `["key"]` map-key or whole-value-replace operations for map data. Stick to top-level field ops (as above) or `diff()` output for portable patches against loose/map values; reserve deep dotted paths for schema-typed structs.

### 4. GS1 stream — a cursor that rejects a stale patch frame

GS1 is a length-delimited, sequence-numbered stream framing protocol for `doc`/`row`/`patch`/`ui`/`ack`/`err`/`ping`/`pong` payloads. It is implemented in Go, Python, and JavaScript/TypeScript, with cross-language golden byte vectors (`go/stream/gs1t_test.go`, decoded and re-encoded by the Python and JS suites). The cursor tracks each stream's current state hash and enforces it on incoming patch frames:

```python
import io
import glyph
from glyph.stream import Writer, Reader, StreamCursor, BaseMismatchError, state_hash_loose

cursor = StreamCursor()
state = glyph.parse("{turn=1 status=running}")

# Frame 1: snapshot doc, establishes state for sid=1.
buf = io.BytesIO()
Writer(buf).write_doc(sid=1, seq=1, payload=glyph.emit(state).encode())
buf.seek(0)
cursor.process_frame(Reader(buf).next())
cursor.set_state(1, state)

# Frame 2: patch whose base is the CURRENT state hash -> accepted.
patch = glyph.emit_patch(glyph.parse_patch("@patch\n= turn 2\n@end"))
buf = io.BytesIO()
Writer(buf).write_patch(sid=1, seq=2, payload=patch.encode(), base=state_hash_loose(state))
buf.seek(0)
cursor.process_frame(Reader(buf).next())
print("accepted: patch base matched current state")

# Frame 3: same patch, but base now points at a STALE state -> rejected.
stale = glyph.parse("{turn=99 status=done}")
buf = io.BytesIO()
Writer(buf).write_patch(sid=1, seq=3, payload=patch.encode(), base=state_hash_loose(stale))
buf.seek(0)
try:
    cursor.process_frame(Reader(buf).next())
except BaseMismatchError as e:
    print("rejected:", e)
```

```text
accepted: patch base matched current state
rejected: gs1: base hash mismatch
```

Full protocol details, including CRC and resync handling, are in [`docs/GS1_SPEC.md`](./docs/GS1_SPEC.md).

## Invariants

These hold across the conformance-tested implementation surface (Go, Python, JS):

```text
parse(emit(x))    = x
emit(parse(s))    = canonical(s)
```

`fingerprint_loose(x)` vs a patch's `@base` are two different digests over two different canonical forms — mixing them up is a real bug class, not a stylistic choice:

| | `fingerprint_loose` (value identity) | `@base` / `compute_base_fingerprint` (patch precondition) |
|---|---|---|
| Pre-image | canonical form **without** auto-tabular | canonical form **with** auto-tabular (the default `emit`/`canonicalize_loose` form) |
| Output | full SHA-256, 64 hex chars | first 16 hex chars of SHA-256 |
| Cross-language identical | yes | yes |
| Enforced automatically? | no — it's a value you compare yourself | yes — `apply_patch`/`ApplyPatch`/`applyPatch` verify it before applying, by default |
| Where it lives | value caching, dedup, "is this the same state" | inside a `@patch` header; also the pre-image family used (untruncated, 32 bytes) for GS1's per-stream state hash checked by the cursor |

If you find a value where canonicalization, parsing, or these fingerprints disagree across Go/Python/JS, that's a spec-level bug against the corpus in `go/glyph/testdata/loose_json` — please file it.

## Documentation map

### Start here
- [Quickstart](./docs/QUICKSTART.md)
- [Documentation Index](./docs/README.md)

### Authoritative specs
- [Loose Mode Spec](./docs/LOOSE_MODE_SPEC.md)
- [GS1 Spec](./docs/GS1_SPEC.md)

### API / language docs
- [API Reference](./docs/API_REFERENCE.md)
- [Python](./py/README.md)
- [Go](./go/README.md)
- [JavaScript / TypeScript](./js/README.md)
- [Rust (attic — parked)](./attic/rust/glyph-codec/README.md)
- [C (attic — parked)](./attic/c/glyph-codec/README.md)

### Examples and history
- [Research Reports](./docs/reports/README.md) — dated benchmark snapshots; treat older token/size percentages there as historical, not current guidance
- [Archive](./docs/archive/README.md) — historical material

## Repo layout

```text
glyph/
├── docs/    authoritative specs, quickstart, index
├── go/      Go implementation
├── py/      Python implementation
├── js/      JavaScript / TypeScript implementation
├── attic/   parked material (rust/glyph-codec, c/glyph-codec, agents, blob_pool)
└── tests/   cross-implementation parity fixtures
```

## Why not just JSON?

Use JSON when interoperability is the priority — it's the right default at API boundaries. GLYPH targets a narrower problem: repeated structured state moved through an agent loop, where you need to know two states are identical without a byte-for-byte diff, or that a patch is safe to apply, or that a stream hasn't desynced. JSON has no built-in answer to any of those; GLYPH's canonical form gives you one for free, and the packing/token savings — where they exist — are a secondary benefit, not the reason to reach for it.

## Why not Protobuf?

Use Protobuf for typed binary service protocols. GLYPH stays text, stays JSON-bridgeable, and is meant to be read by a human or dropped into a prompt — properties Protobuf deliberately gives up.

## The promise

Same value, same canonical bytes, same hash — across Go, Python, and JavaScript, verified by a shared conformance corpus, not asserted. Patches and streams built on top of that identity fail loud on a mismatch instead of applying silently to the wrong state. Token savings are real on the right shape and close to nothing on the wrong one — GLYPH does not pretend otherwise.
