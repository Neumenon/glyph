# GLYPH Stream v1 (GS1) Specification

**Spec ID:** `gs1-1.0.0`  
**Date:** 2026-01-13  
**Status:** Frozen (v1.0)

> **Implementation scope:** GS1 framing is currently implemented in Go and JavaScript / TypeScript only. Python, Rust, and C do not implement GS1.

> This document specifies the GS1 stream framing protocol for GLYPH payloads.
> GS1 headers are NOT part of GLYPH canonicalization.

---

## 0. Scope

**GS1** is a **stream framing protocol** for transporting a sequence of **GLYPH payloads** over streaming transports (TCP, WebSocket, pipes, files, SSE).

- GS1 does **not** modify GLYPH syntax or canonicalization.
- A GS1 frame contains:
  - A **GS1 header** (stream metadata)
  - A **payload** that is **valid GLYPH text** (UTF-8 bytes)
- Canonicalization, schema validation, and patch semantics are properties of the **payload**, not GS1.

### Relationship to GLYPH

- A GS1 implementation **MUST NOT require changes** to the GLYPH parser.
- The GS1 reader is a separate layer that outputs `payloadBytes` to the normal GLYPH decoder.

---

## 1. Terminology

| Term | Definition |
|------|------------|
| **Frame** | One message in the stream (header + payload) |
| **SID** | Stream identifier (multiplex key) |
| **SEQ** | Per-SID sequence number (monotonic) |
| **KIND** | Semantic category of the payload |
| **BASE** | Optional state hash for patch safety |
| **CRC** | Optional CRC-32 checksum for integrity |

---

## 2. Frame Kinds

| Value | Name | Meaning |
|------:|------|---------|
| 0 | `doc` | Snapshot or general GLYPH document/value |
| 1 | `patch` | GLYPH patch doc (`@patch ... @end`) |
| 2 | `row` | Single row value (streaming tabular data) |
| 3 | `ui` | UI event value (progress/log/artifact refs) |
| 4 | `ack` | Acknowledgement (usually no payload) |
| 5 | `err` | Error event (payload describes error) |
| 6 | `ping` | Keepalive / liveness check |
| 7 | `pong` | Ping response |

Implementations **MUST** accept unknown kinds and surface them as `unknown(<byte>)`.

---

## 3. GS1-T (Text Framing)

GS1-T is the text-based wire format, suitable for SSE, WebSocket text frames, logs, and debugging.

### 3.1 Frame Structure

```
@frame{key=value key=value ...}\n
<exactly len bytes of payload>
\n
```

### 3.2 Header Grammar

The header line starts with `@frame{` and ends with `}\n`.

Inside `{}` is a space-separated or comma-separated list of `key=value` pairs.

**Required keys:**

| Key | Type | Description |
|-----|------|-------------|
| `v` | uint8 | Protocol version (MUST be 1; enforced in Go and JS — frames with v ≠ 1 are rejected) |
| `sid` | uint64 | Stream identifier |
| `seq` | uint64 | Sequence number (per-SID, monotonic) |
| `kind` | string/uint8 | Frame kind (name or number) |
| `len` | uint32 | Payload length in bytes |

**Optional keys:**

| Key | Type | Description |
|-----|------|-------------|
| `crc` | string | CRC-32 of payload: `crc32:<8hex>` or `<8hex>` |
| `base` | string | State hash: `sha256:<64hex>` |
| `final` | bool | End-of-stream marker for this SID |
| `flags` | uint8 | Bitmask (hex) |
| `hashmode` | string | Canonicalization mode used for `base` hash: `loose` (default) or `strict`. Absent = `loose`. A receiver MUST reject a frame whose `hashmode` it does not support. |

### 3.3 Payload Reading Rule (Critical)

Receiver **MUST** read payload as raw bytes using `len`.
Receiver **MUST NOT** parse payload boundaries using delimiters.

### 3.4 Trailing Newline

- Writer **MUST** emit a trailing `\n` after payload.
- Reader **SHOULD** consume trailing `\n` but **MUST** accept EOF.

### 3.5 Example

```
@frame{v=1 sid=1 seq=12 kind=patch len=32 crc=89abcdef base=sha256:0123456789abcdef...}
@patch
set .foo 42
@end

```

---

## 4. GS1-B (Binary Framing) - Reserved

GS1-B is reserved for future implementation. Binary header layout:

```
magic   3 bytes  "GS1"
ver     1 byte   uint8 (1)
flags   1 byte   uint8
kind    1 byte   uint8
sid     8 bytes  uint64 big-endian
seq     8 bytes  uint64 big-endian
len     4 bytes  uint32 big-endian
[crc]   4 bytes  uint32 (if HAS_CRC)
[base]  32 bytes (if HAS_BASE)
payload len bytes
```

**Flags bits:**
- bit 0 (`0x01`) = `HAS_CRC`
- bit 1 (`0x02`) = `HAS_BASE`
- bit 2 (`0x04`) = `FINAL`
- bit 3 (`0x08`) = `COMPRESSED` (reserved for GS1.1)

---

## 5. Integrity: CRC-32

When `crc` is present:

- Algorithm: **CRC-32 IEEE** (polynomial 0xEDB88320)
- Input: payload bytes as transmitted
- Format in GS1-T: `crc=<8 lowercase hex digits>` or `crc=crc32:<8hex>`

Receiver **MUST** verify CRC if present and reject frame on mismatch.

---

## 6. Patch Safety: BASE Hash

When `base` is present:

- Algorithm: **SHA-256**
- Input: `CanonicalizeStrict(stateDoc)` or `CanonicalizeLoose(stateDoc)`
- Format in GS1-T: `base=sha256:<64 lowercase hex digits>`

### 6.1 State Hash Definition

```
base = sha256( Canonicalize(stateDoc) )
```

The default canonicalization mode is `loose` (`CanonicalizeLoose`).
Senders using strict mode MUST include `hashmode=strict` in the frame header.
Receivers that do not implement strict mode MUST reject frames bearing
`hashmode=strict` with a `BASE_MISMATCH` error.

If `hashmode` is absent, `loose` is assumed. In Go, the source-of-truth
helper for loose mode is `stream.StateHashLoose`, which hashes
`glyph.CanonicalizeLoose(stateDoc)`.

> **Implementation note:** `stream.StateHashEmit` (which hashes `Emit()` output)
> is not part of this specification and MUST NOT be used to compute the `base`
> field. Its output is not reproducible across formatting changes and is
> incompatible with both `loose` and `strict` modes defined here.

### 6.2 Patch Application Rule

For `kind=patch` frames with `base`:

- Receiver **MUST NOT apply** patch if `receiverStateHash != base`
- On mismatch, receiver **SHOULD**:
  - Request a `doc` snapshot, OR
  - Emit an `err` frame, OR
  - Emit an `ack` with failure payload

---

## 7. Ordering and Acknowledgement

### 7.1 SEQ Monotonicity

For each `sid`:
- `seq` **MUST** be monotonically increasing by 1
- The initial `seq` value is **0**. A frame with `seq=0` is the stream-open
  frame; receivers treat it as the first frame for that SID and reset
  per-SID ordering state.
- A frame with `seq=0` received after a higher `seq` has already been seen
  for that SID is a protocol error and **MUST** be rejected.
- Receivers **SHOULD** detect gaps and handle appropriately.
- Duplicate frames (seq ≤ lastSeen for that SID) **SHOULD** be silently
  discarded; they are not a hard protocol error.

> **Gap vs duplicate handling:** `StreamCursor` (strict mode) treats gaps
> as hard errors. `FrameHandler` (lenient mode) invokes an optional
> `OnSeqGap` callback and continues if the callback returns nil, and
> silently discards duplicates. Both behaviours are conformant with this
> spec; choose based on application requirements.

### 7.2 ACK Frames

- `kind=ack` acknowledges receipt of `(sid, seq)`
- `ack` frames typically have `len=0`
- `ack` with payload **SHOULD** use an `Error@(...)` payload (see §8.2) to
  carry failure details

### 7.3 FINAL Flag

- In **GS1-T**, end-of-stream is indicated solely by the `final=true` key
  in the header.
- The `FlagFinal` bit (`0x04`) in the `flags` field is reserved for
  **GS1-B** (binary) framing only and MUST NOT be used as the sole
  end-of-stream signal in GS1-T.
- Receiver may clean up per-SID state after receiving a final frame.

---

## 8. Recommended Payload Schemas (Non-Normative)

### 8.1 UI Event

```glyph
UIEvent@(type "progress" pct 0.42 msg "processing")
UIEvent@(type "log" level "info" msg "decoded 1000 rows")
UIEvent@(type "artifact" mime "image/png" ref "blob:sha256:..." name "plot.png")
```

### 8.2 Error Event

```glyph
Error@(code "BASE_MISMATCH" msg "state hash mismatch" sid 1 seq 13)
```

The struct type name is `Error@` (not `Err@`). Valid `code` values are
defined in §8.5.

### 8.3 Row Event

Payload is a single GLYPH value (struct/list) representing one row.

### 8.4 Patch Event

```glyph
@patch
set .items[0].qty 5
append .items[+] Item@(id 2 name "widget")
@end
```

### 8.5 Error Code Registry

The following `code` values are defined for `Error@(...)` payloads and
`ResyncRequest@(...)` `reason` fields:

| Code | Trigger |
|------|---------|
| `BASE_MISMATCH` | Patch `base` hash does not match receiver state |
| `SEQ_GAP` | Received `seq` skips one or more values |
| `SEQ_DUP` | Received `seq` is a duplicate (informational; discard) |
| `NO_STATE` | Patch with `base` arrived but receiver has no state hash |
| `CRC_MISMATCH` | CRC-32 verification failed |
| `VERSION_UNSUPPORTED` | `v` field is not 1 |
| `PAYLOAD_TOO_LARGE` | `len` exceeds the implementation maximum |
| `HEADER_TOO_LARGE` | Header line exceeds the implementation maximum |
| `FRAME_INVALID` | Structural parse failure (missing `@frame{`, bad fields, etc.) |

### 8.6 Resync Request

When a receiver detects a base mismatch or sequence gap, it SHOULD send a
resync request using `kind=ui` with a `ResyncRequest@(...)` payload:

```glyph
ResyncRequest@(sid 1 seq 42 want "sha256:..." reason "BASE_MISMATCH")
```

Fields:
- `sid` (uint64) — the stream ID
- `seq` (uint64) — the last good seq seen by the receiver
- `want` (string) — the expected base hash the receiver holds
- `reason` (string) — one of the error codes from §8.5

---

## 9. Security Considerations

- CRC-32 is not cryptographic; it only detects accidental corruption.
- `base` hash prevents accidental state drift but is not authentication.
- Implementations **MUST** enforce maximum `len` (recommended: 64 MiB).
- Implementations **MUST** enforce a maximum header line length
  (recommended: 64 KiB). Headers exceeding this limit MUST be rejected.
- Use TLS for transport security; GS1 does not provide encryption.

---

## 10. Conformance Checklist

A GS1 implementation is conformant if it:

1. Correctly reads/writes GS1-T frames per this spec
2. Enforces `len` limits (recommended max: 64 MiB)
3. Enforces header line length limits (recommended max: 64 KiB)
4. Verifies CRC-32 when present
5. Parses `base` hash correctly and uses `loose` mode by default
6. Rejects `hashmode=strict` if strict mode is not implemented
7. Accepts `seq=0` as the stream-open frame and rejects it after a higher seq
8. Exposes `(sid, seq, kind, payloadBytes, base?, crc?)` to caller
9. Does not require GLYPH parser changes
10. Does not treat GS1 headers as part of GLYPH canonicalization

---

## 11. Test Vectors

### 11.1 Minimal Frame

Header: `@frame{v=1 sid=0 seq=0 kind=doc len=2}`
Payload: `{}`
Full frame:
```
@frame{v=1 sid=0 seq=0 kind=doc len=2}
{}
```

### 11.2 Patch with CRC

Header: `@frame{v=1 sid=1 seq=5 kind=patch len=24 crc=a1b2c3d4}`
Payload: `@patch\nset .x 1\n@end`

### 11.3 UI Event

Header: `@frame{v=1 sid=1 seq=10 kind=ui len=35}`
Payload: `UIEvent@(type "progress" pct 0.5)`

### 11.4 ACK (no payload)

Header: `@frame{v=1 sid=1 seq=10 kind=ack len=0}`
Payload: (empty)

---

## 12. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-13 | Initial frozen spec (GS1-T only) |
| 1.0.1 | 2026-06-20 | Document seq=0 sentinel (§7.1); add hashmode optional header (§3.2, §6.1); add error-code registry (§8.5); add ResyncRequest schema (§8.6); fix Error@ struct name in §8.2; clarify FlagFinal scope (§7.3); document header size limit (§9); update conformance checklist (§10) |

---

## Appendix A: Kind Name Mapping

For GS1-T, `kind` can be specified as name or number:

```
kind=doc     <==> kind=0
kind=patch   <==> kind=1
kind=row     <==> kind=2
kind=ui      <==> kind=3
kind=ack     <==> kind=4
kind=err     <==> kind=5
kind=ping    <==> kind=6
kind=pong    <==> kind=7
```

Unknown numeric kinds (8+) are valid and preserved.
