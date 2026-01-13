# GLYPH

**Token-efficient serialization and streaming protocol for AI agents.**

```
JSON:  {"action": "search", "query": "weather in NYC", "max_results": 10}
GLYPH: {action=search query="weather in NYC" max_results=10}
```

40% fewer tokens. Human-readable. Schema-optional. Streaming validation.

## Implementations

| Language | Path | Status |
|----------|------|--------|
| Go | [go/](./go/) | Production |
| JavaScript/TypeScript | [js/](./js/) | Production |
| Python | [py/](./py/) | Production |
| Rust | [rs/](./rs/) | In Progress |

## Quick Start

### Go

```bash
go get github.com/Neumenon/glyph/glyph
```

```go
import "github.com/Neumenon/glyph/glyph"

text := `Match{home=Arsenal away=Liverpool score=[2 1]}`
val, err := glyph.Parse([]byte(text))
```

### JavaScript

```bash
npm install glyph-js
```

```javascript
import { parse, emit } from 'glyph-js';

const text = `{action=search query="weather"}`;
const value = parse(text);
```

### Python

```bash
pip install glyph-serial
```

```python
import glyph

text = '{action=search query="weather"}'
result = glyph.parse(text)
```

## Features

- **Token Efficiency**: 30-50% smaller than JSON for structured data
- **Streaming Validation**: Detect invalid tool calls early, not at the end
- **State-Verified Patches**: Cryptographic proof of update integrity
- **Human-Readable**: Debug without tools
- **Schema-Optional**: Works without coordination

## Documentation

See [docs/](./docs/) for:
- [README.md](./docs/README.md) - Full documentation
- [LOOSE_MODE_SPEC.md](./docs/LOOSE_MODE_SPEC.md) - Schema-optional JSON interop
- [GS1_SPEC.md](./docs/GS1_SPEC.md) - Streaming protocol specification
- [BLOB_POOL_SPEC.md](./docs/BLOB_POOL_SPEC.md) - Memory pooling
- [LLM_ACCURACY_REPORT.md](./docs/LLM_ACCURACY_REPORT.md) - Benchmark results

## License

MIT
