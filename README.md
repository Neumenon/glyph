# GLYPH

**Canonical context codec for AI systems.**

> JSON at the boundaries. GLYPH in the loop.

GLYPH is a compact, deterministic, JSON-compatible text format for the structured state that long-running AI workflows repeatedly carry through prompts, tools, memory, logs, and streams.

It is not a JSON replacement. JSON is excellent at API boundaries and at constraining model output through JSON Schema. GLYPH targets a narrower problem: the *internal* layer where the same structured state is read, hashed, patched, streamed, and re-inserted into context many times over the lifetime of an agent.

```text
External APIs / tools / model structured output
              │  JSON
              ▼
       ┌──────────────────────────────────────┐
       │            GLYPH layer                │
       │  canonicalize → fingerprint → patch   │
       │       └── pack / tabularize ──┘       │
       │  GS1 frames: doc · row · patch · ui   │
       │              ack · err · ping · pong  │
       └──────────────────────────────────────┘
              │
              ▼
   Agent context · memory · traces · streams
```

## What GLYPH is

- a compact structured text format
- a canonicalization scheme for JSON-domain values
- a JSON bridge in both directions
- a state fingerprinting primitive (SHA-256 of canonical bytes in the Go/Python/JS surfaces)
- a packed / tabular representation for repeated records
- a patch / delta substrate that verifies against base fingerprints
- a stream framing protocol (GS1) for long-running agent workflows
- cross-language: Go, Python, JavaScript / TypeScript, Rust, C

## What GLYPH is not

- not a replacement for JSON at public APIs
- not a replacement for JSON Schema or model-constrained structured output
- not a replacement for Protobuf / gRPC for typed binary RPC
- not a database format or general document language
- not an agent framework
- not a guarantee that LLMs will *generate* GLYPH better than JSON — they generally won't, and that's fine

> Models may read GLYPH. Systems may generate GLYPH. Boundaries stay JSON.

## When to use GLYPH

Good fits:

- agent traces and tool-call logs
- memory snapshots and checkpoints
- compact prompt context with repeated structure
- retrieval payloads that are inserted back into context
- replayable evaluation records
- stream frames for long-running AI tasks
- tabular records with repeated keys
- state-identity caching and patch verification

Poor fits:

- public APIs where JSON is expected
- model output already constrained by JSON Schema
- binary RPC where Protobuf or gRPC already fits
- one-off small payloads where readability outweighs compactness

| Use case                    |        Use JSON |    Use GLYPH |
|-----------------------------|----------------:|-------------:|
| Public REST API             |             Yes |           No |
| LLM structured output       |             Yes |   Usually no |
| Tool-call arguments         |             Yes |   Usually no |
| Agent memory snapshots      |           Maybe |          Yes |
| Long repeated traces        |           Maybe |          Yes |
| Canonical state hash        |           Maybe |          Yes |
| Patch verification          |            Weak |          Yes |
| Streamed agent events       |           Maybe | Yes, via GS1 |
| Human-readable compact logs |           Maybe |          Yes |
| Binary service transport    | No — use Protobuf | No        |

## Install

| Language | Package | Docs |
|----------|---------|------|
| Python | `pip install glyph-py` | [Python README](./py/README.md) |
| Go | `go get github.com/Neumenon/glyph` | [Go README](./go/README.md) |
| JavaScript / TypeScript | `npm install cowrie-glyph` | [JS README](./js/README.md) |
| Rust | `cargo add glyph-rs` | [Rust README](./rust/glyph-codec/README.md) |
| C | build from source | [C README](./c/glyph-codec/README.md) |

## Examples

### 1. JSON bridge

```python
import glyph

data = {"action": "search", "query": "glyph codec", "limit": 5}
text = glyph.json_to_glyph(data)
# {action=search limit=5 query="glyph codec"}

value = glyph.parse(text)
back  = glyph.to_json(value)  # round-trips JSON-domain values
```

### 2. Canonical state fingerprint

Same value → same canonical bytes → same SHA-256 hex, byte-for-byte across Go, Python, and JS:

```python
fp = glyph.fingerprint_loose(glyph.parse("{a=1 b=2}"))
# f35719430d98a2fe1336b584d828e31c0e2182c1b4c8464f75a03b38418ec9a7
```

The same input produces the same 64-char hex digest in the Go, Python, and JavaScript / TypeScript implementations. Use it for state caching, deduplication, and patch base verification when both sides use the same fingerprint helper.

### 3. Repeated records — tabular packing

A list of homogeneous objects:

```json
[
  {"step": 1, "tool": "search",    "status": "ok"},
  {"step": 2, "tool": "fetch",     "status": "ok"},
  {"step": 3, "tool": "summarize", "status": "ok"}
]
```

becomes:

```glyph
@tab _ [step tool status]
|1 search ok|
|2 fetch ok|
|3 summarize ok|
@end
```

Repeated keys are emitted once. The savings show up exactly where agent traces hurt: long lists with the same shape.

### 4. Patch with base fingerprint

```glyph
@patch base=sha256:f35719430d98a2fe @ops=[
  {op=replace path=[memory 3 status] value=done}
]
```

A receiver applies the patch only if its current state's fingerprint matches `base`. Mismatched bases fail explicitly instead of silently corrupting state.

### 5. Stream frame (GS1)

```glyph
@frame{v=1 sid=42 seq=7 kind=patch len=128 base=sha256:abc...}
<patch payload>
```

Length-delimited, sequence-numbered, kind-tagged frames carry `doc`, `row`, `patch`, `ui`, `ack`, `err`, `ping`, and `pong` payloads over a single stream.

## Why not just JSON?

Use JSON when interoperability is the priority. GLYPH targets a narrower problem: repeated structured state inside AI loops. In that setting, JSON's repeated quotes, commas, colons, and object keys become context overhead; canonical identity is not automatic; patch streams need extra protocol; and homogeneous records are inefficient without an additional representation.

GLYPH keeps full JSON compatibility while adding a compact canonical form, state fingerprints, packed and tabular encodings, patches, and stream framing.

## Why not Protobuf?

Use Protobuf for typed binary service protocols. GLYPH is for human- and model-readable structured context: agent traces, memory, state snapshots, patches, and streams where text readability, JSON bridging, and prompt insertion all matter.

## The layers

| Layer | Concern |
|-------|---------|
| GLYPH Loose | canonical JSON-compatible text form |
| GLYPH Pack  | packed / tabular / schema-guided encodings |
| GLYPH Patch | state deltas against base fingerprints |
| GS1         | stream frame protocol |

The codec / spec is the product. The agent-oriented material in this repo is example, not product surface.

## Invariants

These hold across the conformance-tested implementation surface:

```text
parse(emit(x))           = x
emit(parse(s))           = canonical(s)
fingerprint(x)           = SHA256(canonical_no_tabular_bytes(x))  # Go/Python/JS value identity
patch applies            iff current_fingerprint == patch.base
JSON ↔ GLYPH             preserves JSON-domain meaning
conformance impls        agree byte-for-byte on canonical form for the shared corpus
```

If you find a case where any of these break, that is a spec-level bug — please file it.

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
- [Rust](./rust/glyph-codec/README.md)
- [C](./c/glyph-codec/README.md)

### Examples and history
- [Agent Patterns](./docs/AGENTS.md) — higher-level usage examples
- [Research Reports](./docs/reports/README.md) — dated benchmark snapshots
- [Archive](./docs/archive/README.md) — historical material

## Repo layout

```text
glyph/
├── docs/    authoritative specs, quickstart, index
├── go/      Go implementation
├── py/      Python implementation
├── js/      JavaScript / TypeScript implementation
├── rust/    Rust implementation
├── c/       C implementation
└── tests/   cross-implementation parity fixtures
```

## The promise

GLYPH makes repeated structured AI state compact, canonical, and streamable without abandoning JSON.

Not more. Not less.
