# GLYPH API Reference

This page is a routing layer, not a substitute for the language READMEs.

The purpose is to give the current package names, import surfaces, and the core codec concepts that are shared across implementations.

## Package Names

| Language | Package | Primary Doc |
|----------|---------|-------------|
| Python | `glyph-py` | [../py/README.md](../py/README.md) |
| Go | `github.com/Neumenon/glyph` | [../go/README.md](../go/README.md) |
| JavaScript / TypeScript | `cowrie-glyph` | [../js/README.md](../js/README.md) |
| Rust | `glyph-rs` | [../rust/glyph-codec/README.md](../rust/glyph-codec/README.md) |
| C | source build | [../c/glyph-codec/README.md](../c/glyph-codec/README.md) |

## Shared Concepts

Every implementation revolves around the same layers:

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
The streaming layer covers:
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
The module is `github.com/Neumenon/glyph`. Import the codec package as:

```go
import "github.com/Neumenon/glyph/glyph"
```

### JavaScript / TypeScript
Install `cowrie-glyph`. The package exports loose-mode helpers, schema helpers, patch utilities, stream helpers, and the streaming validator.

### Rust
Install `glyph-rs`. In code, import it as `glyph_rs`.

### C
Build the library from `c/glyph-codec/` and include `glyph.h`.

## Scope Boundary

This reference intentionally avoids duplicating large API tables that tend to drift. For implementation details, use:
- the language README
- the spec docs
- the source itself
