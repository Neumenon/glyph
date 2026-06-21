# GLYPH Go

Go implementation of the GLYPH codec and GS1 stream tooling. Together with Python and JavaScript, Go is one of the three conformance-surface implementations; Rust and C ports are parked in `attic/`.

## Install

```bash
go get github.com/Neumenon/glyph/go
```

> **Note:** the module path follows the monorepo subdir convention (`/go` suffix). The repo must be public (or `GOPRIVATE` / `GONOSUMCHECK` configured for it) for `go get` to resolve it through the Go module proxy.

For a local checkout instead:

```bash
git clone https://github.com/Neumenon/glyph
cd glyph/go
go build ./...
```

## Quick Start

```go
package main

import (
    "fmt"
    glyph "github.com/Neumenon/glyph/go/glyph"
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

- The module path is `github.com/Neumenon/glyph/go`.
- The codec package lives under `github.com/Neumenon/glyph/go/glyph`.
- The stream package lives under `github.com/Neumenon/glyph/go/stream`.

For the repo-wide doc map, start at [../README.md](../README.md).
