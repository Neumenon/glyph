# GLYPH

**Token-efficient serialization for AI agents**

```
JSON:  {"action": "search", "query": "weather in NYC", "max_results": 10}
GLYPH: {action=search query="weather in NYC" max_results=10}
```

**40% fewer tokens. Human-readable. Schema-optional.**

---

## Why GLYPH?

| Problem | GLYPH Solution |
|---------|----------------|
| JSON wastes tokens on quotes, colons, commas | 30-50% smaller for structured data |
| Tool call validation requires full response | Streaming validation catches errors at token 3 |
| State updates can conflict | Cryptographic state verification |
| Binary formats aren't debuggable | Human-readable text |

---

## Implementations

| Language | Package | Install |
|----------|---------|---------|
| **Go** | [go/](./go/) | `go get github.com/Neumenon/glyph` |
| **Python** | [py/](./py/) | `pip install glyph-serial` |
| **JavaScript** | [js/](./js/) | `npm install glyph-js` |
| **Rust** | [rs/](./rs/) | *In progress* |

---

## Quick Start

### Python

```bash
pip install glyph-serial
```

```python
import glyph

# JSON to GLYPH (40% smaller)
data = {"action": "search", "query": "weather", "max_results": 10}
text = glyph.json_to_glyph(data)
# {action=search max_results=10 query=weather}

# Parse GLYPH
result = glyph.parse('{name=Alice age=30}')
print(result.get("name").as_str())  # Alice

# Build structured values
from glyph import g, field
team = g.struct("Team", field("name", g.str("Arsenal")), field("rank", g.int(1)))
print(glyph.emit(team))  # Team{name=Arsenal rank=1}

# Roundtrip
restored = glyph.glyph_to_json(text)
assert restored == data
```

### Go

```bash
go get github.com/Neumenon/glyph
```

```go
package main

import (
    "fmt"
    "github.com/Neumenon/glyph/glyph"
)

func main() {
    // Parse GLYPH
    text := `Match{home=Arsenal away=Liverpool score=[2 1]}`
    val, _ := glyph.Parse([]byte(text))

    // Access fields
    home := val.Get("home").String()
    fmt.Println(home)  // Arsenal

    // Emit back
    out := glyph.CanonicalizeLoose(val)
    fmt.Println(string(out))
}
```

### JavaScript / TypeScript

```bash
npm install glyph-js
```

```typescript
import { parse, emit, fromJSON, toJSON } from 'glyph-js';

// Parse GLYPH
const value = parse('{action=search query="test"}');
console.log(value.get('action'));  // search

// JSON to GLYPH
const data = { name: 'Alice', scores: [95, 87, 92] };
const text = emit(fromJSON(data));
console.log(text);  // {name=Alice scores=[95 87 92]}

// GLYPH to JSON
const restored = toJSON(parse(text));
```

---

## Token Savings

| Data Shape | JSON | GLYPH | Savings |
|------------|------|-------|---------|
| Flat object (5 fields) | ~45 tokens | ~30 tokens | **33%** |
| Nested object (3 levels) | ~120 tokens | ~75 tokens | **38%** |
| Array of objects (10 items) | ~300 tokens | ~160 tokens | **47%** |
| Tabular data (20 rows) | ~500 tokens | ~220 tokens | **56%** |

---

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

Output:
```
@tab _ [id score]
|doc_1|0.95|
|doc_2|0.89|
|doc_3|0.84|
@end
```

### Typed Structs

```python
from glyph import g, field

# Named structs for domain modeling
match = g.struct("Match",
    field("home", g.str("Arsenal")),
    field("away", g.str("Liverpool")),
    field("score", g.list(g.int(2), g.int(1)))
)
# Match{away=Liverpool home=Arsenal score=[2 1]}
```

### References

```python
from glyph import GValue

# Typed references for IDs
ref = GValue.id("user", "abc123")
print(glyph.emit(ref))  # ^user:abc123
```

### Fingerprinting

```python
# Deterministic hashing for deduplication
fp = glyph.fingerprint_loose(value)
# SHA-256 hex of canonical form
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [**COOKBOOK.md**](./docs/COOKBOOK.md) | Practical recipes and patterns |
| [**LOOSE_MODE_SPEC.md**](./docs/LOOSE_MODE_SPEC.md) | Schema-optional JSON interop spec |
| [**GS1_SPEC.md**](./docs/GS1_SPEC.md) | Streaming protocol specification |
| [**LLM_ACCURACY_REPORT.md**](./docs/LLM_ACCURACY_REPORT.md) | Benchmark results |
| [**Full Documentation**](./docs/README.md) | Complete reference |

### Implementation Docs

| Implementation | Documentation |
|----------------|---------------|
| Go | [go/glyph/](./go/glyph/) |
| Python | [py/glyph/](./py/glyph/) |
| JavaScript | [js/README.md](./js/README.md) |

---

## Format Overview

```
Null:       ∅  or  _
Bool:       t  or  f
Int:        42, -7, 0
Float:      3.14, 1e-10
String:     hello  or  "hello world"
Bytes:      b64"SGVsbG8="
Time:       2025-01-13T12:00:00Z
Ref:        ^user:abc123
List:       [1 2 3]
Map:        {a=1 b=2}
Struct:     Team{name=Arsenal rank=1}
Sum:        Some(42)  or  None()
```

**Key differences from JSON:**
- No commas between elements
- `=` instead of `:` for key-value
- Bare strings when safe (no quotes needed)
- `t`/`f` for booleans
- `∅` or `_` for null

---

## Use Cases

- **LLM Tool Calling**: Smaller payloads, streaming validation
- **Agent State**: Checkpoint and resume with hash verification
- **API Responses**: Reduce context window usage
- **Multi-Agent Communication**: Efficient message passing
- **Batch Data**: Tabular mode for datasets

See [COOKBOOK.md](./docs/COOKBOOK.md) for detailed examples.

---

## License

MIT

---

<p align="center">
  <sub>Built for AI agents by <a href="https://neumenon.ai">Neumenon</a></sub>
</p>
