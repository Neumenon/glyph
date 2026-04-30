# attic/

Parked work. Not part of the lead product surface, not built by default,
not maintained for parity with the core codec.

## What lives here

- `docs/AGENT.md` — earlier agent-layer prose. The codec is the product;
  agent material is example, not product.
- `docs/AGENTS.md` — agent patterns reference, kept for history.
- (subsequent commits) `agents/` — Python agent framework, debate session
  helpers, and demo scripts.
- (subsequent commits) `blob_pool/` — Blob and Pool subsystems across Go,
  Python, JS, Rust. Removed from the lead-path types and emitter; sources
  preserved here for reference.

## Reviving

These files are preserved with full git history (`git log --follow`).
To revive a parked feature, branch off and lift the relevant files back
into their original locations, then re-wire the call sites.

The wire format does not depend on parked types: a future revival can
reintroduce them without breaking compatibility, but consumers of the
core codec should not assume Blob, PoolRef, or agent helpers exist.
