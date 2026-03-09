# GLYPH

GLYPH is a codec-first structured text format and streaming substrate for AI and ML systems.

The core value is lower in the stack than “agent framework”:
- deterministic loose-mode canonicalization
- JSON bridges
- fingerprinting for state verification
- schema-driven packed, tabular, and patch encodings
- GS1 framing for multiplexed streams
- cross-language implementations in Go, Python, JavaScript, Rust, and C

## Why This Repo Exists

JSON is a fine interchange format, but it is noisy for repeated structured data and weak as a codec substrate for long-running LLM workflows. GLYPH focuses on:

- **Compact text**: fewer tokens than JSON for many structured payloads
- **Determinism**: canonical output suitable for hashing and equality
- **Patchability**: explicit delta-friendly representations
- **Streaming**: frame-oriented transport and incremental validation
- **Parity**: the same semantics across multiple runtimes

If you are evaluating `glyph`, start from the codec and spec layer first. Higher-level agent patterns in this repo are examples, not the product center.

## Install

| Language | Package | Docs |
|----------|---------|------|
| Python | `pip install glyph-py` | [Python README](./py/README.md) |
| Go | `go get github.com/Neumenon/glyph` | [Go README](./go/README.md) |
| JavaScript / TypeScript | `npm install cowrie-glyph` | [JS README](./js/README.md) |
| Rust | `cargo add glyph-rs` | [Rust README](./rust/glyph-codec/README.md) |
| C | build from source | [C README](./c/glyph-codec/README.md) |

## Quick Example

```python
import glyph

data = {"action": "search", "query": "glyph codec", "limit": 5}

text = glyph.json_to_glyph(data)
# {action=search limit=5 query="glyph codec"}

value = glyph.parse(text)
query = value.get("query").as_str()

fingerprint = glyph.fingerprint_loose(glyph.from_json(data))
```

## Documentation Map

### Start Here
- [Quickstart](./docs/QUICKSTART.md)
- [Documentation Index](./docs/README.md)

### Authoritative Specs
- [Loose Mode Spec](./docs/LOOSE_MODE_SPEC.md)
- [GS1 Spec](./docs/GS1_SPEC.md)

### API / Language Docs
- [API Reference](./docs/API_REFERENCE.md)
- [Python](./py/README.md)
- [Go](./go/README.md)
- [JavaScript / TypeScript](./js/README.md)
- [Rust](./rust/glyph-codec/README.md)
- [C](./c/glyph-codec/README.md)

### Example / Historical Material
- [Agent Patterns](./docs/AGENTS.md) — optional higher-level examples
- [Research Reports](./docs/reports/README.md) — dated snapshots, not current API docs
- [Archive](./docs/archive/README.md) — historical material

## Repo Layout

```text
glyph/
├── docs/                  authoritative specs, quickstart, index
├── go/                    Go implementation
├── py/                    Python implementation
├── js/                    JavaScript / TypeScript implementation
├── rust/                  Rust implementation
├── c/                     C implementation
└── tests/                 cross-implementation parity scripts
```

## Current Positioning

The codec layer is the product:
- format contract
- canonicalization
- schema / packed / tabular / patch behavior
- streaming transport
- parity and correctness

The demo and agent-oriented material in this repo should be read as examples built on top of that substrate.
