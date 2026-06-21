# GLYPH API Reference

This page is a routing layer, not a substitute for the language READMEs.

The purpose is to give the current package names, import surfaces, and the core codec concepts that are shared across implementations.

## Package Names

| Language | Package | Primary Doc |
|----------|---------|-------------|
| Python | `glyph-py` | [../py/README.md](../py/README.md) |
| Go | in-repo / source preview (module under `go/`; `go get` not yet a stable path) | [../go/README.md](../go/README.md) |
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
- Go/Python/JS value identity: `fingerprint_loose` / `fingerprintLoose` / `FingerprintLoose`

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
The streaming layer covers (Go and JS only — Python, Rust, and C do not implement GS1):
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
fingerprint = glyph.fingerprint_loose(glyph.from_json(data))
```

## Language Notes

### Python
Use the `glyph` module after installing `glyph-py`. The Python README is the current source of truth for the shipped Python surface.

### Go
**In-repo / source preview.** The Go codec is a full conformance implementation, but it is not yet a polished external module: the module lives under `go/`, and `go get github.com/Neumenon/glyph` / `go mod tidy` do not yet resolve cleanly (subdirectory layout plus an optional dev-only bridge that pulls an unpublished dependency). Use it from a checkout of this repo (`cd go && go build ./...`) until module packaging is stabilized.

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
