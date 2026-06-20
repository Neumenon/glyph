# GLYPH Canonical Forms

**Spec ID:** `glyph-canonical-1.0.0`
**Date:** 2026-06-19
**Status:** Normative — supersedes conflicting statements in LOOSE_MODE_SPEC.md and SPECIFICATIONS.md
where explicitly noted. Cross-references those documents where consistent.

This document is **the contract** that W2/W8 implementation workflows code and test against.
Every rule here is normative. Implementation MUST match exactly; no deviations are permitted
within the conformance surface (Go, Python, JavaScript/TypeScript).

---

## 1. Scope and the Two Stable Surfaces

GLYPH exposes exactly two stable emitter surfaces, as documented in `doc.go:57-73`.
**GLYPH-Loose** (`CanonicalizeLoose` / `CanonicalizeLooseWithOpts`) is schema-optional,
JSON-bridgeable, and deterministically cross-language; it is the fingerprinting and LLM-facing
surface. **GLYPH-Typed** (`Emit` / `EmitWithOptions`, and the schema-bound `EmitPacked` /
`EmitTabular` it composes) is schema-bound and round-trips through `Parse`. All other emitters
(`EmitTokenAware`, `CanonicalHash`, `EmitV2`/`EmitV2Patch`, `EncodeDictFrame`, `Decimal128`)
are experimental, have zero production callers, and are explicitly NOT part of either stable
surface. The canonical forms defined in this document apply uniformly to both stable surfaces
except where a section explicitly notes a surface-specific difference; in all such cases the
difference is explicitly named and justified.

**Key contract (D1):** GLYPH-Loose PRESERVES the full SCALAR value model. The types `bytes`,
`time`, `id`, and the int-vs-float distinction all round-trip through Loose, not collapsed to
JSON-like representations. Named-struct TypeName and sum-tag syntax are **Typed-mode-only
guarantees**: in Loose, a struct collapses to a plain map `{field=val ...}` (sorted keys, no
TypeName), and a sum collapses to `{tag=value}`. This matches current emitter behaviour and
produces zero fingerprint churn for struct/sum values. The invariant `parse(emit(x)) == x`
MUST hold for every GType's scalar payload through the Loose path; the struct/sum outer
wrappers (TypeName, tag syntax) are not preserved by design.

---

## 2. Null, Bool, Int

### 2.1 Null

| Input aliases accepted on parse | Canonical emit (Loose) | Canonical emit (Typed) |
|----------------------------------|------------------------|------------------------|
| `_`, `∅`, `null`, `none`, `nil` | `_` (underscore)       | `∅` (Unicode symbol)   |

The Loose canonical null is `_` (underscore) when using the default `NullStyleUnderscore`
option (`loose.go:344,357`). The `∅` symbol is also valid Loose input but is NOT the default
canonical output. The FingerprintLoose path always uses `_` across Go, Python, and JS
(see `LOOSE_MODE_SPEC.md`, NullStyle table).

### 2.2 Bool

| Value | Canonical form (all modes) |
|-------|---------------------------|
| true  | `t`                        |
| false | `f`                        |

The long forms `true` and `false` are accepted on parse but MUST NOT be emitted by a conforming
emitter.

### 2.3 Int

- **Width:** Signed 64-bit integer (int64). The range is `[-(2^63), 2^63 - 1]`.
- **Canonical form:** Decimal digits, no leading zeros, no leading `+`, `-0` is written `0`.
- **Overflow policy (parse):** An integer literal whose value falls outside int64 range is a
  **hard error** on parse (`parse.go:130` uses `strconv.ParseInt(tok.Value, 10, 64)`; out-of-range
  returns an error that calls `addError` and returns Null). The parser MUST NOT silently coerce
  an out-of-range integer to float or truncate it.
- **Int vs float distinction:** The int type is preserved through Loose. `Int(42)` never becomes
  `Float(42.0)` on a Loose round-trip.

Examples:

```
Int(0)    → 0
Int(42)   → 42
Int(-100) → -100
```

---

## 3. Float

### 3.1 Canonical Rule (D4)

The canonical float form MUST satisfy BOTH of the following conditions simultaneously:

1. **Shortest round-trip digits.** Use the minimum number of significant digits such that
   `parse(emit(f)) == f` holds exactly (IEEE 754 double round-trip).
2. **Always include a decimal point.** A float MUST be distinguishable from an int at the
   lexical level. If shortest-round-trip produces no decimal point or exponent character
   (i.e. the value is a whole number), append `.0`.

This rule is **identical across Go, Python, and JS** and across all emit modes. It supersedes
the threshold-based rule (exponent when `exp < -4` or `exp >= 15`) documented in
`LOOSE_MODE_SPEC.md:29,34-38` and `SPECIFICATIONS.md:54,59-63`, which was disclosed as an
open divergence. The threshold rule is hereby retired. Implementations MUST migrate to the
shortest-round-trip-with-decimal-point rule stated here.

**Special values:**

| Value        | Canonical form |
|--------------|---------------|
| `+0.0`       | `0.0`          |
| `-0.0`       | `0.0`          |
| any NaN/Inf  | See section 4  |

**Worked examples:**

| Go/IEEE double         | Canonical emit | Notes                                  |
|------------------------|---------------|----------------------------------------|
| `Float64(1.0)`         | `1.0`         | Whole number: append `.0`              |
| `Float64(0.1)`         | `0.1`         | Shortest round-trip already has `.`    |
| `Float64(-0.0)`        | `0.0`         | Negative zero normalised to `0.0`      |
| `Float64(3.14)`        | `3.14`        | Shortest round-trip                    |
| `Float64(1e21)`        | `1e+21`       | Exponent form; still has no extra `.`  |
| `Float64(1.5e-10)`     | `1.5e-10`     | Exponent form with fractional mantissa |
| `Float64(1.23456789e15)` | emitter-specific shortest | Must round-trip exactly    |
| `Float64(1e21)` note   | MUST contain either `.` or `e`/`E` | exponent form satisfies condition 2 |

Note on condition 2 for exponent form: a value emitted with an exponent character (`e` or `E`,
lower-case `e` MUST be used) already contains a non-integer indicator and satisfies condition 2
without an additional `.0`. The `.0` suffix is only required when neither a `.` nor `e` is
present in the shortest-round-trip string.

**Current divergence to fix (ground truth):**

- `emitFloat` in `emit.go:148-153` uses `'f'/-1` format which never uses exponent notation,
  then appends `.0` for whole numbers. This satisfies condition 2 but can produce unnecessarily
  long strings for large values (e.g. `1e21` would become `1000000000000000000000.0`). This
  MUST be corrected to use the shortest-round-trip format.
- `canonFloat` in `canon.go:50-55` uses integer format for whole numbers below `1e6`, breaking
  condition 2 for those values (e.g. `Float(1.0)` → `"1"` instead of `"1.0"`). This MUST be
  corrected.
- `writeCanonLoose` in `loose.go:475` uses bare `'g'` format with no decimal-point guard,
  also breaking condition 2 for whole-number floats. This MUST be corrected.

---

## 4. NaN and Infinity (D3)

**Rule:** NaN, +Inf, and -Inf are TYPED-ONLY values. They are valid in the GLYPH-Typed surface
and MUST round-trip with tests. They are a **hard error** in GLYPH-Loose on both emit and parse.

### 4.1 Typed mode

- **Canonical emit tokens:** `NaN`, `Inf`, `-Inf` (bare, no quotes).
- The lexer (`token.go:490`) recognises `NaN` and `Inf` as `TokenFloat`. The negative sign
  on `-Inf` is scanned by `scanNumber` via the `-Inf` path at `token.go:398-403`.
- `emit.go:134-143` correctly emits `NaN`, `Inf`, `-Inf` in Typed mode.
- Tests MUST verify that `parse(emit(NaN)) == NaN`, etc.

### 4.2 Loose mode

- **Emit:** Any attempt to emit a float value that is NaN or Inf in Loose mode MUST return an
  error. No token is emitted.
- **Parse:** A `NaN`, `Inf`, or `-Inf` token encountered during Loose parsing MUST be rejected
  as a hard error. No fallback or coercion is permitted.
- Ground truth: `json_bridge.go:292` already enforces this for the JSON bridge path. The Loose
  emitter path (`writeCanonLoose`) currently has no guard — this is a known bug that W2/W8
  MUST fix.
- Rationale: NaN/Inf are not JSON-compatible; Loose is the JSON-bridgeable surface.

---

## 5. Strings and the Bare-String Rule (D8)

### 5.1 Conservative Quoting Rule

A string value MUST be emitted bare (without quotes) ONLY IF it satisfies the **stricter**
predicate that the actual Parse lexer can read back unambiguously. A string that the lexer
would not recognise as a bare identifier MUST be quoted.

The two predicates that exist in the codebase are:
- `isBareSafeV2` (`canon.go:93`) — allows Unicode letters, `-`, `.`, `/` (continuation); first char must be a Unicode letter or `_`. Note: `+` is NOT allowed by `isBareSafeV2` (see `canon.go:119` — only `- . /` are permitted continuation chars).
- `isValidBareString` (`token.go:585`) — ASCII-only: `[A-Za-z_][A-Za-z0-9_]*`.

**Normative rule:** The emitter MUST use the STRICTER predicate, which is `isValidBareString`,
until the lexer is extended to match `isBareSafeV2`. Emitting a Unicode bare string that the
lexer reads back as a `TokenIdent` and not as a `TokenString` is a round-trip violation. The
`isBareSafeV2` predicate exists in `canon.go` (called from `canonString` and
`writeCanonString`/`writeCanonRef`) and in `loose.go:506` — all call sites MUST be updated
to use `isValidBareString` or an equivalent stricter predicate.

**Exception for future work:** When the lexer is explicitly extended to support the wider bare
grammar (Unicode letters, `-`, `.`, `/`), the bare-safe check MAY be relaxed to match.
Until that change lands, quote conservatively.

### 5.2 Bare-Safe Characters (current Parse lexer)

A string may be emitted bare if and only if ALL of the following hold:

1. The string is non-empty.
2. The first byte is an ASCII letter (`A-Z`, `a-z`) or underscore (`_`).
3. Every remaining byte is an ASCII letter, ASCII digit (`0-9`), or underscore.
4. The string is NOT one of the reserved keywords that the lexer would tokenize as a non-string
   token: `null`, `none`, `nil`, `true`, `false`, `t`, `f`, `struct`, `sum`, `list`, `map`,
   `NaN`, `Inf`.

Characters that FORCE quoting (non-exhaustive): any non-ASCII byte, space, `-`, `.`, `/`,
`+`, `:`, `^`, `"`, `{`, `}`, `[`, `]`, `(`, `)`, `=`, `|`, `@`, `#`, `<`, `>`, `,`, `\`,
any control character.

### 5.3 Quoted String Escape Set

Inside double-quoted strings the following escape sequences are defined. The emitter MUST use
these; the parser (lexer `scanString`, `token.go:255-318`) MUST decode them identically.

| Escape | Decoded value                   |
|--------|---------------------------------|
| `\"`   | U+0022 QUOTATION MARK           |
| `\\`   | U+005C REVERSE SOLIDUS          |
| `\n`   | U+000A LINE FEED                |
| `\r`   | U+000D CARRIAGE RETURN          |
| `\t`   | U+0009 CHARACTER TABULATION     |
| `\uXXXX` | Unicode code point (4 hex digits, case-insensitive on parse, lower-case on emit) |

All other control characters (U+0000–U+001F, excluding `\n`, `\r`, `\t`) MUST be emitted as
`\uXXXX` and MUST be decoded on parse. An unrecognised escape `\x` where `x` is not one of
the above passes through as the literal byte `x` (`token.go:302`), but the emitter MUST NOT
produce such sequences.

The `\uXXXX` escape MUST decode correctly on parse (`token.go:293-300`). Invalid `\uXXXX`
sequences (fewer than 4 hex digits, non-hex characters) are a hard parse error.

Strings containing invalid UTF-8 after unquoting are sanitised by replacing invalid sequences
with U+FFFD (`token.go:314-315`). This sanitisation is a parser-side policy, not a license
for the emitter to produce invalid UTF-8.

---

## 6. Bytes (D6)

### 6.1 Canonical Form

The canonical GLYPH bytes representation is:

```
b64"<standard-base64>"
```

where `<standard-base64>` is RFC 4648 §4 standard base64 (alphabet `A-Za-z0-9+/`, `=` padding).
This form applies to **every** emit mode: Typed, Loose, Packed, and Tabular.

### 6.2 Invalid Base64 is a Hard Error

On parse, a `b64"..."` literal whose body is not valid standard base64 MUST be a hard error.
No silent coercion to a bare string, no fallback to treating the bytes as raw text.
Ground truth: `parse.go:204-212` documents and implements this contract
(`"Invalid base64 is a hard error (never silently coerced to a string)"`).

### 6.3 Current Bugs (to be fixed by W2)

The following emit paths produce the wrong bytes representation and MUST be corrected:

- `emit_packed.go:269-270`: emits `"b64" + quoteString(string(val.bytesVal))` where
  `string(val.bytesVal)` is the raw byte string, not base64-encoded. The `quoteString` call
  then produces an escaped raw-byte string, which the packed parser cannot decode as bytes.
- `emit_tabular.go:202-203`: same bug as above for tabular cells.
- `canon.go:219-220` (`canonValue`): emits `"b64" + quoteString(string(v.bytesVal))` — same
  bug; raw bytes are not base64-encoded before quoting.

The correct implementation is shown in `loose.go:104-113` (`writeCanonBytes`) and in
`emit.go:103-105` (Typed emitter), both of which correctly call
`base64.StdEncoding.EncodeToString(data)` before quoting.

The corresponding parse paths (`parse_packed.go`, `parse_tabular.go`,
`loose.go:1200` `parseLooseValue`) currently have no `b64"..."` decode branch and MUST add one.
The Typed path (`parse.go:204-213`, via `scanBytesLiteral` in `token.go`) is correct.

---

## 7. Time (D2)

### 7.1 Single Canonical Format

There is exactly ONE canonical time format across ALL emit modes:

```
RFC 3339 UTC with 'Z' suffix, sub-second trimmed of trailing zeros
```

Formal pattern: `YYYY-MM-DDTHH:MM:SS[.f+]Z` where `[.f+]` is the optional fractional-seconds
field, present only when the fractional part is non-zero, with trailing zeros trimmed.

| Time value                                | Canonical emit              |
|-------------------------------------------|-----------------------------|
| 2026-06-19 12:00:00 UTC                   | `2026-06-19T12:00:00Z`      |
| 2026-06-19 12:00:00.5 UTC                 | `2026-06-19T12:00:00.5Z`    |
| 2026-06-19 12:00:00.500 UTC               | `2026-06-19T12:00:00.5Z`    |
| 2026-06-19 12:00:00.123456789 UTC         | `2026-06-19T12:00:00.123456789Z` |
| 2026-06-19 14:00:00 +02:00 (local offset) | `2026-06-19T12:00:00Z`      |
| 2026-06-19 00:00:00.000 UTC               | `2026-06-19T00:00:00Z`      |

**UTC conversion:** A non-UTC instant MUST be converted to UTC before emitting. The UTC offset
is NOT preserved in canonical bytes. `parse(emit(t)) == t` holds for the instant (the point in
time), not for the zone.

**Fractional seconds:** If the nanosecond field is zero, no `.` is emitted. If non-zero, emit
the minimum number of decimal digits that represent the value exactly (no trailing zeros).

### 7.2 Input Acceptance

The parser MUST accept all of the following on input (`parse.go:219-232`):

- `time.RFC3339` (`2006-01-02T15:04:05Z07:00`)
- `time.RFC3339Nano` (`2006-01-02T15:04:05.999999999Z07:00`)
- `2006-01-02T15:04:05Z` (UTC no fraction)
- `2006-01-02T15:04:05` (no timezone, treated as UTC)
- `2006-01-02T15:04Z` (minute precision)
- `2006-01-02` (date only)

### 7.3 Current Bugs (to be fixed by W2)

The following emit paths produce an incorrect time format and MUST be corrected:

- `emit.go:108`: uses Go format `"2006-01-02T15:04:05Z07:00"` which preserves the input
  timezone offset (e.g. `+02:00`) instead of converting to UTC and emitting `Z`. This is wrong
  for the canonical form.
- `canon.go:218`, `emit_packed.go:266`, `emit_tabular.go:199`, `loose.go:488`: use the format
  `"2006-01-02T15:04:05Z"` which converts to UTC correctly but drops sub-second precision
  unconditionally. This is wrong when the instant has a non-zero fractional second.

The fix for all paths is to: (a) call `.UTC()` on the time value, (b) check whether the
nanosecond field is zero, (c) if zero emit `"2006-01-02T15:04:05Z"`, otherwise emit with
`time.RFC3339Nano` and trim trailing zeros from the fractional part before the `Z`.

---

## 8. Ref/ID (D7)

### 8.1 Canonical Form

A GLYPH Ref/ID value has a `Prefix` and a `Value` component. The canonical emit forms are:

**Bare form** (when safe):
```
^prefix:value
```

**Quoted form** (when prefix or value contains characters unsafe for bare scanning):
```
^"prefix:value"
```

In the bare form, the `^` character is followed directly by the full `prefix:value` string
(including the separating `:`). If `Prefix` is empty, the form is `^value` (no colon).

### 8.2 Safety Check for Bare Form

A ref string `prefix:value` (or `value` when prefix is empty) is safe for bare emission if
every character in the string satisfies the `isRefSafe` predicate (`canon.go:131-149`):
ASCII or Unicode letters, digits, `_`, `-`, `.`, `/`, `:`.

If any character outside this set appears (spaces, `@`, `"`, `\`, control characters, etc.),
the entire `prefix:value` string MUST be emitted in the quoted form `^"..."` using the same
escape set as quoted strings (section 5.3).

The `canonRef` function (`canon.go:78-84`) and `writeCanonRef` function (`loose.go:544-554`)
implement this correctly. The plain `Emit` path (`emit.go:111-116`) writes raw `^prefix:value`
with no safety check — this is a bug that W2 MUST fix by routing through `canonRef`.

**Known limitation (C4 / D8) — '/' mismatch between `isRefSafe` and the Typed lexer:**
`isRefSafe` (`canon.go:143`) allows `/` as a safe ref character. However the Typed lexer's
`isRefChar` predicate (`token.go:571-573`) does NOT include `/`; `scanRef` will terminate on
`/`, producing an incomplete token. This means a ref whose prefix or value contains `/` is
emitted bare by `canonRef` but cannot be scanned back by the Typed lexer — a round-trip
violation under D8. **Normative fix (implemented by W2):** `isRefSafe` MUST be tightened to
reject `/` so that any ref containing `/` is emitted in the quoted `^"..."` form, which the
Typed lexer can scan after W3 adds the `^"..."` branch to `scanRef`. Until W3 lands, such refs
are correctly quoted but cannot be parsed by the Typed lexer — this is tracked as a W3 item.

### 8.3 Colon Escape Model (the ':' separator problem)

The first `:` in the bare `^prefix:value` string is the prefix/value separator. This creates an
ambiguity when `:` appears inside a prefix name or value payload.

**Normative decision:** The bare ref form uses **first-`:` splitting**. A `:` character
anywhere in prefix or value MUST cause the ref to be emitted in the **quoted form** `^"..."`,
because the quoted form is opaque to the separator logic and the entire string is reconstructed
by `parseRefFromString` only after unquoting.

Specifically:
- If `prefix` contains `:`, the ref MUST be quoted.
- If `value` contains `:`, the ref MUST be quoted.
- The parser (`parseRefFromString` at `bridge.go:160-168` and `parseRefIDFromTarget` at
  `parse_header.go:141-147`) splits on the **first** `:` with no escape interpretation.
  This is correct for bare refs, which by the above rule never contain `:` in prefix or value.
- The scanner (`scanRef` at `token.go:370-386`) accepts `:` as a ref character, so
  `^user:abc123` scans correctly as a single ref token. However `scanRef` has no quoted-ref
  branch, which means the lexer cannot currently scan `^"..."` refs directly — this is a known
  limitation. Packed and tabular parsers handle `^"..."` internally.

**Implementation requirement (W2/W3):** The Typed lexer `scanRef` MUST be extended to recognise
`^"..."` and produce a `TokenRef` whose value is the unquoted string, so that `parse(emit(r))==r`
holds even when prefix or value contains special characters.

### 8.4 Emission Summary

| Condition                                   | Emitted form              |
|---------------------------------------------|---------------------------|
| `prefix` and `value` are both ref-safe       | `^prefix:value`           |
| `prefix` is empty, `value` is ref-safe       | `^value`                  |
| Either contains a non-ref-safe character     | `^"prefix:value"` (quoted)|

---

## 9. Header (D5)

### 9.1 Canonical Spelling

The canonical GLYPH header spelling is `@glyph`. This is what every conforming emitter MUST
write. Ground truth: `EmitHeader` at `parse_header.go:149-154` writes `@glyph` since PR #9.

### 9.2 Legacy Acceptance

The parser (`ParseHeader` at `parse_header.go:37-39`) MUST accept BOTH `@glyph` and `@lyph`.
The `@lyph` spelling was the original form and appears in pre-PR-#9 payloads; rejecting it
would break backward compatibility. Implementations MUST accept it on input, but MUST NOT emit
it.

---

## 10. Map Key Ordering and Duplicate-Key Policy

### 10.1 Key Ordering

Map keys MUST be sorted by **bytewise UTF-8 comparison** of their canonical string form
(as produced by `canonString` / `writeCanonString`). This is the same rule as
`LOOSE_MODE_SPEC.md:71-79` and `SPECIFICATIONS.md:116-122`.

The canonical string form of a key means: if the key is bare-safe, compare its bytes directly;
if it is quoted, compare the quoted form's bytes including the surrounding `"` characters.
Quoted keys (which begin with `"`, ASCII 0x22) sort before bare keys that begin with an ASCII
letter (0x41+), so `"_"=5` precedes `A=4`.

Example (from `LOOSE_MODE_SPEC.md`):
```
Input:  {"b":1,"a":2,"aa":3,"A":4,"_":5}
Output: {"_"=5 A=4 a=2 aa=3 b=1}
```

### 10.2 Duplicate Key Policy

When a GLYPH map (or JSON object input) contains duplicate keys, the **last-wins** policy
applies: the final occurrence of a key determines the stored value; earlier occurrences are
discarded. This is consistent with `LOOSE_MODE_SPEC.md:83-88`.

Example:
```
Input:  {"k":1,"k":2,"k":3}
Output: {k=3}
```

---

## 11. Expected Canonical Forms — Golden Reference Table

This table is the **golden reference** for W2 conformance tests. For every GType it provides
a concrete Go value, its exact canonical Loose string, and (where it differs) its canonical
Typed string. Test fixtures MUST reproduce these strings exactly.

| GType    | Go constructor example                             | Canonical Loose string              | Canonical Typed string (if different) |
|----------|----------------------------------------------------|-------------------------------------|---------------------------------------|
| Null     | `Null()`                                           | `_`                                 | `∅`                                   |
| Bool     | `Bool(true)`                                       | `t`                                 | (same)                                |
| Bool     | `Bool(false)`                                      | `f`                                 | (same)                                |
| Int      | `Int(0)`                                           | `0`                                 | (same)                                |
| Int      | `Int(42)`                                          | `42`                                | (same)                                |
| Int      | `Int(-100)`                                        | `-100`                              | (same)                                |
| Int      | `Int(9223372036854775807)` (max int64)              | `9223372036854775807`               | (same)                                |
| Float    | `Float(1.0)`                                       | `1.0`                               | (same)                                |
| Float    | `Float(0.1)`                                       | `0.1`                               | (same)                                |
| Float    | `Float(-0.0)`                                      | `0.0`                               | (same)                                |
| Float    | `Float(3.14)`                                      | `3.14`                              | (same)                                |
| Float    | `Float(1e21)`                                      | `1e+21`                             | (same)                                |
| Float    | `Float(1.5e-10)`                                   | `1.5e-10`                           | (same)                                |
| Float    | `Float(0.0)`                                       | `0.0`                               | (same)                                |
| Str      | `Str("hello")`                                     | `hello`                             | (same)                                |
| Str      | `Str("hello world")`                               | `"hello world"`                     | (same)                                |
| Str      | `Str("true")`                                      | `"true"`                            | (same)                                |
| Str      | `Str("café")` (Unicode)                            | `"café"`                            | (same)                                |
| Str      | `Str("line\nbreak")`                               | `"line\nbreak"`                     | (same)                                |
| Str      | `Str("")` (empty)                                  | `""`                                | (same)                                |
| Bytes    | `Bytes([]byte{0x48,0x65,0x6c,0x6c,0x6f})`         | `b64"SGVsbG8="`                     | (same)                                |
| Bytes    | `Bytes([]byte{})` (empty)                          | `b64""`                             | (same)                                |
| Time     | 2026-06-19T12:00:00 UTC                            | `2026-06-19T12:00:00Z`              | (same)                                |
| Time     | 2026-06-19T12:00:00.5 UTC                          | `2026-06-19T12:00:00.5Z`            | (same)                                |
| Time     | 2026-06-19T14:00:00+02:00 (non-UTC)                | `2026-06-19T12:00:00Z`              | (same)                                |
| Ref/ID   | `ID("user","abc123")`                              | `^user:abc123`                      | (same)                                |
| Ref/ID   | `ID("","abc123")`                                  | `^abc123`                           | (same)                                |
| Ref/ID   | `ID("ns","val:with:colon")`                        | `^"ns:val:with:colon"`              | (same)                                |
| List     | `List(Int(1), Int(2), Int(3))`                     | `[1 2 3]`                           | (same)                                |
| List     | `List()` (empty)                                   | `[]`                                | (same)                                |
| Map      | `Map({"a":Int(1),"b":Int(2)})`                     | `{a=1 b=2}`                         | `{a:1 b:2}` (uses `:` separator)      |
| Map      | `Map({})` (empty)                                  | `{}`                                | (same)                                |
| NaN      | `Float(math.NaN())`                                | **ERROR** (Loose hard error)        | `NaN`                                 |
| +Inf     | `Float(math.Inf(1))`                               | **ERROR** (Loose hard error)        | `Inf`                                 |
| -Inf     | `Float(math.Inf(-1))`                              | **ERROR** (Loose hard error)        | `-Inf`                                |

**Extended golden entries (G1–G5):**

| GType   | Go constructor example                             | Canonical Loose string              | Canonical Typed string (if different) | Notes |
|---------|----------------------------------------------------|-------------------------------------|---------------------------------------|-------|
| Struct  | `Struct("Match", [("home",Int(1)),("away",Int(2))])` | `{away=2 home=1}` (sorted keys, no TypeName) | `Match{home=1 away=2}` | G1: Loose collapses to map; TypeName is Typed-only |
| Sum     | `Sum("Ok", Str("done"))`                          | `{Ok="done"}`                       | `Ok("done")`                          | G2: Loose is `{tag=value}`; Typed uses Tag(val) syntax |
| Ref/ID  | `ID("ns","path/value")` (slash in value)          | `^"ns:path/value"` (quoted — D8/C4) | `^"ns:path/value"` (quoted)           | G3: '/' is safe per isRefSafe but not per Typed isRefChar — must quote |
| Int     | parse of `9223372036854775808` (2^63, overflow)   | **PARSE ERROR** (hard error)        | **PARSE ERROR** (hard error)          | G4: one above max int64; MUST NOT silently coerce or truncate |
| Bytes   | `Bytes([]byte{0x01})` (single non-zero byte)      | `b64"AQ=="`                         | `b64"AQ=="`                           | G5: standard base64 with `=` padding |
| Bytes   | `Bytes([]byte{})` (empty)                         | `b64""`                             | `b64""`                               | G5: empty bytes — no padding characters |
| Bytes   | `Bytes([]byte{0xff, 0xfe})` (non-ASCII)           | `b64"//4="`                         | `b64"//4="`                           | G5: non-ASCII bytes — `+/` in base64 alphabet |
| Bytes   | parse of `b64"!!!!"` (invalid base64)             | **PARSE ERROR** (hard error, D6)    | **PARSE ERROR** (hard error, D6)      | G5: invalid base64 character — MUST hard-error |

Notes on the table:
- "same" means the Loose and Typed canonical strings are identical for that value.
- The Map separator differs: Loose uses `key=value`; Typed (`emit.go`) uses `key:value`. The
  Loose form is the fingerprinting canonical; tests for Typed must use the Typed form.
- NaN/Inf in Loose are errors, not strings; a conforming Loose emitter returns an error and
  produces no output.
- The `b64""` form for empty bytes is defined by `loose.go:107` and MUST be matched exactly.
- For the Ref `ID("ns","val:with:colon")`, the colon in the value triggers quoted form because
  the parser's first-`:` split would misinterpret it.
- **G1 (Struct, Loose):** `writeStructLoose` (`loose.go:661-667`) calls `writeMapLoose` on the
  struct's `Fields` slice, dropping the TypeName. Keys are sorted by canonical key bytewise.
  This is the confirmed current behaviour — the Loose golden form is a plain sorted map.
- **G2 (Sum, Loose):** `writeSumLoose` (`loose.go:670-680`) emits `{tag=value}` where `tag` is
  the sum's `Tag` string and `value` is the recursive Loose form of the payload. TypeName and
  tag-variant syntax are not present in Loose output.
- **G3 (Ref with '/'):** `isRefSafe` (`canon.go:143`) allows `/` but the Typed lexer's
  `isRefChar` rejects it (see §8.2, C4). Under D8 the conformant action is to quote. W2 tightens
  `isRefSafe` to reject `/`; until then the ref is incorrectly emitted bare by `canonRef`.
  Golden form is the contract-correct post-W2 value; mark as `currentlyBuggy: true` in fixtures.
- **G4 (Int overflow):** `strconv.ParseInt(tok.Value, 10, 64)` at `parse.go:130` returns an
  error for values outside `[-2^63, 2^63-1]`. The parser calls `addError` and returns Null.
  The error case MUST appear in conformance fixtures.
- **G5 (Bytes):** `[]byte{0x01}` base64-encodes to `AQ==` (standard RFC 4648 with padding).
  `[]byte{0xff,0xfe}` encodes to `//4=`. Empty bytes encode to the empty string, giving `b64""`.
  Invalid base64 bodies MUST produce a hard parse error (no fallback).

---

## Appendix A: Cross-Reference to Existing Specs

| Topic | This document | LOOSE_MODE_SPEC.md | SPECIFICATIONS.md |
|-------|--------------|--------------------|--------------------|
| Float format | Section 3 (D4 — supersedes) | §Float Formatting (threshold rule — retired) | §Float Formatting (threshold rule — retired) |
| Float zero / negative zero (G6) | Section 3.1: `Float(0.0)→"0.0"`, `Float(-0.0)→"0.0"` (D4 — **supersedes**) | "Zero: always 0" — **RETIRED** | Not specified |
| NaN/Inf | Section 4 (D3) | "NaN/Infinity: Rejected with error" | "NaN/Infinity: Rejected with error" |
| Bare-string rule | Section 5 (D8 — conservative) | §String Bare-Safe Rule (allows Unicode) | §String Bare-Safe Rule (allows Unicode) |
| Bytes form | Section 6 (D6) | Not addressed | `b64"..."` mentioned in type table |
| Time format | Section 7 (D2 — UTC+sub-sec) | "ISO-8601 UTC" (no sub-sec rule) | "ISO-8601 strings" |
| Key ordering | Section 10 | §Key Ordering | §Key Ordering |
| Duplicate keys | Section 10 | §Duplicate Keys | §Duplicate Keys |
| Null canonical | Section 2 | `_` default | `_` default |

**Note on Float(0.0) / Float(-0.0) (C3/G6):** `LOOSE_MODE_SPEC.md` contains the rule
"Zero: always 0" (i.e. `Float(0.0)` emits the bare integer `0`). This rule is **retired and
superseded** by D4 in Section 3.1 of this document. The correct canonical form for both
`Float(0.0)` and `Float(-0.0)` is `"0.0"` — the decimal point is required to distinguish float
zero from integer zero (`Int(0)` → `"0"`). Implementations that still emit `"0"` for
`Float(0.0)` are non-conformant.

Where this document says "supersedes", the rule in this document is normative and the older
statement in `LOOSE_MODE_SPEC.md` or `SPECIFICATIONS.md` should be treated as outdated. All
other rules in those documents remain valid.

---

## Appendix B: Known Bugs Requiring W2 Fixes

This appendix consolidates the bugs cited in-line above for the W2 implementer.

| File | Location | Bug | Fix |
|------|----------|-----|-----|
| `emit.go` | line 108 | Time: preserves offset (`Z07:00`) instead of UTC `Z` | Use `.UTC()` + conditional nano format |
| `emit.go` | lines 148-153 | Float: `'f'/-1` never uses exponent; whole numbers correctly get `.0` but large values are long | Use `'g'/-1` (shortest) then append `.0` if no `.` or `e` present |
| `canon.go` | lines 50-55 (`canonFloat`) | Float: whole numbers below `1e6` emitted without `.` (integer format) | Add `.0` for whole number floats |
| `canon.go` | line 218 (`canonValue`) | Time: drops sub-second | Conditional nano format |
| `canon.go` | lines 219-220 | Bytes: raw bytes `quoteString(string(bytesVal))` not base64 | Use `base64.StdEncoding.EncodeToString` |
| `emit_packed.go` | lines 269-270 | Bytes: same raw-bytes bug | Same fix |
| `emit_tabular.go` | lines 202-203 | Bytes: same raw-bytes bug | Same fix |
| `emit_packed.go` | line 266 | Time: drops sub-second | Conditional nano format |
| `emit_tabular.go` | line 199 | Time: drops sub-second | Conditional nano format |
| `loose.go` | line 475 (`writeCanonLoose`) | Float: bare `'g'` no decimal-point guard for whole floats | Add `.0` guard |
| `loose.go` | line 488 (`writeCanonLoose`) | Time: drops sub-second | Conditional nano format |
| `loose.go` | line 1200 (`parseLooseValue`) | Bytes: no `b64"..."` decode branch | Add decode branch |
| `emit.go` | lines 111-116 | Ref: raw emit with no `canonRef` safety check | Route through `canonRef` |
| `token.go` | `scanRef` | Ref: no quoted `^"..."` branch in lexer | Add quoted-ref scanning |
| `writeCanonLoose` / `canonString` | Loose+canon paths | Bare-string: uses `isBareSafeV2` (allows Unicode) instead of `isValidBareString` | Replace with stricter predicate until lexer is extended |
| `loose.go` / `canon.go` (float, NaN) | Loose paths | No NaN/Inf guard in Loose emit | Add `math.IsNaN`/`math.IsInf` check returning error |
| `parse_packed.go` / `parse_tabular.go` | Parse paths | No `b64"..."` decode in packed/tabular parsers | Add decode branch matching `parse.go:204-213` |
