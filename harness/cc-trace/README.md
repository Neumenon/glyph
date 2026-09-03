# cc-trace — Claude Code as a GLYPH trace workload

A small harness that uses **Claude Code as a real trace producer** and measures
the in-repo GLYPH codec against an honest baseline (NDJSON) on that workload.

It is *example / benchmark* material — a consumer of the codec, not part of the
codec's product surface (see the repo [README](../../README.md): "the
agent-oriented material in this repo is example, not product surface").

```text
Claude Code hook events            (capture: .claude/hooks/trace_event.py)
        │  raw JSONL
        ▼
canonical TraceEvent[]             (adapter #1: agenttrace/normalize.py)
        │
        ├── encode ────────────────────────────────┐
        │   ndjson · glyph_loose · glyph_tabular    │ (agenttrace/encode.py → py/glyph)
        ▼                                           ▼
   replay → RunState  ◄── equivalence oracle ──  decode → replay → RunState
        │
        ▼
   bench: bytes · tokens · decode_ok · replay_ok   (agenttrace/bench.py)
```

The core (`schema`, `encode`, `replay`, `bench`) is **host-agnostic**. Claude
Code is adapter #1. The encoders drive the **real** GLYPH implementation under
`py/` — nothing here reimplements the format, because the point is to measure the
actual codec.

## Layout

```text
harness/cc-trace/
  agenttrace/            host-agnostic core
    schema.py            canonical TraceEvent (uniform keys → tabular-friendly)
    normalize.py         Claude Code hook JSON → TraceEvent[]   (adapter #1)
    encode.py            ndjson / glyph_loose / glyph_tabular  (drives py/glyph)
    tokens.py            real BPE tokens (tiktoken) or none — no fake heuristic
    replay.py            TraceEvent[] → RunState (the equivalence oracle)
    bench.py             per-format size/tokens/decode/replay + savings
  cli.py                 normalize | bench | replay
  .claude/
    hooks/trace_event.py passive capture hook (never blocks; always exit 0)
    settings.json        hooks template (copy into a project-root .claude/)
  fixtures/
    failing_test_repair.raw.jsonl   bundled synthetic capture (regenerable)
    _gen_failing_test_repair.py     its generator
  traces/                live captures land here (git-ignored — see Privacy)
  tests/test_harness.py
```

## Run it (no Claude Code needed)

The bundled fixture makes everything deterministic today:

```bash
cd harness/cc-trace

python3 cli.py bench   fixtures/failing_test_repair.raw.jsonl
python3 cli.py replay  fixtures/failing_test_repair.raw.jsonl
python3 cli.py normalize fixtures/failing_test_repair.raw.jsonl -o /tmp/events.json

python3 -m pytest tests -q          # or: python3 tests/test_harness.py
```

### Verified result (bundled `failing_test_repair`, 26 events)

```text
format             bytes    tokens  vs ndjson  decode replay
------------------------------------------------------------
ndjson              5789      1947          —      ok     ok
glyph_loose         4890      1717     +15.5%      ok     ok
glyph_tabular       3512      1414     +39.3%      ok     ok

glyph_loose   vs ndjson: +15.5% bytes, +11.8% tokens
glyph_tabular vs ndjson: +39.3% bytes, +27.4% tokens
```

`decode`/`replay` = the encoding parsed back to events **and** those events
reduced to the identical RunState as the reference. Compression that changes the
trace's meaning does not count as a win.

> **Tokens:** bytes are exact and are the headline metric. Token counts are real
> BPE (`cl100k_base`) and appear only when `tiktoken` is installed (`pip install
> tiktoken`); otherwise the column shows `-`. This harness never reports the
> deprecated whitespace-split estimate (see `js/src/index.ts`).

## Live capture from real sessions

A passive hook is wired in this repo's root `.claude/settings.json`, so Claude
Code sessions **run from the repo root** append raw records to
`harness/cc-trace/traces/raw-jsonl/<session>.jsonl`. Then:

```bash
python3 cli.py bench traces/raw-jsonl/<session>.jsonl
```

- The hook is **observability only**: it never blocks a tool call, emits no
  decision, and always exits 0. A tracing failure can't break a session.
- To capture in **another** repo, copy the `hooks` block from
  `.claude/settings.json` (template) into that project's `.claude/settings.json`
  or your `~/.claude/settings.json`.
- To **stop** capturing, delete the `hooks` block from the repo-root
  `.claude/settings.json`.

### Privacy

Live captures contain prompts, commands, and tool I/O. They are **git-ignored**
(`harness/cc-trace/traces/raw-jsonl/*`). Only the synthetic `fixtures/` sample is
committed. Don't commit real captures.

## Deferred (intentionally — this is the narrow first A/B)

- **GS1 framing** (`glyph_gs1`) and a corruption/CRC-rejection demo (Go/JS surface).
- **Live `claude -p --output-format stream-json` orchestration** and the 5-task
  scenario battery (refactor / feature loop / unsafe command / research).
- **`PreToolUse` safety detection** (blocking unsafe commands at trace time).
- **Adapter #2: claude-trace** — the API-traffic capture from
  [`badlogic/lemmy` apps/claude-trace](https://github.com/badlogic/lemmy/tree/main/apps/claude-trace),
  which patches Claude Code's `fetch` to record full request/response JSONL. It's
  richer than hooks (full conversation, token usage) but heavier. Because
  `TraceEvent` is host-agnostic, it slots in as a sibling normalizer next to
  `normalize.py` — the encoders, replay, and bench don't change.
```
