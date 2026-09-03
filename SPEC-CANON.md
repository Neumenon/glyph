# GLYPH Canonical JSON Profile (identity substrate)

**Spec ID:** `glyph-canon-json-1.0.0` · **Date:** 2026-09-02 · **Status:** Normative for identity.

This document defines the **only** byte form that GLYPH hashes. `fingerprint(v)`, the patch
`base`, and the GS1 per-frame state hash are all `SHA-256(canon_json(v))`. There is one digest.

GLYPH text (`{k=v}`, `[a b]`, `@tab`) is a **renderer** of the same value model, governed by
`docs/CANONICAL_FORMS.md`. It is never hashed. `render(v)` and `parse(render(v))` must
round-trip the value model; identity is computed on the value, not on the rendering.

## 1. Output grammar

`canon_json(v)` is a UTF-8 byte string that is valid JSON (RFC 8259) with these constraints:

1. **No whitespace** anywhere outside string literals.
2. **Root** may be any value (object, array, string, number, `true`, `false`, `null`).
3. **Object keys** are unique and sorted by the **UTF-8 bytes of the raw key string**
   (equivalently: by Unicode code point). Duplicate keys in the value model are an error.
4. **Strings** (keys and values) are always quoted. Escaping is exactly RFC 8785 §3.2.2.2:
   `\"` `\\` `\b` `\f` `\n` `\r` `\t`; any other code point < U+0020 as `\u00xx` with
   lowercase hex; every other code point emitted as raw UTF-8 (no `\uXXXX` for non-ASCII,
   no HTML escaping, no `/` escaping). No Unicode normalization is applied.
5. **Numbers** (§2).
6. **Depth** (nesting of arrays/objects) greater than 1000 is an error.

## 2. Numbers

The value model distinguishes Int and Float. **Identity does not**: JSON consumers cannot tell
`1` from `1.0`, so integral values within the safe range collapse to integer digits. The safe
range is |x| ≤ 2^53 − 1 (`Number.MAX_SAFE_INTEGER`, the bound all three bridges already use).

| Value | canon_json |
|---|---|
| Int, |n| ≤ 2^53−1 | decimal digits, no exponent, no `.0`; zero is `0` |
| Int, |n| > 2^53−1 | **error** (`ErrIntegerRange`). Only reachable by native construction; see bridge rule below. |
| Float, finite, integral, |x| ≤ 2^53−1 | decimal digits, same as the Int (so `1.0` → `1`, `-0.0` → `0`) |
| Float, finite, otherwise | shortest round-trip digits with the existing GLYPH float rule: exponent form iff decimal exponent `E >= 6` or `E <= -5`, exponent written `e±dd` (sign always present, at least two digits), mantissa without trailing zeros. Same code as `canonFloat` (`go/glyph/canon.go`), `canon_float` (`py/glyph/loose.py`), `goFormatFloat` (`js/src/loose.ts`). So `1e300` → `1e+300`, `2^53` → `9.007199254740992e+15`. |
| NaN, +Inf, -Inf | **error** (`ErrNonFinite`) |

**JSON bridge rule.** When the input is JSON text, an integer literal beyond ±(2^53−1) is
parsed as a Float (this is what `JSON.parse` does unconditionally, and what the Go and Python
bridges already do at `json_bridge.go:107` / `loose.py:568`). Precision loss is a property of
the input format, applied identically in every language, so cross-language identity holds.
A strict bridge option may reject such literals instead.

## 3. Non-JSON scalars of the value model

Emitted as single-key objects whose key starts with `$`. These keys are **reserved**: a
JSON→value bridge that meets a single-key object with one of these keys reconstructs the
typed scalar.

| Kind | canon_json | Payload text rule |
|---|---|---|
| bytes | `{"$bytes":"<b64>"}` | RFC 4648 §4 standard base64 with `=` padding (CANONICAL_FORMS §6.1) |
| time | `{"$time":"<rfc3339>"}` | UTC, `Z` suffix, fractional seconds trimmed of trailing zeros (CANONICAL_FORMS §7.1) |
| id | `{"$id":["<prefix>","<value>"]}` | two-element array; empty prefix is `""` |
| tensor | `{"$tensor":{"dtype":"<name>","sha256":"<64 hex>","shape":[…]}}` | §4 |
| struct | plain object of its fields | TypeName dropped (same as Loose, CANONICAL_FORMS D1) |
| sum | `{"<tag>":<value>}` | same as Loose |

A bridge that meets one of the first four keys with a malformed payload (wrong JSON type, invalid base64, unparseable time, `$id` not a two-string array) errors; it never falls back to a map. `$time` beyond microsecond precision is not portable (the Python value model is microseconds), so producers that want cross-language identity do not emit it.

## 4. Tensor reference

A tensor never carries its bytes inside the value. `sha256` is over the **raw element bytes**:
little-endian, row-major, contiguous; dtypes narrower than 8 bits packed LSB-first with the
final byte's unused high bits zero (cowrie SPEC-v1 §tensor). `dtype` names: `float32`,
`float16`, `bfloat16`, `int8`, `int16`, `int32`, `int64`, `uint8`, `uint16`, `uint32`,
`uint64`, `float64`, `bool`, `qint4`, `qint2`, `qint3`, `ternary`, `binary`. `shape` is an
array of non-negative integers; rank 0 is `[]`.

The same rule (`sha256(uncompressed bytes)`) is used for wshard block leaves, so a
`signal/*` block hash equals the `$tensor.sha256` an agent state would cite. A wshard
file commits to all its blocks in a `meta/identity` block, written last, holding
`{"entries":{"<block>":"<64 hex>",…},"leaf":"sha256","v":1}` in this canonical form; the
file's identity is `sha256` of that block, i.e. the fingerprint of that value.

## 5. Digest and strict check

- `fingerprint(v) = hex(SHA-256(canon_json(v)))`, 64 lowercase hex characters. Used verbatim
  as patch `base` and as the GS1 state hash. No truncated variants.
- `is_canonical(b) = (canon_json(parse_json(b)) == b)`. Receivers at trust boundaries reject
  bytes that fail this check: the GS1 cursor rejects `kind=doc` and `kind=patch` frames whose
  payload is not canonical. This gives "exactly one valid encoding" without a bespoke
  decoder, and makes `sha256(payload)` of a doc frame equal to the state hash of its value.

## 6. Relationship to RFC 8785 (JCS)

On values with ASCII keys, safe integers, and non-integral floats inside JCS's exponent
window, `canon_json` and JCS produce identical bytes. Documented divergences:

1. **Key order**: UTF-8 byte order here; UTF-16 code-unit order in JCS. Differs only when a
   non-BMP key is compared with a key in U+E000–U+FFFF.
2. **Integers beyond 2^53−1**: native Ints error here; JSON literals become doubles (as in JS). JCS impls variously refuse, raise, or lose precision.
3. **Float exponent thresholds**: GLYPH rule (`E>=6`/`E<=-5`, `e+06`) vs ES `Number::toString`
   (`1e21`/`1e-7`). Both are shortest-round-trip; only the exponent window differs.

## 7. Patch wire form

A patch is a value of this profile, emitted with `canon_json`:

```
{"glyph_patch":1,"ops":[op,…],"base":"<64 hex>"?,"target":"<prefix>:<value>"?,
 "schema":"<id>"?,"type":"<TypeName>"?}
op  := {"op":"="|"+"|"-"|"~","path":[seg,…],"value":<v>?,"index":<n>?}
seg := <string>   -- struct field or map key
     | <integer>  -- list index, ≥ 0
```

- `glyph_patch` is always `1`. `ops` is required and may be empty. The other top-level keys
  are omitted when empty; `target` is `prefix:value` split at the first colon.
- `value` is required for `=`, `+`, `~` and forbidden for `-`. For `~` it is a number (the
  delta). Otherwise it is any value of this profile, so typed scalars ride as §3 objects.
- `index` is allowed only on `+`: insert before that list position; omitted means append.
- Emitters sort ops by (`canon_json(path)`, op) so a patch diffed in any language emits the
  same bytes. Parsers accept any JSON spelling; canonical bytes are enforced by §5 receivers.
- Unknown keys at either level are an error.

## 8. Conformance

- `harness/state_identity` subject `canon_json` must agree across Python, Go, and JS on every
  fixture (uniform errors count as agreement) and every canonical output must parse with the
  language's stdlib JSON and re-canonicalize to identical bytes.
- Depth and integer-range errors are unit-tested per language (Python's stdlib JSON parser
  cannot load a 1001-deep fixture, so depth is not a harness fixture).
- Bridges may enforce tighter resource limits on ingest than §1's depth 1000: the JSON
  bridges reject nesting deeper than 128, and `is_canonical` inherits that limit.
