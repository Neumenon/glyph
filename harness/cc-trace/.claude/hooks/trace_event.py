#!/usr/bin/env python3
"""Passive Claude Code trace hook — capture adapter #1, capture side.

Reads one hook event as JSON on stdin and appends a raw record to
`harness/cc-trace/traces/raw-jsonl/<session>.jsonl`. It is *observability only*:
it never blocks a tool call, never emits a decision, and always exits 0 — a
tracing failure must never break a Claude Code session.

The normalizer (`agenttrace/normalize.py`) turns these raw records into the
canonical TraceEvent schema; this script intentionally stays dumb and stable.
"""
import hashlib
import json
import pathlib
import sys
import time

# .../harness/cc-trace/.claude/hooks/trace_event.py -> harness/cc-trace is parents[2]
HARNESS = pathlib.Path(__file__).resolve().parents[2]
OUT = HARNESS / "traces" / "raw-jsonl"
now_ms = int(time.time() * 1000)


def _log_error(msg):
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        with open(OUT / "trace-hook-errors.log", "a", encoding="utf-8") as fh:
            fh.write(f"{now_ms} {msg}\n")
    except Exception:
        pass  # truly last resort: never raise


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except Exception as exc:
        _log_error(f"parse_error {exc}: {raw[:500]}")
        return

    session = (
        event.get("session_id")
        or event.get("sessionId")
        or event.get("transcript_path")
        or "unknown"
    )
    event_name = (
        event.get("hook_event_name")
        or event.get("hookEventName")
        or event.get("event")
        or "unknown"
    )

    record = {
        "ts_ms": now_ms,
        "session": str(session),
        "event": event_name,
        "tool": event.get("tool_name") or event.get("toolName"),
        "cwd": event.get("cwd"),
        "raw": event,
    }

    try:
        OUT.mkdir(parents=True, exist_ok=True)
        sid_hash = hashlib.sha256(str(session).encode()).hexdigest()[:12]
        with open(OUT / f"{sid_hash}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
    except Exception as exc:
        _log_error(f"write_error {exc}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # absolute backstop
        _log_error(f"unexpected {exc}")
    sys.exit(0)  # never block Claude Code
