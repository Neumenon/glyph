module github.com/Neumenon/glyph

go 1.24.0

require (
	github.com/Neumenon/cowrie/go v0.0.0
	github.com/klauspost/compress v1.18.0 // indirect
)

// Local development: cowrie/go v2.0.0 uses a module path without /v2 suffix,
// which is invalid for Go modules v2+. Until cowrie migrates to
// github.com/Neumenon/cowrie/go/v2, we use a replace directive.
// See: https://go.dev/ref/mod#major-version-suffixes
replace github.com/Neumenon/cowrie/go => ../../cowrie/go
