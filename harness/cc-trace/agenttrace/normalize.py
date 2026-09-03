"""Claude Code hook JSON -> canonical TraceEvent[]  (capture adapter #1).

Input is the list of raw records written by `.claude/hooks/trace_event.py`:

    {"ts_ms": ..., "session": ..., "event": <hook_event_name>,
     "tool": ..., "cwd": ..., "raw": <full hook JSON>}

We read from `rec["raw"]` (the source of truth) and fall back to the record's
top-level fields. The mapping below is the *only* Claude-Code-specific code in
the harness; a second host (e.g. claude-trace's API-traffic capture) would add a
sibling normalizer that targets the same schema.
"""
from .schema import normalize_keys, validate_event

# Claude Code hook_event_name -> (event, phase)
_HOOK_MAP = {
    "SessionStart": ("session", "start"),
    "UserPromptSubmit": ("prompt", "submit"),
    "PreToolUse": ("tool_call", "pre"),
    "PostToolUse": ("tool_call", "post"),
    "Stop": ("stop", "end"),
    "SubagentStop": ("stop", "end"),
    "SessionEnd": ("session", "end"),
}

# Tool outputs (and prompts) can be huge; cap string values so a trace stays a
# trace and not a file dump. Every encoding sees the same capped events, so the
# size comparison stays fair.
_MAX_STR = 500


def _truncate(v, limit=_MAX_STR):
    if isinstance(v, str) and len(v) > limit:
        return v[:limit] + f"…(+{len(v) - limit})"
    if isinstance(v, dict):
        return {k: _truncate(x, limit) for k, x in v.items()}
    if isinstance(v, list):
        return [_truncate(x, limit) for x in v]
    return v


def _hook_name(raw, rec):
    return raw.get("hook_event_name") or raw.get("hookEventName") or rec.get("event") or "unknown"


def _derive_ok(resp):
    """Conservative success flag for a tool result; default True."""
    if isinstance(resp, dict):
        if resp.get("is_error") or resp.get("error") or resp.get("interrupted"):
            return False
        ec = resp.get("exit_code", resp.get("returncode"))
        if isinstance(ec, int) and ec != 0:
            return False
    return True


def _as_dict(v):
    return v if isinstance(v, dict) else ({"value": v} if v is not None else {})


def _input_for(event, phase, raw):
    if event == "prompt":
        return {"text": _truncate(raw.get("prompt", ""))}
    if event == "session" and phase == "start":
        return {"source": raw.get("source", "")}
    if event == "session" and phase == "end":
        return {"reason": raw.get("reason", "")}
    if event == "tool_call" and phase == "pre":
        return _truncate(_as_dict(raw.get("tool_input")))
    if event == "tool_call" and phase == "post":
        return _truncate(_as_dict(raw.get("tool_response", raw.get("tool_result"))))
    return {}


def normalize(raw_records):
    """raw hook records -> validated, sequenced TraceEvent list (run-ordered)."""
    # Group by session; within a session, order by (ts_ms, capture_index).
    runs = {}
    for idx, rec in enumerate(raw_records):
        raw = rec.get("raw", rec) or {}
        sid = (
            rec.get("session")
            or raw.get("session_id")
            or raw.get("transcript_path")
            or "unknown"
        )
        runs.setdefault(str(sid), []).append((idx, rec, raw))

    events = []
    for sid, items in runs.items():
        items.sort(key=lambda t: (t[1].get("ts_ms", t[2].get("ts_ms", 0)), t[0]))
        last_pre_ts = {}  # tool -> ts of its most recent `pre`, for latency
        seq = 0
        for idx, rec, raw in items:
            hook = _hook_name(raw, rec)
            if hook not in _HOOK_MAP:
                continue  # ignore hook events we don't model (PreCompact, etc.)
            event, phase = _HOOK_MAP[hook]
            seq += 1
            ts = rec.get("ts_ms", raw.get("ts_ms", 0))
            tool = (raw.get("tool_name") or rec.get("tool")) if event == "tool_call" else None

            ok, latency = True, None
            if event == "tool_call" and phase == "pre":
                last_pre_ts[tool] = ts
            elif event == "tool_call" and phase == "post":
                ok = _derive_ok(raw.get("tool_response", raw.get("tool_result")))
                if tool in last_pre_ts:
                    latency = ts - last_pre_ts[tool]

            ev = normalize_keys(
                {
                    "run": str(sid),
                    "seq": seq,
                    "event": event,
                    "phase": phase,
                    "tool": tool,
                    "input": _input_for(event, phase, raw),
                    "ok": ok,
                    "latency_ms": latency,
                    "cwd": rec.get("cwd") or raw.get("cwd"),
                    "ts_ms": ts,
                }
            )
            validate_event(ev)
            events.append(ev)
    return events
