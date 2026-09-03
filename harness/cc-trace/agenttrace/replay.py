"""Deterministic reducer: TraceEvent[] -> RunState.

This is the equivalence oracle for the bench. It reads events *by key only*, so
it produces the identical RunState regardless of which format the events were
decoded from. The bench asserts:

    decode(format) -> events -> replay(events) == replay(reference events)

which is what stops a "compression win" that silently dropped semantics from
counting as a win.
"""

_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def replay(events):
    state = {
        "run": events[0]["run"] if events else "",
        "prompts": 0,
        "tool_calls": 0,
        "tool_failures": 0,
        "edits": 0,
        "bash_commands": 0,
        "final_status": "unknown",
        "files_touched": [],
        "errors": [],
    }
    touched = set()
    for ev in events:
        et, ph = ev.get("event"), ev.get("phase")
        if et == "prompt" and ph == "submit":
            state["prompts"] += 1
        elif et == "tool_call" and ph == "pre":
            # Count initiated calls by their `pre` event.
            state["tool_calls"] += 1
            tool = ev.get("tool")
            if tool == "Bash":
                state["bash_commands"] += 1
            if tool in _EDIT_TOOLS:
                state["edits"] += 1
                fp = (ev.get("input") or {}).get("file_path")
                if fp:
                    touched.add(fp)
        elif et == "tool_call" and ph == "post":
            if not ev.get("ok", True):
                state["tool_failures"] += 1
                state["errors"].append({"tool": ev.get("tool"), "seq": ev.get("seq")})
        elif et == "stop" and ph == "end":
            state["final_status"] = "success" if ev.get("ok", True) else "error"
    state["files_touched"] = sorted(touched)
    return state
