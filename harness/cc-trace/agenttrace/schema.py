"""Canonical TraceEvent schema — stable, encoder-agnostic.

One dict per agent-loop event. Every event carries the *same* top-level key set
(missing values are explicit null) for two reasons:

  1. A homogeneous list of events packs cleanly into a GLYPH `@tab` block — the
     repeated keys are emitted once, which is exactly where agent traces hurt.
  2. The reducer in `replay.py` reads by key, so it is identical no matter which
     encoding the events were decoded from.

The schema is deliberately independent of any agent host. `normalize.py` maps a
specific host's events (Claude Code first) onto it.
"""

EVENT_TYPES = ("session", "prompt", "tool_call", "stop")
PHASES = ("start", "submit", "pre", "post", "end")

# Stable field order. This is also the `@tab` column order, so keep it fixed.
FIELDS = ("run", "seq", "event", "phase", "tool", "input", "ok", "latency_ms", "cwd", "ts_ms")


def empty_event():
    """A fully-populated event with default/null values for every field."""
    return {
        "run": "",
        "seq": 0,
        "event": "",
        "phase": "",
        "tool": None,
        "input": {},
        "ok": True,
        "latency_ms": None,
        "cwd": None,
        "ts_ms": 0,
    }


def normalize_keys(ev):
    """Return a new event with exactly FIELDS, in stable order, filling gaps.

    Uniform keys across every event are what let the list tabularize.
    """
    base = empty_event()
    for k in FIELDS:
        if k in ev and ev[k] is not None:
            base[k] = ev[k]
        elif k in ev:
            base[k] = ev[k]  # explicit None passes through (e.g. tool=None)
    return {k: base[k] for k in FIELDS}


def validate_event(ev):
    """Fail loud on a malformed event rather than silently encoding garbage."""
    missing = [k for k in FIELDS if k not in ev]
    if missing:
        raise ValueError(f"event missing fields: {missing}")
    if ev["event"] not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {ev['event']!r}")
    if ev["phase"] not in PHASES:
        raise ValueError(f"unknown phase: {ev['phase']!r}")
    if not isinstance(ev["input"], dict):
        raise ValueError(f"input must be an object, got {type(ev['input']).__name__}")
    return ev
