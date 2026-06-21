# GLYPH Spec Governance

This document describes how the GLYPH specifications are versioned, how they change, and what
external implementers can expect.

---

## 1. What counts as a spec

Three documents form the normative specification surface:

| Document | Spec ID | Covers |
|---|---|---|
| `docs/CANONICAL_FORMS.md` | `glyph-canonical-1.0.0` | Canonical form rules (authoritative) |
| `docs/LOOSE_MODE_SPEC.md` | `glyph-loose-1.0.0` | GLYPH-Loose subset |
| `docs/GS1_SPEC.md` | `gs1-1.0.0` | GS1 stream framing |

`CANONICAL_FORMS.md` is the authoritative contract for the canonical form rules; it supersedes
conflicting statements in other documents where it says so explicitly.

The 51-case conformance corpus in `conformance/corpus/` (sourced from
`go/glyph/testdata/loose_json/`) is normative test data. A case file + its paired `.want` file
define expected output for all conforming implementations.

---

## 2. Spec versioning

Spec IDs follow **semver** (`MAJOR.MINOR.PATCH`), independent of any implementation version.

| Increment | When |
|---|---|
| PATCH | Wording clarification with no behavior change; no re-test required |
| MINOR | New optional behavior or corpus addition that is backward-compatible |
| MAJOR | Any change to canonical output for existing inputs; existing conformance claims must be re-verified |

A corpus case, once frozen, has immutable `input → output`. Removing a case is a MAJOR change.
Adding a case is a MINOR change.

This project is **pre-1.0**. The `1.0.0` IDs on the existing specs are intentional — they mark
the first stable freeze of the conformance surface, not a production-ready commitment. Breaking
changes before a public v1 release may happen with a MINOR corpus version bump and a clear
changelog entry.

---

## 3. Change process

1. Open an issue describing the proposed change and the reason.
2. Update the relevant spec document(s) and bump the version in the header.
3. If canonical output changes for any existing case, update `go/glyph/testdata/loose_json/golden/`
   and regenerate `conformance/corpus/` (run `conformance/materialize_corpus.sh`).
4. All three gate implementations (Go, Python, JS) must pass `conformance/run_conformance.sh`
   before merging.
5. Tag the commit with `spec-vX.Y.Z` (e.g. `spec-v1.0.1`) in addition to any code tags.

---

## 4. Backward-compatibility commitment

Within a MAJOR version (e.g. `1.x`):

- Canonical output for any **existing** corpus input will not change.
- New corpus cases will not contradict existing cases.
- The Go module path (`github.com/Neumenon/glyph/go`) will not change.
- The Python package name (`glyph-py`) and the npm package name (`cowrie-glyph`) will not change.

**No ABI/API stability is guaranteed at this stage** for non-canonical-form surfaces (GS1
framing flags, experimental emitters, schema APIs). Those surfaces are marked in `doc.go`.

---

## 5. Divergence reports

If an external implementer finds a case where their implementation matches the spec but the
reference implementations produce different output, or where the spec is ambiguous:

1. Open an issue in this repo with the label `spec-divergence`.
2. Include: the spec document + section, the input, expected output (per spec), actual output
   from one or more reference implementations.
3. The maintainer will respond within a reasonable time. There is no SLA — this is a small
   open-source project maintained by one person.

If the code is wrong: a fix will be released as a patch to the affected implementation(s).
If the spec is ambiguous: the spec will be clarified with a PATCH version bump.
If the spec is wrong: the spec will be corrected; if canonical output changes, a MAJOR bump.

---

## 6. Claiming conformance

An implementation may claim "GLYPH-Loose conformant (corpus vX.Y)" if it passes all cases in
the `conformance/corpus/` directory at that corpus version. See `conformance/README.md` for how
to run the corpus and what to include in a conformance claim.

There is no formal certification body. The claim is self-reported.
