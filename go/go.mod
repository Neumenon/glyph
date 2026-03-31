module github.com/Neumenon/glyph

go 1.24.0

require (
	github.com/Neumenon/cowrie/go/v2 v2.0.0
	github.com/klauspost/compress v1.18.0 // indirect
)

// Local development: resolve cowrie/go/v2 from the monorepo.
// Remove this replace directive for release builds once cowrie v2.0.1+
// is tagged and published to the Go proxy.
replace github.com/Neumenon/cowrie/go/v2 => ../../cowrie/go
