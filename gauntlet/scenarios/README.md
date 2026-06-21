# GLYPH 8-Scenario Cross-Language Gauntlet

A scenario-based acceptance suite that exercises **every major GLYPH capability**
as realistic AI-workflow usage, runs each scenario **identically across the three
conformance implementations** (Go, Python, JS), applies one consistent **pass/fail**
rubric, records evidence for every outcome, and gates on a hard exit code.

```
python3 gauntlet/scenarios/gauntlet.py            # build JS, run all, report, exit 1 on any fail
python3 gauntlet/scenarios/gauntlet.py --no-build  # skip the JS tsc build (use existing dist/)
```

## How it is structured

| Piece | Role |
|-------|------|
| `gen_inputs.py` → `inputs.json` | **Single shared fixture source.** All three runners read the same bytes → "same conditions". Regenerate with `python3 gen_inputs.py`. |
| `runner.py`, `runner.cjs`, `../../go/cmd/gauntletrunner` | **Per-language runners.** Each runs the scenarios applicable to it using the real public API and prints a JSON *evidence* object. Runners **measure only** — they never decide pass/fail. |
| `gauntlet.py` | **Orchestrator / single evaluator.** Runs all three runners, applies identical pass/fail criteria (incl. byte-for-byte cross-language equality), prints the report, writes `report.json`, exits non-zero on any failure. |

The Go runner lives inside the Go module (`go/cmd/gauntletrunner`) so the local
`glyph`/`stream` packages resolve without a separate module.

## Evaluation method

**Pass/fail**, applied by the orchestrator (one evaluator → consistent across
languages). A scenario passes iff **every applicable language ran cleanly AND
every check holds** — per-language checks *and* cross-language byte-for-byte
equality checks. All evidence (canonical strings, fingerprints, byte counts,
wire hashes, verdicts) is recorded in `report.json`.

## The 8 scenarios

| # | Scenario | Langs | Capability | Key success criteria |
|---|----------|-------|------------|----------------------|
| S1 | JSON bridge round-trip fidelity | go/py/js | JSON ↔ GLYPH | round-trip == source (each lang); round-trips identical across langs |
| S2 | Canonicalization determinism + agreement | go/py/js | canonical form | key-order variants → one canonical form; canonical + number formatting identical across langs |
| S3 | Fingerprint identity, sensitivity & parity | go/py/js | state fingerprint | equal→equal, changed→different, 64-hex; `fp` byte-for-byte identical across langs |
| S4 | Tabular compaction + recovery + parity | go/py/js | pack/tabular | emits `@tab`; tabular < JSON (≥40%) and < list form; round-trips; tabular canonical identical across langs |
| S5 | Patch apply (set/append/delete/Δ) | go/py/js | patch | applied state == expected; base immutable; result + fingerprint identical across langs |
| S6 | Patch base verification / fail-closed | go/py/js | patch `@base` | correct base accepted, **stale base rejected** (Go/Py); base fingerprint identical across Go/Py/JS |
| S7 | GS1 framing: wire parity + cursor | go/js | GS1 stream | frames decode; **stale-base patch frame rejected**; encoded wire bytes + state hash byte-for-byte identical (Go==JS) |
| S8 | Streaming firewall (early rejection) | py/js | streaming validator | allowed accepted; **unknown tool rejected early** (bytes avoided); verdict parity Py/JS |

Cross-language conformance — GLYPH's core value prop — is woven through S1–S5
(all three), S6 (base parity, all three), S7 (Go↔JS wire bytes), and S8 (Py↔JS
verdict).

## Findings from the first run (fixed)

The first full run was **6/8**. The two failures were genuine cross-language
divergences where **Go and JS agreed and Python was the outlier**; per the
decision that **Go is the source of truth**, Python was brought into line:

1. **S4 — tabular header.** Go/JS emit `@tab _ rows=N cols=M [cols]` (v2.4.0
   metadata for streaming resync); Python emitted the bare `@tab _ [cols]` and
   its parser *rejected* the Go/JS form (so Python could not read Go/JS tabular
   output). Fix: `py/glyph/loose.py` emits the metadata; `py/glyph/parse.py`
   tolerates `rows=/cols=` (and any `key=val`) before `[`.

2. **S6 — patch `@base` basis.** Go/JS compute `@base = sha256(canonicalize_loose(state))[:16]`
   (tabular form, null → `_`); Python used the no-tabular fingerprint basis
   (null → `∅`). They diverge whenever the base state contains a null. Fix:
   `py/glyph/patch.py` `compute_base_fingerprint`/`verify_patch_base` use
   `canonicalize_loose`, matching Go/JS and `LOOSE_MODE_SPEC.md` §"Patch Base
   Fingerprint". The README invariant block was corrected accordingly.

After the fixes: **8/8**, with the full existing suites still green
(py 444, py-gauntlet 81, go all, js 579, cross-impl parity gate all).

## Numeric domain

Cross-language byte-for-byte checks stay inside the JS-safe integer domain
(`|int| ≤ 2^53`). Integers beyond that (`9007199254740992`) are a **documented**
divergence (Go preserves int64; Py/JS fall back to float), not a conformance
target, so the fixtures avoid them in parity-gated positions.
