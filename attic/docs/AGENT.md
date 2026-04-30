# GLYPH for Agents

## Testing Philosophy (VITAL)

**`../../docs/TESTING_PHILOSOPHY.md`** is the canonical testing guide for all projects in this workspace. Read it before writing or reviewing tests.

> Status: legacy positioning note. Useful as an example-oriented document, but not the primary codec-first entry point for this repo.
> Start with [README.md](./README.md) and [docs/README.md](./docs/README.md) for current package names and active docs.

> The serialization format designed for how AI agents actually work.

---

## Why GLYPH Exists

JSON was designed in 2001 for web browsers. AI agents have different needs:

| Agent Need | JSON Reality | GLYPH Solution |
|------------|--------------|----------------|
| Token efficiency | 40% of tokens are syntax noise | 30-50% smaller payloads |
| Streaming validation | Must wait for complete parse | Validate at token 3-5 |
| State synchronization | Resend everything every turn | Verified incremental patches |
| Tool call safety | Hallucinations detected late | Cancel generation on first invalid token |
| Batch operations | Repeated keys waste context | Tabular mode: headers once, rows stream |

GLYPH is not a general-purpose format. It's purpose-built for the agent execution loop.

---

## The Agent Tax

Every token your agent reads or writes costs money and latency. JSON extracts a tax:

```json
{"action":"search","query":"weather in NYC","max_results":10}
```
**42 tokens**

```
{action=search query="weather in NYC" max_results=10}
```
**28 tokens** — same information, 33% cheaper.

At scale, this compounds:

| Scenario | JSON | GLYPH | Savings |
|----------|------|-------|---------|
| Tool call | 42 tok | 28 tok | 33% |
| API response | 156 tok | 98 tok | 37% |
| 10-row dataset | 320 tok | 145 tok | 55% |
| Agent trace | 890 tok | 520 tok | 42% |

For agents processing thousands of requests, GLYPH pays for itself immediately.

---

## Core Capabilities

### 1. Streaming Validation

The killer feature for tool-calling agents.

**Problem**: Your agent hallucinates a tool call. With JSON, you discover this after generating 50+ tokens—wasted compute, wasted money.

**Solution**: GLYPH validates as tokens arrive:

```
Token 1: SearchWeb        ← Tool name detected
Token 2: {                ← Struct opened
Token 3: query            ← Field validated against schema
Token 4: =                ← Assignment
Token 5: "hotels          ← Value streaming...

→ If "SearchWeb" isn't registered: CANCEL at token 1
→ If "query" isn't a valid field: CANCEL at token 3
→ If value violates constraints: CANCEL immediately
```

**Result**: Invalid tool calls cost 5 tokens instead of 50. At $15/M output tokens, this adds up.

```python
from glyph import StreamingValidator, ToolRegistry

registry = ToolRegistry()
registry.add_tool("search", {
    "query": {"type": "str", "required": True},
    "max_results": {"type": "int", "min": 1, "max": 100}
})

validator = StreamingValidator(registry)

for token in llm_stream:
    result = validator.push_token(token)
    if result.should_cancel:
        cancel_generation()  # Stop bleeding tokens
        break
```

### 2. State Verification

Long-running agents accumulate state. Syncing that state is expensive.

**Problem**: Every turn, you re-serialize the full agent memory into context. O(n) growth kills long conversations.

**Solution**: GLYPH patches with cryptographic verification:

```
# Initial state (sent once)
AgentState{memory=[...] tools=[...] context=[...]}

# Turn 2: Only send what changed
@patch base=a7f3c2...
memory[3]=Observation{content="User confirmed booking"}

# Turn 3: Another incremental update
@patch base=b8e4d1...
memory+Observation{content="Payment processed"}
context.step~1
```

The `base=` hash ensures patches apply to the expected state. Mismatch? Automatic resync. No silent corruption.

**Patch operations**:
- `field=value` — Set/replace
- `list+item` — Append
- `counter~1` — Increment

### 3. Tabular Mode

Agents often work with homogeneous data: search results, embeddings, database rows.

**Problem**: JSON repeats keys for every item:

```json
[{"name":"Alice","score":95},{"name":"Bob","score":87},{"name":"Carol","score":91}]
```

**Solution**: GLYPH sends headers once:

```
@tab Result [name score]
Alice 95
Bob 87
Carol 91
@end
```

**55-70% smaller** for typical datasets. Headers transmitted once, rows stream efficiently.

### 4. Three Encoding Modes

GLYPH adapts to your needs:

**Struct Mode** — Human-readable, debuggable:
```
Match{home=Arsenal away=Liverpool score=[2 1]}
```

**Packed Mode** — Maximum compression (schema required):
```
Match@(Arsenal Liverpool [2 1])
```
Fields encoded positionally. 20-30% smaller than struct mode.

**Tabular Mode** — Bulk data:
```
@tab Match [home away score]
Arsenal Liverpool [2 1]
Chelsea "Man City" [1 1]
@end
```

The encoder picks automatically based on data shape, or you force a mode.

---

## When to Use GLYPH

### Use GLYPH When:

**You're building tool-calling agents**
- Streaming validation catches hallucinations early
- Tool definitions are 40% smaller in system prompts
- Constraint checking happens mid-generation

**Your agents have long-running state**
- Patches beat full reserialization
- State hashing prevents corruption
- Memory stays bounded

**You're processing batch data in context**
- Tabular mode for search results, embeddings, datasets
- 55%+ savings on homogeneous lists
- Streaming row output

**Token costs matter**
- 30-50% reduction adds up at scale
- Especially for high-volume inference
- Context window pressure relief

**You need multi-agent coordination**
- GS1 protocol for multiplexed streaming
- Stream IDs for agent-to-agent channels
- Verified state sync across processes

### Maybe Don't Use GLYPH When:

- You're building a REST API for browsers (use JSON)
- You need maximum binary efficiency (use Protobuf/MessagePack)
- Your tooling ecosystem requires JSON (gradual migration works)
- Single-shot, stateless requests with no validation needs

---

## Integration Patterns

### Tool Calling (Any LLM)

Define tools in your system prompt:

```
You have access to these tools:

SearchTool{
  query: str           # What to search for
  max_results: int     # 1-100, default 10
  filters: Filters?    # Optional filtering
}

Filters{
  date_range: str?     # "today", "week", "month", "year"
  source: str?         # Domain to restrict to
}

Respond with a tool call or Answer{content="..."}.
```

The LLM outputs:
```
SearchTool{query="GLYPH serialization format" max_results=5}
```

Parse and validate:
```python
import glyph

result = glyph.parse(llm_output)
# result = {"query": "GLYPH serialization format", "max_results": 5}
```

### LangChain Integration

```python
from langchain.output_parsers import BaseOutputParser
import glyph

class GlyphOutputParser(BaseOutputParser):
    def parse(self, text: str) -> dict:
        return glyph.parse(text)

    def get_format_instructions(self) -> str:
        return "Respond in GLYPH format: {key=value key2=value2}"

# Use with any chain
chain = prompt | llm | GlyphOutputParser()
```

### Multi-Agent Coordination (GS1)

GS1 is GLYPH's streaming protocol for agent networks:

```python
from glyph.stream import GS1Writer, GS1Reader

# Agent A sends on stream 1
writer = GS1Writer(connection)
writer.write_doc(sid=1, data=TaskAssignment{...})
writer.write_patch(sid=1, base_hash=..., patch=StatusUpdate{...})

# Agent B receives
reader = GS1Reader(connection)
for frame in reader:
    if frame.sid == 1:
        handle_task(frame.data)
```

**Frame types**:
- `doc` — Full document
- `patch` — Incremental update with base hash
- `row` — Tabular data row
- `ui` — Progress/status events
- `ack/err` — Acknowledgments
- `ping/pong` — Keepalive

### JSON Interop

GLYPH converts losslessly to/from JSON:

```python
import glyph
import json

# JSON → GLYPH
json_data = {"name": "Alice", "scores": [95, 87, 91]}
glyph_text = glyph.from_json(json_data)
# → {name=Alice scores=[95 87 91]}

# GLYPH → JSON
glyph_text = '{action=search query="test"}'
json_data = glyph.to_json(glyph.parse(glyph_text))
# → {"action": "search", "query": "test"}
```

Migrate incrementally. Run both formats during transition.

---

## Agent Patterns

### ReAct Loop with Compressed State

```python
state = {"memory": [], "step": 0}

while not done:
    # State in context is GLYPH-compressed
    prompt = f"""
Current state:
{glyph.json_to_glyph(state)}

Think step by step, then respond with either:
- Thought{{content="..."}}
- Action{{tool="..." args={{...}}}}
- Answer{{content="..."}}
"""

    response = llm(prompt)
    parsed = glyph.parse(response)
    payload = glyph.to_json(parsed)
    kind = payload.pop("$type", "")

    if kind == "Action":
        result = execute_tool(payload["tool"], payload["args"])
        state["memory"].append({"content": result})
        state["step"] += 1
```

### Streaming Tool Validation

```python
async def validated_tool_call(llm_stream, registry):
    validator = StreamingValidator(registry)
    tokens = []

    async for token in llm_stream:
        tokens.append(token)
        result = validator.push_token(token)

        if result.should_cancel:
            await llm_stream.cancel()
            raise InvalidToolCall(
                f"Rejected at token {len(tokens)}: {'; '.join(result.errors)}"
            )

        if result.complete:
            return {"tool_name": result.tool_name, "fields": result.fields}

    raise IncompleteToolCall()
```

### Checkpoint/Resume

```python
import glyph
import hashlib

def checkpoint(agent_state, checkpoint_id):
    encoded = glyph.json_to_glyph(agent_state)
    state_hash = hashlib.sha256(encoded.encode()).hexdigest()[:12]

    save_to_storage(checkpoint_id, {
        "data": encoded,
        "hash": state_hash,
        "timestamp": time.time()
    })
    return state_hash

def resume(checkpoint_id, expected_hash=None):
    checkpoint = load_from_storage(checkpoint_id)

    if expected_hash and checkpoint["hash"] != expected_hash:
        raise CheckpointMismatch()

    return glyph.parse(checkpoint["data"])
```

### Batch Inference Results

```python
from glyph import TabularWriter

writer = TabularWriter(schema=InferenceResult)

# Stream results as they complete
for item in batch_inference(inputs):
    writer.write_row({
        "input_id": item.id,
        "embedding": item.embedding,  # List becomes space-separated
        "confidence": item.score
    })

output = writer.finish()
# @tab InferenceResult [input_id embedding confidence]
# img_001 [0.1 0.2 0.3 ...] 0.95
# img_002 [0.4 0.5 0.6 ...] 0.87
# @end
```

---

## Schema Definition

Schemas are optional but unlock compression and validation:

```python
from glyph import Schema

schema = Schema()

# Define a struct
schema.add_struct("SearchTool", {
    "query": {
        "type": "str",
        "wire_key": "q",      # Compress to single char
        "required": True,
        "min_length": 1,
        "max_length": 1000
    },
    "max_results": {
        "type": "int",
        "wire_key": "n",
        "default": 10,
        "min": 1,
        "max": 100
    },
    "filters": {
        "type": "SearchFilters",
        "wire_key": "f",
        "optional": True
    }
})

# Enable packed mode for this type
schema.enable_packed("SearchTool")

# Now encoding uses wire keys and packed format:
# SearchTool@("weather" 5) instead of SearchTool{query="weather" max_results=5}
```

---

## Performance

Benchmarks on M3 MacBook Pro (Go implementation):

| Operation | Throughput |
|-----------|------------|
| Parse (small) | 450,000 ops/sec |
| Parse (medium) | 85,000 ops/sec |
| Emit (small) | 620,000 ops/sec |
| Emit (tabular rows) | 180,000 rows/sec |
| Streaming validation | 1.2M tokens/sec |

Memory allocation is minimal—most operations are zero-copy on the parse path.

---

## Language Support

GLYPH has identical implementations in 5 languages:

| Language | Package | Install |
|----------|---------|---------|
| **Go** | `github.com/Neumenon/glyph` | `go get github.com/Neumenon/glyph` |
| **Python** | `glyph-py` | `pip install glyph-py` |
| **TypeScript** | `cowrie-glyph` | `npm install cowrie-glyph` |
| **Rust** | `glyph-rs` | `cargo add glyph-rs` |
| **C** | source build | Build from source |

All implementations produce identical output for the same input. Cross-language tests verify parity.

---

## Quick Reference

### Syntax

```
# Struct (map with known type)
TypeName{field=value field2=value2}

# Anonymous map
{key=value key2=value2}

# List
[item1 item2 item3]

# Nested
Outer{inner=Inner{value=42} list=[1 2 3]}

# Strings (quotes optional for simple values)
{name=Alice}           # Bare word
{name="Alice Smith"}   # Quoted for spaces
{json="has \"quotes\""}  # Escaped

# Numbers
{int=42 float=3.14 neg=-10 sci=1.5e10}

# Booleans and null
{yes=t no=f empty=null}

# Packed (positional, schema required)
TypeName@(value1 value2 value3)

# Tabular
@tab TypeName [field1 field2 field3]
value1a value2a value3a
value1b value2b value3b
@end

# Patch
@patch base=abc123...
field=new_value
list+appended_item
counter~1
```

### API (Python)

```python
import glyph

# Parse
data = glyph.parse('{action=search query="test"}')
# → GValue representing {action=search query=test}

# Emit
text = glyph.json_to_glyph({"action": "search", "query": "test"})
# → {action=search query=test}

# Convert back to JSON-compatible Python data
payload = glyph.to_json(data)
# → {"action": "search", "query": "test"}

# JSON bridge
glyph_text = glyph.json_to_glyph(json_data)
json_data = glyph.to_json(glyph.parse(glyph_text))

# Canonicalize (deterministic output)
canonical = glyph.canonicalize(data)
```

---

## Migration from JSON

1. **Start with tool outputs**: Parse LLM responses as GLYPH
2. **Add to system prompts**: Define tools in GLYPH format
3. **Enable streaming validation**: Catch hallucinations early
4. **Migrate state serialization**: Use patches for long-running agents
5. **Add schemas incrementally**: Unlock packed/tabular modes

GLYPH and JSON coexist. Migrate at your own pace.

---

## Further Reading

- [COOKBOOK.md](docs/COOKBOOK.md) — 10+ detailed recipes
- [LOOSE_MODE_SPEC.md](docs/LOOSE_MODE_SPEC.md) — Schema-free canonical format
- [GS1_SPEC.md](docs/GS1_SPEC.md) — Streaming protocol specification
- [OPTIMIZATION_REPORT.md](docs/reports/OPTIMIZATION_REPORT.md) — Encoding efficiency analysis

---

## TL;DR

GLYPH is for agents what JSON is for web apps—but designed for the constraints that actually matter:

1. **Tokens cost money** → 30-50% smaller
2. **Hallucinations waste compute** → Validate at token 5, not 50
3. **State grows unbounded** → Verified incremental patches
4. **Batch data bloats context** → Tabular mode

If you're building agents that call tools, manage state, or process data at scale, GLYPH pays for itself.

```
{start=here}
```
