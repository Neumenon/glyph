# GLYPH for AI Agents

## Testing Philosophy (VITAL)

**`../../../docs/TESTING_PHILOSOPHY.md`** is the canonical testing guide for all projects in this workspace. Read it before writing or reviewing tests. Particularly relevant: Class 4 (overflow), Class 5 (resource exhaustion), Class 6 (cross-language parity), Class 9 (parser edge cases), Class 10 (limits bypass).

---

Quick patterns for using GLYPH in agent systems.

**TL;DR:**
1. Define tools in GLYPH (40% fewer tokens in system prompt)
2. Validate tool calls as tokens stream (detect errors and cancel immediately—not after full generation)
3. Run persona agents on verified state with checkpoint / resume and patch history

---

## Python Agent SDK

Python now ships a first-class runtime layer above the codec and validator:

```python
import asyncio
import glyph


class DemoModel:
    async def stream(self, prompt: str, *, agent, state, session_id):
        return iter([
            'Explanation{summary="Keep tool loops validated and state compact." '
            'key_points=["streaming validation" "fingerprints"] '
            'assumptions=["shared state is JSON-compatible"] confidence=0.83}'
        ])


async def main():
    session = glyph.create_debate_session([glyph.feynman_agent(DemoModel())])
    outcome = await glyph.run_turn(session, "Explain how GLYPH helps agent runtimes")
    print(outcome.answer)
    print(glyph.export_trace(session))


asyncio.run(main())
```

For a debate trio, combine `glyph.feynman_agent(...)`,
`glyph.von_neumann_agent(...)`, `glyph.einstein_agent(...)`, and optionally
`glyph.arbiter_agent(...)`.

---

## Tool Definitions

### Minimal (no schema)

```python
# System prompt
TOOLS = """
Available tools:
- search{query:str max_results:int} - Search the web
- calculate{expression:str} - Evaluate math
- browse{url:str} - Fetch webpage content
"""

# Parse tool call from model output
tool_call = glyph.parse(model_output)
name = tool_call.type_name  # "search"
args = tool_call.fields     # {"query": "weather NYC", "max_results": 10}
```

### With Validation

```python
registry = glyph.ToolRegistry()

registry.add_tool("search", {
    "query": {"type": "str", "required": True, "min_len": 1},
    "max_results": {"type": "int", "min": 1, "max": 100, "default": 10},
})

registry.add_tool("calculate", {
    "expression": {"type": "str", "required": True},
})

registry.add_tool("browse", {
    "url": {"type": "str", "required": True, "pattern": r"^https?://"},
})
```

### System Prompt Pattern

```
You have access to these tools:

search{query:str max_results:int[1..100]=10}
  Search the web. Returns list of results.

calculate{expression:str}
  Evaluate a mathematical expression. Returns number.

browse{url:str}
  Fetch and summarize a webpage. Returns text.

To use a tool, output:
ToolName{arg1=value arg2=value}

Example:
search{query="python async tutorial" max_results=5}
```

---

## Streaming Validation

Detect invalid tool calls **before generation completes**. Save tokens and latency.

```python
validator = glyph.StreamingValidator(registry)

async for token in llm_stream:
    result = validator.push_token(token)

    # Tool name detected early
    if result.tool_name:
        print(f"Tool: {result.tool_name} at token {result.tool_detected_at_token}")

        # Unknown tool? Cancel immediately
        if not result.tool_allowed:
            await cancel_generation()
            raise ToolNotFoundError(result.tool_name)

    # Constraint violation? Cancel
    if result.should_cancel:
        await cancel_generation()
        raise ValidationError(result.errors)

# Generation complete - execute if valid
if result.complete and result.valid:
    return await execute_tool(result.tool_name, result.fields)
```

### When to Cancel

| Condition | Action |
|-----------|--------|
| Unknown tool name | Cancel at token ~3-5 |
| Wrong argument type | Cancel when type detected |
| Constraint violation | Cancel when value complete |
| Missing required arg | Wait until `}` then error |

---

## State Management

### Simple: Full State Per Message

```python
# Agent state as GLYPH
from glyph import field, g

state = g.struct(
    "AgentState",
    field("goal", g.str("Find weather in NYC")),
    field(
        "memory",
        g.list(glyph.from_json({"query": "NYC weather", "result": "72F sunny"})),
    ),
    field("turn", g.int(3)),
)

# Include in context
context = f"""
Current state:
{glyph.emit(state)}

Continue toward the goal.
"""
```

### Advanced: Verified State Patches

For long-running Python agents, use fingerprint-verified state patches.

```python
before = {
    "turn": 3,
    "memory": [{"query": "NYC weather", "result": "72F sunny"}],
}
after = {
    "turn": 4,
    "memory": [
        {"query": "NYC weather", "result": "72F sunny"},
        {"query": "tomorrow", "result": "68F cloudy"},
    ],
}

patch = glyph.create_state_patch(
    before,
    after,
    author_id="planner",
    revision=1,
    reason="append_observation",
)

restored = glyph.apply_state_patch(before, patch)
assert restored == after
```

---

## Common Patterns

### ReAct Loop

```python
async def react_loop(goal: str, max_turns: int = 10):
    state = {"goal": goal, "observations": [], "turn": 0}

    for turn in range(max_turns):
        # Format state as GLYPH (compact)
        state_glyph = glyph.emit(glyph.from_json(state))

        prompt = f"""
State: {state_glyph}

Think step by step, then either:
1. Use a tool: ToolName{{args}}
2. Return final answer: Answer{{result="..."}}
"""

        response = await llm.generate(prompt)
        parsed = glyph.parse(response)
        payload = glyph.to_json(parsed)
        kind = payload.pop("$type", "")

        if kind == "Answer":
            return payload["result"]

        # Execute tool
        result = await execute_tool(kind, payload)
        state["observations"].append({
            "tool": kind,
            "args": payload,
            "result": result,
        })
        state["turn"] += 1

    raise MaxTurnsExceeded()
```

### Multi-Agent Coordination

Use stream IDs (SID) to multiplex agent communication.

```python
# Coordinator assigns SIDs
PLANNER_SID = 1
EXECUTOR_SID = 2
CRITIC_SID = 3

# Planner sends task
writer.write_frame(
    sid=EXECUTOR_SID,
    seq=0,
    kind="doc",
    payload='Task{action=search query="latest AI news"}',
)

# Executor sends result
writer.write_frame(
    sid=PLANNER_SID,
    seq=0,
    kind="doc",
    payload='Result{task_id=1 status=complete data={...}}',
)

# Critic sends feedback
writer.write_frame(
    sid=EXECUTOR_SID,
    seq=1,
    kind="doc",
    payload='Feedback{task_id=1 score=0.8 suggestion="Include source URLs"}',
)
```

### Checkpoint / Resume

```python
def save_checkpoint(agent_state: dict, path: str):
    with open(path, "w") as f:
        f.write(glyph.json_to_glyph(agent_state))

def load_checkpoint(path: str):
    with open(path) as f:
        return glyph.glyph_to_json(f.read())

# Save periodically
if turn % 5 == 0:
    save_checkpoint(state, f"checkpoint_{turn}.glyph")

# Resume from crash
state = load_checkpoint("checkpoint_latest.glyph")
```

### Progress Reporting

```python
# Send progress during long operations
writer.write_frame(
    sid=1,
    seq=seq,
    kind="ui",
    payload='Progress{pct=0.45 msg="Processing batch 9 of 20" eta_seconds=120}',
)

# Client handles UI updates
@handler.on_ui
def handle_ui(sid, seq, payload, state):
    event = glyph.to_json(glyph.parse(payload))
    if event.get("$type") == "Progress":
        update_progress_bar(event["pct"], event["msg"])
```

---

## Anti-Patterns

### Don't: Parse with Regex

```python
# BAD - breaks on nested structures
match = re.search(r'search\{query="([^"]+)"', response)

# GOOD - use the parser
result = glyph.parse(response)
```

### Don't: Validate After Full Generation

```python
# BAD - wastes tokens on invalid calls
response = await llm.generate(prompt)  # 50 tokens
result = glyph.parse(response)
tool_name = glyph.to_json(result).get("$type", "")
if tool_name not in allowed_tools:  # Discovered too late
    raise Error()

# GOOD - validate as tokens arrive
async for token in llm.stream(prompt):
    result = validator.push_token(token)
    if result.tool_name and not result.tool_allowed:
        await cancel()  # Stop at token 5
        break
```

### Don't: Send Full State Every Turn

```python
# BAD - O(n) tokens per turn for n observations
state["observations"].append(new_obs)
send_full_state(state)  # Gets bigger every turn

# GOOD - O(1) patches
before = {"observations": observations}
after = {"observations": observations + [new_obs]}

patch = glyph.create_state_patch(
    before,
    after,
    author_id="planner",
    revision=7,
    reason="append_observation",
)
send_patch(patch)
```

### Don't: Inline Large Data

```python
# BAD - bloats context
state = {"embeddings": [[0.1, 0.2, ...] * 1536] * 100}  # Huge

# GOOD - use an external reference descriptor
state = {
    "embeddings_ref": {
        "cid": "sha256:abc123...",
        "mime": "application/octet-stream",
        "bytes": 614400,
        "caption": "100 embeddings, 1536-dim each",
    }
}
```

---

## Quick Reference

### GLYPH vs JSON Token Counts

| Pattern | JSON | GLYPH | Savings |
|---------|------|-------|---------|
| Tool call | 42 | 28 | 33% |
| Tool list (5 tools) | 180 | 95 | 47% |
| Agent state (small) | 120 | 75 | 38% |
| Agent state (large) | 500 | 290 | 42% |
| Tabular data (10 rows) | 320 | 145 | 55% |

### Type Cheatsheet

```
null:    _
bool:    t / f
int:     42
float:   3.14
string:  hello  or  "with spaces"
list:    [1 2 3]
map:     {a=1 b=2}
struct:  Type{field=value}
id:      ^prefix:value
```

### Frame Types (GS1)

| Kind | Use |
|------|-----|
| `doc` | Full state snapshot |
| `patch` | Incremental update |
| `row` | Single record (streaming tabular) |
| `ui` | Progress, logs, artifacts |
| `ack` | Acknowledgement |
| `err` | Error event |

---

## Links

- [README](./README.md) - Full documentation
- [LOOSE_MODE_SPEC](./LOOSE_MODE_SPEC.md) - Canonical encoding rules
- [GS1_SPEC](./GS1_SPEC.md) - Streaming protocol
