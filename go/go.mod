module github.com/Neumenon/glyph

go 1.24.0

require (
	github.com/Neumenon/cowrie/go/v2 v2.0.0
	github.com/klauspost/compress v1.18.0 // indirect
)

// cowrie is required ONLY by the optional `cogs` bridge (//go:build cogs:
// glyph/bridge.go, glyph/bridge_collision_test.go, cmd/bridgecheck). The default
// build (`go build ./...`, no tags) never imports it and is clean.
//
// CAVEAT (release): Go has no tag-conditional `require`, so this line sits in the
// published go.mod unconditionally. Until cowrie/go/v2 is tagged+published to the
// Go proxy, external `go get github.com/Neumenon/glyph` / `go mod tidy` FAIL while
// resolving it (a plain `go build` still works via module-graph pruning). To make
// `go get` clean for everyone, either publish cowrie or move the cogs bridge into
// a separate module (blocked today because bridge.go uses unexported glyph
// internals). The replace below resolves cowrie from the monorepo for local
// `-tags cogs` development only.
replace github.com/Neumenon/cowrie/go/v2 => ../../cowrie/go
