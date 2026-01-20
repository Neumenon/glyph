# GLYPH

**Token-efficient serialization for AI agents. 40% fewer tokens, streaming validation, human-readable.**

```json
JSON:  {"action": "search", "query": "weather in NYC", "max_results": 10}
```

```glyph
GLYPH: {action=search query="weather in NYC" max_results=10}
```

**84 tokens vs 140 tokens** (40% reduction)

---

## Why GLYPH?

JSON wastes tokens on redundant syntax and validates too late. GLYPH fixes both:

**1. 30-56% Token Reduction**: No quotes, no colons, no commas - just data
**2. Streaming Validation**: Catch errors at token 3, not after full generation
**3. Human-Readable**: Still debuggable, unlike binary formats

---

## Key Features

### 🎯 **30-56% Token Reduction**
- Flat objects: 33% savings
- Nested structures: 40-47% savings
- Tabular data: 50-56% savings (auto-table mode)

| Data Shape | JSON Tokens | GLYPH Tokens | Savings |
|------------|-------------|--------------|---------|
| Flat object (5 fields) | 45 | 30 | **33%** |
| Nested object (3 levels) | 120 | 75 | **38%** |
| Array of objects (10 items) | 300 | 160 | **47%** |
| Tabular data (20 rows) | 500 | 220 | **56%** |

### ⚡ **Streaming Validation**
Validate tool calls at **token 3** instead of waiting for full generation.

```glyph
{tool=unknown...  ← Cancel at token 3, not token 150
```

**Why it matters**: Catch bad tool names, missing params, constraint violations immediately. Save tokens and latency.

### 📊 **Auto-Tabular Mode**
Homogeneous lists compress to tables automatically:

```glyph
@tab _ [name age city]
|Alice|28|NYC|
|Bob|32|SF|
|Carol|25|Austin|
@end
```

**50-70% smaller** than JSON arrays.

### 🔒 **State Fingerprinting**
SHA-256 hashing prevents concurrent modification conflicts. Enables checkpoint/resume workflows.

### 🔄 **JSON Interoperability**
Drop-in replacement. Bidirectional conversion. One-line change.

---

## Quick Start

### Install

| Language | Installation | Documentation |
|----------|--------------|---------------|
| **Python** | `pip install glyph-serial` | [Python Guide →](py/README.md) |
| **Go** | `go get github.com/Neumenon/glyph` | [Go Guide →](go/README.md) |
| **JavaScript** | `npm install glyph-js` | [JS Guide →](js/README.md) |
| **Rust** | `cargo add glyph-codec` | [Rust Guide →](rust/README.md) |
| **C** | `make` | [C Guide →](c/README.md) |

### Example: Python

```python
import glyph

# JSON to GLYPH
data = {"action": "search", "query": "AI agents", "limit": 5}
glyph_str = glyph.json_to_glyph(data)
# Result: {action=search limit=5 query="AI agents"}

# GLYPH to JSON
original = glyph.glyph_to_json(glyph_str)

# Parse and access
result = glyph.parse('{name=Alice age=30}')
print(result.get("name").as_str())  # Alice
```

### Example: Go

```go
import "github.com/Neumenon/glyph/glyph"

text := `{action=search query=weather limit=10}`
val, _ := glyph.Parse([]byte(text))
action := val.Get("action").String()  // "search"
```

### Example: JavaScript

```typescript
import { parse, emit, fromJSON } from 'glyph-js';

const value = parse('{action=search query=test}');
console.log(value.get('action'));  // 'search'

const text = emit(fromJSON({ name: 'Alice', scores: [95, 87, 92] }));
// {name=Alice scores=[95 87 92]}
```

**More examples**: [5-Minute Tutorial →](docs/QUICKSTART.md)

---

## When to Use GLYPH

### ✅ Use GLYPH:
- LLMs **reading** structured data (tool responses, state, batch data)
- Streaming validation needed (real-time error detection)
- Token budgets are tight
- Multi-agent systems with state management

### ⚠️ Use JSON:
- LLMs **generating** output (they're trained on JSON)
- Existing JSON-only system integrations

**Best Practice**: Hybrid—LLMs generate JSON, serialize to GLYPH for storage/transmission.

---

## Format Reference

```
Null:    ∅ or _          List:    [1 2 3]
Bool:    t / f           Map:     {a=1 b=2}
Int:     42, -7          Struct:  Team{name=Arsenal}
Float:   3.14, 1e-10     Sum:     Some(42) / None()
String:  hello           Ref:     ^user:abc123
Bytes:   b64"SGVsbG8="   Time:    2025-01-13T12:00:00Z
```

**vs JSON**: No commas · `=` not `:` · bare strings · `t`/`f` bools · `∅` null

---

## Documentation

### 📚 Getting Started
- [5-Minute Quickstart](docs/QUICKSTART.md) - Get running fast
- [Comprehensive Guide](docs/GUIDE.md) - Features and patterns *(coming soon)*
- [AI Agent Patterns](docs/AGENTS.md) - LLM integration recipes

### 🔧 Reference
- [Technical Specifications](docs/SPECIFICATIONS.md) - Loose Mode, GS1, type system *(coming soon)*
- [API Reference](docs/API_REFERENCE.md) - Per-language API docs *(coming soon)*
- [Visual Guide](docs/visual-guide.html) - Interactive examples

### 📊 Research & Benchmarks
- [LLM Accuracy Report](docs/LLM_ACCURACY_REPORT.md) - How LLMs handle GLYPH
- [Performance Benchmarks](docs/CODEC_BENCHMARK_REPORT.md) - Speed and token metrics
- [Cookbook](docs/COOKBOOK.md) - 10 practical recipes
- [All Reports →](docs/)

---

## Use Cases

**Tool Calling**: Define tools in GLYPH (40% smaller system prompts), validate at token 3-5 during streaming.

**Agent State**: Store conversation history 40% more efficiently, patch with base hashes for concurrent safety.

**Batch Data**: Auto-tabular mode for embeddings, search results, logs (50-70% reduction).

[More Examples →](docs/QUICKSTART.md)

---

## Advanced Features

**Loose Mode**: Schema-optional, JSON-compatible. [Spec →](docs/LOOSE_MODE_SPEC.md)

**GS1 Streaming**: Frame protocol with CRC-32 and SHA-256 verification. [Spec →](docs/GS1_SPEC.md)

**Agent Patterns**: Tool definitions, state patches, ReAct loops, multi-agent coordination. [Guide →](docs/AGENTS.md)

---

## Performance

**Codec Speed** (Go implementation):
- Canonicalization: 2M+ ops/sec
- Parsing: 1.5M+ ops/sec

[Full Benchmarks →](docs/CODEC_BENCHMARK_REPORT.md)

---

## Project Structure

```
glyph/
├── README.md              ← You are here
├── docs/                  ← Documentation
│   ├── QUICKSTART.md
│   ├── AGENTS.md
│   ├── COOKBOOK.md
│   └── ...
├── go/                    ← Go implementation
├── py/                    ← Python implementation
├── js/                    ← JavaScript/TypeScript
├── rust/                  ← Rust implementation
├── c/                     ← C implementation
└── tests/                 ← Cross-language tests
```

---

## Contributing

Contributions welcome! Please see:
- [Issues](https://github.com/Neumenon/glyph/issues) - Bug reports and feature requests
- [Discussions](https://github.com/Neumenon/glyph/discussions) - Questions and ideas

---

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

---

**Built by [Neumenon](https://neumenon.ai)** · Making AI agents more efficient, one token at a time.
