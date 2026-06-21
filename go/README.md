# GLYPH Go

Go implementation of the GLYPH codec and GS1 stream tooling. Together with Python and JavaScript, Go is one of the three conformance-surface implementations; Rust and C ports are parked in `attic/`.

## Status: in-repo / source preview

The Go codec is a full conformance implementation, but it is **not yet a polished
external module**, so `go get github.com/Neumenon/glyph` is not a stable install
path today. Two things block a clean `go get` / `go mod tidy`:

- the module lives in the `go/` subdirectory of this repo (its module path is
  `github.com/Neumenon/glyph`, which does not match the repo-root layout `go get`
  expects), and
- the optional dev-only `cogs` bridge pulls an unpublished `cowrie/go/v2`
  dependency, so external `go get` / `go mod tidy` fail resolving it. A plain
  `go build` of the codec still works via module-graph pruning — see
  [Internal: `cogs` cowrie bridge](#internal-cogs-cowrie-bridge-not-part-of-the-release-surface)
  and the caveat in `go.mod`.

Until external module packaging is stabilized, use the codec from a checkout of
this repo:

```bash
git clone https://github.com/Neumenon/glyph
cd glyph/go
go build ./...
```

Within the module, import the codec package as:

```go
import glyph "github.com/Neumenon/glyph/glyph"
```

## Quick Start

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

    jsonValue, _ := glyph.FromJSONLoose([]byte(`{"status":"active","count":42}`))
    fmt.Println(glyph.CanonicalizeLoose(jsonValue))
}
```

## Core Surfaces

- `Parse`, `ParseWithSchema`, `ParseWithOptions`
- `FromJSONLoose`, `ToJSONLoose`
- `CanonicalizeLoose`, `CanonicalizeLooseNoTabular`, `FingerprintLoose`
- packed / tabular / patch helpers under `go/glyph`
- GS1 stream helpers under `go/stream`

## Notes

- The module path is `github.com/Neumenon/glyph`.
- The codec package lives under `github.com/Neumenon/glyph/glyph`.
- The stream package lives under `github.com/Neumenon/glyph/stream`.

## Internal: `cogs` cowrie bridge (not part of the release surface)

Files behind `//go:build cogs` (`glyph/bridge.go`, `cmd/bridgecheck`) provide an
internal bridge between `GValue` and the binary [cowrie](https://github.com/Neumenon/cowrie)
wire format. It is **not** a published feature: the default build never compiles
it, and it depends on an unpublished sibling. Build it for local development only:

```sh
# requires a cowrie/go checkout at ../../cowrie/go (see the replace in go.mod)
go build -tags cogs ./...
```

See the caveat in `go.mod`: until cowrie is published, external
`go get`/`go mod tidy` cannot resolve it. Use the default (no-tags) build for the
shipped codec.

For the repo-wide doc map, start at [../README.md](../README.md).
