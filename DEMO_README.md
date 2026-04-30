# GLYPH Oracle Demo: Production-Grade Agent Scenario

> Status: legacy demo documentation. This is an example showcase, not the primary documentation path for the codec.
> For current docs, start with [README.md](./README.md) and [docs/README.md](./docs/README.md).

## Overview

This sophisticated demo showcases GLYPH in a **real-world AI agent workload**—a customer service agent handling a refund request with streaming validation, state checkpointing, and knowledge base queries.

The demo is designed to **prove GLYPH's value** through concrete metrics and production-like patterns:

```
Run: python3 demo_oracle_sophisticated.py
```

---

## What This Demo Demonstrates

### 1. **Streaming Tool Call Validation**
The killer feature for AI agents. Invalid tool calls are detected at token 5 instead of token 50+.

```
Hallucinating tool "delete_database"?
  → Detected at token 3
  → Rejected immediately
  → Saves 47 tokens, ~$0.07 per error

With JSON:
  → Detected after generation completes
  → 50+ wasted tokens
  → No early detection
```

### 2. **State Serialization (10-15% savings)**
Multi-turn agent conversations are 10-15% smaller than JSON, freeing context window space.

```
Turn 1 state:
  JSON:  774 chars
  GLYPH: 694 chars  (-10.3%)

Turn 2 state (larger):
  JSON:  1603 chars
  GLYPH: 1433 chars (-10.6%)
```

### 3. **Tabular Format for Knowledge Base Results (55% savings)**
Search results and embeddings are dramatically smaller in tabular format:

```
5-article knowledge base:
  JSON:   ~780 tokens
  GLYPH:  ~350 tokens  (-55%)

The GLYPH tabular format:
@tab Article [id title relevance snippet]
kb_001 "Refund Policy 2025" 0.98 "30-day full refunds"
kb_002 "Defective Item Replacement" 0.95 "Free shipping both ways"
@end
```

### 4. **Incremental Patching (67% savings)**
After Turn 2, resending full state costs 1603 chars. GLYPH patches cost 150 chars.

```
Full resync (JSON):  1603 chars
Patch (GLYPH):       150 chars
Savings:             90.6%
```

### 5. **Context Window Impact**
For a 100k-token context window, GLYPH frees up 3,800 tokens:

```
                    JSON      GLYPH     Freed
Tool definitions    ~1,500    ~900      +40%
Conversation        ~950      ~550      +42%
KB results          ~780      ~350      +55%
State checkpoint    ~1,200    ~400      +67%
─────────────────────────────────────────────
Overhead (full):    ~94,000   ~97,800   +3,800 tokens
```

### 6. **Cryptographic Verification**
Prevent silent state corruption in distributed agents:

```
Turn 1: {conv_id=xxx ...} → hash: 0e8686232e66cfdc
Turn 2: {conv_id=xxx ...} → hash: 78bc1460e64bcff5

If agent receives:
  @patch base=0e8686232e66cfdc...

But actual state hash is 78bc1460e64bcff5:
  → Automatic resync triggered
  → No silent corruption
```

---

## Real-World Scenario Walkthrough

### Scenario: Customer Refund Request

**User**: "My TV arrived damaged. What's your refund policy?"

#### Turn 1: Agent researches policy
1. **Tool call**: `search_knowledge_base{query="refund policy damaged item" top_k=3}`
   - 3 KB articles returned in GLYPH tabular format
   - 55% smaller than JSON
   
2. **State saved**:
   - Conversation turn #1 + KB results + thought process
   - GLYPH: 694 chars
   - JSON: 774 chars (-10.3%)

#### Turn 2: Agent fetches customer history & processes refund
1. **Tool call #1**: `fetch_customer_history{customer_id="cust_789"}`
   - Returns: lifetime_value_cents, account_age_days, orders
   - GLYPH format shows customer is eligible (487-day account, positive history)

2. **Tool call #2**: `process_refund{customer_id="cust_789" order_id="ORD_2025_001" amount_cents=5999 reason="item_damaged"}`
   - **Streaming validation** detects "process_refund" at token 15
   - Validates against registry: ✓ Tool exists, ✓ arguments valid
   - If tool was hallucinated → reject at token 3, save 47 tokens

3. **State updated**:
   - GLYPH: 1433 chars
   - JSON: 1603 chars (-10.6%)
   - State hash: 78bc1460e64bcff5 (cryptographic verification)

#### Turn 3 (Hypothetical):
Instead of resending full 1603-char state, GLYPH patches only changes:

```
@patch base=78bc1460e64bcff5
turns+{num=3 user="..." tools=[...]}
current_step~1
refund_sent=t
```

Saves: 90.6% (150 chars vs 1603 chars)

---

## Key Metrics for Production

For **1M agent requests** with average 10k tokens per interaction:

| Metric | JSON | GLYPH | Savings |
|--------|------|-------|---------|
| Avg tokens/request | 10,000 | 8,400 | 1,600 |
| Monthly requests | 1,000,000 | 1,000,000 | — |
| **Total tokens/month** | **10B** | **8.4B** | **1.6B** |
| Cost @ $1.50/M tokens | **$15.00** | **$12.60** | **$2.40** |
| **Monthly savings** | — | — | **$2,400** (100k req/day) |

For **high-volume inference** (100M+ requests/month), this compounds to **$240K+ annual savings**.

---

## Architecture Patterns Shown

### 1. Tool Registry with Allow-Lists
```python
registry = ToolRegistry()
registry.tools["process_refund"] = {
    "description": "Issue a refund",
    "args": {
        "customer_id": {"type": "str", "required": True},
        "amount_cents": {"type": "int", "min": 1, "max": 100000}
    }
}
```

### 2. Structured Agent State
```python
@dataclass
class AgentState:
    conversation_id: str
    customer_id: str
    turns: list[ConversationTurn]  # Serialized to GLYPH
    state_hash: str  # Cryptographic verification
```

### 3. Streaming Validation
```python
validator = StreamingToolValidator(registry)

for token in llm_stream:
    result = validator.push_token(token)
    if result['should_continue'] == False:
        cancel_generation()  # Reject early
        break
```

### 4. Tabular Knowledge Base Results
```
@tab Article [id title relevance snippet]
kb_001 "Refund Policy 2025" 0.98 "30-day full refunds"
kb_002 "Defective Item Replacement" 0.95 "Free shipping both ways"
@end
```

---

## Running the Demo

### Prerequisites
```bash
cd /path/to/glyph
pip install -e py/  # Install glyph in editable mode
```

### Run
```bash
python3 demo_oracle_sophisticated.py
```

### Expected Output
- Turn 1: Knowledge base search with tabular results
- Turn 2: Customer history + streaming validation + state serialization
- Turn 3: Incremental patching visualization
- Context window impact analysis
- Cryptographic verification demo
- Final cost/savings metrics

---

## Why This Demo Convinces Engineers

### Realistic Scenario
- ✓ Real customer service workflow
- ✓ Multi-turn conversation with state growth
- ✓ Multiple tool types (search, fetch, process)
- ✓ Knowledge base integration

### Concrete Metrics
- ✓ Actual character counts (not projections)
- ✓ Token savings by use case
- ✓ Context window impact (real problem for long agents)
- ✓ Cost analysis (what CFOs care about)

### Production-Grade Patterns
- ✓ Streaming validation (prevents hallucinations)
- ✓ State checkpointing (fault tolerance)
- ✓ Cryptographic verification (Byzantine safety)
- ✓ Tabular batches (RAG/vector DB integration)

### Backward Compatibility
- ✓ Drop-in JSON replacement (`json_to_glyph`)
- ✓ Existing tool registries work unchanged
- ✓ No LLM retraining needed

---

## Next Steps

1. **Try the demo**: Run it and see actual token counts
2. **Adapt the scenario**: Replace customer service with your domain
3. **Measure baseline**: How many tokens is your current system using?
4. **Calculate ROI**: At your request volume, what's the savings?

For questions:
- See [COOKBOOK.md](docs/COOKBOOK.md) for integration patterns
- See [AGENT.md](AGENT.md) for design philosophy
- See [TOOL_CALL_REPORT.md](docs/reports/TOOL_CALL_REPORT.md) for streaming validation details

---

<p align="center">
  <strong>GLYPH: 30-50% token savings. Streaming validation. State verification. Built for agents.</strong>
</p>
