# GLYPH Conformance Suite

This directory contains the official GLYPH-Loose conformance corpus and runner.

---

## What "GLYPH conformance" means

A GLYPH-Loose implementation is **conformant** if, for every case in `corpus/cases/`, it
produces output that exactly matches the corresponding file in `corpus/golden/` (byte-identical,
no trailing newline unless the golden file has one).

The conformance surface is **GLYPH-Loose canonicalization only** — the mapping from JSON input
to GLYPH-Loose canonical text as specified in:

- `docs/CANONICAL_FORMS.md` (`glyph-canonical-1.0.0`) — authoritative rules
- `docs/LOOSE_MODE_SPEC.md` (`glyph-loose-1.0.0`) — supplementary detail

GS1 framing (`docs/GS1_SPEC.md`) has its own test suite inside the Go package and is not part
of this corpus.

---

## Corpus

`corpus/` is a materialized copy of `go/glyph/testdata/loose_json/`.
Do not edit it directly. Regenerate with:

```
bash conformance/materialize_corpus.sh
```

### Structure

```
corpus/
  manifest.json         # Canonical list of all 51 cases (name + file path)
  cases/                # JSON input files  (NNN_name.json)
  golden/               # Expected GLYPH output (NNN_name.want)
```

Each `.want` file contains the exact bytes a conforming emitter must produce for the
corresponding `.json` input when called via the GLYPH-Loose path.

---

## Running the conformance suite

```bash
# All three reference implementations (Go, Python, JS):
bash conformance/run_conformance.sh

# Or via Python (same logic, friendlier output):
python conformance/run_conformance.py
```

The runner will report per-implementation pass/fail for each case and exit non-zero if any
required implementation fails.

**Requirements:**

| Implementation | Requirement |
|---|---|
| Go | `go` on PATH; module resolves from `go/` directory |
| Python | Python 3.8+; `glyph` package importable from `py/` |
| JavaScript | `node` on PATH; `js/dist/index.js` must exist (`npm run build` in `js/`) |

---

## Claiming conformance

To claim "GLYPH-Loose conformant":

1. Run `run_conformance.sh` (or an equivalent driver) against your implementation for all 51
   cases in this corpus.
2. All cases must produce byte-identical output matching `corpus/golden/`.
3. State the corpus version (`manifest.json` → `version` field) in your claim.
4. Example: *"This library is GLYPH-Loose conformant against corpus v2.2.1-loose."*

There is no formal certification. The claim is self-reported and verifiable by anyone with this
repo.

To report a spec–code divergence, open an issue with the label `spec-divergence`. See
`SPEC_GOVERNANCE.md` for the full process.

---

## Testing your own implementation

Feed each file in `corpus/cases/` through your `fromJsonLoose` + `canonicalizeLoose` pipeline
and compare the output bytes against the corresponding file in `corpus/golden/`. The comparison
must be exact (no whitespace normalization).

Pseudocode:

```
for each case in manifest.json:
    input  = read(corpus/cases/<case.file>)
    want   = read(corpus/golden/<name>.want)
    got    = your_impl.from_json_loose(input).canonicalize_loose()
    assert got == want, f"FAIL {case.name}: got {repr(got)}, want {repr(want)}"
```
