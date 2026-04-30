# GLYPH Python

Python implementation of the GLYPH codec.

The primary surface is still codec-first:
- parse and emit values
- JSON bridge helpers
- canonicalization and fingerprinting
- streaming validation

Higher-level agent helpers exist, but they are optional layers on top of the codec.

## Install

```bash
pip install glyph-py
```

## Quick Start

```python
import glyph

data = {"action": "search", "query": "weather", "max_results": 10}

text = glyph.json_to_glyph(data)
print(text)

restored = glyph.glyph_to_json(text)
assert restored == data

value = glyph.parse('{name=Alice age=30 active=t}')
print(value.get("name").as_str())
print(value.get("age").as_int())

fp = glyph.fingerprint_loose(glyph.from_json(data))
print(fp)
```

## Core Functions

| Function | Description |
|----------|-------------|
| `parse(text)` | Parse GLYPH text to `GValue` |
| `emit(value)` | Emit a `GValue` as canonical loose GLYPH |
| `json_to_glyph(data)` | Convert Python data directly to GLYPH text |
| `glyph_to_json(text)` | Parse GLYPH text to Python data |
| `from_json(data)` | Convert Python data to `GValue` |
| `to_json(value)` | Convert `GValue` to Python data |
| `fingerprint_loose(value)` | SHA-256 fingerprint of canonical loose form |
| `equal_loose(a, b)` | Equality by canonical loose form |

## Building Values

```python
from glyph import g, field

team = g.struct(
    "Team",
    field("name", g.str("Arsenal")),
    field("rank", g.int(1)),
)

print(glyph.emit(team))
```

## Streaming Validation

```python
from glyph import StreamingValidator, ToolRegistry

registry = ToolRegistry()
registry.add_tool("search", {
    "query": {"type": "str", "required": True},
    "max_results": {"type": "int", "min": 1, "max": 100},
})

validator = StreamingValidator(registry)

for token in 'search{query="glyph" max_results=5}':
    result = validator.push_token(token)

assert result.complete
assert result.valid
assert result.tool_name == "search"
```

## Attic

An earlier agent-oriented runtime (`agent.py`) is parked in `attic/agents/` and is not part of the installed package.

For repo-wide docs, start at [../README.md](../README.md).
