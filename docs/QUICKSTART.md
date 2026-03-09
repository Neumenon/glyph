# GLYPH Quickstart

Get a verified feel for the codec in a few minutes.

## Install

| Language | Command |
|----------|---------|
| Python | `pip install glyph-py` |
| Go | `go get github.com/Neumenon/glyph` |
| JavaScript / TypeScript | `npm install cowrie-glyph` |
| Rust | `cargo add glyph-rs` |
| C | build from `../c/glyph-codec/` |

## Python

```python
import glyph

data = {"action": "search", "query": "glyph codec", "limit": 5}

text = glyph.json_to_glyph(data)
print(text)
# {action=search limit=5 query="glyph codec"}

value = glyph.parse(text)
print(value.get("query").as_str())

fp = glyph.fingerprint_loose(glyph.from_json(data))
print(fp)
```

## Go

```go
package main

import (
    "fmt"
    glyph "github.com/Neumenon/glyph/glyph"
)

func main() {
    parsed, err := glyph.Parse(`{name=Alice age=30}`)
    if err != nil {
        panic(err)
    }

    name, _ := parsed.Value.Get("name").AsStr()
    fmt.Println(name)
}
```

## JavaScript / TypeScript

```typescript
import { fromJsonLoose, canonicalizeLoose } from 'cowrie-glyph';

const value = fromJsonLoose({
  action: 'search',
  query: 'glyph codec',
  limit: 5,
});

console.log(canonicalizeLoose(value));
// {action=search limit=5 query="glyph codec"}
```

## Rust

```rust
use glyph_rs::{from_json, canonicalize_loose};
use serde_json::json;

let value = from_json(&json!({
    "action": "search",
    "query": "glyph codec",
    "limit": 5
}));

println!("{}", canonicalize_loose(&value));
```

## What To Read Next

- [../README.md](../README.md) for the repo overview
- [LOOSE_MODE_SPEC.md](./LOOSE_MODE_SPEC.md) for canonicalization rules
- [GS1_SPEC.md](./GS1_SPEC.md) for streaming transport
- [API_REFERENCE.md](./API_REFERENCE.md) for the current package map

## What Not To Treat As Canonical

The demo docs, visual guide, and reports are useful context, but they are not the primary source of truth for the codec surface. Use the README, spec docs, and language READMEs first.
