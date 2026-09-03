# State Identity Harness — pre-registration

**Written before any benchmark runs.** Expected outcomes below are committed
before execution; the report (`results/REPORT.md`) must show where reality
disagreed with them, in either direction.

## Run it

```bash
cd harness/state_identity && python3 run_all.py
# -> results/results.json (deterministic), results/costs.json, results/meta.json
```

Deps: `pip install rfc8785 tiktoken` · `npm install canonicalize` (pinned in
js/package.json devDeps) · Go deps pinned in `subjects/go/go.mod`. No network
at run time.

## Question

> Does content-addressed identity (canonical bytes → SHA-256) with enforced
> patch preconditions measurably reduce silent state corruption and stale-cache
> incidents in multi-agent sessions, versus ad-hoc JSON hashing — and what does
> it cost?

## Subjects

| id | definition |
|---|---|
| `naive` | `sha256(json.dumps(value, sort_keys=True))` per language's default serializer settings |
| `minified` | same + compact separators / no whitespace |
| `jcs` | RFC 8785 canonicalization + SHA-256 |
| `glyph` | GLYPH-Loose canonical form + SHA-256 (`fingerprint_loose`) |

Each subject runs in **Python 3.14, Go 1.25, Node 22** so cross-language
agreement is a measured axis, not an assumption.

Pinned JCS implementations:

- Python: [`rfc8785`](https://pypi.org/project/rfc8785/) (installed 2026-08-21)
- JS: [`canonicalize@2.1.0`](https://www.npmjs.com/package/canonicalize)
- Go: [`github.com/cyberphone/json-canonicalization`](https://github.com/cyberphone/json-canonicalization) @ `19d51d7fe467` (RFC author's reference impl, ES6 number formatter)

All three are validated against the official RFC 8785 test vectors before any
harness run (`selftest_jcs`). A subject that fails its vectors is reported as
invalid rather than compared.

## Parts

- **A. Divergence hunt** — adversarial value corpus (floats, big ints, Unicode
  NFC/NFD, key-order permutations, duplicate keys, null-vs-absent, nesting).
  Every subject hashes every fixture in every language. Oracle flags any
  cross-language disagreement within a subject and cross-subject disagreement
  on logically identical inputs.
- **B. Session simulations** — five seeded scenarios, oracle classifies each
  event as `correct` / `detected-error` / `silent-corrupt` / `wrong-cache-hit`:
  - S1 stale-patch race (patch computed against v1 applied after state moved to v2)
  - S2 cross-language relay (Py writes → Go mutates → JS verifies)
  - S3 stream desync (dropped/replayed/reordered frames vs unframed JSONL)
  - S4 context-cache dedup under formatting variance
  - S5 malformed LLM output recovery (loose mode vs strict parsers)
- **C. Cost accounting** — CPU ns/op per hasher per language, token counts via
  `tiktoken cl100k_base`, storage bytes, integration LOC.

## Pre-registered expectations

If reality matches all of these, the harness confirms the marketing. Where it
doesn't, the report must say so plainly.

1. **naive/minified diverge cross-language** on at least: `-0.0` handling,
   non-ASCII escaping, and integers beyond float64 (JS parse precision).
   *Falsified if they agree on all fixtures.*
2. **jcs agrees cross-language on canonical output** for every fixture whose
   values survive each language's parser intact. Known caveat, pre-declared:
   JS numbers are always float64, so big-int literals lose precision at
   *parse* time in JS regardless of canonicalizer. The harness separates
   parse-layer divergence from canonicalization divergence.
3. **GLYPH agrees cross-language on all fixtures** (conformance-tested surface).
   *Any fixture where it diverges is a conformance gap finding and gets filed,
   not buried.*
4. **S1**: unchecked baselines corrupt silently at ~100% of stale applies;
   baseline+manual-recheck detects as well as GLYPH but costs extra LOC and an
   extra hash per apply; GLYPH detects by default.
5. **S3**: GS1 detects desync at the offending frame; unframed streams detect
   late or never.
6. **S4**: naive/minified suffer false-negative cache misses when only
   formatting varies; jcs and glyph do not.
7. **S5**: loose mode recovers a substantial fraction of realistic LLM syntax
   errors that strict parsers reject outright.
8. **Costs (expected losses, published anyway)**: GLYPH fingerprinting is
   slower than `json.dumps+sha256`; expect ≥2× CPU in Python. Token counts:
   GLYPH smaller on homogeneous/tabular state, equal-or-larger elsewhere.
9. **The serious-contest outcome is declared in advance:** if jcs matches
   glyph everywhere in Part A, and recheck-wrapped baselines match glyph's
   detection rates in S1/S3 at comparable cost, then the honest conclusion is
   *"JCS + discipline ≈ GLYPH for identity"* — and GLYPH's remaining case must
   rest on enforcement-by-default, patch/stream integration, and error
   tolerance (S5), not on identity alone.

## Reproducibility contract

- Fixed seeds, committed fixtures, no network at run time.
- `run_all.py` exits non-zero if the harness itself malfunctions; results are
  written to `results/`.
- Running twice produces byte-identical `results.json`.
- Tool versions recorded in `results/meta.json`.

## Out of scope

Live LLM calls (comprehension lives in `harness/comprehension/`), binary
formats (Cowrie), and throughput benchmarking of the JS streaming validator
(covered by gauntlet).

---

## Amendment A1 (2026-08-21, recorded during build, before full-suite runs)

While implementing S4 it became clear expectation #6 was **wrong within a
single language**: any subject that parses then re-serializes (naive included)
is automatically invariant to whitespace/key-order/escaping, because hashing
happens on the re-dumped value. The within-language cache-FN story therefore
only exists for systems that hash *raw received text* without parsing — added
as subject `rawtext`, which is arguably the most common DIY pattern of all.
Expectation #6 stands **cross-language**: naive/minified keys computed in one
language will not match another language's keys (escaping defaults, float
formatting, `-0.0`). No other expectations were edited.
