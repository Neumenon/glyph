# GLYPH Research & Benchmark Reports

**Performance analysis, benchmarks, and research findings.**

---

## Reports Index

### Performance & Benchmarks

**[CODEC_BENCHMARK_REPORT.md](CODEC_BENCHMARK_REPORT.md)**
- Codec performance (parsing, canonicalization, fingerprinting)
- Speed metrics across languages (Go, Python, JS)
- Token reduction measurements
- **Key finding**: Go achieves 2M+ ops/sec canonicalization

**[OPTIMIZATION_REPORT.md](OPTIMIZATION_REPORT.md)**
- Performance optimization techniques
- Memory usage analysis
- Codec tuning results

**[BENCHMARK_INDEX.md](BENCHMARK_INDEX.md)**
- Index of all benchmark runs
- Historical performance data
- Comparison across versions

### LLM Integration

**[LLM_ACCURACY_REPORT.md](LLM_ACCURACY_REPORT.md)**
- How LLMs handle GLYPH vs JSON
- Retrieval accuracy across formats
- Generation quality comparison
- Embedding analysis
- **Key finding**: Hybrid approach recommended (LLMs generate JSON, store as GLYPH)

**[STREAMING_VALIDATION_REPORT.md](STREAMING_VALIDATION_REPORT.md)**
- Streaming validation performance
- Token-by-token error detection
- Latency savings measurements
- **Key finding**: Cancel invalid requests at token 3-5, saving 95% latency

**[TOOL_CALL_REPORT.md](TOOL_CALL_REPORT.md)**
- Tool calling patterns
- System prompt token reduction
- Validation accuracy
- Error recovery strategies

---

## Quick Links

**Documentation:**
- [Quickstart](../QUICKSTART.md) - Get started in 5 minutes
- [Complete Guide](../GUIDE.md) - Features and patterns
- [Specifications](../SPECIFICATIONS.md) - Technical specs

**Code:**
- [Python](../../py/) - Python implementation
- [Go](../../go/) - Go implementation
- [JavaScript](../../js/) - JS implementation

---

**Questions?** Open an [issue](https://github.com/Neumenon/glyph/issues) or check [discussions](https://github.com/Neumenon/glyph/discussions).
