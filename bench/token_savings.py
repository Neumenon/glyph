#!/usr/bin/env python3
"""Reproduce the README's token-savings table.

Measures GLYPH (loose canonical form, auto-tabular on) against minified JSON
with real tiktoken tokenizers on four fixed payload shapes. The payloads are
deterministic literals — no randomness, no timestamps — so every run of this
script on any machine produces the same table, and the README numbers can be
checked against it directly:

    cd py && pip install -e . tiktoken
    python ../bench/token_savings.py

The shapes mirror real agent artifacts:
  homogeneous   40 uniform eval/log records      (GLYPH's best case: tabular)
  trace         12-step tool-call trace          (repeated-but-nested fields)
  chat_state    multi-turn message history       (dominated by unique text)
  prose_heavy   long free-text transcript        (GLYPH's worst case)
"""

import json
import sys

try:
    import tiktoken
except ImportError:
    sys.exit("pip install tiktoken")

try:
    from glyph import from_json_loose, canonicalize_loose
except ImportError:
    sys.exit("install glyph first: cd py && pip install -e .")


def homogeneous_records():
    """40 uniform records — eval batch / tool-call log rows."""
    return [
        {
            "id": f"run-{i:03d}",
            "model": "m-7b" if i % 2 == 0 else "m-70b",
            "score": round(0.5 + (i % 40) * 0.01, 2),
            "latency_ms": 100 + i * 7,
            "passed": i % 3 != 0,
            "retries": i % 4,
        }
        for i in range(40)
    ]


def trace():
    """12-step structured trace: repeated fields, nested args."""
    tools = ["search", "read_file", "write_file", "bash"]
    return {
        "trace_id": "tr-8891",
        "steps": [
            {
                "step": i,
                "tool": tools[i % 4],
                "args": {"query": f"item {i} lookup", "limit": 5 + i},
                "status": "ok" if i % 5 else "error",
                "duration_ms": 40 + i * 13,
            }
            for i in range(12)
        ],
        "total_ms": 1420,
    }


def chat_state():
    """Multi-turn conversation history — LangGraph/provider message shape."""
    return {
        "session": "s-2213",
        "messages": [
            {"role": "user", "content": "Can you check whether the deploy to staging finished and whether the smoke tests passed?"},
            {"role": "assistant", "content": "I'll check the deploy status and the smoke test results for staging now.",
             "tool_calls": [{"id": "c1", "name": "check_deploy", "arguments": {"env": "staging"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "deploy complete at rev 4f21; smoke suite: 47 passed, 1 flaked (retried ok)"},
            {"role": "assistant", "content": "The staging deploy finished at revision 4f21. All 47 smoke tests passed; one flaked initially but passed on retry. You're clear to promote."},
            {"role": "user", "content": "Great — promote it to production and watch the error rate for ten minutes afterwards."},
            {"role": "assistant", "content": "Promoting to production now; I'll monitor the error rate for ten minutes and report back.",
             "tool_calls": [{"id": "c2", "name": "promote", "arguments": {"from": "staging", "to": "production"}}]},
        ],
        "memory": {"env": "staging", "last_rev": "4f21", "pending": "promote+watch"},
    }


def prose_heavy():
    """Long free-text transcript — structural savings swamped by content."""
    return {
        "doc": "meeting-notes-114",
        "sections": [
            {"heading": "Decisions",
             "body": "We agreed to freeze the wire format after the conformance suite has been green for two consecutive weeks across all three implementations, and to treat any canonicalization change after that point as a major version bump regardless of how small the byte-level difference appears to be."},
            {"heading": "Risks",
             "body": "The largest open risk remains adoption: the format is technically sound but has no external users, so every design decision is still being validated against internal workloads only, which historically has hidden exactly the class of edge case that external users find in the first week."},
            {"heading": "Next steps",
             "body": "Publish the release notes, tag the release so continuous integration publishes the packages, send the prepared outreach messages, and instrument the example repository so we can tell whether anyone who stars the project actually runs the quickstart end to end."},
        ],
    }


SHAPES = [
    ("homogeneous", homogeneous_records()),
    ("trace", trace()),
    ("chat_state", chat_state()),
    ("prose_heavy", prose_heavy()),
]

ENCODINGS = ["cl100k_base", "o200k_base"]


def main():
    encs = {name: tiktoken.get_encoding(name) for name in ENCODINGS}

    print(f"{'shape':<13} {'json B':>7} {'glyph B':>8} {'bytes':>7}", end="")
    for name in ENCODINGS:
        print(f" {name + ' tok j/g':>20} {'save':>6}", end="")
    print()

    for label, payload in SHAPES:
        j = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        gl = canonicalize_loose(from_json_loose(payload))

        byte_save = 100.0 * (1 - len(gl.encode()) / len(j.encode()))
        print(f"{label:<13} {len(j.encode()):>7} {len(gl.encode()):>8} {byte_save:>6.1f}%", end="")

        for name in ENCODINGS:
            jt = len(encs[name].encode(j))
            gt = len(encs[name].encode(gl))
            tok_save = 100.0 * (1 - gt / jt)
            print(f" {f'{jt}/{gt}':>20} {tok_save:>5.1f}%", end="")
        print()


if __name__ == "__main__":
    main()
