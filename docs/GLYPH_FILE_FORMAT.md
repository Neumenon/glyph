# GLYPH File Format Specification

## Overview

A `.glyph` file is a text-based serialization file using the GLYPH-Loose canonical encoding. It serves as a compact, LLM-friendly alternative to JSON for configuration, state snapshots, and structured data.

## File Properties

| Property | Value |
|----------|-------|
| Extension | `.glyph` |
| MIME type | `text/glyph` |
| Encoding | UTF-8 (no BOM) |
| Line endings | LF (`\n`) |
| Shard content type | `CONTENT_TYPE_GLYPH = 0x0004` |

## Content Format

A `.glyph` file contains GLYPH-Loose canonical text, as produced by `CanonicalizeLoose()` (Go), `canonicalize_loose()` (Python), or `canonicalizeLoose()` (JS).

### Allowed Top-Level Forms

1. **Value**: A single GLYPH value (map, list, struct, or scalar)
   ```
   {action=search query="weather in NYC" max_results=10}
   ```

2. **With directives**: Optional `@schema`, `@pool`, `@tab` preamble followed by a value
   ```
   @pool.str id=S1 ["hello" "world"]

   {greeting=^S1:0 farewell=^S1:1}
   ```

3. **Patch**: A `@patch ... @end` block (for delta files)
   ```
   @patch
   = .step 2
   + .items {id=1 name="item_1"}
   @end
   ```

### Directives

| Directive | Purpose |
|-----------|---------|
| `@schema#<id>` | Schema reference or inline definition |
| `@pool.str id=<id> [...]` | String pool definition |
| `@pool.obj id=<id> [...]` | Object pool definition |
| `@tab _ [col1 col2 ...]` | Tabular (column-oriented) encoding |
| `@patch ... @end` | Semantic delta encoding |

## Detection

A `.glyph` file can be identified by:
1. File extension: `.glyph`
2. First non-whitespace character is one of: `{`, `[`, `@`, or an uppercase letter (struct type name)
3. In shard context: entry content type equals `0x0004`

## Fingerprinting

The canonical fingerprint of a `.glyph` file is the SHA-256 hash of its UTF-8 byte content after canonicalization. This matches the `fingerprint_loose()` / `StateHashLoose()` functions across all language implementations.

## In Shard v2 Context

When stored in a Shard v2 container:
- Content type: `CONTENT_TYPE_GLYPH = 0x0004` (stored in index entry reserved field)
- Entry name: typically ends in `.glyph` (e.g., `config.glyph`)
- Compression: optional (zstd or lz4 at the shard level)
- The shard reader does not parse GLYPH content; it is treated as opaque UTF-8 bytes

## Cross-References

- [GLYPH Loose Mode Spec](LOOSE_MODE_SPEC.md) - Full canonical encoding rules
- [GS1 Streaming Spec](GS1_SPEC.md) - Streaming frames carrying GLYPH payloads
- [GLYPH Specifications](SPECIFICATIONS.md) - Complete language specification
