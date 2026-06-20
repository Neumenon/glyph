# GLYPH-T Specification

**Spec ID:** `glyph-t-1.0.0`
**Date:** 2026-06-19
**Status:** Normative (Typed surface + Patch + Path grammars)

This document specifies the GLYPH-T (typed text) encoding surface, the Patch
grammar, the Path grammar, and the canonical forms that every emit path must
produce. It is authoritative over the code for the typed layer. Loose-mode
rules not covered here are governed by `docs/LOOSE_MODE_SPEC.md`.

For the canonical scalar forms (shared by Typed, Loose, Packed, and Tabular
modes) see `docs/CANONICAL_FORMS.md` (normative companion). This document
references that file rather than duplicating the bit-level rules.

---

## 1. Value Model and Round-Trip Guarantee

### 1.1 The GType value model

GLYPH has a single abstract value model shared by every encoding surface:

| GType    | Go internal field | Notes |
|----------|-------------------|-------|
| Null     | –                 | singleton |
| Bool     | `boolVal`         | |
| Int      | `intVal int64`    | 64-bit signed |
| Float    | `floatVal float64`| IEEE-754 double; includes NaN/Inf in Typed mode only |
| Str      | `strVal string`   | valid UTF-8 |
| Bytes    | `bytesVal []byte` | opaque binary |
| Time     | `timeVal time.Time`| nanosecond precision |
| ID/Ref   | `idVal RefID`     | `{Prefix, Value string}` pair |
| List     | `listVal`         | ordered sequence |
| Map      | `mapVal`          | ordered k/v pairs |
| Struct   | `structVal`       | named type + ordered fields |
| Sum      | `sumVal`          | tagged union |

### 1.2 Full-model round-trip (D1)

**Normative.** `Parse(Emit(x)) == x` MUST hold for every GType, in every
mode. This includes the extended types (Bytes, Time, ID, and the
Int-vs-Float distinction) that JSON cannot represent natively. GLYPH-Loose
preserves the full value model; it does not collapse to a JSON-like subset.

### 1.3 NaN / +Inf / -Inf (D3)

**Typed mode only.** The bare tokens `NaN`, `Inf`, and `-Inf` are valid in
GLYPH-T and must round-trip. They are parsed by the lexer as `TokenFloat`
(token.go:390-402, 491-492) and emitted by `emitFloat` (emit.go:134-144).

**Loose, Packed, and Tabular modes.** NaN/Inf are a **hard error** on both
emit and parse. The JSON bridge enforces this at `json_bridge.go:292`.
Neither `canonFloat` (canon.go:39-65) nor `writeCanonLoose` (loose.go:475)
contain a NaN/Inf guard today — that is a **known bug** (see W2/W3 items).

---

## 2. GLYPH-T Typed Value Grammar

The GLYPH-T lexer is defined in `token.go`. The parser is in `parse.go`.
The emitter is in `emit.go`. The grammar below is EBNF-ish; whitespace
(spaces, tabs, newlines) and `// line comments` are skipped between tokens.

```ebnf
document   ::= value

value      ::= null | bool | int | float | bytes | time | ref | string
             | list | map | struct | sum

(* Scalars *)
null       ::= '∅' | 'null' | 'none' | 'nil'
bool       ::= 't' | 'true' | 'f' | 'false'
int        ::= '-'? digit+
float      ::= ('-'? digit+ '.' digit+)
             | ('-'? digit+ ('e'|'E') ('+'|'-')? digit+)
             | 'NaN' | 'Inf' | '-Inf'
             (* NaN/Inf: typed mode only — hard error in Loose/Packed/Tabular *)

bytes      ::= 'b64' '"' base64-body '"'
             (* base64-body: standard base64 alphabet, padding with '=' *)

time       ::= YYYY '-' MM '-' DD 'T' HH ':' MM ':' SS ('.' frac)? ('Z' | tz-offset)
             (* lexer scans via scanTimeFromNumber; parser accepts RFC3339/RFC3339Nano *)

ref        ::= '^' ref-bare | '^' '"' ref-quoted '"'
ref-bare   ::= (ident-char | ':' | '-' | '.')+
             (* isRefChar: letter, digit, _, :, -, . — see token.go:571-573 *)
ref-quoted ::= (* same quoted-string escape model as string; see §2.1 *)

string     ::= bare-string | '"' string-body '"'
bare-string ::= ident-start ident-continue*
             (* ident-start: ASCII letter or _ — isIdentStart, token.go:563-565 *)
             (* ident-continue: ident-start | ASCII digit — isIdentContinue, token.go:567-569 *)
             (* bare-string MUST NOT match a keyword: see §2.2 *)

(* Containers *)
list       ::= '[' value* ']'
             (* elements space- or comma-separated; commas are optional *)

map        ::= '{' map-entry* '}'
map-entry  ::= map-key ('=' | ':') value
map-key    ::= ident-token | string

(* Typed containers *)
struct     ::= type-name '{' struct-field* '}'
struct-field ::= field-key ('=' | ':') value
field-key  ::= ident-token | string
type-name  ::= ident-token  (* starts with uppercase by convention *)

sum        ::= tag-name '(' value? ')'   (* Tag(value) or Tag() for unit variant *)
             | tag-name '{' struct-field* '}'  (* Tag{...} when payload is a struct *)
tag-name   ::= ident-token

(* Lexer character classes *)
ident-start    ::= 'A'-'Z' | 'a'-'z' | '_'
ident-continue ::= ident-start | '0'-'9'
digit          ::= '0'-'9'
base64-char    ::= 'A'-'Z' | 'a'-'z' | '0'-'9' | '+' | '/' | '='
```

### 2.1 String escape model

Inside a quoted string `"..."`:

| Escape   | Meaning          |
|----------|------------------|
| `\\`     | backslash        |
| `\"`     | double quote     |
| `\n`     | newline (U+000A) |
| `\r`     | carriage return  |
| `\t`     | horizontal tab   |
| `\uXXXX` | Unicode codepoint (4 hex digits) |
| other    | literal byte     |

The emitter uses `\uXXXX` for control characters below U+0020 other than
`\n`, `\r`, `\t` (emit.go:337-348, canon.go:170-190). Invalid UTF-8 sequences
produced by `\uXXXX` escapes (e.g. lone surrogates) are replaced with U+FFFD
by the scanner (token.go:313-317).

### 2.2 Bare-string rule and keyword exclusions (D8)

**Normative: conservative quoting.** The emitter MUST emit a value bare ONLY
if it satisfies the stricter predicate that the actual Parse lexer can read back.

The lexer's `isValidBareString` predicate (token.go:585-607) is the
**authoritative gate**:
- Non-empty
- First byte: ASCII letter or `_`
- Remaining bytes: ASCII letter, ASCII digit, or `_`
- Not a keyword that would re-tokenize as a non-string: `null`, `none`, `nil`,
  `true`, `false`, `t`, `f`, `struct`, `sum`, `list`, `map`, `NaN`, `Inf`

The broader `isBareSafeV2` predicate (canon.go:93-127) allows Unicode letters
and the characters `-`, `.`, `/`. It is used by `canonString` and
`writeCanonString` in Loose/Packed/Tabular paths. The **discrepancy** between
`isBareSafeV2` and `isValidBareString` is a known bug (D8): if a Loose
canonical form with a Unicode-letter bare string is fed to the Typed parser,
the parser may reject it or mis-tokenize it. Resolution in W3: the Typed
lexer must be widened to match `isBareSafeV2`, or `canonString` must be
narrowed to match `isValidBareString`. Until that fix lands, **the Typed
emitter (`emit.go:emitString`) already uses the conservative `isValidBareString`
and is correct**; the bug is in Packed/Tabular emit paths that call `canonString`
and then feed output to the Typed parser.

### 2.3 Canonical forms for scalars

See `docs/CANONICAL_FORMS.md` for the authoritative bit-level rules. A
summary for reference:

| GType  | Canonical token                                          | Source |
|--------|----------------------------------------------------------|--------|
| Null   | `∅`                                                     | canon.go:16 |
| Bool   | `t` / `f`                                               | canon.go:22 |
| Int    | decimal, no leading zeros, `-0 → 0`                     | canon.go:30 |
| Float  | shortest round-trip digits, always has decimal point (D4)| emit.go:148 |
| Bytes  | `b64"<standard-base64>"` (D6)                           | emit.go:103 |
| Time   | UTC, RFC3339, `Z` suffix, non-zero sub-second retained (D2)| emit.go:108 (BUG — see §2.4) |
| ID/Ref | `^prefix:value` or `^"..."` for unsafe chars (D7)       | emit.go:111 |
| Str    | bare or `"..."` (see §2.2)                              | emit.go:157 |

#### Float canonical form (D4)

`emitFloat` (emit.go:148-153) produces shortest round-trip via `strconv.FormatFloat(f,'f',-1,64)`,
then appends `.0` if no decimal point is present. This correctly ensures
`Float(1.0) → "1.0"` and `Float(0.1) → "0.1"`.

**Known bug in `canonFloat` (canon.go:39-65):** integral floats below 1e6
are emitted without a decimal point (e.g. `Float(1.0) → "1"`). This breaks
the D4 rule and causes cross-language fingerprint divergence. Fix in W2:
`canonFloat` must append `.0` for integral values, matching `emitFloat`.

#### Bytes canonical form (D6)

**Typed path correct.** `emit.go:103-105` produces `b64"..."` using
`base64.StdEncoding`. The parser decodes and hard-errors on invalid base64
(`parse.go:207-214`).

**Packed/Tabular paths broken.** `emit_packed.go:269-270` and
`emit_tabular.go:202-203` emit `b64` followed by `quoteString(string(val.bytesVal))`,
which quotes the raw byte string rather than base64-encoding it. This is a
**data corruption bug** that must be fixed in W3 by calling
`base64.StdEncoding.EncodeToString(val.bytesVal)` before `quoteString`.

`parse_packed.go` and `parse_tabular.go` have no `b64"..."` decode branch.
`parseLooseValue` (loose.go:1200) also lacks a `b64"..."` branch. These must
be added in W3.

#### Time canonical form (D2)

**Normative rule:** normalize to UTC, RFC3339, always `Z` suffix. Keep
sub-second precision when the fractional part is non-zero, trimming trailing
zeros. A non-UTC instant is converted to UTC first; the UTC offset is NOT
preserved in canonical bytes. This is the SINGLE format for every emit path.

Examples:
```
2026-06-19T12:00:00Z            (no sub-second)
2026-06-19T12:00:00.5Z          (500ms — trailing zeros trimmed)
2026-06-19T12:00:00.123456789Z  (full nanosecond precision)
```

**Known bugs:**
- `emit.go:108` uses `"2006-01-02T15:04:05Z07:00"` — offset-preserving, wrong.
- `canon.go:218`, `emit_packed.go:266`, `emit_tabular.go:199`, `loose.go:488`
  all use `"2006-01-02T15:04:05Z"` — UTC correct, but drops sub-second precision.

Fix in W2/W3: all emit paths must use Go format string
`"2006-01-02T15:04:05Z"` for zero-nanosecond times, and a sub-second-aware
format (trimming trailing zeros) otherwise.

The **parser** accepts the full RFC3339Nano on input (`parse.go:221`), which
is correct.

#### Ref/ID canonical form (D7)

Emit: if `^prefix:value` is lexer-safe (characters from `isRefSafe`: letter,
digit, `_`, `-`, `.`, `/`, `:`), emit as `^prefix:value`. Otherwise emit as
`^"..."` using the string escape model (§2.1).

`canonRef` at canon.go:78-84 implements this correctly and is used by
`emit_packed.go:263` and `emit_tabular.go:196`.

**Bug in `emit.go:111-116`:** the Typed emitter writes raw `^prefix:value`
without calling `canonRef`, so it does not quote unsafe refs. Fix in W2/W3:
call `canonRef` from `emit.go`.

**Escape model for `:` inside prefix or value.** The current parsers — `parseRef`
(parse.go:196-201), `parseRefFromString` (bridge.go:160-168), and
`parseRefIDFromTarget` (parse_header.go:141-147) — split on the **first** `:`
without escaping. This means a prefix or value that itself contains `:` cannot
round-trip in the bare form. **Normative rule (D7):** when `prefix` or `value`
contains `:` (or any character outside `isRefSafe`), the entire
`prefix:value` string MUST be emitted in the quoted form `^"..."`. The quoted
form is decoded by the standard string scanner. `parseRef` (parse.go) already
handles the token produced by `scanRef` for unquoted refs; the Typed parser must
also accept `^"..."` by detecting a leading `"` after `^` in `scanRef`
(token.go:370-386 — currently has no quoted-ref branch). Fix tracked as W3/W6.

**Note on `scanRef` (token.go:370-386):** the lexer does not handle `^"..."`
today. `packed/tabular parsers` handle `^"..."` internally via their own string
detection. Adding `^"..."` to `scanRef` is required for Typed-mode
round-trip correctness.

---

## 3. Schema-Bound Encoding

### 3.1 Schema text grammar

A schema is an inline `@schema{...}` block. Schema text is parsed by
`schemaParser` in `parse.go:600-1068`.

```ebnf
schema-block ::= '@schema' '{' type-def* '}'

type-def     ::= type-name version? type-flag* kind-keyword '{' field-def* '}'
               | type-name version? type-flag* 'sum' '{' variant-def* '}'

version      ::= ':' ident-token          (* e.g. :v1 *)
type-flag    ::= '@pack' | '@tab' | '@open'

kind-keyword ::= 'struct' | 'sum'

field-def    ::= field-name ':' type-spec constraint* field-annot*

type-spec    ::= primitive-name
               | 'list' '<' type-spec '>'
               | 'map' '<' type-spec ',' type-spec '>'
               | type-name                 (* named reference *)
               | 'struct' '{' field-def* '}'  (* inline struct *)

primitive-name ::= 'null' | 'bool' | 'int' | 'float' | 'str'
                 | 'bytes' | 'time' | 'id'

constraint   ::= '[' constraint-body ']'
constraint-body ::= 'optional' | 'nonempty'
                  | 'min' '='? number | 'max' '='? number
                  | 'len' '='? int-lit
                  | number '..' number     (* range *)

field-annot  ::= '@k' '(' ident-token ')'       (* wire key *)
               | '@fid' '(' int-lit ')'         (* stable field ID *)
               | '@codec' '(' ident-token ')'   (* encoding hint *)
               | '@keepnull'                    (* emit null in packed even if optional *)
               | '@default' '(' scalar-value ')' (* scalar defaults only *)

variant-def  ::= '|'? tag-name ':' type-spec

int-lit      ::= '-'? digit+
number       ::= int-lit | float-lit
scalar-value ::= null | bool | int | float | string | ref | time
```

### 3.2 Wire keys

When `@k(wireKey)` is declared on a field and the emitter is configured with
`UseWireKeys: true`, the field is emitted with the short wire key instead of
the full field name. The parser resolves wire keys back to canonical names when
a schema is provided (`parseStructField`, parse.go:437-483).

Default emit options use `UseWireKeys: false`; `CompactEmitOptions` uses
`UseWireKeys: true` (emit.go:44-51).

### 3.3 FID-keyed structs and field order in packed encoding

Every field with an `@fid(N)` annotation has a stable numeric identity (FID ≥ 1;
never reuse a FID after a field is removed). FIDs govern field ordering in
packed and tabular encodings. Fields without FIDs retain declaration order.

Schema methods:
- `FieldsByFID()` — all fields ordered by FID ascending
- `RequiredFieldsByFID()` — required fields ordered by FID
- `OptionalFieldsByFID()` — optional fields ordered by FID

### 3.4 Packed encoding: @pack

Applies when `TypeDef.PackEnabled == true` (schema annotation `@pack`).

```ebnf
packed-value  ::= type-name '@' packed-body
packed-body   ::= '(' field-val* ')'                  (* dense form *)
                | '{' 'bm' '=' bitmap '}' '(' field-val* ')'  (* bitmap form *)

bitmap        ::= '0b' ('0'|'1')+
                  (* MSB first; bit i (from MSB) = presence of optional field i *)
                  (* bit 0 (LSB) = first optional field by FID order *)

field-val     ::= value  (* positional; order is FieldsByFID() *)
```

Dense form: all fields (required + optional) in FID order; absent optionals
emit `∅`.

Bitmap form: used when at least one optional field is absent. Required fields
first (FID order), then only the PRESENT optional fields (in FID order), guided
by the bitmap. Implemented in `emitPackedBitmap` (emit_packed.go:133-184).

Bitmap encoding: `maskToBinary` (canon.go:236-261), `binaryToMask`
(canon.go:267-295). LSB = lowest-FID optional field; bits written MSB-first in
the `0b` literal.

### 3.5 Tabular encoding: @tab

Applies when `TypeDef.TabEnabled == true` (schema annotation `@tab`).
Encodes `list<StructType>` as a header + rows.

```ebnf
tabular-block ::= tab-header newline row* '@end'

tab-header    ::= '@tab' type-name '[' col-name* ']'
col-name      ::= field-key  (* wire key or full name depending on KeyMode *)

row           ::= cell (' ' cell)* newline
cell          ::= value          (* positional; matches col order *)
```

Implemented in `emitTabularTable` (emit_tabular.go:92). Column order is
`FieldsByFID()`.

Inline tabular for nested `list<struct>` in a packed value:
`@tab Type [cols] v1a v1b | v2a v2b | ... @end` on a single line
(`EmitInlineTabular`, emit_tabular.go:288).

### 3.6 Open structs: @open

When `TypeDef.Open == true`, the parser accepts unknown fields and stores them
in an internal `@unknown` map rather than hard-erroring. This enables schema
evolution without breaking older readers.

### 3.7 KeepNull flag

When `FieldDef.KeepNull == true`, a null optional field IS included in the
packed bitmap as "present" and its `∅` value is written. Without `KeepNull`,
null optionals are treated as absent and omitted from the payload.

`isFieldPresent` (emit_packed.go:200-212) enforces this rule.

### 3.8 How typed text differs from loose text

| Aspect          | GLYPH-T (Typed)                    | GLYPH-Loose                         |
|-----------------|------------------------------------|--------------------------------------|
| NaN/Inf         | Valid bare tokens                  | Hard error                          |
| Struct syntax   | `TypeName{field=val ...}`          | `TypeName{field=val ...}` (same)    |
| Sum syntax      | `Tag(val)` or `Tag{...}`          | Same                                |
| Bytes           | `b64"..."` only                   | Same (after D6 bug fix)             |
| Bare-string set | Conservative (ASCII only)          | Wider (Unicode + `-./`)             |
| Float           | `emitFloat`: shortest + `.` always | `canonFloat`: same after D4 fix     |
| Time            | UTC + `Z` + sub-second (D2)       | Same                                |
| Wire keys       | Optional via `UseWireKeys`         | Not applicable                      |
| Schema blocks   | Embedded `@schema{...}` accepted  | Skipped on parse                    |
| Packed          | `Type@(...)` / `Type@{bm=...}(...)` | Not applicable                    |
| Tabular         | `@tab Type [...] \n rows \n @end` | Auto-tabular auto-detection only    |

---

## 4. Patch Grammar

### 4.1 Document-level structure

A patch document is a self-contained text block with a `@patch` header,
zero or more operation lines, and an `@end` footer.

```ebnf
patch-doc   ::= patch-header newline op-line* '@end'
op-line     ::= (op-set | op-append | op-delete | op-delta) newline
              | comment-line | blank-line
comment-line ::= '#' (any char)* newline
blank-line   ::= newline
```

Example (from emit_patch.go comment block):

```
@patch @schema#abc123 @keys=wire @target=M-123
= home.ft_h 2
= away.ft_a 1
+ events 90' Goal{scorer=^p:smith assist=∅}
- odds
~ home.rating +0.15
@end
```

### 4.2 Patch header

```ebnf
patch-header ::= '@patch' patch-attr*

patch-attr   ::= '@schema#' schema-hash
               | '@keys=' key-mode
               | '@target=' ref-target
               | '@base=' fingerprint

schema-hash  ::= hex-string           (* SHA-256 prefix of schema canonical form *)
key-mode     ::= 'wire' | 'name' | 'fid'
ref-target   ::= ref-bare             (* without leading ^ *)
fingerprint  ::= hex-string           (* first 16 chars of SHA-256 of base state *)
hex-string   ::= (hex-digit)+
```

Implemented in `parsePatchHeader` (parse_patch.go:85-132) and `EmitPatchWithOptions`
(emit_patch.go:291-351).

**Key mode semantics:**
- `wire` (default): field names use wire keys when available; falls back to name.
- `name`: always full canonical field names.
- `fid`: path segments use `#N` instead of field names.

**Note on `@target` parsing.** `parseRefIDFromTarget` (parse_header.go:141-147)
splits on the first `:` without escaping. A target value containing `:` that is
not a prefix separator will be mis-parsed. This is the same unescaped-ref bug
described in §2.3 (D7). Fix in W6.

### 4.3 Operation lines

```ebnf
op-set    ::= '=' ' ' path ' ' value
op-append ::= '+' ' ' path ' ' value (' @idx=' int-lit)?
op-delete ::= '-' ' ' path
op-delta  ::= '~' ' ' path ' ' delta-value

delta-value ::= ('+' | '-') number    (* explicit sign required *)
```

Operation characters are literal `=`, `+`, `-`, `~`. The parser dispatches
on `line[0]` (parse_patch.go:148-163).

`@idx=N` on an append operation inserts at position N instead of appending to
the end (parse_patch.go:192-204).

The value on `=` / `+` lines is parsed by `parseInlineValue` (parse_patch.go:260-281),
which delegates to the main Typed parser (`ParseWithOptions`) for normal values
or to `ParsePacked` for packed-format inline structs.

### 4.4 Path grammar

A path is a sequence of segments separated by `.` for struct fields, `[N]` for
list indices, and `["key"]` for map keys.

```ebnf
path         ::= path-seg ('.' path-seg | index-seg)*
             |   (* empty path = root operation *)

path-seg     ::= field-seg | fid-seg
field-seg    ::= bare-field-name | '"' string-body '"'
fid-seg      ::= '#' digit+          (* FID reference; key-mode=fid only *)

index-seg    ::= '[' int-lit ']'     (* list index *)
               | '["' map-key-body '"]'  (* map key *)

bare-field-name ::= ident-start (ident-start | digit | '_' | '-')+
```

Implemented in `parsePathToSegs` (emit_patch.go:188-265) and
`emitPathSegs` (emit_patch.go:419-458).

**FID path segments.** When `@keys=fid` is used, field segments are emitted
as `#N` (FID) rather than by name. The FID-resolution pre-pass is
`ResolveFIDs` / `ResolvePathFIDs` (emit_patch.go:533-597). FID segments are
represented internally as `PathSeg{Kind: PathSegField, FID: N, Field: ""}`;
the pre-pass populates `Field` from the schema before `ApplyPatch` navigates.

**Known weak spots (W6 scope — do not fix here, flag only):**

1. **List-index conversion errors silently ignored.**
   `parsePathToSegs` (emit_patch.go:219): `idx, _ := strconv.Atoi(inner)` —
   a non-integer inside `[...]` is silently converted to 0, which then
   silently patches the wrong list position. Normative intent: a non-integer
   inside `[...]` (when not prefixed with `"`) MUST be a parse error.

2. **Map-key quoting in `parsePathToSegs`.**
   `emit_patch.go:213-216`: the map-key body is extracted by
   `strings.Trim(inner, "\"")`, which only trims outer quotes but does not
   unescape the body. A map key containing `\"` inside `["\"key\""]` will
   be incorrectly unescaped. Normative intent: map key bodies inside path
   segments follow the same string escape model as §2.1 and must be properly
   unescaped with the `unquoteString` utility.

3. **Unresolved FID in navigation.**
   When `ApplyPatch` (not `ApplyPatchWithSchema`) is called on a FID-mode
   patch, navigation fails with an explicit error message
   (`"unresolved FID #N in path; apply with ApplyPatchWithSchema"` —
   emit_patch.go:697). This is a deliberate safety guard, not a bug.

---

## 5. Document Header

The document header identifies a GLYPH-T stream and carries optional
schema, mode, and key-mode annotations.

```ebnf
glyph-header ::= ('@glyph' | '@lyph') version? header-attr*
header-attr  ::= '@schema#' schema-hash
               | '@mode=' mode-name
               | '@keys=' key-mode
               | '@tab'
               | '@patch'

version      ::= ident-token      (* e.g. 'v2' *)
mode-name    ::= 'auto' | 'struct' | 'packed' | 'tabular' | 'tab' | 'patch'
```

Implemented in `ParseHeader` (parse_header.go:34-108) and
`EmitHeader` (parse_header.go:154+).

**Canonical spelling (D5):** The emitter MUST write `@glyph` (enforced since
PR #9 — `EmitHeader` at parse_header.go:157). The parser MUST accept both
`@glyph` and the legacy `@lyph` (enforced: parse_header.go:38). This
backward-compatibility rule is permanent.

---

## 6. Conformance Notes

### 6.1 Typed Emit/Parse round-trip

**Normative.** For every GValue `v` produced by the API:

```
Parse(Emit(v)).Value == v
```

This is the primary conformance test. The canonical forms in §2.3 define the
single expected byte string for each value. A conforming implementation
produces no alternative representations.

Current deviations from this rule that must be fixed before W1 closes:
- `emit.go:108` time format (§2.3, D2)
- `canonFloat` integer representation (§2.3, D4)
- `emit.go:111-116` unquoted unsafe refs (§2.3, D7)
- `emit_packed.go:269-270`, `emit_tabular.go:202-203` raw-bytes bug (§2.3, D6)
- `scanRef` in token.go: no `^"..."` branch (§2.3, D7)

### 6.2 Loose round-trip

GLYPH-Loose (`CanonicalizeLoose`) is a distinct emit path from GLYPH-T Emit.
Both share the same canonical scalar forms (after bugs are fixed). The
`FingerprintLoose` (SHA-256 over `CanonicalizeLoose`) is the stable
cross-language hash; it MUST be byte-identical across Go, Python, and JS.

Float unification (D4) is required for cross-language fingerprint parity.
See `LOOSE_MODE_SPEC.md §Float Formatting` and `SPECIFICATIONS.md:205` for
the currently documented divergence.

### 6.3 Cross-mode value identity

A value parsed from Typed text and then emitted in Loose canonical form (or
vice versa) MUST produce the same GValue. The GType model (§1.1) is the
single source of truth; no mode-specific erasure is permitted during
round-trip.

### 6.4 Experimental surface

The following exports are **not part of the supported typed surface** and
may change or be removed without notice (see `doc.go:69-73`):

- `EmitV2`, `EmitV2Patch` — experimental, not round-trip-integrated
- `EmitTokenAware` — deprecated, zero production callers
- `EncodeDictFrame` — experimental
- `Decimal128` — experimental
- `CanonicalHash` — deprecated; use `FingerprintLoose` instead

---

## 7. Open Issues for Future Work Items

| Issue | Severity | Work item |
|-------|----------|-----------|
| `emit.go:108` wrong time format (offset-preserving) | High | W2 |
| `canonFloat` drops decimal point for integral floats | High | W2 |
| `emit.go:111-116` unquoted unsafe refs | High | W2/W3 |
| `emit_packed.go:269`, `emit_tabular.go:202` raw-bytes bug | High | W3 |
| `parseLooseValue` no `b64"..."` branch | High | W3 |
| `scanRef` no `^"..."` branch (Typed lexer) | Medium | W3 |
| `isBareSafeV2` vs `isValidBareString` divergence | Medium | W3 |
| `parsePathToSegs` silently ignores `Atoi` error | Medium | W6 |
| `parsePathToSegs` unescaped map-key body | Medium | W6 |
| `parseRefIDFromTarget` first-`:` split (no escaping) | Medium | W6 |
| `canonFloat` in Python/JS still uses threshold rule (D4) | High | W8 |
| Time sub-second trimming in all emit paths | High | W2/W3 |
| NaN/Inf guard missing in `canonFloat`/`writeCanonLoose` | Medium | W2/W3 |
