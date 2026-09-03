"""Tests for the cc-trace harness.

These encode the *intent* of the experiment, not just mechanics:

  - the canonical schema stays uniform (so trace lists tabularize);
  - every encoding round-trips to the SAME RunState (compression must not drop
    semantics — that is the whole claim);
  - GLYPH meaningfully beats the NDJSON baseline on a real trace;
  - tabular survives values that collide with its own `|` delimiter.

Run:  python -m pytest harness/cc-trace/tests -q
 or:  python harness/cc-trace/tests/test_harness.py
"""
import json
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))

from agenttrace import FIELDS, bench, decode, encode, normalize, replay, validate_event  # noqa: E402
from agenttrace.schema import normalize_keys  # noqa: E402

FIXTURE = HARNESS / "fixtures" / "failing_test_repair.raw.jsonl"


def _load_fixture_events():
    records = [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]
    return normalize(records)


def test_normalize_produces_uniform_validated_events():
    events = _load_fixture_events()
    assert len(events) == 26
    for ev in events:
        validate_event(ev)
        # Uniform key set is what lets the list pack into one @tab block.
        assert tuple(ev.keys()) == FIELDS


def test_reference_runstate_is_what_we_recorded():
    state = replay(_load_fixture_events())
    assert state["prompts"] == 1
    assert state["tool_calls"] == 11
    assert state["bash_commands"] == 4
    assert state["edits"] == 2
    assert state["tool_failures"] == 2
    assert state["final_status"] == "success"
    assert state["files_touched"] == ["src/invoice.py"]


def test_every_format_roundtrips_to_same_runstate():
    events = _load_fixture_events()
    result = bench(events)
    for row in result["rows"]:
        assert row["decode_ok"], f"{row['format']} failed to decode: {row['error']}"
        assert row["replay_ok"], f"{row['format']} changed the RunState"


def test_glyph_beats_ndjson_on_a_real_trace():
    result = bench(_load_fixture_events())
    by = {r["format"]: r for r in result["rows"]}
    # Loose (per-line) should beat the line-oriented baseline...
    assert by["glyph_loose"]["bytes_vs_ndjson_pct"] >= 8.0
    # ...and tabular should crush it on repeated records.
    assert by["glyph_tabular"]["bytes_vs_ndjson_pct"] >= 30.0
    # tokens are either real BPE ints or absent (no fabricated heuristic).
    for r in result["rows"]:
        assert r["tokens"] is None or isinstance(r["tokens"], int)


def test_tabular_survives_delimiter_like_values():
    """A value containing GLYPH's own `|`/quotes/newlines/unicode must survive
    the tabular round-trip — otherwise a 'win' would be silent corruption."""
    nasty = 'grep -n "a|b" file.txt | wc -l  # quote " and \n newline 文字'
    events = [
        normalize_keys({"run": "r", "seq": 1, "event": "prompt", "phase": "submit",
                        "input": {"text": nasty}, "ts_ms": 1}),
        normalize_keys({"run": "r", "seq": 2, "event": "tool_call", "phase": "pre",
                        "tool": "Bash", "input": {"command": nasty}, "ts_ms": 2}),
        normalize_keys({"run": "r", "seq": 3, "event": "tool_call", "phase": "post",
                        "tool": "Bash", "input": {"stdout": nasty, "exit_code": 0},
                        "ok": True, "ts_ms": 3}),
        normalize_keys({"run": "r", "seq": 4, "event": "stop", "phase": "end",
                        "ok": True, "ts_ms": 4}),
    ]
    for fmt in ("glyph_loose", "glyph_tabular", "ndjson"):
        decoded = decode(fmt, encode(fmt, events))
        # Exact value equality, order-independent.
        assert [json.dumps(e, sort_keys=True) for e in decoded] == \
               [json.dumps(e, sort_keys=True) for e in events], f"{fmt} corrupted a value"


def test_tabular_actually_uses_a_tab_block():
    events = _load_fixture_events()
    assert "@tab" in encode("glyph_tabular", events)
    assert "@tab" not in encode("glyph_loose", events)


if __name__ == "__main__":
    import traceback

    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failed += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    sys.exit(1 if failed else 0)
