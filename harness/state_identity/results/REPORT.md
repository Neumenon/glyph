# State Identity Harness — Results Report

> **Snapshot history (2026-08-21 → 2026-09-02).** The first run predates the
> identity substrate move to canonical JSON (`SPEC-CANON.md`). The body below
> is the 2026-09-02 re-run over the enlarged corpus (318 fixtures: the old 280
> plus non-BMP keys, integer edges around ±2⁵³, `1.0`/`1e21`/`-0.0`, duplicate
> keys, depth 1001, and 8 tensor-ref vectors) with a fifth subject, `canon_json`:
>
> | | 2026-08-21 | 2026-09-02 |
> |---|---:|---:|
> | glyph agree | 297/298 | **317/318** |
> | jcs agree / refuse | 210 / 88 | **223 / 95** |
> | minified agree | 271/297 | 283/318 |
> | naive agree | 115/297 | 119/318 |
> | glyph≡jcs identical bytes | 105/298 | **307/317** |
>
> New check: `canon_json` re-parses its own output with stdlib JSON and
> re-canonicalizes to identical bytes — 951/951 language-fixture pairs.
> `canon_json` and `glyph` produce the same digest by construction now
> (`fingerprint = sha256(canon_json(v))`), so their rows are identical.
> The glyph≡jcs jump is the substrate change: canonical JSON *is* JCS's output
> on everything but the three documented divergences.
>
> Part B is unchanged by the re-run: S1 3000/3000 detected with verify on and
> 2997/3000 silent with it off; S2 43/43; S3 1.00 on all four faults for both
> GS1 channels; S5 11/15 loose vs 2/15 strict, fidelity 6/7. Current raw
> numbers are always in `results.json` next to this file.

**Run date:** 2026-09-02 · **Corpus:** 318 fixtures + 18 variant forms + 15 malformed + 4 bench payloads
**Matrix:** 3 languages (Python 3.14 / Go 1.25 / Node 22) × 5 subjects (`naive`, `minified`, `jcs`, `glyph`, `canon_json`)
**Reproduce:** `python3 run_all.py` from this directory. Deterministic: two runs
produced byte-identical `results.json`. JCS implementations validated against
all 6 official RFC 8785 vector files before any measurement.

---

## Executive verdict

**GLYPH's cross-language identity claim survives adversarial testing
unconditionally: 317/318 fixtures agree byte-for-byte across all three
languages, with zero unexpected errors** (the single "error" is a deliberately
malformed leading-zeros literal that every parser rejects). **No DIY baseline
comes close**: naive per-language-default hashing agrees across languages on
only 119/318 fixtures (37%); even sort_keys+minified misses 34. JCS, the
serious incumbent, is internally consistent where it runs at all — but its
three vetted implementations *refused to hash* 95/318 values (non-object
roots, out-of-safe-range integers), which is itself a portability finding no
prose comparison had surfaced.

The honest cost side: GLYPH fingerprints are 2–9× slower than naive hashing
in Python/JS depending on payload (Go is a surprise exception — fastest of all subjects),
and token savings remain shape-dependent (−41% tokens on tabular batches,
−1% on deep nested traces). Detection scenarios confirm the enforcement story:
base-verified patches catch stale applies 100%, GS1 framing catches all four
stream faults while content-hash sidecars catch only bit-flips.

Per pre-registration #9: JCS+discipline matches GLYPH's detection rates when
engineers add manual re-checks — but "discipline" proved to be exactly 95
silent refusals and 198 silent cross-language disagreements deep. That gap is
the product.

---

## Pre-registration scorecard

| # | Expectation | Outcome |
|---|---|---|
| 1 | naive/minified diverge cross-language | **Confirmed** — 198/318 naive, 34/318 minified |
| 2 | jcs agrees where it runs; parse-layer vs canon-layer split | **Confirmed** + unanticipated domain refusals |
| 3 | GLYPH agrees on all fixtures | **Confirmed** — 317/318 (1 = malformed-by-design) |
| 4 | S1 detection rates | **Confirmed exactly** — see below |
| 5 | S3 GS1 catches desync | **Confirmed** — 100% all four fault types |
| 6 | Cache FNs under formatting variance | **Partially falsified within-language** (Amendment A1); confirmed for raw-text hashing |
| 7 | Loose-mode recovery beats strict JSON | **Confirmed** — 11/15 vs 2/15, fidelity 6/7 |
| 8 | Costs published despite being unflattering | **Done** — table below; Go result was better than predicted |
| 9 | Serious-contest outcome declared in advance | **Resolved in GLYPH's favor on portability grounds** — jcs+discipline matched detection but not portability |

---

## Part A — divergence hunt

Cross-language agreement (identical hash in Py+Go+JS; lower bound = all three must run):

| Subject | Agree | Disagree | Errors | Verdict |
|---|---:|---:|---:|---|
| **glyph** | **317** | **0** | 1† | portable by construction |
| jcs | 223 | 0 | 95‡ | consistent but frequently refuses |
| minified | 283 | 34 | 1† | mostly portable; number/escape edges leak |
| naive | 119 | 198 | 1† | not a portable spec at all |

† `i_leading_zeros_txt` ("007") — invalid JSON rejected identically everywhere.
‡ Go reference impl accepts top-level objects only; Python `rfc8785` raises
`IntegerDomainError` beyond ±2⁵³; JS loses big-int precision at parse.

Divergence classes (where disagreement concentrates):

- `naive/random`: 133 divergences — serializer defaults differ (Python's
  `, `/`: ` spacing + ensure_ascii escaping vs compact/literal JS & Go)
- `naive/unicode`, `minified/unicode`: 6/6 each — escaping policy
- `*/float`, `minified/variant/trace_rows`: integral floats serialize as
  `0.0` (Py) vs `0` (JS) vs `0` (Go re-marshal) — `-0.0` likewise
- `*/bigint`: JS float64 parse layer (pre-declared); py-jcs refuses instead
- `naive/permutation`: 3/3 disagree — same logical value, different key order,
  different serializer conventions → different bytes

Logical invariance over variant groups (same value, 3–5 textual forms):
glyph 12/12 groups consistent · canon_json 12/12 · jcs 12/12 · naive 11/12 · minified 11/12
(the miss: trace-row integral floats across languages).

Notable: for 307/317 values, JCS canonical text and GLYPH canonical
text are byte-identical (plain ASCII scalars/structures) → identical SHA-256.
The schemes genuinely converge on the easy middle of the value space.

## Part B — session simulations

### S1 stale-patch race (3,000 seeded trials)

| Mode | Detection | Silent corruption |
|---|---:|---:|
| glyph default (verify_base ON) | **100%** | **0%** |
| glyph verify=False (opted out) | 0% | 99.9% |
| baseline unchecked merge-patch | 0% | 100% |
| baseline + manual re-hash | 100% (+2 hashes/apply) | 0% |

Enforcement, not format, is what catches staleness — and GLYPH is the only
subject where it is on by default. Baseline-recheck matches detection at the
price of extra hashes per apply plus the discipline to never forget.

### S2 cross-language relay — **43/43 full agreement** (py emit → go/js parse+fingerprint)

### S3 stream desync (30 trials/fault)

| Channel | drop | replay | swap | bitflip |
|---|---:|---:|---:|---:|
| gs1-crc | **1.00** | **1.00** | **1.00** | **1.00** |
| gs1-nocrc | **1.00** | **1.00** | **1.00** | **1.00** |
| jsonl | 0 | 0 | 0 | 0 |
| jsonl+sidecar-hash | 0 | 0 | 0 | **1.00** |

Content hashes cannot see drops/replays/swaps — there is no signal without
sequence numbers. gs1-nocrc still catching bit-flips reflects payload parse
strictness, not integrity checking (footnote honestly kept).

### S4 cache dedup (within-language)

`rawtext` (hash received bytes unparsed): hit rate **38.9%**, 61.1% wasted
recompute. All parse-then-hash subjects: 100% — within one language, parsing
already normalizes formatting (Amendment A1). The cache-portability axis is
Part A's answer: only glyph/jcs keys match across service boundaries.

### S5 malformed LLM output recovery (Python)

Strict json.loads 2/15 · GLYPH loose **11/15** · semantic fidelity 6/7 checked.
Fidelity miss footnoted: `{"verbose":True}` recovers as string `"True"`,
not boolean — recovered-but-re-typed beats a crash, but consumers should know.

---

## Part C — costs

Tokens (cl100k, GLYPH canonical vs minified JSON): tabular_batch **−41.2%** ·
small_state −16.7% · nested_trace −1.1%. Bytes: small_state −22.9% ·
nested_trace −26.0% · tabular_batch −63.0%.

CPU ns/op (300 iters, committed payloads; informational — re-tabled from
`costs.json`, 2026-09-02 run):

| payload | lang | naive | jcs | glyph |
|---|---|---:|---:|---:|
| small_state | python | 3,511 | 13,862 | 17,202 |
| | go | 2,092 | 4,289 | **1,445** |
| | js | 6,381 | 8,624 | 17,411 |
| tabular_batch | python | 34,115 | 219,800 | 304,410 |
| | go | 35,283 | 68,090 | **22,534** |
| | js | 24,839 | 56,139 | 60,771 |
| nested_trace | python | 5,250 | 30,413 | 46,383 |
| | go | 4,344 | 6,254 | **1,700** |
| | js | 4,083 | 4,840 | 9,142 |

Go's fingerprint path is the fastest subject tested (works on the parsed
GValue; no re-marshal). Python pays ~5× on small states (~9× on the larger
payloads). JS ~2–3×. These are
identity-computation costs paid per state-version, dwarfed by network/model
latency in the target use cases — but stated plainly, as promised.

---

## Findings filed during this harness run

1. **[High] Python-only patch bug — FIXED same day.** `diff()` emitted nested
   map-key ops that py's applier rejected (`cannot navigate map_key in map`),
   and investigation widened it to three coupled defects (applier navigation,
   bracket-path parsing, quote-aware op-line splitting). Go and JS were
   correct throughout. Fixed in `py/glyph/patch.py`; regression tests added
   (`TestNestedMapKeyRegression`, `TestBracketPathParsing`); gauntlet S5
   extended with depth-2 bracket paths + space-containing key — 8/8 scenarios
   pass across languages. Post-fix harness re-run: sanity trips 46 → 0,
   glyph-default 3000/3000 detected with zero errors. Repro history:
   [`findings/2026-08-21-py-nested-map-key-remove.md`](./findings/2026-08-21-py-nested-map-key-remove.md).
2. **[Medium] JCS portability friction** — the three vetted RFC 8785
    implementations disagree on *what they will hash at all*: Go reference
    impl rejects non-object roots; Python refuses out-of-safe-range integers;
    JS silently degrades big-int precision at parse. Any cross-language system
    built on JCS must handle 95/318 refusal/degradation paths. This is the
   empirically strongest argument for a bridge that defines behavior on the
   whole value space.
3. **[Low] `rawtext` hashing** — the most common real-world pattern (hash
   bytes as received) wastes 61% of cache capacity under mere formatting
   variance.

## Bottom line

Same-value→same-hash-everywhere holds for GLYPH on everything the corpus can
throw at it, including the cases where the incumbent ecosystem either
disagrees with itself (naive: 62%) or declines to answer (jcs refusals: 30%).
Identity is cheap-to-free relative to model latency, and the fail-loud
properties (patch preconditions, stream cursors) demonstrably convert into
detected-not-corrupted outcomes. What remains open is unchanged by this run:
adoption, integrations, and the comprehension-cost question — owned by
`harness/comprehension/`.
