#!/usr/bin/env python3
"""Generate the bundled `failing_test_repair.raw.jsonl` sample capture.

This produces raw records in the exact shape `.claude/hooks/trace_event.py`
writes, so the rest of the harness can be exercised deterministically without a
live Claude Code session. The scenario is a realistic failing-test-repair loop:

    prompt -> pytest (fail) -> grep/read -> edit -> pytest (still fails)
           -> read -> edit -> pytest (passes) -> full suite (passes) -> stop

Re-generate with:  python fixtures/_gen_failing_test_repair.py
"""
import json
import pathlib

SESSION = "sess-7f3a9c21"
CWD = "/home/dev/acme"
OUT = pathlib.Path(__file__).resolve().parent / "failing_test_repair.raw.jsonl"

# (hook_event_name, extra-fields) in capture order. ts is assigned by index.
STEPS = [
    ("SessionStart", {"source": "startup"}),
    ("UserPromptSubmit", {"prompt": "Run the test suite, find the first failing test, fix it, and rerun the relevant tests."}),

    ("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "pytest -q", "description": "Run the test suite"}}),
    ("PostToolUse", {"tool_name": "Bash", "tool_input": {"command": "pytest -q"},
                     "tool_response": {"exit_code": 1, "stdout": "....F\n1 failed, 41 passed in 0.42s", "stderr": ""}}),

    ("PreToolUse", {"tool_name": "Grep", "tool_input": {"pattern": "def test_", "path": "tests", "output_mode": "files_with_matches"}}),
    ("PostToolUse", {"tool_name": "Grep", "tool_input": {"pattern": "def test_"},
                     "tool_response": {"filenames": ["tests/test_invoice.py", "tests/test_user.py"], "numFiles": 2}}),

    ("PreToolUse", {"tool_name": "Read", "tool_input": {"file_path": "tests/test_invoice.py"}}),
    ("PostToolUse", {"tool_name": "Read", "tool_input": {"file_path": "tests/test_invoice.py"},
                     "tool_response": {"type": "text", "file": {"numLines": 38}}}),

    ("PreToolUse", {"tool_name": "Read", "tool_input": {"file_path": "src/invoice.py"}}),
    ("PostToolUse", {"tool_name": "Read", "tool_input": {"file_path": "src/invoice.py"},
                     "tool_response": {"type": "text", "file": {"numLines": 64}}}),

    ("PreToolUse", {"tool_name": "Grep", "tool_input": {"pattern": "def total", "path": "src", "output_mode": "content"}}),
    ("PostToolUse", {"tool_name": "Grep", "tool_input": {"pattern": "def total"},
                     "tool_response": {"numLines": 1, "numMatches": 1}}),

    ("PreToolUse", {"tool_name": "Edit", "tool_input": {
        "file_path": "src/invoice.py",
        "old_string": "    return sum(i.price for i in self.items)",
        "new_string": "    return sum(i.price * i.qty for i in self.items)"}}),
    ("PostToolUse", {"tool_name": "Edit", "tool_input": {"file_path": "src/invoice.py"},
                     "tool_response": {"filePath": "src/invoice.py", "structuredPatch": [{"oldStart": 21}]}}),

    ("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "pytest -q tests/test_invoice.py", "description": "Rerun the failing test"}}),
    ("PostToolUse", {"tool_name": "Bash", "tool_input": {"command": "pytest -q tests/test_invoice.py"},
                     "tool_response": {"exit_code": 1, "stdout": "F\n1 failed in 0.08s\nE  assert 0 == 40", "stderr": ""}}),

    ("PreToolUse", {"tool_name": "Read", "tool_input": {"file_path": "src/invoice.py"}}),
    ("PostToolUse", {"tool_name": "Read", "tool_input": {"file_path": "src/invoice.py"},
                     "tool_response": {"type": "text", "file": {"numLines": 64}}}),

    ("PreToolUse", {"tool_name": "Edit", "tool_input": {
        "file_path": "src/invoice.py",
        "old_string": "        self.qty = qty or 0",
        "new_string": "        self.qty = qty if qty is not None else 1"}}),
    ("PostToolUse", {"tool_name": "Edit", "tool_input": {"file_path": "src/invoice.py"},
                     "tool_response": {"filePath": "src/invoice.py", "structuredPatch": [{"oldStart": 9}]}}),

    ("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "pytest -q tests/test_invoice.py", "description": "Rerun the failing test"}}),
    ("PostToolUse", {"tool_name": "Bash", "tool_input": {"command": "pytest -q tests/test_invoice.py"},
                     "tool_response": {"exit_code": 0, "stdout": ".\n1 passed in 0.07s", "stderr": ""}}),

    ("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "pytest -q", "description": "Run the full suite"}}),
    ("PostToolUse", {"tool_name": "Bash", "tool_input": {"command": "pytest -q"},
                     "tool_response": {"exit_code": 0, "stdout": "....\n42 passed in 0.46s", "stderr": ""}}),

    ("Stop", {"stop_hook_active": False}),
    ("SessionEnd", {"reason": "other"}),
]


def main():
    base_ts = 1760000000000
    lines = []
    for i, (hook, extra) in enumerate(STEPS):
        ts = base_ts + i * 1000  # 1s apart; deterministic
        raw = {"hook_event_name": hook, "session_id": SESSION, "cwd": CWD, "transcript_path": f"/tmp/{SESSION}.jsonl"}
        raw.update(extra)
        record = {
            "ts_ms": ts,
            "session": SESSION,
            "event": hook,
            "tool": extra.get("tool_name"),
            "cwd": CWD,
            "raw": raw,
        }
        lines.append(json.dumps(record, separators=(",", ":"), ensure_ascii=False))
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} records -> {OUT}")


if __name__ == "__main__":
    main()
