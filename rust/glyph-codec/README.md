# GLYPH Codec - Rust

Rust implementation of the GLYPH codec.

## Install

```toml
[dependencies]
glyph-rs = "1.0"
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
- 16-hex hash helper plus canonical-form fingerprint helper
- schema evolution helpers
- streaming validator

This crate is currently best read as the Rust codec implementation, not as the full spec surface for every GLYPH feature described elsewhere in the repo.

For the repo-wide doc map, start at [../../README.md](../../README.md).
