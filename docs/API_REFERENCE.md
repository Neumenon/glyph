# GLYPH API Reference

This page is a routing layer, not a substitute for the language READMEs.

The purpose is to give the current package names, import surfaces, and the core codec concepts that are shared across implementations.

## Package Names

| Language | Package | Primary Doc |
|----------|---------|-------------|
| Python | `glyph-py` | [../py/README.md](../py/README.md) |
| Go | `go get github.com/Neumenon/glyph/go` | [../go/README.md](../go/README.md) |
| JavaScript / TypeScript | `cowrie-glyph` | [../js/README.md](../js/README.md) |
| Rust | parked in `attic/` — emit-only, not published | [../attic/rust/glyph-codec/README.md](../attic/rust/glyph-codec/README.md) |
| C | parked in `attic/c/` — emit-only, build from source | [../attic/c/glyph-codec/README.md](../attic/c/glyph-codec/README.md) |

## Shared Concepts

The Go, Python, and JS implementations share the same layers (the parked Rust and C ports in `attic/` implement Loose emit only):

### Loose Mode
- parse or bridge JSON-compatible data
- canonicalize to a deterministic text form
- fingerprint the canonical form

Typical operations:
- `from_json` / `fromJson` / `FromJSONLoose`
- `to_json` / `toJson` / `ToJSONLoose`
- `canonicalize_loose` / `canonicalizeLoose` / `CanonicalizeLoose`
- Go/Python/JS value identity: `fingerprint` / `fingerprint` / `Fingerprint` (SHA-256 of `canon_json(v)`, SPEC-CANON.md §5)

Rust and C currently expose narrower hash helpers; use their language READMEs
as the source of truth for those packages.

### Structured Values
Implementations expose a typed value model with:
- null / bool / int / float / string
- bytes / time / ref ID
- list / map / struct / sum

### Schema-Oriented Encoding
Where implemented, the schema layer covers:
- packed encoding
- tabular encoding
- patch encoding
- schema evolution helpers

### Streaming
The streaming layer covers (Go, Python, and JS; Rust and C do not implement GS1):
- GS1 framing
- stream cursors / readers / writers
- UI event frames
- streaming validator for incremental tool validation

## Minimal Verified Python Example

```python
import glyph

data = {"name": "Alice", "scores": [95, 87, 92]}

text = glyph.json_to_glyph(data)
value = glyph.parse(text)
fingerprint = glyph.fingerprint(glyph.from_json(data))
```

## Language Notes

### Python
Use the `glyph` module after installing `glyph-py`. The Python README is the current source of truth for the shipped Python surface.

### Go
Install with `go get github.com/Neumenon/glyph/go`. The module (under `go/` in this repo) is dependency-free — standard library only — and builds with `go build ./...` from a checkout.

Within the module, the import path is:

```go
import "github.com/Neumenon/glyph/go/glyph"
```

### JavaScript / TypeScript
Install `cowrie-glyph`. The package exports loose-mode helpers, schema helpers, patch utilities, stream helpers, and the streaming validator.

### Rust
Parked in `attic/rust/glyph-codec/`. Emit-only (no text parser, no patch/GS1/pack). Not published; `cargo add glyph-rs` is not a valid install path. See the attic README for build instructions.

### C
Parked in `attic/c/glyph-codec/`. Emit-only (no text parser, no patch/GS1/pack). Build from source and include `glyph.h`. See the attic README for build instructions.

## Scope Boundary

This reference intentionally avoids duplicating large API tables that tend to drift. For implementation details, use:
- the language README
- the spec docs
- the source itself
