# GLYPH Go

Go implementation of the GLYPH codec and GS1 stream tooling.

## Install

```bash
go get github.com/Neumenon/glyph
```

Import the codec package as:

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

For the repo-wide doc map, start at [../README.md](../README.md).
