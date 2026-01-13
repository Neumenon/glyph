# GLYPH Benchmark Reports Index

**Last Updated:** December 26, 2024

---

## Quick Summary: GLYPH vs JSON vs ZON vs TOON

| Metric | GLYPH | JSON | ZON | TOON |
|--------|:-----:|:----:|:---:|:----:|
| Size vs JSON | **-48%** | -- | -72% | +12% |
| Tokens vs JSON | **-48%*** | -- | -61% | +17% |
| LLM Retrieval | **100%** | 100% | 95% | 100% |
| LLM Generation (1st try) | 81-92% | **100%** | 0% | 33% |
| LLM Generation (w/recovery) | **100%** | **100%** | N/A | N/A |
| Round-trip Safe | ✓ | ✓ | ✗ | ✓ |
| Streaming Validation | ✓ | ✓ | - | - |
| Human Readable | ✓✓✓ | ✓✓ | ✓ | ✓✓✓ |
| Adversarial Tests | **200** | - | - | - |

*With auto-pool for repeated data

---

## Available Reports

### 1. [CODEC_BENCHMARK_REPORT.md](./CODEC_BENCHMARK_REPORT.md)
**Comprehensive comparison of all codecs**
- Size and token comparison
- LLM retrieval accuracy by model
- LLM generation quality
- Round-trip safety
- Feature comparison matrix

### 2. [LLM_ACCURACY_REPORT.md](./LLM_ACCURACY_REPORT.md)
**Detailed LLM accuracy analysis**
- Retrieval accuracy by question type
- Generation quality analysis
- Embedding similarity (wire vs semantic)
- Model-specific results (3B, 8B, 24B)

### 3. [STREAMING_VALIDATION_REPORT.md](./STREAMING_VALIDATION_REPORT.md)
**Real LLM streaming validation tests**
- Early tool detection (50% through response)
- Early rejection (66% tokens saved)
- Incremental constraint validation
- Latency savings measurement

### 4. [TOOL_CALL_REPORT.md](./TOOL_CALL_REPORT.md)
**GLYPH for LLM tool calls**
- Schema definition and validation
- Allow list implementation
- Generation results by model
- Integration examples

### 5. [SUBSTRATE_COMPARISON.md](./SUBSTRATE_COMPARISON.md)
**Agent substrate benchmarks**
- Agent trace compression
- Deduplication efficiency
- Incremental updates

### 6. [OPTIMIZATION_REPORT.md](./OPTIMIZATION_REPORT.md)
**GLYPH optimization techniques**
- Auto-pool for string deduplication
- Tabular format for arrays
- Best practices

### 7. [GLYPH_BENCHMARK_REPORT.md](../benchmark/comparison/js/glyph_tests/GLYPH_BENCHMARK_REPORT.md)
**LLM Generation Benchmark (8 tests, 96+ cases)**
- 4 frontier models tested (Claude Sonnet 4, Haiku, GPT-4o, GPT-4o-mini)
- 100% accuracy with error recovery
- Few-shot scaling, complex payloads, multi-turn editing
- Hardest cases stress test

### 8. [GLYPH_VALUE_REPORT.html](./GLYPH_VALUE_REPORT.html)
**Interactive Value Report**
- Hero metrics and competitive matrix
- Cost savings calculator (real API pricing)
- Security section (200 adversarial tests)
- Collapsible test results

---

## Key Findings

### Size Efficiency
```
Agent Trace (50 steps):
  JSON:       66,103 bytes (baseline)
  GLYPH:      57,485 bytes (-13%)
  GLYPH+Pool: 26,167 bytes (-60%)
  ZON:        18,367 bytes (-72%)
  TOON:       73,739 bytes (+12%)
```

### LLM Retrieval Accuracy (mistral-small:24b)
```
JSON:       100%
GLYPH:      100%
GLYPH+Pool: 100%
TOON:       100%
ZON:         95%
```

### LLM Generation Accuracy (Frontier Models)
```
GLYPH with Error Recovery:  100% (all 4 models)
  - Claude Sonnet 4:     92% first try → 100% with retry
  - Claude 3.5 Haiku:    83% first try → 100% with retry  
  - GPT-4o:              75% first try → 100% with retry
  - GPT-4o-mini:         75% first try → 100% with retry
  
Every failure fixed with ONE retry. 100% recovery rate.
```

### Streaming Validation Benefits
```
Early tool detection:    50% through response
Tokens saved on reject:  66%
Time saved on reject:    33%
```

### Embedding Similarity
```
With semantic projection, ALL codecs achieve identical similarity.
Don't embed wire format - embed semantic view.
```

---

## Recommendations

### Use GLYPH When:
- Token budget is constrained
- LLM reads but doesn't generate the format
- Streaming validation is needed
- Human readability matters

### Use GLYPH+Pool When:
- Agent traces with repeated schemas
- Storage efficiency is critical
- Tools process output (not LLMs)

### Use JSON When:
- Maximum compatibility needed
- No streaming requirement
- (Note: GLYPH now matches JSON on LLM generation with error recovery)

### Avoid ZON When:
- Round-trip safety required
- Boolean values are important (T/F confuses LLMs)

### Avoid TOON When:
- Token efficiency matters (larger than JSON)

---

## Running Benchmarks

```bash
cd sjson/benchmark/comparison/js

# Size comparison
node codec_substrate_bench.mjs

# LLM accuracy
node codec_llm_accuracy_bench.mjs --model=llama3.2:3b

# Streaming validation
node streaming_validation_test.mjs

# Tool calls
node codec_toolcall_bench.mjs
```

---

## Test Data Location

- Results: `sjson/benchmark/comparison/js/*_results/`
- Scripts: `sjson/benchmark/comparison/js/*.mjs`
- Datasets: `sjson/glyph/bench/datasets/`

---

*Retrieval benchmarks: Ollama local inference (llama3.2:3b, qwen3:8b, mistral-small:24b)*
*Generation benchmarks: Frontier API models (Claude Sonnet 4, Haiku, GPT-4o, GPT-4o-mini)*
