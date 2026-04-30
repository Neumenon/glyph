# GLYPH Documentation

This directory is the active documentation surface for the `glyph` codec.

If you only read three files, read these:
1. [../README.md](../README.md)
2. [QUICKSTART.md](./QUICKSTART.md)
3. [LOOSE_MODE_SPEC.md](./LOOSE_MODE_SPEC.md)

## Active Docs

### Product / Repo Entry
- [../README.md](../README.md) — codec-first repo overview and install matrix
- [QUICKSTART.md](./QUICKSTART.md) — minimal verified examples
- [API_REFERENCE.md](./API_REFERENCE.md) — current package names and language doc links

### Authoritative Specs
- [LOOSE_MODE_SPEC.md](./LOOSE_MODE_SPEC.md) — loose mode and canonicalization
- [GS1_SPEC.md](./GS1_SPEC.md) — multiplexed streaming protocol

### Supporting Guides
- [GUIDE.md](./GUIDE.md) — broader concepts and patterns
- [SPECIFICATIONS.md](./SPECIFICATIONS.md) — overview-level technical summary

### Language-Specific Docs
- [../py/README.md](../py/README.md)
- [../go/README.md](../go/README.md)
- [../js/README.md](../js/README.md)
- [../rust/glyph-codec/README.md](../rust/glyph-codec/README.md)
- [../c/glyph-codec/README.md](../c/glyph-codec/README.md)

## Historical / Secondary Material

These files are still useful, but they are not the source of truth for the current codec surface:

- [reports/README.md](./reports/README.md) — dated research and benchmark snapshots
- [archive/README.md](./archive/README.md) — archived docs and experiments
- [../DEMO_README.md](../DEMO_README.md) and [../DEMO_QUICK_REFERENCE.md](../DEMO_QUICK_REFERENCE.md) — legacy demo material
- [visual-guide.html](./visual-guide.html) — visual explainer, not authoritative API/spec text
- [../attic/](../attic/) — parked features (agent framework, blob/pool); preserved for history, not part of the lead surface

## Documentation Rules For This Repo

- Specs beat guides.
- Manifests beat README install snippets.
- Language READMEs should document the shipped package names and exported APIs.
- Demo docs and reports must be clearly marked when they are historical or example-only.

## Known Cleanup Boundaries

Some older report/demo files still contain dated package names, benchmark timestamps, or example integrations. Those files should be treated as historical context unless they are explicitly refreshed.
