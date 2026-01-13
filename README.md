# GLYPH

**Token-efficient serialization for AI agents**

```
JSON:  {"action": "search", "query": "weather in NYC", "max_results": 10}
GLYPH: {action=search query="weather in NYC" max_results=10}
```

**40% fewer tokens. Human-readable. Schema-optional.**

## Why GLYPH?

| Problem | Solution |
|---------|----------|
| JSON wastes tokens on syntax | 30-50% smaller output |
| Tool calls need full response to validate | Streaming validation at token 3 |
| State updates can conflict | Cryptographic fingerprinting |
| Binary formats aren't debuggable | Human-readable text |

## Implementations

| Language | Install | Docs |
|----------|---------|------|
| **Go** | `go get github.com/Neumenon/glyph` | [go/](./go/) |
| **Python** | `pip install glyph-serial` | [py/](./py/) |
| **JavaScript** | `npm install glyph-js` | [js/](./js/) |
| **Rust** | *In progress* | [rs/](./rs/) |

## Quick Start

**Python**
```python
import glyph

# JSON to GLYPH
data = {"action": "search", "query": "weather", "max_results": 10}
text = glyph.json_to_glyph(data)
# {action=search max_results=10 query=weather}

# GLYPH to JSON
restored = glyph.glyph_to_json(text)

# Parse and access fields
result = glyph.parse('{name=Alice age=30}')
print(result.get("name").as_str())  # Alice
```

**Go**
```go
import "github.com/Neumenon/glyph/glyph"

text := `Match{home=Arsenal away=Liverpool score=[2 1]}`
val, _ := glyph.Parse([]byte(text))
home := val.Get("home").String()  // Arsenal
```

**JavaScript**
```typescript
import { parse, emit, fromJSON, toJSON } from 'glyph-js';

const value = parse('{action=search query="test"}');
console.log(value.get('action'));  // search

const text = emit(fromJSON({ name: 'Alice', scores: [95, 87, 92] }));
// {name=Alice scores=[95 87 92]}
```

## Token Savings

| Data Shape | JSON | GLYPH | Savings |
|------------|------|-------|---------|
| Flat object (5 fields) | ~45 | ~30 | **33%** |
| Nested object (3 levels) | ~120 | ~75 | **38%** |
| Array of objects (10 items) | ~300 | ~160 | **47%** |
| Tabular data (20 rows) | ~500 | ~220 | **56%** |

## Features

### Auto-Tabular Mode

Homogeneous lists automatically emit as compact tables:

```python
data = [
    {"id": "doc_1", "score": 0.95},
    {"id": "doc_2", "score": 0.89},
    {"id": "doc_3", "score": 0.84},
]
print(glyph.json_to_glyph(data))
```
```
@tab _ [id score]
|doc_1|0.95|
|doc_2|0.89|
|doc_3|0.84|
@end
```

### Typed Structs & References

```python
from glyph import g, field, GValue

# Named structs
match = g.struct("Match",
    field("home", g.str("Arsenal")),
    field("away", g.str("Liverpool")),
    field("score", g.list(g.int(2), g.int(1)))
)
# Match{away=Liverpool home=Arsenal score=[2 1]}

# Typed references
ref = GValue.id("user", "abc123")  # ^user:abc123
```

### Fingerprinting

```python
fp = glyph.fingerprint_loose(value)  # SHA-256 of canonical form
```

## Format Reference

```
Null:    ∅ or _          List:    [1 2 3]
Bool:    t / f           Map:     {a=1 b=2}
Int:     42, -7          Struct:  Team{name=Arsenal}
Float:   3.14, 1e-10     Sum:     Some(42) / None()
String:  hello           Ref:     ^user:abc123
Bytes:   b64"SGVsbG8="   Time:    2025-01-13T12:00:00Z
```

**vs JSON:** No commas · `=` not `:` · bare strings · `t`/`f` bools · `∅` null

## Documentation

| Resource | Description |
|----------|-------------|
| [COOKBOOK.md](./docs/COOKBOOK.md) | Practical recipes and patterns |
| [LOOSE_MODE_SPEC.md](./docs/LOOSE_MODE_SPEC.md) | Schema-optional JSON interop |
| [GS1_SPEC.md](./docs/GS1_SPEC.md) | Streaming protocol spec |
| [LLM_ACCURACY_REPORT.md](./docs/LLM_ACCURACY_REPORT.md) | Benchmark results |

## Use Cases

- **LLM Tool Calling** — Smaller payloads, streaming validation
- **Agent State** — Checkpoint/resume with hash verification
- **API Responses** — Reduce context window usage
- **Multi-Agent** — Efficient message passing
- **Batch Data** — Tabular mode for datasets

See [COOKBOOK.md](./docs/COOKBOOK.md) for detailed examples.

---

Apache 2.0 License · Built for AI agents by [Neumenon](https://neumenon.ai)
