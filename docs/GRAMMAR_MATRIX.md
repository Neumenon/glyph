# GRAMMAR_MATRIX — GLYPH Codec Feature × Mode Conformance

**Status: NORMATIVE.** This document is the authoritative reference for
which features each codec mode must support. Emitters MUST NOT emit a
token that the same mode's parser cannot read back (the conservative-quoting
invariant, D8). Where the current implementation diverges from the TARGET
column, footnotes name the workflow that closes the gap.

---

## Legend

- **yes** — fully specified and implemented in the current codebase (main @ c335622).
- **no** — not implemented; emitting the feature in this mode, or expecting to parse it, is currently incorrect.
- **subset (note)** — partially implemented; the note identifies the restriction.
- **error** — the feature is a hard parse/emit error in this mode by design; not a gap.

Incremental is explicitly a documented subset of Typed. Its limits are per
`incremental.go` and do not constitute open bugs unless otherwise noted.

The CONTRACT DECISIONS (D1–D8) referenced in cell notes are defined in the
Architecture Review decisions document; their canonical text is reproduced in
abbreviated form in the footnotes below.

---

## Feature × Mode Matrix

| Feature | Loose | Typed | Packed | Tabular | Patch | Incremental |
|---|---|---|---|---|---|---|
| **Null — `∅` symbol** | yes | yes | yes | yes | yes | yes |
| **Null — `_` spelling** | yes | no [^null-typed] | yes [^null-packed] | yes | no [^null-patch] | no [^null-incr] |
| **Null — `null`/`none`/`nil`** | yes (parse) | yes (parse) | no [^null-packed-alias] | no [^null-tabrow] | no | no |
| **Bool `t`/`f`** | yes | yes | yes | yes | yes | yes |
| **Bool `true`/`false`** | yes (parse) | yes (parse) | subset (parse only, emit always `t`/`f`) | subset (parse only) | no | yes (parse) |
| **Int64 — parse/emit** | yes | yes | yes | yes | yes | yes |
| **Int64 — overflow detection** | yes (`ParseInt` 64-bit) | yes (`ParseInt` 64-bit) | yes (`ParseInt` 64-bit) | yes (`ParseInt` 64-bit) | yes | yes |
| **Float (D4: shortest + decimal point)** | no [^float-loose] | no [^float-typed] | no [^float-packed] | no [^float-tabular] | no [^float-patch] | no [^float-incr] |
| **NaN / `+Inf` / `-Inf` (D3)** | error [^nan-loose] | yes [^nan-typed] | no [^nan-packed] | no [^nan-tabular] | no [^nan-patch] | error [^nan-incr] |
| **String — quoted `"…"` + `\n\r\t\\\"` escapes** | yes | yes | yes | yes | yes | yes |
| **String — `\uXXXX` escape (emit + parse)** | yes (emit: `quoteString`; parse: `unquoteString` via `parseQuotedStringShared`) | yes | yes (via `parseQuotedStringShared`) | yes (via `parseQuotedStringShared`) | yes (via Typed) | yes (in-place `decodeUnicodeEscape` in `scanString`) |
| **Unicode bare strings (D8 conflict)** | subset [^bare-loose] | no [^bare-typed] | subset [^bare-packed] | subset [^bare-tabular] | no [^bare-patch] | no [^bare-incr] |
| **`b64"…"` bytes — emit (D6)** | yes (`writeCanonBytes`, `loose.go:104–113`) | yes (`emit.go:102–105`) | no [^bytes-packed-emit] | no [^bytes-tabular-emit] | yes (via Typed value parser) | no [^bytes-incr] |
| **`b64"…"` bytes — parse (D6)** | no [^bytes-loose-parse] | yes (`parseBytes`, `parse.go:207–213`, hard error on bad b64) | no [^bytes-packed-parse] | no [^bytes-tabular-parse] | yes (via Typed) | no [^bytes-incr] |
| **Time — UTC `Z` canonical (D2)** | subset [^time-loose] | no [^time-typed] | subset [^time-packed] | subset [^time-tabular] | subset (inherits emitter path) | no [^time-incr] |
| **Time — sub-second precision (D2)** | no [^time-sub] | no [^time-sub] | no [^time-sub] | no [^time-sub] | no [^time-sub] | no [^time-sub] |
| **Time — parse RFC3339Nano on input** | yes (`parseLooseValue` via `looksLikeTime` + `parseTimeLiteralStr`) | yes (`parse.go:218–239`, tries RFC3339Nano) | yes (via shared `parseTimeLiteralStr`, canonical format list) | yes (via shared `parseTimeLiteralStr`) | yes (via Typed) | error (hard decline — W3 fix: no silent truncation) [^time-incr] |
| **`^prefix:value` ref — bare emit** | yes (`writeCanonRef`, `loose.go:544–554`) | no [^ref-typed] | yes (`canonRef`, `emit_packed.go:263`) | yes (`canonRef`, `emit_tabular.go:196`) | yes (`emit_patch.go:317`) | yes (bare `parseRef`) |
| **`^"…"` quoted ref — emit (D7)** | yes (via `isRefSafe` + `writeCanonRef`) | no [^ref-typed] | yes (`canonRef`) | yes (`canonRef`) | yes (`canonRef`) | no [^ref-incr] |
| **`^"…"` quoted ref — parse (D7)** | no [^ref-loose-parse] | no [^scanRef-typed] | yes (`parse_packed.go:507–517`) | yes (`parse_tabular.go:637–665`) | yes (via Typed) | no [^ref-incr] |
| **Ref — `:` escaping inside prefix/value (D7)** | no [^ref-escape] | no [^ref-escape] | no [^ref-escape] | no [^ref-escape] | no [^ref-escape] | no [^ref-escape] |
| **`@glyph` header — emit (D5)** | yes (`EmitHeader`, `parse_header.go:157`) | yes | yes | yes | yes | n/a |
| **`@lyph` header — parse compat (D5)** | yes (`parse_header.go:38`) | yes | yes | yes | yes | n/a |
| **`struct Name{…}` — emit** | subset [^struct-loose] | yes | yes | yes (as rows) | yes (as values) | yes (EventStartObject + TypeName) |
| **`struct Name{…}` — parse** | no [^struct-loose-parse] | yes | yes | yes | yes | yes |
| **Sum types `Tag(v)` / `Tag{…}`** | subset [^sum-loose] | yes | yes | yes | yes | yes |
| **Nested containers (list of list, map of list, etc.)** | yes | yes | yes | yes | subset [^nested-patch] | yes |
| **Map `{k=v …}` — emit + parse** | yes | yes | yes | yes | yes (values) | yes |
| **Duplicate-key policy** | last-wins (no warning in loose) [^dupkey-loose] | last-wins + warning (`parse.go:283`) | last-wins (no warning) | last-wins (no warning) | n/a (path-addressed) | last-wins (no warning) |
| **`\u` escapes in strings — round-trip** | yes (emit: `quoteString`; parse: `unquoteString` via `parseQuotedStringShared`) | yes (`token.go:293–301` emit; `scanUnicodeEscape` parse) | yes (via `parseQuotedStringShared`) | yes (via `parseQuotedStringShared`) | yes (via Typed) | yes (`decodeUnicodeEscape` in `scanString`) |

---

## Footnotes — current gaps and closing workflows

[^float-loose]: `writeCanonLoose` (`loose.go:473–481`) uses `'g'/-1` which drops the decimal point for integral floats (e.g. `Float(1.0)` → `"1"`). **TARGET (D4):** always keep a decimal point; use shortest round-trip form. Closed by **W2**.

[^float-typed]: `emitFloat` (`emit.go:148–153`) uses `'f'/-1` and appends `.0` only when the formatted string lacks `.`; `canonFloat` (`canon.go:50–55`) emits integral floats without a decimal point for values < 1e6. Two divergent paths; neither matches D4 exactly. Closed by **W2**.

[^float-packed]: `canonFloat` is used; same issue as `float-typed`. Closed by **W2**.

[^float-tabular]: `canonFloat` is used; same issue as `float-typed`. Closed by **W2**.

[^float-patch]: `canonFloat` is used in `emit_patch.go:402`. Closed by **W2**.

[^float-incr]: Incremental parser parses floats correctly but does not emit; consumers receive a `*GValue` and rely on the caller's emitter. No incremental emitter exists; gap is in the owning mode's emitter. Closed by **W2**.

[^nan-loose]: `writeCanonLoose` (`loose.go:473`) uses `'g'` on the bare float value with no NaN/Inf guard. `math.IsNaN`/`IsInf` are not checked; the Go `strconv.FormatFloat` call would emit the strings `NaN`, `+Inf`, `-Inf` — which the Loose parser cannot read back. Per D3, this must be a hard error on emit. Closed by **W2**.

[^nan-typed]: `emit.go:133–143` explicitly emits `NaN`/`Inf`/`-Inf`; `token.go:490–491` recognises `NaN`/`Inf` as `TokenFloat`; `-Inf` is scanned via `scanNumber` at `token.go:397–403`. Round-trips correctly. NaN/Inf for Typed is normatively correct per D3.

[^nan-packed]: `canonFloat` (`canon.go:39–65`) has no NaN/Inf guard; the packed emitter would silently emit them as bare strings. The packed parser has no NaN/Inf branch. Closed by **W2**.

[^nan-tabular]: Same as `nan-packed`. Closed by **W2**.

[^nan-patch]: `canonFloat` is used in delta-value emission (`emit_patch.go:402`); no guard. Closed by **W2**.

[^nan-incr]: `incremental.go:599` explicitly rejects NaN and Inf during number parse with a hard error. Correct per D3.

[^null-typed]: The Typed lexer (`token.go:483–488`) recognises `null`/`none`/`nil` as `TokenNull`, but not `_`. A bare `_` would lex as `TokenIdent` and fall through to a bare-string parse. **TARGET:** decide whether `_` is a valid Typed-mode null synonym. Not required by D1; left to W3.

[^null-packed]: `canonNull()` returns `∅`; `parseValue` in packed checks `0xe2` byte for `∅` symbol only. `_` is recognised by the tabular row parser (`parse_tabular.go:316–319`) but not the packed parser. Inconsistency to be resolved by **W3**.

[^null-patch]: Patch ops use `parseInlineValue` which delegates to the Typed parser; same `_` gap as Typed.

[^null-incr]: `incremental.go:429–439` recognises `∅` (3-byte UTF-8) only. `_` is not handled as null.

[^null-packed-alias]: `null`/`none`/`nil` are not guarded in the packed value scanner. `parseBareOrQuotedString` would return them as `Str` values instead of `Null`.

[^null-tabrow]: Tabular row parser (`parse_tabular.go:312–323`) recognises `∅`, `_`, and `null`. Alias support is complete here.

[^bytes-packed-emit]: `emitPackedValue` (`emit_packed.go:268–270`) emits `b64` + `quoteString(string(val.bytesVal))`, which writes the raw byte slice as a Go string, not as a base64-encoded string. This is a **bug**: bytes are corrupted on any non-ASCII byte value. Closed by **W2**.

[^bytes-tabular-emit]: `emitTabularCell` (`emit_tabular.go:201–203`) has the same bug as packed. Closed by **W2**.

[^bytes-loose-parse]: `parseLooseValue` (`loose.go:1200–1246`) has no `b64"..."` branch; a `b64"..."` token in a loose cell is silently passed to `tryParseNumber` (fails) then returned as a bare string. Closed by **W3**.

[^bytes-packed-parse]: `parse_packed.go` has no dedicated `b64"..."` decode branch today (cell = **no**). The previously recorded `yes` was incorrect — the quoted-ref path at `parse_packed.go:507–517` handles `^"..."` refs, not `b64"..."` bytes literals. After **W2** fixes the emitter and adds a `b64` keyword → base64-decode branch to `parse_packed.go`, this cell becomes **yes**. Closed by **W2**+**W3**.

[^bytes-tabular-parse]: Same situation as packed — `parse_tabular.go` has no `b64"..."` decode branch today (cell = **no**). The previously recorded `yes` was incorrect. After **W2** adds the decode branch, this cell becomes **yes**. Closed by **W2**+**W3**.

[^bytes-incr]: **W3 fixed (hard error).** `parseIdentifier` in `incremental.go` now detects `b64` followed by `"` and emits a hard error instead of silently returning `b64` as a bare string followed by a separate quoted string. Full bytes-literal support in the incremental parser remains a future item.

[^time-loose]: `writeCanonLoose` and `canonValue` use `"2006-01-02T15:04:05Z"` which is UTC-only and correct for the `Z` suffix (D2), but strips sub-second precision unconditionally. Closed by **W2** (add fractional seconds when non-zero per D2).

[^time-typed]: `emit.go:108` uses `"2006-01-02T15:04:05Z07:00"` which preserves the original offset instead of normalising to UTC first — violating D2. Closed by **W2**.

[^time-packed]: `emitPackedValue` uses `"2006-01-02T15:04:05Z"` (UTC, correct suffix) but strips sub-second precision. Closed by **W2**.

[^time-tabular]: `emitTabularCell` uses `"2006-01-02T15:04:05Z"`, same issue as packed. Closed by **W2**.

[^time-sub]: No emitter currently preserves sub-second precision. D2 requires keeping fractional seconds when non-zero, trimming trailing zeros. Closed by **W2** for all modes.

[^time-parse-loose]: **W3 fixed.** `parseLooseValue` now calls `looksLikeTime` before `tryParseNumber` and delegates to the shared `parseTimeLiteralStr`. Time tokens in loose cell values are now parsed correctly instead of falling through to bare strings.

[^time-incr]: **W3 fixed (hard error).** `parseNumber` in `incremental.go` now detects a digit run followed by `-`, `T`, `:`, `Z`, or `+` (time-literal continuation characters) and emits a hard error immediately, rather than silently truncating e.g. `2026-06-19T12:00:00Z` to `Int(2026)`. Full time-literal support in the incremental parser (requiring an RFC3339Nano state machine) remains a future item.

[^ref-typed]: `emit.go:110–116` writes `^prefix:value` by string concatenation without calling `canonRef`, so unsafe characters in prefix or value are not quoted. `scanRef` (`token.go:370–386`) does not handle the `^"..."` quoted form; a quoted ref from another mode cannot be parsed by the Typed lexer. Closed by **W3** (fix emit.go to use canonRef; extend scanRef).

[^ref-loose-parse]: **W3 fixed.** `parseLooseValue` now has a `^` prefix branch that handles both bare refs (`^prefix:value`) and quoted refs (`^"prefix:value"`), using the shared `parseRefIDFromTarget` helper.

[^scanRef-typed]: `scanRef` in `token.go:370–386` accepts only `isRefChar` characters (letters, digits, `_`, `-`, `.`, `:`) without quoted-ref support. A `^"..."` ref produced by `canonRef` cannot be read back by the Typed lexer. Closed by **W3**.

[^ref-incr]: Incremental `parseRef` (`incremental.go:683–713`) handles only bare `^prefix:value`; no `^"..."` branch. Closed by **W3**.

[^ref-escape]: D7 requires an explicit escape model for `:` appearing inside prefix or value. Currently `parseRefFromString`/`parseRef` split on the first `:` unconditionally (`bridge.go:160–168`, `parse_header.go:141–147`), so a prefix containing `:` is silently misread. No escape model exists yet. Closed by **W3** (define and implement the escape rule; until then, the emitter must refuse to emit refs where prefix or value contains `:`).

[^bare-loose]: `isBareSafeV2` (`canon.go:93–127`) allows Unicode letters, `-`, `.`, `/` as continuation characters, but `isValidBareString` (`token.go:585–607`) used by the Typed emitter is ASCII-only. If a Loose-emitted bare token is then read by the Typed lexer, Unicode continuations are rejected (D8 violation). **TARGET (D8):** the normative bare-safe predicate is the stricter `isValidBareString` for all emitters. Loose must quote anything `isValidBareString` rejects. Closed by **W2**.

[^bare-typed]: `emitString` (`emit.go:156–163`) uses `isValidBareString`, which is the stricter ASCII-only predicate. This is correct per D8. No change needed.

[^bare-packed]: `canonString` uses `isBareSafeV2` (wider Unicode predicate). Same D8 hazard as bare-loose. Closed by **W2**.

[^bare-tabular]: `canonString` uses `isBareSafeV2`. Same D8 hazard. Closed by **W2**.

[^bare-patch]: Patch value emission delegates to `canonString` (for map keys) and `parseInlineValue` (which uses the Typed parser). Map key emission has the same D8 hazard via `canonString`. Closed by **W2**.

[^bare-incr]: Incremental keys are parsed as `isIdentContinue` (ASCII-only); only emits events, no string emission. No D8 gap on the parser side.

[^u-loose]: **W3 fixed.** `quoteString` emits `\uXXXX` for control characters below U+0020. `unquoteString` in `loose.go` now delegates to `parseQuotedStringShared`, which handles `\uXXXX` correctly. Control-character round-trip is now correct in Loose cell parsing.

[^u-packed]: **W3 fixed.** `parseQuotedString` in `parse_packed.go` now delegates to `parseQuotedStringShared` which handles `\uXXXX` via `decodeUnicodeEscape`.

[^u-tabular]: **W3 fixed.** `parseQuotedString` in `parse_tabular.go` now delegates to `parseQuotedStringShared`.

[^u-incr]: **W3 fixed.** `scanString` in `incremental.go` now handles `\uXXXX` with an in-place `decodeUnicodeEscape` call, preserving the `[]byte` buffer and "reset on incomplete" contract.

[^struct-loose]: `writeStructLoose` emits the struct fields as a plain `{k=v …}` map, dropping the type name. Loose parse of a type-named struct (e.g. `Match{…}`) is not supported by `parseLooseValue`; the full Typed parser handles it. This is a deliberate schema-optional design but means struct TypeName does not round-trip through Loose. Per D1 Loose must preserve the full value model; TypeName loss may be acceptable for schema-optional operation but should be explicitly documented. Not assigned to a single workflow; surfaces in **W4**.

[^struct-loose-parse]: `parseLooseValue` has no `Type{…}` branch. The full Loose `Parse()` path (Typed lexer) handles it. The lightweight cell parser does not. Closed by **W3**.

[^sum-loose]: `writeSumLoose` (`loose.go:669–680`) emits as `{tag=value}`, losing the sum tag syntax. Round-trip through the lightweight Loose parser does not reconstruct a `TypeSum` node. Full parse path handles it. Closed by **W3** (add sum detection in `parseLooseValue`).

[^nested-patch]: Patch operations address values at a path; nested containers are valid as set/append values (parsed via `parseInlineValue` → Typed parser). The emitter supports nested containers in patch values via `EmitPatch` delegating to `canonValue`. Deeply nested structures in a single patch value are supported to the degree the Typed parser supports them.

[^dupkey-loose]: Loose `writeMapLoose` sorts by canonical key deterministically; a map constructed with duplicate keys in memory would emit only what the `[]MapEntry` slice contains. The Loose parse path (Typed lexer + `parseMap`) applies last-wins with a warning. The lightweight `parseLooseValue` map parser has no duplicate detection.

---

## Target Summary (post W2/W3)

After W2 (canonical scalar consistency) and W3 (parser unification):

- All modes emit the same float form: shortest round-trip digits, always with a decimal point (D4).
- All modes normalise time to UTC with optional sub-second fractional part (D2).
- All modes emit `b64"<standard-base64>"` for bytes; parsers hard-error on invalid base64 (D6).
- All emitters use the stricter `isValidBareString` (ASCII-only) predicate (D8).
- NaN/Inf are a hard error on both emit and parse in Loose; valid in Typed only (D3).
- `\uXXXX` escapes round-trip in all modes.
- The Typed lexer and `scanRef` accept `^"..."` quoted refs (D7).
- `parseLooseValue` gains time, bytes, and quoted-ref branches (W3).

W6 (patch hardening) closes the remaining `OpDelta`-on-float canonical form gap.
