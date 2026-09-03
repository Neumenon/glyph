# comprehension — does a model read GLYPH as well as JSON?

The decisive experiment for the "JSON at the boundaries, GLYPH in the loop"
thesis. Everywhere you can compress, GLYPH's size win is redundant with zstd; the
**only** place its compactness is non-redundant is **uncompressed text in an LLM
context window** — because the model sees tokens, not zstd bytes. That payoff is
real only if the model reads the compact format *as accurately* as JSON.

This harness measures exactly that, on the same questions over the same data:

```text
homogeneous record datasets ──► encode 3 ways ──► ask Claude N questions each
                                json                      │
                                glyph_loose               ├─ accuracy (code-graded)
                                glyph_tabular             └─ tokens   (count_tokens)
                                                          ▼
                              the trade: tokens saved vs accuracy lost vs JSON
```

- **Accuracy** is graded by code (Rule 5 — no LLM judge). Each answer is forced
  through a `submit_answer` tool and checked against a ground truth computed from
  the records. The checks are verified to accept correct answers and reject wrong
  ones.
- **Tokens** are counted with `messages.count_tokens` — Claude's real tokenizer,
  not tiktoken (which is wrong for Claude).
- Questions span lookup / count / sum / argmax / existence / list-ids, so the
  per-kind table shows *where* a format fails — e.g. if tabular's positional
  `|v|v|v|` rows cost accuracy on field lookups specifically.

## Why this is the experiment that matters

Bytes and even BPE token savings are settled (see `../cc-trace`): GLYPH-tabular
is smaller. But if the model answers a few points *less* accurately in GLYPH, the
~15–60% tokens saved is a bad trade — you bought cheaper context by making the
model dumber on it. This harness is the only thing that tells you which way the
trade actually goes. It is also GLYPH's *strongest* case (re-inserted structured
context), not its weakest (append-only logs), so it's the fair fight.

## Run it

Needs an Anthropic API key in the environment (`ANTHROPIC_API_KEY`). The default
model is **Haiku** — cheapest, fastest, and the most likely to *reveal* a
comprehension gap; re-run on Opus for the deployment-relevant tier.

```bash
cd harness/comprehension
pip install -r requirements.txt          # anthropic SDK

python run.py --preview                   # offline: design + byte sizes, no API, no key

ANTHROPIC_API_KEY=sk-... python run.py                          # Haiku, 4 datasets (~156 calls)
ANTHROPIC_API_KEY=sk-... python run.py --model claude-opus-4-8  # frontier tier
ANTHROPIC_API_KEY=sk-... python run.py --primer                 # with a GLYPH format primer
ANTHROPIC_API_KEY=sk-... python run.py --datasets 8 --concurrency 8
```

Cost is small: the default run is ~156 short calls + ~12 token counts. On Haiku
that's pennies; on Opus, low single-digit dollars.

## Reading the output

```text
format          questions  correct  accuracy  avg_tokens  tok vs json  acc Δ
json                    52       51     98.1%         612          —       —
glyph_loose             52       49     94.2%         556      -9.2%    -3.9
glyph_tabular           52       44     84.6%         503     -17.8%   -13.5   ← example
```

- **`acc Δ`** is the number that decides it: GLYPH's accuracy minus JSON's. If it's
  ~0, the token savings are free and the thesis holds. If it's meaningfully
  negative, the savings cost comprehension and the trade is bad.
- The **per-kind** table localizes any loss (e.g. tabular fine on counts, bad on
  lookups → the model miscounts columns).
- Run `--primer` to test whether a one-paragraph format explanation rescues GLYPH.

The numbers above are an *illustrative layout*, not results — run it to get real
ones.

## Interpreting it honestly

- `acc Δ ≈ 0` on Opus **and** Haiku → GLYPH-in-context is a real, free win; the
  thesis is validated where it matters most.
- `acc Δ ≈ 0` on Opus but negative on Haiku → only safe with frontier models.
- Negative on both, primer doesn't fix it → the size win isn't worth the
  comprehension cost; GLYPH-for-LLM-context doesn't pay off, and the project's
  remaining value is the canonicalization/conformance engineering, not the format.

## Files

```text
harness/comprehension/
  comprehension/
    data.py     datasets, questions, code-computed ground truth + scoring
    encode.py   json / glyph_loose / glyph_tabular (drives the real py/glyph)
    model.py    Claude call (forced submit_answer) + count_tokens
  run.py        CLI: --preview / live, aggregation + report
  results/      per-run JSON reports (git-ignored)
```
