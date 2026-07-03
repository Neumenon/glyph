> **PARKED: emit-only Rust port, not a conformance port (no GLYPH text
> parser, no patch/GS1/pack). Lives in attic/. Kept for reference.**

# GLYPH Codec - Rust

Rust implementation of the GLYPH codec.

## Install

**Not published.** `Cargo.toml` sets `publish = false`, and this crate has
never been pushed to crates.io — `cargo add glyph-rs` will fail to resolve.
It is a parked, emit-only port kept for reference in `attic/`; build it from
source.

Build and test in place:

```bash
cd attic/rust/glyph-codec
cargo build
cargo test
```

To depend on it from another crate in this repo, use a path dependency
(adjust the relative path to your crate's location):

```toml
[dependencies]
glyph-rs = { path = "../attic/rust/glyph-codec" }
serde_json = "1"
```

In Rust code, import it as `glyph_rs`.

## Quick Start

```rust
use glyph_rs::{from_json, to_json, canonicalize_loose, hash_loose};
use serde_json::json;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let data = json!({
        "action": "search",
        "query": "glyph codec",
        "limit": 5
    });

    let value = from_json(&data);
    let text = canonicalize_loose(&value)?;
    let restored = to_json(&value);
    let hash = hash_loose(&value)?;

    println!("{}", text);
    println!("{}", restored);
    println!("{}", hash);

    Ok(())
}
```

## Current Surface

- loose-mode canonicalization
- JSON bridge
- 64-hex SHA-256 fingerprint (`hash_loose` / `fingerprint_loose`): hashes the
  no-tabular canonical form and returns the full 64-character hex digest,
  matching Go/Python/JS `FingerprintLoose` semantics
- schema evolution helpers
- streaming validator

**Known limitation — float formatting**: this port formats floats with a
hand-rolled decimal/exponential printer that may diverge from the canonical
shortest-roundtrip representation used by the Go, Python, and JS ports. Float
formatting unification is deferred and out of scope for this port.

This crate is currently best read as the Rust codec implementation, not as the full spec surface for every GLYPH feature described elsewhere in the repo.

For the repo-wide doc map, start at [../../README.md](../../README.md).
