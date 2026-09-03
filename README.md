# GLYPH

**One digest for structured agent state: canonical JSON → SHA-256 → a patch that refuses a stale base → a stream cursor that catches drift.**

```python
>>> import glyph
>>> v = glyph.from_json_loose({"b": 2, "a": 1})
>>> glyph.canon_json(v)
'{"a":1,"b":2}'
>>> glyph.fingerprint(v)
'43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777'
```

The canonical form is ordinary JSON, so anyone can check that digest with a
stdlib and nothing else — in a language GLYPH has no port for, in a shell, in a
database:

```console
$ printf '{"a":1,"b":2}' | sha256sum
43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777  -
```

`fingerprint(v) = sha256(canon_json(v))` is the **only** digest in the project
([`SPEC-CANON.md`](./SPEC-CANON.md)). The fingerprint of a value, the base a
patch is applied against, and the state hash a GS1 cursor tracks are the same
64 hex characters. Everything else — patch application that refuses a stale
base, a cursor that rejects a desynced frame, `$tensor` references that name
multimodal state by content, wshard episode identity — is that one line plus
plumbing. Go, Python, and JavaScript/TypeScript agree byte-for-byte on every
value in the shared conformance corpus (`go/glyph/testdata/loose_json`), and
the identity harness re-checks it across all three on every run.

GLYPH's `{a=1 b=2}` text is a **renderer** of the same value model, for
LLM-facing surfaces. It is never hashed.

## What GLYPH is

- a **canonical JSON profile** (`glyph-canon-json-1.0.0`, [`SPEC-CANON.md`](./SPEC-CANON.md)): one deterministic byte sequence per value, expressible in stdlib JSON, with the number, key-order, and error rules pinned in two pages
- a **content-addressed identity primitive**: `fingerprint` / `Fingerprint` / `fingerprint` — SHA-256 of the canonical JSON, identical across Go, Python, and JS — for state caching, deduplication, and "did this sub-agent actually see the state I think it saw"
- a **strict check**: `is_canonical(bytes)` — exactly one byte sequence per value is accepted, so bytes on a wire cannot disagree with their own digest
- a **content reference for large blobs**: `{"$tensor":{"dtype","shape","sha256"}}` names a tensor by the SHA-256 of its raw elements, so multimodal state fingerprints without the bytes riding along
- a **patch/delta substrate with an enforced precondition**: a patch can record the fingerprint of the state it was computed against, and applying it verifies that fingerprint first, raising a typed error on mismatch instead of silently applying a delta to the wrong base
- a **stream framing protocol (GS1)** — implemented in Go, Python, and JavaScript/TypeScript — whose cursor tracks per-stream state hashes and rejects a patch frame whose declared base doesn't match, so a desynced or replayed frame fails loud instead of corrupting state
- a **text renderer** — `{k=v}`, `[a b]`, and tabular packing for repeated-shape records — lossless against the value model, never hashed, which incidentally reduces token count on some shapes; see below for honest, shape-dependent numbers
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

### "Why not just JCS + SHA-256?"

RFC 8785 canonicalization plus a hash is the right instinct — it is the
serious incumbent, and on friendly values the two schemes' canonical forms
even coincide byte-for-byte. Measured head-to-head over an adversarial corpus
(318 fixtures: float edges, big integers beyond float64, Unicode NFC/NFD,
duplicate keys, key-order permutations, non-BMP keys, tensor refs; three
languages each), the difference is *portability under hostility*:

| Cross-language agreement (Py+Go+JS identical hash) | naive | minified | JCS (3 vetted impls) | GLYPH |
|---|---:|---:|---:|---:|
| fixtures agreeing | 119/318 | 283/318 | 223/318 | **317/318** |

(2026-09-02 run; the one non-agreeing fixture is a value all three languages
reject identically. `canon_json` re-parses and re-canonicalizes to identical
bytes on 951/951 language-fixture pairs.)

JCS's gap is not correctness but *domain*: its reference implementations
refuse to hash 95/318 values — non-object roots (Go reference impl),
integers beyond ±2⁵³ (Python raises `IntegerDomainError`), silent big-int
precision loss at JS parse. A cross-language system built on JCS must define
behavior for every refusal path itself. GLYPH defines all of them.

Where both can hash a value, the two canonical forms usually *are* the same
bytes: 307 of the 317 hashable fixtures produce an identical SHA-256. GLYPH
diverges in exactly three places, all in
[`SPEC-CANON.md`](./SPEC-CANON.md) §6:

1. **Roots.** Any value may be a root, not only an object or array — agent
   state is often a bare string or number.
2. **Key order.** Keys sort by the UTF-8 bytes of the raw key, not UTF-16 code
   units. The two orders differ for non-BMP keys, where JCS's rule places
   emoji before U+E000–U+FFFF; UTF-8 byte order is what Go and Python produce
   natively, and JS is made to match.
3. **Integers beyond ±2⁵³.** An **error**, not a silent collapse to float64
   and not a refusal to serialize. Numbers that size travel as strings. This is
   the one place GLYPH is stricter than every implementation in the table.

Full method, pre-registration, scenarios, and costs:
[`harness/state_identity/results/REPORT.md`](./harness/state_identity/results/REPORT.md).


## The renderer: GLYPH text

The value model has a text form — `{k=v}`, `[a b]`, `@[k1 k2](v1 v2)` — that
round-trips losslessly (`parse(emit(x)) = x`) and is meant to be read by a
model or a human. **It is not the identity substrate**: nothing hashes it, no
patch base is computed from it, no GS1 frame carries it. Use it when a payload
is going into a prompt; use canonical JSON everywhere a digest is involved.

### Token savings: shape-dependent, not a fixed number

GLYPH text's compactness comes from bare keys, `=` instead of `: `, no mandatory quoting, and auto-tabular packing for lists of same-shaped records. That helps a lot on some shapes and almost nothing on others. Measured against minified JSON (`json.dumps(x, separators=(",", ":"))`) with a real tokenizer (`tiktoken`, `cl100k_base`), not a heuristic character-count estimate. Every number below is reproduced by a committed script over fixed, deterministic payloads — run [`bench/token_savings.py`](./bench/token_savings.py) and you get this exact table:

| Payload shape | Token savings (cl100k) | Bytes | Why |
|---|---:|---:|---|
| Homogeneous records — 40 uniform eval/log rows | **39.9%** | 61.6% | Auto-tabular packing emits repeated keys once; this is GLYPH's best case |
| Structured trace — 12-step tool-call log, nested args | **24.2%** | 43.7% | Some repeated structure, but not fully tabular |
| Nested chat-message state — multi-turn conversation history | **0.4%** (1.6% on o200k) | 11.8% | Dominated by unique free-text content; punctuation savings apply to a small fraction of the payload |
| Prose-heavy document — long free-text sections | **−2.7%** (GLYPH larger) | 2.1% | Almost nothing repeated for tabular packing to work against |

The gradient is the honest finding: **savings shrink toward zero, and go negative, as payload content shifts from repeated structure toward unique prose.** Don't take "~40%" as a blanket number; measure your own payload shape (`bench/token_savings.py` is easy to point at your data) before rendering to GLYPH text for a token-cost reason. If your reason is state identity or patch safety, the shape doesn't matter — and you want the JSON form anyway.

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

fp = glyph.fingerprint(glyph.parse("{a=1 b=2}"))
print(fp)
# 43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777
```

The same call in Go (`glyph.Fingerprint(parsed.Value)`) and JavaScript (`fingerprint(parseLoose("{a=1 b=2}"))`) produces the identical 64-character hex string: `sha256(canon_json(value))`, the canonical JSON profile in [`SPEC-CANON.md`](./SPEC-CANON.md). It is the one digest — value identity, patch base, and GS1 state hash are all this value. `fingerprint_loose` remains as an alias.

### 3. Patch application with an enforced base

A patch can record the fingerprint of the state it expects to be applied to. Applying it verifies that fingerprint *before* touching any operation — this is enforced by default in all three languages, not an opt-in check the caller has to remember.

```python
import json
import glyph

base = glyph.parse("{status=running turn=1}")
patch = glyph.parse_patch(json.dumps({
    "glyph_patch": 1,
    "base": glyph.fingerprint(base),
    "ops": [{"op": "=", "path": ["status"], "value": "done"},
            {"op": "~", "path": ["turn"], "value": 1}],
}))

result = glyph.apply_patch(base, patch)   # base matches -> applies
print(glyph.emit(result))
# {status=done turn=2}

stale = glyph.parse("{status=done turn=5}")
glyph.apply_patch(stale, patch)           # base does NOT match -> raises
# glyph.PatchBaseMismatch: patch base fingerprint mismatch: got '426bfbce2b3c5546b7ac7fda0e5e82f41fc4816cf94ee919aa4ae5234a98d28c', want 'f7a5eb1274c380e4b693fedd20e06f2ae1cc5964a67cce9e944e3a6c57763b3d'
```

The same patch, applied through `glyph.ApplyPatch` in Go and `applyPatch` in JS, produces the identical accepted result and the identical rejected-fingerprint pair above — verified directly while writing this document, not assumed from the Python behavior. `apply_patch(base, patch, verify_base=False)` (Go: `ApplyPatchUnchecked`; JS: `applyPatch(v, p, { verifyBase: false })`) is the explicit opt-out for callers who already verified the base elsewhere. `glyph.diff(from_value, to_value)` computes a `Patch` between two states in all three languages if you'd rather generate one than hand-write it.

A patch path is a list of segments: a string segment walks a struct field or a map key (one kind on the wire, resolved against whatever the value is), an integer segment indexes a list. Hand-written and `diff()`-generated patches share the JSON wire form in [`SPEC-CANON.md`](./SPEC-CANON.md) §7, and a GS1 cursor rejects any patch or state frame whose bytes are not canonical.

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
Writer(buf).write_doc(sid=1, seq=1, payload=glyph.canon_json(state).encode())
buf.seek(0)
cursor.process_frame(Reader(buf).next())
cursor.set_state(1, state)

# Frame 2: patch whose base is the CURRENT state hash -> accepted.
patch = glyph.emit_patch(glyph.parse_patch('{"glyph_patch":1,"ops":[{"op":"=","path":["turn"],"value":2}]}'))
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

`fingerprint(x) = sha256(canon_json(x))` is the only digest ([`SPEC-CANON.md`](./SPEC-CANON.md) §5). A patch's `base` field is this value for the state it expects; `apply_patch`/`ApplyPatch`/`applyPatch` verify it before applying, by default. GS1's per-stream state hash, checked by the cursor, is the same digest as raw 32 bytes, and the cursor rejects `doc`/`patch` frames whose payload is not canonical JSON.

If you find a value where canonicalization, parsing, or these fingerprints disagree across Go/Python/JS, that's a spec-level bug against the corpus in `go/glyph/testdata/loose_json` — please file it.

## Documentation map

### Start here
- [Quickstart](./docs/QUICKSTART.md)
- [Documentation Index](./docs/README.md)

### Authoritative specs
- [Canonical JSON Profile](./SPEC-CANON.md) — the identity substrate: canonical form, the one digest, `$tensor`, patch wire form
- [Loose Mode Spec](./docs/LOOSE_MODE_SPEC.md) — the text renderer
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

It *is* JSON. The canonical form is a JSON document, and every digest here is
a SHA-256 over one. What plain JSON does not give you is a *single* byte
sequence per value — key order, `1` vs `1.0`, and escaping are all free
choices, so two encoders that agree on the value disagree on the hash. GLYPH
pins those choices (§1–§2), makes anything outside them an error rather than a
silent reinterpretation, and builds three things on the resulting digest that
JSON has no answer for: a patch that refuses to apply to the wrong base, a
stream cursor that notices drift, and a content reference for tensors. A
verifier needs stdlib JSON plus a ~150-line canonicalizer, not a bespoke
parser.

## Why not Protobuf?

Use Protobuf for typed binary service protocols. GLYPH stays text, stays JSON-bridgeable, and is meant to be read by a human or dropped into a prompt — properties Protobuf deliberately gives up.

## The promise

Same value, same canonical bytes, same hash — across Go, Python, and JavaScript, verified by a shared conformance corpus, not asserted, and checkable by anyone with a JSON parser and a SHA-256. Patches and streams built on that identity fail loud on a mismatch instead of applying silently to the wrong state. The text renderer's token savings are real on the right shape and close to nothing on the wrong one — GLYPH does not pretend otherwise, and never hashes it.
