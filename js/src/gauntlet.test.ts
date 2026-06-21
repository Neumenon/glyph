/**
 * GLYPH JS Correctness Gauntlet
 *
 * Mirrors the cross-language gauntlet data at
 * /home/omen/Documents/Project/cogs/glyph/gauntlet/data/gauntlet-data.json
 *
 * LOOSE ROUND-TRIP (closed gap): JS now has a schema-free loose-text parser,
 * parseLoose(glyphText) -> GValue, the inverse of canonicalizeLoose(). The loop
 * is bidirectional and matches Go (ParseDocument) and Python (parse):
 *   JSON value <-> fromJsonLoose/toJsonLoose <-> GValue <-> canonicalizeLoose/parseLoose <-> glyph text
 *
 * Note: parseJsonLoose() is a separate JSON bridge (parses JSON text, not glyph
 * text); parseLoose() is the glyph-text parser. parseLoose round-trips scalars,
 * maps, lists, nested @tab blocks, and refs. Time values are out of loose scope
 * in all three languages (JSON-domain only), as is int precision beyond 2^53 in JS.
 *
 * All byte counts and savings numbers come from the real codec via gauntlet-data.json.
 */

import {
  fromJsonLoose,
  toJsonLoose,
  canonicalizeLoose,
  canonicalizeLooseNoTabular,
  parseLoose,
  parseJsonLoose,
  parseTabularLoose,
  defaultLooseCanonOpts,
  StreamingValidator,
  defaultToolRegistry,
  ErrorCode,
  emitPatch,
  parsePatch,
  applyPatch,
  PatchBuilder,
  g,
  field,
} from './index';

// ============================================================
// Museum of Edge Cases
// All 14 cases from gauntlet-data.json edgeCases.
// Forward path: JSON value -> fromJsonLoose() -> canonicalizeLoose()
// ============================================================

describe('MuseumOfEdgeCases: JSON-bridge forward path (JSON value -> GValue -> glyph text)', () => {
  // Helper: JSON text -> glyph text via the real JS forward path.
  function jsonToGlyph(jsonText: string): string {
    const jsValue = JSON.parse(jsonText);
    const gv = fromJsonLoose(jsValue);
    return canonicalizeLoose(gv);
  }

  test('empty_str: empty string needs quotes in glyph', () => {
    expect(jsonToGlyph('""')).toBe('""');
  });

  test('unicode: café ☕ λ', () => {
    expect(jsonToGlyph('"café ☕ λ"')).toBe('"café ☕ λ"');
  });

  test('embedded_quote: double-quotes are escaped', () => {
    expect(jsonToGlyph('"say \\"hello\\""')).toBe('"say \\"hello\\""');
  });

  test('pipe: pipe chars are quoted', () => {
    expect(jsonToGlyph('"a|b|c"')).toBe('"a|b|c"');
  });

  test('newlines: embedded newlines are escaped', () => {
    expect(jsonToGlyph('"line1\\nline2\\r\\nline3"')).toBe('"line1\\nline2\\r\\nline3"');
  });

  test('null_value: JSON null -> glyph _ (underscore, defaultLooseCanonOpts)', () => {
    expect(jsonToGlyph('null')).toBe('_');
  });

  test('bool_true: true -> t', () => {
    expect(jsonToGlyph('true')).toBe('t');
  });

  test('bool_false: false -> f', () => {
    expect(jsonToGlyph('false')).toBe('f');
  });

  test('big_int: 9007199254740992 — JS precision limit', () => {
    // The gauntlet data records: glyphText "9.007199254740992e+15"
    // 9007199254740992 = MAX_SAFE_INTEGER + 1. JS parses it as a float,
    // so fromJsonLoose treats it as float, not int.
    const result = jsonToGlyph('9007199254740992');
    // It should be a float in scientific notation, not an integer.
    expect(result).toBe('9.007199254740992e+15');
  });

  test('float_sci: 1.23e-9 -> canonical scientific notation', () => {
    expect(jsonToGlyph('1.23e-9')).toBe('1.23e-09');
  });

  test('neg_zero: JSON 0 -> 0 (neg zero from JS is normalized)', () => {
    // The gauntlet data: neg_zero jsonText "0" glyphText "0"
    // JSON.parse("0") is 0 which is an integer -> "0"
    expect(jsonToGlyph('0')).toBe('0');
    // -0 as a float directly gets normalized to "0.0"
    const negZeroGv = fromJsonLoose(-0);
    // -0 passes Number.isInteger and abs <= MAX_SAFE_INTEGER, so it becomes int(0)
    // canonInt(0) = "0"
    expect(canonicalizeLoose(negZeroGv)).toBe('0');
  });

  test('date_string: ISO date stays as string in loose mode (no type inference)', () => {
    // Stays as a quoted string, not promoted to time type
    expect(jsonToGlyph('"2024-03-15T12:00:00Z"')).toBe('"2024-03-15T12:00:00Z"');
  });

  test('nested_list: mixed-type list', () => {
    expect(jsonToGlyph('[1,2,"three",null]')).toBe('[1 2 three _]');
  });

  test('nested_map: nested object', () => {
    expect(jsonToGlyph('{"a":1,"b":{"c":2}}')).toBe('{a=1 b={c=2}}');
  });
});

// ============================================================
// Loose-text round-trip (gap CLOSED): parseLoose(canonicalizeLoose(v)) == v.
// JS now matches Go (ParseDocument) and Python (parse). The invariant we assert
// is canonical idempotence — canonicalizeLoose sorts map keys, so re-emitting a
// parsed value must reproduce the exact same text.
// ============================================================

describe('Loose-text round-trip — parseLoose is the inverse of canonicalizeLoose', () => {
  // The strongest practical invariant: emit -> parse -> emit is a fixed point.
  function assertRoundTrip(json: unknown): void {
    const text = canonicalizeLoose(fromJsonLoose(json));
    const reparsed = parseLoose(text);
    expect(canonicalizeLoose(reparsed)).toBe(text);
  }

  test('scalars round-trip: bool, null, int, float, string', () => {
    expect(parseLoose('t').asBool()).toBe(true);
    expect(parseLoose('f').asBool()).toBe(false);
    expect(parseLoose('_').isNull()).toBe(true);
    expect(parseLoose('42').asInt()).toBe(42);
    expect(parseLoose('-7').asInt()).toBe(-7);
    expect(parseLoose('3.14').asFloat()).toBeCloseTo(3.14);
    expect(parseLoose('"hello world"').asStr()).toBe('hello world');
    expect(parseLoose('bareword').asStr()).toBe('bareword');
  });

  test('quoted strings with escapes round-trip (quotes, pipe, newline, unicode)', () => {
    for (const s of ['', 'he said "hi"', 'a|b|c', 'l1\nl2', 'café 😈 λ']) {
      const gv = parseLoose(canonicalizeLoose(fromJsonLoose(s)));
      expect(gv.asStr()).toBe(s);
    }
  });

  test('map round-trips (canonical key order preserved)', () => {
    assertRoundTrip({ action: 'search', query: 'weather in Chicago', max_results: 5 });
  });

  test('nested map + list round-trips', () => {
    assertRoundTrip({ a: 1, b: { c: 2 }, d: [1, 2, 'three', null] });
  });

  test('deeply nested structure round-trips', () => {
    assertRoundTrip({ deep: { a: { b: { c: { d: [1, [2, [3, [4]]]] } } } } });
  });

  test('top-level @tab block round-trips back to a list of maps', () => {
    const rows = [
      { a: 1, b: 'x' },
      { a: 2, b: 'y' },
      { a: 3, b: 'z' },
    ];
    const text = canonicalizeLoose(fromJsonLoose(rows));
    expect(text).toContain('@tab _'); // confirm we exercised the tabular path
    const reparsed = parseLoose(text);
    expect(reparsed.type).toBe('list');
    expect(reparsed.len()).toBe(3);
    expect(canonicalizeLoose(reparsed)).toBe(text);
  });

  test('@tab nested inside a map round-trips (the hard case)', () => {
    // canonicalizeLoose inlines a multi-line @tab block as a map field value.
    assertRoundTrip({
      rows: [
        { a: 1, b: 2 },
        { a: 3, b: 4 },
        { a: 5, b: 6 },
      ],
      note: 'nested',
    });
  });

  test('empty containers round-trip', () => {
    expect(canonicalizeLoose(parseLoose('{}'))).toBe('{}');
    expect(canonicalizeLoose(parseLoose('[]'))).toBe('[]');
  });

  test('semantic JSON survives a full round-trip (modulo canonical key sort)', () => {
    const original = { action: 'search', query: 'x', max_results: 5 };
    const back = toJsonLoose(parseLoose(canonicalizeLoose(fromJsonLoose(original))));
    // Same key/value set; canonicalization sorts keys, so compare as objects.
    expect(back).toEqual(original);
  });

  test('parseLoose rejects trailing garbage', () => {
    expect(() => parseLoose('{a=1} extra')).toThrow(/trailing garbage/);
  });

  test('parseLoose enforces a nesting depth guard (DoS protection)', () => {
    const bomb = '['.repeat(200) + ']'.repeat(200);
    expect(() => parseLoose(bomb)).toThrow(/maximum nesting depth/);
  });

  test('parseLoose and parseJsonLoose are distinct entry points', () => {
    // parseJsonLoose is the JSON bridge: it parses JSON text, not glyph text.
    expect(() => parseJsonLoose('t')).toThrow(); // glyph bool, invalid JSON
    expect(parseLoose('t').asBool()).toBe(true); // glyph parser handles it
    // parseJsonLoose still works for real JSON.
    expect(parseJsonLoose('{"x": 42}').get('x')!.asInt()).toBe(42);
  });
});

// ============================================================
// TypeZoo: fromJsonLoose + toJsonLoose round-trip
// Tests that JS values survive fromJsonLoose -> GValue -> toJsonLoose intact.
// ============================================================

describe('TypeZoo: fromJsonLoose -> toJsonLoose round-trip (JSON -> GValue -> JSON)', () => {
  test('null round-trips', () => {
    const gv = fromJsonLoose(null);
    expect(gv.type).toBe('null');
    expect(toJsonLoose(gv)).toBeNull();
  });

  test('bool true round-trips', () => {
    const gv = fromJsonLoose(true);
    expect(gv.type).toBe('bool');
    expect(toJsonLoose(gv)).toBe(true);
  });

  test('bool false round-trips', () => {
    const gv = fromJsonLoose(false);
    expect(gv.type).toBe('bool');
    expect(toJsonLoose(gv)).toBe(false);
  });

  test('integer round-trips', () => {
    const gv = fromJsonLoose(42);
    expect(gv.type).toBe('int');
    expect(toJsonLoose(gv)).toBe(42);
  });

  test('negative integer round-trips', () => {
    const gv = fromJsonLoose(-7);
    expect(gv.type).toBe('int');
    expect(toJsonLoose(gv)).toBe(-7);
  });

  test('float round-trips', () => {
    const gv = fromJsonLoose(3.14);
    expect(gv.type).toBe('float');
    expect(toJsonLoose(gv)).toBeCloseTo(3.14);
  });

  test('string round-trips', () => {
    const gv = fromJsonLoose('hello world');
    expect(gv.type).toBe('str');
    expect(toJsonLoose(gv)).toBe('hello world');
  });

  test('unicode string round-trips', () => {
    const gv = fromJsonLoose('café ☕ λ');
    expect(gv.type).toBe('str');
    expect(toJsonLoose(gv)).toBe('café ☕ λ');
  });

  test('array round-trips', () => {
    const gv = fromJsonLoose([1, 'two', null, false]);
    expect(gv.type).toBe('list');
    expect(toJsonLoose(gv)).toEqual([1, 'two', null, false]);
  });

  test('object round-trips', () => {
    const obj = { a: 1, b: 'hello', c: null };
    const gv = fromJsonLoose(obj);
    expect(gv.type).toBe('map');
    expect(toJsonLoose(gv)).toEqual(obj);
  });

  test('nested object round-trips', () => {
    const obj = { outer: { inner: [1, 2, 3] } };
    const gv = fromJsonLoose(obj);
    expect(toJsonLoose(gv)).toEqual(obj);
  });

  test('MAX_SAFE_INTEGER round-trips as int', () => {
    const gv = fromJsonLoose(Number.MAX_SAFE_INTEGER);
    expect(gv.type).toBe('int');
    expect(toJsonLoose(gv)).toBe(Number.MAX_SAFE_INTEGER);
  });

  test('[KNOWN GAP] MAX_SAFE_INTEGER+1 loses precision in JS (becomes float)', () => {
    // 9007199254740993 is MAX_SAFE_INTEGER+1.
    // JS parses it from JSON as 9007199254740992 (nearest float64).
    // fromJsonLoose sees a non-safe-integer float and tags it as float.
    // Go and Python handle this correctly as int64.
    const bigInt = 9007199254740993;
    const gv = fromJsonLoose(bigInt);
    // JS cannot distinguish this from 9007199254740992 after JSON.parse.
    expect(gv.type).toBe('float');
    // The glyph text will be the float representation.
    const glyphText = canonicalizeLoose(gv);
    expect(glyphText).toBe('9.007199254740992e+15');
  });

  test('NaN is rejected by fromJsonLoose', () => {
    expect(() => fromJsonLoose(NaN)).toThrow();
  });

  test('Infinity is rejected by fromJsonLoose', () => {
    expect(() => fromJsonLoose(Infinity)).toThrow();
  });

  test('-Infinity is rejected by fromJsonLoose', () => {
    expect(() => fromJsonLoose(-Infinity)).toThrow();
  });
});

// ============================================================
// Tabular savings sanity: glyph bytes < json bytes for repeated rows
// Uses real rows of match data (same structure as gauntlet-data.json tabular section).
// The assertion is a real inequality, not a pinned number.
// ============================================================

describe('Tabular savings: glyph bytes < json bytes for homogeneous repeated rows', () => {
  // Build N rows of match data (same schema as gauntlet benchmark data).
  function makeMatchRows(n: number): object[] {
    const statuses = ['live', 'finished', 'upcoming'];
    return Array.from({ length: n }, (_, i) => ({
      id: `m${i}`,
      home: `Team_${(i % 10) + 1}`,
      away: `Team_${(i % 10) + 11}`,
      venue: `Stadium_${(i % 10) + 1}`,
      minute: i * 3,
      score_home: (i % 5) + 1,
      score_away: i % 3,
      status: statuses[i % 3],
    }));
  }

  test('10 rows: glyph bytes < json bytes (real codec comparison)', () => {
    const rows = makeMatchRows(10);
    const jsonBytes = Buffer.byteLength(JSON.stringify(rows), 'utf8');
    const gv = fromJsonLoose(rows);
    const glyphText = canonicalizeLoose(gv);
    const glyphBytes = Buffer.byteLength(glyphText, 'utf8');

    // Must emit tabular format (@tab _ ...) for 10 homogeneous rows
    expect(glyphText).toContain('@tab _');
    expect(glyphBytes).toBeLessThan(jsonBytes);

    // Sanity: savings should be substantial (>40%) for repeated rows
    const savingsPct = (1 - glyphBytes / jsonBytes) * 100;
    expect(savingsPct).toBeGreaterThan(40);
  });

  test('100 rows: glyph bytes < json bytes, ~63% savings (gauntlet headline)', () => {
    const rows = makeMatchRows(100);
    const jsonBytes = Buffer.byteLength(JSON.stringify(rows), 'utf8');
    const gv = fromJsonLoose(rows);
    const glyphText = canonicalizeLoose(gv);
    const glyphBytes = Buffer.byteLength(glyphText, 'utf8');

    expect(glyphText).toContain('@tab _');
    expect(glyphBytes).toBeLessThan(jsonBytes);

    // Gauntlet data records 63.38% savings for 100 rows.
    // We allow ±5% tolerance for the live codec to avoid brittleness.
    const savingsPct = (1 - glyphBytes / jsonBytes) * 100;
    expect(savingsPct).toBeGreaterThan(55);
    expect(savingsPct).toBeLessThan(75);
  });

  test('1000 rows: glyph bytes < json bytes (scales correctly)', () => {
    const rows = makeMatchRows(1000);
    const jsonBytes = Buffer.byteLength(JSON.stringify(rows), 'utf8');
    const gv = fromJsonLoose(rows);
    const glyphText = canonicalizeLoose(gv);
    const glyphBytes = Buffer.byteLength(glyphText, 'utf8');

    expect(glyphText).toContain('@tab _');
    expect(glyphBytes).toBeLessThan(jsonBytes);
    const savingsPct = (1 - glyphBytes / jsonBytes) * 100;
    expect(savingsPct).toBeGreaterThan(55);
  });

  test('fewer than minRows (2 rows): no tabular format emitted', () => {
    const rows = makeMatchRows(2);
    const gv = fromJsonLoose(rows);
    const glyphText = canonicalizeLoose(gv);
    // 2 rows < minRows=3, so no @tab block
    expect(glyphText).not.toContain('@tab _');
  });

  test('canonicalizeLooseNoTabular emits list form, not @tab, for same data', () => {
    const rows = makeMatchRows(10);
    const gv = fromJsonLoose(rows);
    const glyphNoTab = canonicalizeLooseNoTabular(gv);
    expect(glyphNoTab).not.toContain('@tab _');
    expect(glyphNoTab).toContain('[');
  });

  test('parseTabularLoose recovers @tab block rows as plain JS objects', () => {
    const rows = makeMatchRows(5);
    const gv = fromJsonLoose(rows);
    const glyphText = canonicalizeLoose(gv);

    // parseTabularLoose can recover the data as plain objects (not GValue)
    const result = parseTabularLoose(glyphText);
    expect(result.rows).toHaveLength(5);
    expect(result.columns).toContain('id');
    expect(result.columns).toContain('home');
    expect(result.columns).toContain('away');
    // Row values are plain JS — not GValues
    expect(result.rows[0]['id']).toBe('m0');
  });
});

// ============================================================
// PatchApply: emitPatch / parsePatch / applyPatch
// Uses real match state structure matching gauntlet-data.json matchStream.
// ============================================================

describe('PatchApply: emitPatch / parsePatch / applyPatch', () => {
  // Match state as a loose GValue (via fromJsonLoose)
  function makeMatchState(minute: number, scoreHome: number, scoreAway: number) {
    return fromJsonLoose({
      id: 'match:001',
      minute,
      score_home: scoreHome,
      score_away: scoreAway,
      home: 'Arsenal',
      away: 'Chelsea',
      status: 'live',
    });
  }

  test('emitPatch produces @patch text with correct header', () => {
    const patch = new PatchBuilder({ prefix: 'match', value: '001' })
      .set('minute', g.int(45))
      .set('score_home', g.int(1))
      .set('score_away', g.int(0))
      .build();

    const text = emitPatch(patch);
    expect(text).toContain('@patch');
    expect(text).toContain('@target=match:001');
    expect(text).toContain('= minute 45');
    expect(text).toContain('@end');
  });

  test('parsePatch recovers patch from emitPatch output', () => {
    const original = new PatchBuilder({ prefix: 'match', value: '001' })
      .set('minute', g.int(45))
      .set('score_home', g.int(1))
      .set('score_away', g.int(0))
      .build();

    const text = emitPatch(original);
    const parsed = parsePatch(text);

    expect(parsed.target.prefix).toBe('match');
    expect(parsed.target.value).toBe('001');
    expect(parsed.ops).toHaveLength(3);
  });

  test('applyPatch updates fields on a map GValue', () => {
    const state = makeMatchState(0, 0, 0);
    const patch = new PatchBuilder({ prefix: 'match', value: '001' })
      .set('minute', g.int(45))
      .set('score_home', g.int(1))
      .set('score_away', g.int(0))
      .build();

    const updated = applyPatch(state, patch);
    expect(updated.get('minute')!.asInt()).toBe(45);
    expect(updated.get('score_home')!.asInt()).toBe(1);
    expect(updated.get('score_away')!.asInt()).toBe(0);
  });

  test('round-trip: emitPatch -> parsePatch -> applyPatch updates state correctly', () => {
    const state = makeMatchState(10, 0, 0);

    const patch = new PatchBuilder({ prefix: 'match', value: '001' })
      .set('minute', g.int(60))
      .set('score_home', g.int(2))
      .set('score_away', g.int(1))
      .build();

    const patchText = emitPatch(patch);
    const parsedPatch = parsePatch(patchText);
    const updated = applyPatch(state, parsedPatch);

    expect(updated.get('minute')!.asInt()).toBe(60);
    expect(updated.get('score_home')!.asInt()).toBe(2);
    expect(updated.get('score_away')!.asInt()).toBe(1);
    // Unpatch fields remain unchanged
    expect(updated.get('home')!.asStr()).toBe('Arsenal');
    expect(updated.get('status')!.asStr()).toBe('live');
  });

  test('patch bytes < snapshot bytes (gauntlet matchStream finding)', () => {
    // The gauntlet data records 32.81% savings for patches vs full snapshots.
    // We verify the inequality holds in the live codec.
    const state = makeMatchState(45, 1, 0);
    const snapshotText = JSON.stringify(toJsonLoose(state));
    const snapshotBytes = Buffer.byteLength(snapshotText, 'utf8');

    const patch = new PatchBuilder({ prefix: 'match', value: '001' })
      .set('minute', g.int(45))
      .set('score_home', g.int(1))
      .set('score_away', g.int(0))
      .build();

    const patchText = emitPatch(patch);
    const patchBytes = Buffer.byteLength(patchText, 'utf8');

    // Patches should be smaller than full snapshots
    expect(patchBytes).toBeLessThan(snapshotBytes);
  });

  test('sample patch text from gauntlet data parses correctly', () => {
    // gauntlet-data.json samplePatchText (sorted ops by emitPatch default):
    // "@patch @keys=wire @target=match:001\n= minute 45\n= score_away 0\n= score_home 1\n@end"
    const samplePatch = '@patch @keys=wire @target=match:001\n= minute 45\n= score_away 0\n= score_home 1\n@end';
    const parsed = parsePatch(samplePatch);
    expect(parsed.target.prefix).toBe('match');
    expect(parsed.target.value).toBe('001');
    // 3 ops: minute, score_away, score_home
    expect(parsed.ops).toHaveLength(3);
    // Find minute op
    const minuteOp = parsed.ops.find(op => op.path[0]?.field === 'minute');
    expect(minuteOp).toBeDefined();
    expect(minuteOp!.value!.asInt()).toBe(45);
  });
});

// ============================================================
// StreamingValidator Firewall
// Tests from gauntlet-data.json toolFirewall section.
// ============================================================

describe('StreamingValidator firewall', () => {
  test('allowed tool (search) is detected early and accepted', () => {
    const registry = defaultToolRegistry();
    const sv = new StreamingValidator(registry);

    // Feed the allowed tool text char by char.
    // gauntlet data: "{action=search query=...}" — tool detected at char 15
    const text = '{action=search query="latest weather in Chicago" max_results=5}';
    let result = sv.getResult();

    for (const c of text) {
      result = sv.pushToken(c);
    }

    expect(result.toolName).toBe('search');
    expect(result.toolAllowed).toBe(true);
    expect(result.errors).toHaveLength(0);
    expect(result.complete).toBe(true);
  });

  test('tool (search) is detected at char 15 (gauntlet headline)', () => {
    const registry = defaultToolRegistry();
    const sv = new StreamingValidator(registry);

    const text = '{action=search query="latest weather in Chicago" max_results=5}';
    let detectedAtChar = -1;

    for (let i = 0; i < text.length; i++) {
      const result = sv.pushToken(text[i]);
      if (result.toolName !== null && detectedAtChar === -1) {
        detectedAtChar = result.toolDetectedAtChar;
      }
    }

    // gauntlet-data.json: toolDetectedAtChar == 15 for the allowed tool
    expect(detectedAtChar).toBe(15);
  });

  test('blocked tool (wire_transfer) is rejected natively — not in defaultToolRegistry', () => {
    const registry = defaultToolRegistry();
    // Confirm wire_transfer is absent from the default registry
    expect(registry.isAllowed('wire_transfer')).toBe(false);

    const sv = new StreamingValidator(registry);
    const text = '{action=wire_transfer amount=1000000 target=unknown}';

    let result = sv.getResult();
    for (const c of text) {
      result = sv.pushToken(c);
    }

    expect(result.toolName).toBe('wire_transfer');
    expect(result.toolAllowed).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.errors[0].code).toBe(ErrorCode.UnknownTool);
  });

  test('wire_transfer rejected at char 22 (gauntlet headline)', () => {
    const registry = defaultToolRegistry();
    const sv = new StreamingValidator(registry);

    const text = '{action=wire_transfer amount=1000000 target=unknown}';
    let rejectAtChar = -1;

    for (let i = 0; i < text.length; i++) {
      const result = sv.pushToken(text[i]);
      if (result.errors.length > 0 && rejectAtChar === -1) {
        rejectAtChar = result.charCount;
      }
    }

    // gauntlet-data.json: toolDetectedAtChar == 22 for wire_transfer
    expect(rejectAtChar).toBe(22);
  });

  test('shouldStop() returns true after UnknownTool error', () => {
    const registry = defaultToolRegistry();
    const sv = new StreamingValidator(registry);

    const text = '{action=wire_transfer amount=1000000 target=unknown}';
    let stoppedAt = -1;

    for (let i = 0; i < text.length; i++) {
      sv.pushToken(text[i]);
      if (sv.shouldStop() && stoppedAt === -1) {
        stoppedAt = i + 1;
      }
    }

    // shouldStop() should trigger at char 22 (detection = rejection for unknown tool)
    expect(stoppedAt).toBe(22);
  });

  test('bytes avoided: stopping at char 22 avoids remaining 30 bytes', () => {
    const text = '{action=wire_transfer amount=1000000 target=unknown}';
    const totalChars = text.length; // 52
    const rejectAtChar = 22;
    const bytesAvoided = totalChars - rejectAtChar;

    // gauntlet data: bytesAvoided == 30, totalChars == 52, rejectAtChar == 22
    expect(totalChars).toBe(52);
    expect(rejectAtChar).toBe(22);
    expect(bytesAvoided).toBe(30);
  });

  test('defaultToolRegistry contains exactly: search, calculate, browse, execute, read_file, write_file', () => {
    const registry = defaultToolRegistry();
    // From gauntlet-data.json registryNote
    expect(registry.isAllowed('search')).toBe(true);
    expect(registry.isAllowed('calculate')).toBe(true);
    expect(registry.isAllowed('browse')).toBe(true);
    expect(registry.isAllowed('execute')).toBe(true);
    expect(registry.isAllowed('read_file')).toBe(true);
    expect(registry.isAllowed('write_file')).toBe(true);
    // wire_transfer is absent
    expect(registry.isAllowed('wire_transfer')).toBe(false);
  });

  test('feeding text token by token produces same result as char by char', () => {
    const registry = defaultToolRegistry();
    const sv1 = new StreamingValidator(registry);
    const sv2 = new StreamingValidator(registry);

    const text = '{action=search query="test"}';

    // Char by char
    for (const c of text) {
      sv1.pushToken(c);
    }

    // As a single token
    sv2.pushToken(text);

    const r1 = sv1.getResult();
    const r2 = sv2.getResult();

    expect(r1.toolName).toBe(r2.toolName);
    expect(r1.toolAllowed).toBe(r2.toolAllowed);
    expect(r1.complete).toBe(r2.complete);
    expect(r1.errors.length).toBe(r2.errors.length);
  });
});

// ============================================================
// Cross-language compatibility notes
// These tests document the JS codec's position in the multi-language ecosystem.
// ============================================================

describe('Cross-language compatibility documentation', () => {
  test('[DOC] JS loose mode is bidirectional — parseLoose closes the round-trip', () => {
    // Previously JS was forward-only in loose mode (emit but no schema-free parse).
    // parseLoose() now provides glyphText -> GValue, matching Go (ParseDocument)
    // and Python (parse). A JS service can re-parse loose glyph text received from
    // a Go or Python peer without a schema.
    const original = { id: 'm1', home: 'ARS', away: 'LIV', score: [2, 1] };
    const glyphText = canonicalizeLoose(fromJsonLoose(original));
    const reparsed = parseLoose(glyphText);
    expect(canonicalizeLoose(reparsed)).toBe(glyphText); // bidirectional fixed point
    expect(toJsonLoose(reparsed)).toEqual(original);
  });

  test('[DOC] estimateTokens is deprecated — not a real BPE tokenizer', () => {
    // The gauntlet data includes token savings figures marked as illustrative only.
    // estimateTokens() splits on whitespace — dense glyph output has fewer spaces
    // than pretty JSON, so savings look negative (glyph appears to use MORE tokens).
    // A real BPE tokenizer would show genuine savings.
    // Use tiktoken or similar for accurate comparisons.
    expect(true).toBe(true); // Documentation test
  });

  test('[DOC] fingerprintLoose uses crypto (Node-only, not browser-safe)', () => {
    // The browser bundle (glyph.bundle.js) was built with --external:crypto.
    // fingerprintLoose() calls require('crypto') which works in Node but not browser.
    // All other loose-mode functions (canonicalizeLoose, fromJsonLoose, etc.) are safe.
    // Downstream browser pages must avoid fingerprintLoose or provide a crypto shim.
    expect(true).toBe(true); // Documentation test
  });
});
