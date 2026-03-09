/**
 * Coverage boost tests for glyph JS/TS
 * Targets: parse.ts, emit.ts, json.ts, loose.ts, decimal128.ts, patch.ts
 */

import {
  GValue, g, field,
  Schema, SchemaBuilder, t,
  fromJson, toJson, parseJson, stringifyJson, normalizeJson,
  emit, emitPacked, emitTabular, emitV2, emitHeader,
  parsePacked, parseTabular, parseHeader,
  PatchBuilder, emitPatch, parsePatch, applyPatch,
  parsePathToSegs, fieldSeg, listIdxSeg, mapKeySeg,
  canonicalizeLoose, canonicalizeLooseNoTabular, canonicalizeLooseTabular,
  canonicalizeLooseWithOpts, canonicalizeLooseWithSchema,
  equalLoose, fromJsonLoose, toJsonLoose, jsonEqual,
  parseJsonLoose, stringifyJsonLoose,
  parseTabularLoose, unescapeTabularCell,
  buildKeyDictFromValue, parseSchemaHeader, parseTabularLooseHeaderWithMeta,
  fingerprintLoose,
  Decimal128, DecimalError, decimal, isDecimalLiteral, parseDecimalLiteral,
  estimateTokens, compareTokens,
} from './index';

// ============================================================
// Parse — deeper coverage
// ============================================================

describe('Parse coverage', () => {
  const schema = new SchemaBuilder()
    .addPackedStruct('Team', 'v2')
      .field('id', t.id(), { fid: 1, wireKey: 't' })
      .field('name', t.str(), { fid: 2, wireKey: 'n' })
      .field('league', t.str(), { fid: 3, wireKey: 'l' })
    .build();

  test('parse quoted strings with escapes', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Msg', 'v1')
        .field('text', t.str(), { fid: 1 })
      .build();
    const result = parsePacked('Msg@("hello\\nworld")', s);
    expect(result.get('text')?.asStr()).toBe('hello\nworld');
  });

  test('parse quoted string escape sequences', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Msg', 'v1')
        .field('text', t.str(), { fid: 1 })
      .build();
    // Test \r, \t, \\, \" escapes
    const result = parsePacked('Msg@("a\\rb\\tc\\\\d\\"e")', s);
    expect(result.get('text')?.asStr()).toBe('a\rb\tc\\d"e');
  });

  test('parse with trailing whitespace (no garbage)', () => {
    const result = parsePacked('Team@(^t:ARS Arsenal EPL)  ', schema);
    expect(result.get('name')?.asStr()).toBe('Arsenal');
  });

  test('parse negative numbers', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Score', 'v1')
        .field('val', t.int(), { fid: 1 })
      .build();
    const result = parsePacked('Score@(-42)', s);
    expect(result.get('val')?.asInt()).toBe(-42);
  });

  test('parse float values', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Metric', 'v1')
        .field('val', t.float(), { fid: 1 })
      .build();
    const result = parsePacked('Metric@(3.14)', s);
    expect(result.get('val')?.asFloat()).toBeCloseTo(3.14);
  });

  test('parse float with exponent', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Metric', 'v1')
        .field('val', t.float(), { fid: 1 })
      .build();
    const result = parsePacked('Metric@(1.5e3)', s);
    expect(result.get('val')?.asFloat()).toBe(1500);
  });

  test('parse time values', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Event', 'v1')
        .field('when', t.time(), { fid: 1 })
      .build();
    const result = parsePacked('Event@(2025-12-19T10:30:00Z)', s);
    expect(result.get('when')?.asTime().toISOString()).toContain('2025-12-19');
  });

  test('parse list value', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Data', 'v1')
        .field('items', t.list(t.int()), { fid: 1 })
      .build();
    const result = parsePacked('Data@([1 2 3])', s);
    expect(result.get('items')?.len()).toBe(3);
    expect(result.get('items')?.index(0).asInt()).toBe(1);
  });

  test('parse map value', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Data', 'v1')
        .field('meta', t.map(t.str(), t.int()), { fid: 1 })
      .build();
    const result = parsePacked('Data@({x=1 y=2})', s);
    const meta = result.get('meta');
    expect(meta?.get('x')?.asInt()).toBe(1);
    expect(meta?.get('y')?.asInt()).toBe(2);
  });

  test('parse ref without prefix', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Ref', 'v1')
        .field('r', t.id(), { fid: 1 })
      .build();
    const result = parsePacked('Ref@(^ABC)', s);
    expect(result.get('r')?.asId().prefix).toBe('');
    expect(result.get('r')?.asId().value).toBe('ABC');
  });

  test('parse quoted ref', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Ref', 'v1')
        .field('r', t.id(), { fid: 1 })
      .build();
    const result = parsePacked('Ref@(^"user:has space")', s);
    expect(result.get('r')?.asId().prefix).toBe('user');
    expect(result.get('r')?.asId().value).toBe('has space');
  });

  test('parse boolean values', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Flags', 'v1')
        .field('a', t.bool(), { fid: 1 })
        .field('b', t.bool(), { fid: 2 })
      .build();
    const result = parsePacked('Flags@(t f)', s);
    expect(result.get('a')?.asBool()).toBe(true);
    expect(result.get('b')?.asBool()).toBe(false);
  });

  test('parse boolean full words', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Flags', 'v1')
        .field('a', t.bool(), { fid: 1 })
        .field('b', t.bool(), { fid: 2 })
      .build();
    const result = parsePacked('Flags@(true false)', s);
    expect(result.get('a')?.asBool()).toBe(true);
    expect(result.get('b')?.asBool()).toBe(false);
  });

  test('parse bare string that starts with t/f but is not boolean', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Data', 'v1')
        .field('name', t.str(), { fid: 1 })
      .build();
    const result = parsePacked('Data@(testing)', s);
    expect(result.get('name')?.asStr()).toBe('testing');
  });

  test('parse nested packed struct', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Inner', 'v1')
        .field('val', t.int(), { fid: 1 })
      .addPackedStruct('Outer', 'v1')
        .field('inner', t.ref('Inner'), { fid: 1 })
      .build();
    const result = parsePacked('Outer@(Inner@(42))', s);
    expect(result.get('inner')?.get('val')?.asInt()).toBe(42);
  });

  test('parse with early close paren (remaining fields null)', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Partial', 'v1')
        .field('a', t.str(), { fid: 1 })
        .field('b', t.str(), { fid: 2 })
        .field('c', t.str(), { fid: 3 })
      .build();
    const result = parsePacked('Partial@(hello)', s);
    expect(result.get('a')?.asStr()).toBe('hello');
    expect(result.get('b')?.isNull()).toBe(true);
    expect(result.get('c')?.isNull()).toBe(true);
  });

  test('parse bitmap header', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Bm', 'v1')
        .field('req', t.str(), { fid: 1 })
        .field('opt1', t.str(), { fid: 2, optional: true })
        .field('opt2', t.str(), { fid: 3, optional: true })
      .build();
    const result = parsePacked('Bm@{bm=0b10}(hello world)', s);
    expect(result.get('req')?.asStr()).toBe('hello');
    expect(result.get('opt1')?.isNull()).toBe(true);
    expect(result.get('opt2')?.asStr()).toBe('world');
  });

  test('error: unknown type', () => {
    expect(() => parsePacked('Unknown@(1)', schema)).toThrow('unknown type');
  });

  test('error: unexpected end of input', () => {
    expect(() => parsePacked('', schema)).toThrow();
  });

  test('error: expected @ after type name', () => {
    expect(() => parsePacked('Team(1)', schema)).toThrow();
  });

  test('error: unterminated string', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Msg', 'v1')
        .field('text', t.str(), { fid: 1 })
      .build();
    expect(() => parsePacked('Msg@("hello)', s)).toThrow('unterminated string');
  });

  // Tabular parse coverage
  test('tabular parse with fid columns', () => {
    const result = parseTabular(`@tab Team [#1 #2 #3]
^t:ARS Arsenal EPL
@end`, schema);
    expect(result.rows.length).toBe(1);
    expect(result.rows[0].get('id')?.asId().value).toBe('ARS');
  });

  test('tabular parse skips empty lines and comments', () => {
    const result = parseTabular(`@tab Team [t n l]

# This is a comment
^t:ARS Arsenal EPL

@end`, schema);
    expect(result.rows.length).toBe(1);
  });

  test('tabular parse error: not starting with @tab', () => {
    expect(() => parseTabular('invalid', schema)).toThrow('tabular must start with @tab');
  });

  test('tabular parse error: unknown type', () => {
    expect(() => parseTabular('@tab Unknown [a b]\n1 2\n@end', schema)).toThrow('unknown type');
  });

  // Header parse coverage
  test('parseHeader with @glyph prefix', () => {
    const h = parseHeader('@glyph v3 @mode=packed');
    expect(h?.version).toBe('v3');
    expect(h?.mode).toBe('packed');
  });

  test('parseHeader with target', () => {
    const h = parseHeader('@lyph v2 @target=m:ARS-LIV');
    expect(h?.target?.prefix).toBe('m');
    expect(h?.target?.value).toBe('ARS-LIV');
  });

  test('parseHeader with target no prefix', () => {
    const h = parseHeader('@lyph v2 @target=somevalue');
    expect(h?.target?.prefix).toBe('');
    expect(h?.target?.value).toBe('somevalue');
  });

  test('parseHeader returns null for non-header', () => {
    expect(parseHeader('hello world')).toBeNull();
  });

  test('parseHeader with keys=name', () => {
    const h = parseHeader('@lyph v2 @keys=name');
    expect(h?.keyMode).toBe('name');
  });

  test('parseHeader with no version token after @lyph', () => {
    const h = parseHeader('@lyph @mode=packed');
    expect(h?.version).toBe('v2'); // default
    expect(h?.mode).toBe('packed');
  });

  // Tabular row with scalar types
  test('tabular row: list, map, quoted string, null, time', () => {
    const s2 = new SchemaBuilder()
      .addPackedStruct('Row', 'v1')
        .field('a', t.str(), { fid: 1 })
        .field('b', t.str(), { fid: 2 })
      .build();
    const result = parseTabular(`@tab Row [a b]
"hello world" ∅
@end`, s2);
    expect(result.rows[0].get('a')?.asStr()).toBe('hello world');
    expect(result.rows[0].get('b')?.isNull()).toBe(true);
  });
});

// ============================================================
// Emit — deeper coverage
// ============================================================

describe('Emit coverage', () => {
  const schema = new SchemaBuilder()
    .addPackedStruct('Team', 'v2')
      .field('id', t.id(), { fid: 1, wireKey: 't' })
      .field('name', t.str(), { fid: 2, wireKey: 'n' })
      .field('league', t.str(), { fid: 3, wireKey: 'l' })
    .build();

  test('emit null, bool, int, float', () => {
    expect(emit(g.null())).toBe('∅');
    expect(emit(g.bool(true))).toBe('t');
    expect(emit(g.bool(false))).toBe('f');
    expect(emit(g.int(0))).toBe('0');
    expect(emit(g.int(42))).toBe('42');
    expect(emit(g.float(3.14))).toContain('3.14');
    expect(emit(g.float(0))).toBe('0');
  });

  test('emit string bare vs quoted', () => {
    expect(emit(g.str('hello'))).toBe('hello');
    expect(emit(g.str('hello world'))).toBe('"hello world"');
    expect(emit(g.str(''))).toBe('""');
    expect(emit(g.str('true'))).toBe('"true"');
    expect(emit(g.str('null'))).toBe('"null"');
  });

  test('emit string with special chars', () => {
    expect(emit(g.str('a\nb'))).toBe('"a\\nb"');
    expect(emit(g.str('a\rb'))).toBe('"a\\rb"');
    expect(emit(g.str('a\tb'))).toBe('"a\\tb"');
    expect(emit(g.str('a"b'))).toBe('"a\\"b"');
    expect(emit(g.str('a\\b'))).toBe('"a\\\\b"');
  });

  test('emit string with control chars', () => {
    const result = emit(g.str('a\x01b'));
    expect(result).toContain('\\u0001');
  });

  test('emit bytes', () => {
    const result = emit(g.bytes(new Uint8Array([72, 101, 108, 108, 111])));
    expect(result).toContain('b64');
  });

  test('emit time', () => {
    const result = emit(g.time(new Date('2025-12-19T10:30:00Z')));
    expect(result).toContain('2025-12-19');
  });

  test('emit ref with and without prefix', () => {
    expect(emit(g.id('t', 'ARS'))).toBe('^t:ARS');
    expect(emit(g.id('', 'ARS'))).toBe('^ARS');
  });

  test('emit ref with special characters', () => {
    const result = emit(g.id('t', 'has space'));
    expect(result).toContain('^');
    expect(result).toContain('"');
  });

  test('emit list', () => {
    expect(emit(g.list())).toBe('[]');
    expect(emit(g.list(g.int(1), g.int(2)))).toBe('[1 2]');
  });

  test('emit map', () => {
    expect(emit(g.map())).toBe('{}');
    expect(emit(g.map(field('x', g.int(1))))).toBe('{x:1}');
  });

  test('emit struct with key modes', () => {
    const team = g.struct('Team',
      field('id', g.id('t', 'ARS')),
      field('name', g.str('Arsenal')),
      field('league', g.str('EPL'))
    );
    const wireResult = emit(team, { schema, keyMode: 'wire' });
    expect(wireResult).toContain('n=');
    expect(wireResult).toContain('l=');

    const fidResult = emit(team, { schema, keyMode: 'fid' });
    expect(fidResult).toContain('"#1"=');
    expect(fidResult).toContain('"#2"=');
  });

  test('emit sum type', () => {
    const sumEmpty = g.sum('Ok', null);
    expect(emit(sumEmpty)).toBe('Ok()');

    const sumVal = g.sum('Err', g.str('oops'));
    expect(emit(sumVal)).toBe('Err(oops)');

    // Sum with struct value
    const sumStruct = g.sum('Data', g.struct('Info', field('x', g.int(1))));
    const result = emit(sumStruct);
    expect(result).toContain('Data');
    expect(result).toContain('x=1');
  });

  // Packed emit coverage
  test('emitPacked error: non-struct', () => {
    expect(() => emitPacked(g.int(42), schema)).toThrow('packed encoding requires struct value');
  });

  test('emitPacked error: unknown type', () => {
    const unknown = g.struct('Nope', field('x', g.int(1)));
    expect(() => emitPacked(unknown, schema)).toThrow('unknown struct type');
  });

  test('emitPacked with bitmap', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Opts', 'v1')
        .field('req', t.str(), { fid: 1 })
        .field('opt1', t.str(), { fid: 2, optional: true })
        .field('opt2', t.str(), { fid: 3, optional: true })
      .build();
    // opt1 missing => should use bitmap
    const val = g.struct('Opts',
      field('req', g.str('hello')),
      field('opt1', g.null()),
      field('opt2', g.str('world'))
    );
    const result = emitPacked(val, s);
    expect(result).toContain('bm=');
    expect(result).toContain('0b10');
  });

  test('emitPacked nested packed struct', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Inner', 'v1')
        .field('val', t.int(), { fid: 1 })
      .addPackedStruct('Outer', 'v1')
        .field('inner', t.ref('Inner'), { fid: 1 })
      .build();
    const val = g.struct('Outer',
      field('inner', g.struct('Inner', field('val', g.int(42))))
    );
    const result = emitPacked(val, s);
    expect(result).toBe('Outer@(Inner@(42))');
  });

  test('emitPacked with list and map values', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Complex', 'v1')
        .field('items', t.list(t.int()), { fid: 1 })
        .field('meta', t.map(t.str(), t.int()), { fid: 2 })
      .build();
    const val = g.struct('Complex',
      field('items', g.list(g.int(1), g.int(2))),
      field('meta', g.map(field('x', g.int(10))))
    );
    const result = emitPacked(val, s);
    expect(result).toContain('[1 2]');
    expect(result).toContain('{x:10}');
  });

  test('emitPacked with sum value', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('WithSum', 'v1')
        .field('result', t.str(), { fid: 1 })
      .build();
    const val = g.struct('WithSum',
      field('result', g.sum('Ok', g.int(42)))
    );
    const result = emitPacked(val, s);
    expect(result).toContain('Ok(42)');
  });

  test('emitPacked with null sum', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('WithSum', 'v1')
        .field('result', t.str(), { fid: 1 })
      .build();
    const val = g.struct('WithSum',
      field('result', g.sum('None', null))
    );
    const result = emitPacked(val, s);
    expect(result).toContain('None()');
  });

  test('emitPacked with bytes value', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Bin', 'v1')
        .field('data', t.bytes(), { fid: 1 })
      .build();
    const val = g.struct('Bin',
      field('data', g.bytes(new Uint8Array([1, 2, 3])))
    );
    const result = emitPacked(val, s);
    expect(result).toContain('b64');
  });

  test('emitPacked with time value', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Ev', 'v1')
        .field('when', t.time(), { fid: 1 })
      .build();
    const val = g.struct('Ev',
      field('when', g.time(new Date('2025-12-19T10:30:00Z')))
    );
    const result = emitPacked(val, s);
    expect(result).toContain('2025-12-19');
  });

  // Tabular emit
  test('emitTabular empty list', () => {
    const result = emitTabular(g.list(), schema);
    expect(result).toBe('[]');
  });

  test('emitTabular error: non-list', () => {
    expect(() => emitTabular(g.int(1), schema)).toThrow('tabular encoding requires list value');
  });

  test('emitTabular error: non-struct elements', () => {
    expect(() => emitTabular(g.list(g.int(1)), schema)).toThrow('tabular encoding requires list of structs');
  });

  test('emitTabular error: mixed types', () => {
    const list = g.list(
      g.struct('Team', field('id', g.id('t', 'ARS')), field('name', g.str('Arsenal')), field('league', g.str('EPL'))),
      g.struct('Other', field('id', g.id('t', 'LIV')), field('name', g.str('Liverpool')), field('league', g.str('EPL')))
    );
    expect(() => emitTabular(list, schema)).toThrow('all elements must be same type struct');
  });

  test('emitTabular with fid keyMode', () => {
    const list = g.list(
      g.struct('Team',
        field('id', g.id('t', 'ARS')),
        field('name', g.str('Arsenal')),
        field('league', g.str('EPL'))
      )
    );
    const result = emitTabular(list, schema, { keyMode: 'fid' });
    expect(result).toContain('#1');
    expect(result).toContain('#2');
  });

  test('emitTabular with name keyMode', () => {
    const list = g.list(
      g.struct('Team',
        field('id', g.id('t', 'ARS')),
        field('name', g.str('Arsenal')),
        field('league', g.str('EPL'))
      )
    );
    const result = emitTabular(list, schema, { keyMode: 'name' });
    expect(result).toContain('id');
    expect(result).toContain('name');
    expect(result).toContain('league');
  });

  // Header emit
  test('emitHeader basic', () => {
    expect(emitHeader()).toBe('@lyph v2');
  });

  test('emitHeader with all options', () => {
    const h = emitHeader({
      version: 'v3',
      schemaId: 'abc',
      mode: 'packed',
      keyMode: 'name',
      target: { prefix: 'm', value: 'ARS' },
    });
    expect(h).toContain('@lyph v3');
    expect(h).toContain('@schema#abc');
    expect(h).toContain('@mode=packed');
    expect(h).toContain('@keys=name');
    expect(h).toContain('@target=m:ARS');
  });

  test('emitHeader target without prefix', () => {
    const h = emitHeader({ target: { prefix: '', value: 'ARS' } });
    expect(h).toContain('@target=ARS');
  });

  // V2 emitter
  test('emitV2 auto mode selects packed for struct', () => {
    const team = g.struct('Team',
      field('id', g.id('t', 'ARS')),
      field('name', g.str('Arsenal')),
      field('league', g.str('EPL'))
    );
    const result = emitV2(team, schema);
    expect(result).toContain('Team@(');
  });

  test('emitV2 with header', () => {
    const team = g.struct('Team',
      field('id', g.id('t', 'ARS')),
      field('name', g.str('Arsenal')),
      field('league', g.str('EPL'))
    );
    const result = emitV2(team, schema, { includeHeader: true });
    expect(result).toContain('@lyph v2');
  });

  test('emitV2 struct mode', () => {
    const team = g.struct('Team',
      field('id', g.id('t', 'ARS')),
      field('name', g.str('Arsenal')),
      field('league', g.str('EPL'))
    );
    const result = emitV2(team, schema, { mode: 'struct' });
    expect(result).toContain('Team{');
  });

  test('emitV2 tabular mode for list', () => {
    const s = new SchemaBuilder()
      .addPackedStruct('Item', 'v1')
        .field('id', t.int(), { fid: 1 })
        .field('name', t.str(), { fid: 2 })
      .build();
    const list = g.list(
      g.struct('Item', field('id', g.int(1)), field('name', g.str('a'))),
      g.struct('Item', field('id', g.int(2)), field('name', g.str('b'))),
      g.struct('Item', field('id', g.int(3)), field('name', g.str('c')))
    );
    const result = emitV2(list, s);
    expect(result).toContain('@tab');
  });
});

// ============================================================
// JSON — deeper coverage
// ============================================================

describe('JSON coverage', () => {
  test('fromJson undefined', () => {
    expect(fromJson(undefined).isNull()).toBe(true);
  });

  test('fromJson with parseRefs=false', () => {
    const result = fromJson('^t:ARS', { parseRefs: false });
    expect(result.type).toBe('str');
    expect(result.asStr()).toBe('^t:ARS');
  });

  test('fromJson with parseDates=false', () => {
    const result = fromJson('2025-12-19T10:30:00Z', { parseDates: false });
    expect(result.type).toBe('str');
  });

  test('fromJson ref without prefix', () => {
    const result = fromJson('^SOMETHING');
    expect(result.type).toBe('id');
    expect(result.asId().prefix).toBe('');
    expect(result.asId().value).toBe('SOMETHING');
  });

  test('fromJson $ref marker', () => {
    const result = fromJson({ $ref: 't:ARS' });
    expect(result.type).toBe('id');
    expect(result.asId().prefix).toBe('t');
  });

  test('fromJson $ref marker without prefix', () => {
    const result = fromJson({ $ref: 'ABC' });
    expect(result.type).toBe('id');
    expect(result.asId().prefix).toBe('');
    expect(result.asId().value).toBe('ABC');
  });

  test('fromJson $time marker', () => {
    const result = fromJson({ $time: '2025-12-19T10:30:00Z' });
    expect(result.type).toBe('time');
  });

  test('fromJson $bytes marker', () => {
    const result = fromJson({ $bytes: 'SGVsbG8=' });
    expect(result.type).toBe('bytes');
  });

  test('fromJson $tag marker', () => {
    const result = fromJson({ $tag: 'Ok', $value: 42 });
    expect(result.type).toBe('sum');
    expect(result.asSum().tag).toBe('Ok');
    expect(result.asSum().value?.asInt()).toBe(42);
  });

  test('fromJson $tag marker without value', () => {
    const result = fromJson({ $tag: 'None' });
    expect(result.type).toBe('sum');
    expect(result.asSum().value).toBeNull();
  });

  test('fromJson with typeName hint', () => {
    const schema = new SchemaBuilder()
      .addPackedStruct('Team', 'v1')
        .field('name', t.str(), { fid: 1 })
      .build();
    const result = fromJson({ name: 'Arsenal' }, { schema, typeName: 'Team' });
    expect(result.type).toBe('struct');
    expect(result.asStruct().typeName).toBe('Team');
  });

  test('toJson ref non-compact', () => {
    const json = toJson(g.id('t', 'ARS'), { compactRefs: false }) as Record<string, unknown>;
    expect(json.$ref).toBe('t:ARS');
  });

  test('toJson time non-formatted', () => {
    const json = toJson(g.time(new Date('2025-12-19T10:30:00Z')), { formatDates: false }) as Record<string, unknown>;
    expect(json.$time).toBeDefined();
  });

  test('toJson bytes', () => {
    const json = toJson(g.bytes(new Uint8Array([72, 101]))) as Record<string, unknown>;
    expect(json.$bytes).toBeDefined();
  });

  test('toJson sum', () => {
    const json = toJson(g.sum('Ok', g.int(42))) as Record<string, unknown>;
    expect(json.$tag).toBe('Ok');
    expect(json.$value).toBe(42);
  });

  test('toJson sum without value', () => {
    const json = toJson(g.sum('None', null)) as Record<string, unknown>;
    expect(json.$tag).toBe('None');
  });

  test('toJson list', () => {
    const json = toJson(g.list(g.int(1), g.int(2)));
    expect(json).toEqual([1, 2]);
  });

  test('toJson with wire keys', () => {
    const schema = new SchemaBuilder()
      .addPackedStruct('Team', 'v1')
        .field('name', t.str(), { fid: 1, wireKey: 'n' })
      .build();
    const json = toJson(
      g.struct('Team', field('name', g.str('Arsenal'))),
      { useWireKeys: true, schema }
    ) as Record<string, unknown>;
    expect(json.n).toBe('Arsenal');
  });

  test('parseJson convenience', () => {
    const result = parseJson('{"x": 42}');
    expect(result.get('x')?.asInt()).toBe(42);
  });

  test('stringifyJson convenience', () => {
    const result = stringifyJson(g.map(field('x', g.int(42))));
    expect(JSON.parse(result)).toEqual({ x: 42 });
  });

  test('stringifyJson with indent', () => {
    const result = stringifyJson(g.map(field('x', g.int(1))), {}, 2);
    expect(result).toContain('\n');
  });

  test('normalizeJson', () => {
    const result = normalizeJson({ $type: 'Team', name: 'Arsenal' }, {}, { includeTypeMarkers: true });
    expect((result as Record<string, unknown>).$type).toBe('Team');
  });
});

// ============================================================
// Loose — deeper coverage
// ============================================================

describe('Loose coverage', () => {
  test('canonicalize bytes', () => {
    const result = canonicalizeLoose(g.bytes(new Uint8Array([1, 2, 3])));
    expect(result).toContain('b64');
  });

  test('canonicalize empty bytes', () => {
    const result = canonicalizeLoose(g.bytes(new Uint8Array([])));
    expect(result).toBe('b64""');
  });

  test('canonicalize time', () => {
    const result = canonicalizeLoose(g.time(new Date('2025-12-19T10:30:00Z')));
    expect(result).toContain('2025-12-19T10:30:00Z');
  });

  test('canonicalize float special values', () => {
    expect(canonicalizeLoose(g.float(NaN))).toBe('NaN');
    expect(canonicalizeLoose(g.float(Infinity))).toBe('Inf');
    expect(canonicalizeLoose(g.float(-Infinity))).toBe('-Inf');
    expect(canonicalizeLoose(g.float(-0))).toBe('0');
  });

  test('canonicalize float exponential', () => {
    // Very small number (exp < -4 triggers exponential)
    const result = canonicalizeLoose(g.float(1e-5));
    expect(result).toBe('1e-05');

    // Very large number
    const result2 = canonicalizeLoose(g.float(1e20));
    expect(result2).toContain('e');

    // Number in normal range
    const result3 = canonicalizeLoose(g.float(0.001));
    expect(result3).toBe('0.001');
  });

  test('canonicalize struct as map', () => {
    const result = canonicalizeLoose(g.struct('Team', field('name', g.str('Arsenal'))));
    expect(result).toBe('{name=Arsenal}');
  });

  test('canonicalize sum as map', () => {
    const result = canonicalizeLoose(g.sum('Ok', g.int(42)));
    expect(result).toBe('{Ok=42}');
  });

  test('canonicalize sum with null value', () => {
    const result = canonicalizeLoose(g.sum('None', null));
    expect(result).toBe('{None=_}');
  });

  test('canonicalizeLooseWithOpts with nullStyle=symbol', () => {
    const result = canonicalizeLooseWithOpts(g.null(), { nullStyle: 'symbol' });
    expect(result).toBe('∅');
  });

  test('canonicalizeLooseWithOpts with nullStyle=underscore', () => {
    const result = canonicalizeLooseWithOpts(g.null(), { nullStyle: 'underscore' });
    expect(result).toBe('_');
  });

  test('fingerprintLoose', () => {
    const fp = fingerprintLoose(g.int(42));
    expect(fp).toBe('42');
  });

  test('canonicalizeLooseTabular (deprecated alias)', () => {
    const list = g.list(
      g.map(field('id', g.int(1))),
      g.map(field('id', g.int(2))),
      g.map(field('id', g.int(3)))
    );
    const result = canonicalizeLooseTabular(list);
    expect(result).toContain('@tab');
  });

  test('tabular with allowMissing=false and mismatched keys', () => {
    const list = g.list(
      g.map(field('a', g.int(1))),
      g.map(field('b', g.int(2))),
      g.map(field('a', g.int(3)))
    );
    const result = canonicalizeLooseWithOpts(list, { autoTabular: true, minRows: 3, allowMissing: false });
    // Should NOT be tabular because keys don't match
    expect(result).toBe('[{a=1} {b=2} {a=3}]');
  });

  test('tabular rejected when mostly disjoint keys', () => {
    const list = g.list(
      g.map(field('a', g.int(1)), field('b', g.int(2))),
      g.map(field('c', g.int(3)), field('d', g.int(4))),
      g.map(field('e', g.int(5)), field('f', g.int(6)))
    );
    const result = canonicalizeLooseWithOpts(list, { autoTabular: true, minRows: 3 });
    // Disjoint keys -> should NOT use tabular
    expect(result).not.toContain('@tab');
  });

  test('tabular rejected when too many columns', () => {
    const entries = Array.from({ length: 25 }, (_, i) => field(`col${i}`, g.int(i)));
    const list = g.list(
      g.map(...entries),
      g.map(...entries),
      g.map(...entries)
    );
    const result = canonicalizeLooseWithOpts(list, { autoTabular: true, minRows: 3, maxCols: 20 });
    expect(result).not.toContain('@tab');
  });

  test('tabular with empty maps', () => {
    const list = g.list(g.map(), g.map(), g.map());
    const result = canonicalizeLooseWithOpts(list, { autoTabular: true, minRows: 3 });
    // Empty maps have 0 keys -> no tabular
    expect(result).toBe('[{} {} {}]');
  });

  // Schema header / compact keys
  test('canonicalizeLooseWithSchema with schemaRef', () => {
    const result = canonicalizeLooseWithSchema(g.int(42), { schemaRef: 'abc123' });
    expect(result).toContain('@schema#abc123');
    expect(result).toContain('42');
  });

  test('canonicalizeLooseWithSchema with keyDict + compact keys', () => {
    const val = g.map(field('name', g.str('Alice')), field('age', g.int(30)));
    const result = canonicalizeLooseWithSchema(val, {
      keyDict: ['age', 'name'],
      useCompactKeys: true,
    });
    expect(result).toContain('@schema');
    expect(result).toContain('keys=');
    expect(result).toContain('#0=');
    expect(result).toContain('#1=');
  });

  test('buildKeyDictFromValue', () => {
    const val = g.map(
      field('b', g.int(1)),
      field('a', g.map(field('c', g.int(2))))
    );
    const keys = buildKeyDictFromValue(val);
    expect(keys).toEqual(['a', 'b', 'c']);
  });

  test('buildKeyDictFromValue with struct and list', () => {
    const val = g.list(
      g.struct('Team', field('name', g.str('Arsenal'))),
      g.map(field('id', g.int(1)))
    );
    const keys = buildKeyDictFromValue(val);
    expect(keys).toContain('name');
    expect(keys).toContain('id');
  });

  test('parseSchemaHeader basic', () => {
    const result = parseSchemaHeader('@schema#abc123 keys=[name age]');
    expect(result.schemaRef).toBe('abc123');
    expect(result.keyDict).toEqual(['name', 'age']);
  });

  test('parseSchemaHeader no keys', () => {
    const result = parseSchemaHeader('@schema#abc123');
    expect(result.schemaRef).toBe('abc123');
    expect(result.keyDict).toEqual([]);
  });

  test('parseSchemaHeader error: not a schema header', () => {
    expect(() => parseSchemaHeader('hello')).toThrow('not a schema header');
  });

  test('parseSchemaHeader error: keys= missing bracket', () => {
    expect(() => parseSchemaHeader('@schema#ref keys=abc')).toThrow('keys= must be followed by []');
  });

  test('parseSchemaHeader error: keys= missing closing bracket', () => {
    expect(() => parseSchemaHeader('@schema#ref keys=[abc')).toThrow('missing ]');
  });

  test('parseTabularLooseHeaderWithMeta with rows/cols', () => {
    const result = parseTabularLooseHeaderWithMeta('@tab _ rows=5 cols=3 [a b c]');
    expect(result.rows).toBe(5);
    expect(result.cols).toBe(3);
    expect(result.keys).toEqual(['a', 'b', 'c']);
  });

  // parseTabularLoose edge cases
  test('parseTabularLoose error: not @tab _ header', () => {
    expect(() => parseTabularLoose('@tab Type [a]\n|1|\n@end')).toThrow('expected @tab _ header');
  });

  test('parseTabularLoose error: too short', () => {
    expect(() => parseTabularLoose('@tab _ [a]')).toThrow('tabular block requires at least header and @end');
  });

  test('parseTabularLoose with underscore null', () => {
    const result = parseTabularLoose('@tab _ [a b]\n|1|_|\n@end');
    expect(result.rows[0].b).toBeNull();
  });

  // fromJsonLoose / toJsonLoose edge cases
  test('fromJsonLoose with extended time marker', () => {
    const result = fromJsonLoose({ $glyph: 'time', value: '2025-12-19T10:30:00Z' }, { extended: true });
    expect(result.type).toBe('time');
  });

  test('fromJsonLoose with extended id marker', () => {
    const result = fromJsonLoose({ $glyph: 'id', value: '^user:123' }, { extended: true });
    expect(result.type).toBe('id');
    expect(result.asId().prefix).toBe('user');
  });

  test('fromJsonLoose with extended id marker no prefix', () => {
    const result = fromJsonLoose({ $glyph: 'id', value: 'ABC' }, { extended: true });
    expect(result.type).toBe('id');
    expect(result.asId().prefix).toBe('');
  });

  test('fromJsonLoose with extended bytes marker', () => {
    const result = fromJsonLoose({ $glyph: 'bytes', base64: 'SGVsbG8=' }, { extended: true });
    expect(result.type).toBe('bytes');
  });

  test('fromJsonLoose error: unknown $glyph marker', () => {
    expect(() => fromJsonLoose({ $glyph: 'unknown', value: '?' }, { extended: true })).toThrow('Unknown $glyph marker');
  });

  test('fromJsonLoose error: $glyph time missing value', () => {
    expect(() => fromJsonLoose({ $glyph: 'time' }, { extended: true })).toThrow('missing value');
  });

  test('fromJsonLoose error: $glyph id missing value', () => {
    expect(() => fromJsonLoose({ $glyph: 'id' }, { extended: true })).toThrow('missing value');
  });

  test('fromJsonLoose error: $glyph bytes missing base64', () => {
    expect(() => fromJsonLoose({ $glyph: 'bytes' }, { extended: true })).toThrow('missing base64');
  });

  test('fromJsonLoose with -Infinity', () => {
    expect(() => fromJsonLoose(-Infinity)).toThrow('NaN/Infinity');
  });

  test('toJsonLoose bytes without extended', () => {
    const result = toJsonLoose(g.bytes(new Uint8Array([72, 101])));
    expect(typeof result).toBe('string');
  });

  test('toJsonLoose bytes with extended', () => {
    const result = toJsonLoose(g.bytes(new Uint8Array([72, 101])), { extended: true }) as Record<string, unknown>;
    expect(result.$glyph).toBe('bytes');
    expect(result.base64).toBeDefined();
  });

  test('toJsonLoose struct', () => {
    const result = toJsonLoose(g.struct('Team', field('name', g.str('Arsenal')))) as Record<string, unknown>;
    expect(result.name).toBe('Arsenal');
  });

  test('toJsonLoose sum', () => {
    const result = toJsonLoose(g.sum('Ok', g.int(42))) as Record<string, unknown>;
    expect(result.Ok).toBe(42);
  });

  test('toJsonLoose sum without value', () => {
    const result = toJsonLoose(g.sum('None', null)) as Record<string, unknown>;
    expect(result.None).toBeNull();
  });

  test('toJsonLoose float NaN error', () => {
    expect(() => toJsonLoose(g.float(NaN))).toThrow('NaN/Infinity');
  });

  test('parseJsonLoose convenience', () => {
    const result = parseJsonLoose('{"x": 42}');
    expect(result.get('x')?.asInt()).toBe(42);
  });

  test('stringifyJsonLoose convenience', () => {
    const result = stringifyJsonLoose(g.map(field('x', g.int(42))));
    expect(JSON.parse(result)).toEqual({ x: 42 });
  });

  test('stringifyJsonLoose with indent', () => {
    const result = stringifyJsonLoose(g.map(field('x', g.int(1))), {}, 2);
    expect(result).toContain('\n');
  });

  test('jsonEqual with arrays', () => {
    expect(jsonEqual('[1,2,3]', '[1,2,3]')).toBe(true);
    expect(jsonEqual('[1,2]', '[1,2,3]')).toBe(false);
  });

  test('jsonEqual with nested', () => {
    expect(jsonEqual('{"a":{"b":1}}', '{"a":{"b":1}}')).toBe(true);
    expect(jsonEqual('{"a":{"b":1}}', '{"a":{"b":2}}')).toBe(false);
  });

  test('jsonEqual different types', () => {
    expect(jsonEqual('1', '"1"')).toBe(false);
  });

  test('jsonEqual null', () => {
    expect(jsonEqual('null', 'null')).toBe(true);
    expect(jsonEqual('null', '1')).toBe(false);
  });

  test('jsonEqual key count mismatch', () => {
    expect(jsonEqual('{"a":1}', '{"a":1,"b":2}')).toBe(false);
  });
});

// ============================================================
// Decimal128 — coverage
// ============================================================

describe('Decimal128 coverage', () => {
  test('fromInt', () => {
    const d = Decimal128.fromInt(42);
    expect(d.toString()).toBe('42');
    expect(d.scale).toBe(0);
    expect(d.coef).toBe(42n);
  });

  test('fromInt with bigint', () => {
    const d = Decimal128.fromInt(100n);
    expect(d.toString()).toBe('100');
  });

  test('fromString basic', () => {
    const d = Decimal128.fromString('123.45');
    expect(d.toString()).toBe('123.45');
    expect(d.scale).toBe(2);
    expect(d.coef).toBe(12345n);
  });

  test('fromString negative', () => {
    const d = Decimal128.fromString('-0.001');
    expect(d.toString()).toBe('-0.001');
    expect(d.isNegative()).toBe(true);
  });

  test('fromString integer', () => {
    const d = Decimal128.fromString('999');
    expect(d.toString()).toBe('999');
  });

  test('fromString with m suffix', () => {
    const d = Decimal128.fromString('123.45m');
    expect(d.toString()).toBe('123.45');
  });

  test('fromString error: multiple dots', () => {
    expect(() => Decimal128.fromString('1.2.3')).toThrow('invalid decimal format');
  });

  test('fromNumber', () => {
    const d = Decimal128.fromNumber(3.14);
    expect(d.toNumber()).toBeCloseTo(3.14);
  });

  test('scale out of range', () => {
    expect(() => new Decimal128(128, 1n)).toThrow('scale must be');
    expect(() => new Decimal128(-128, 1n)).toThrow('scale must be');
  });

  test('toInt truncates', () => {
    const d = Decimal128.fromString('123.99');
    expect(d.toInt()).toBe(123n);
  });

  test('toNumber', () => {
    const d = Decimal128.fromString('123.45');
    expect(d.toNumber()).toBeCloseTo(123.45);
  });

  test('toString with padding', () => {
    const d = Decimal128.fromString('0.001');
    expect(d.toString()).toBe('0.001');
  });

  test('isZero', () => {
    expect(Decimal128.fromInt(0).isZero()).toBe(true);
    expect(Decimal128.fromInt(1).isZero()).toBe(false);
  });

  test('isNegative / isPositive', () => {
    expect(Decimal128.fromInt(-1).isNegative()).toBe(true);
    expect(Decimal128.fromInt(-1).isPositive()).toBe(false);
    expect(Decimal128.fromInt(1).isPositive()).toBe(true);
    expect(Decimal128.fromInt(1).isNegative()).toBe(false);
    expect(Decimal128.fromInt(0).isNegative()).toBe(false);
    expect(Decimal128.fromInt(0).isPositive()).toBe(false);
  });

  test('abs', () => {
    const d = Decimal128.fromInt(-42);
    expect(d.abs().toNumber()).toBe(42);
    expect(Decimal128.fromInt(42).abs().toNumber()).toBe(42);
  });

  test('negate', () => {
    const d = Decimal128.fromInt(42);
    expect(d.negate().toNumber()).toBe(-42);
    expect(d.negate().negate().toNumber()).toBe(42);
  });

  test('add', () => {
    const a = Decimal128.fromString('10.50');
    const b = Decimal128.fromString('3.25');
    expect(a.add(b).toString()).toBe('13.75');
  });

  test('add different scales', () => {
    const a = Decimal128.fromString('1.5');   // scale 1
    const b = Decimal128.fromString('0.25');  // scale 2
    expect(a.add(b).toString()).toBe('1.75');
  });

  test('sub', () => {
    const a = Decimal128.fromString('10.50');
    const b = Decimal128.fromString('3.25');
    expect(a.sub(b).toString()).toBe('7.25');
  });

  test('mul', () => {
    const a = Decimal128.fromString('2.5');
    const b = Decimal128.fromString('4.0');
    expect(a.mul(b).toString()).toBe('10.00');
  });

  test('mul scale overflow', () => {
    const a = new Decimal128(100, 1n);
    const b = new Decimal128(28, 1n);
    expect(() => a.mul(b)).toThrow('scale overflow');
  });

  test('div', () => {
    const a = Decimal128.fromInt(10);
    const b = Decimal128.fromInt(3);
    expect(a.div(b).toNumber()).toBe(3); // integer division
  });

  test('div by zero', () => {
    expect(() => Decimal128.fromInt(1).div(Decimal128.fromInt(0))).toThrow('division by zero');
  });

  test('cmp', () => {
    const a = Decimal128.fromString('10.5');
    const b = Decimal128.fromString('10.5');
    const c = Decimal128.fromString('20.0');
    expect(a.cmp(b)).toBe(0);
    expect(a.cmp(c)).toBe(-1);
    expect(c.cmp(a)).toBe(1);
  });

  test('cmp different scales', () => {
    const a = Decimal128.fromString('1.0');
    const b = Decimal128.fromString('1.00');
    expect(a.cmp(b)).toBe(0);
  });

  test('equals', () => {
    expect(Decimal128.fromString('1.0').equals(Decimal128.fromString('1.00'))).toBe(true);
    expect(Decimal128.fromString('1.0').equals(Decimal128.fromString('2.0'))).toBe(false);
  });

  test('lt / gt / lte / gte', () => {
    const a = Decimal128.fromInt(1);
    const b = Decimal128.fromInt(2);
    expect(a.lt(b)).toBe(true);
    expect(b.gt(a)).toBe(true);
    expect(a.lte(a)).toBe(true);
    expect(a.gte(a)).toBe(true);
    expect(b.lte(a)).toBe(false);
    expect(a.gte(b)).toBe(false);
  });

  test('isDecimalLiteral', () => {
    expect(isDecimalLiteral('123.45m')).toBe(true);
    expect(isDecimalLiteral('123m')).toBe(true);
    expect(isDecimalLiteral('123')).toBe(false);
    expect(isDecimalLiteral('abcm')).toBe(false);
  });

  test('parseDecimalLiteral', () => {
    const d = parseDecimalLiteral('123.45m');
    expect(d.toString()).toBe('123.45');
  });

  test('parseDecimalLiteral error: no suffix', () => {
    expect(() => parseDecimalLiteral('123')).toThrow('not a decimal literal');
  });

  test('decimal convenience', () => {
    expect(decimal('1.5').toNumber()).toBe(1.5);
    expect(decimal(42).toNumber()).toBe(42);
    expect(decimal(100n).toNumber()).toBe(100);
  });

  test('DecimalError name', () => {
    const err = new DecimalError('test');
    expect(err.name).toBe('DecimalError');
    expect(err.message).toBe('test');
  });
});

// ============================================================
// Patch — deeper coverage
// ============================================================

describe('Patch coverage', () => {
  test('parsePathToSegs with field and list index', () => {
    const segs = parsePathToSegs('events[0]');
    expect(segs.length).toBe(2);
    expect(segs[0].kind).toBe('field');
    expect(segs[0].field).toBe('events');
    expect(segs[1].kind).toBe('listIdx');
    expect(segs[1].listIdx).toBe(0);
  });

  test('parsePathToSegs with map key', () => {
    const segs = parsePathToSegs('data["key"]');
    expect(segs.length).toBe(2);
    expect(segs[1].kind).toBe('mapKey');
    expect(segs[1].mapKey).toBe('key');
  });

  test('parsePathToSegs with field id', () => {
    const segs = parsePathToSegs('#1.#2');
    expect(segs.length).toBe(2);
    expect(segs[0].kind).toBe('field');
    expect(segs[0].fid).toBe(1);
    expect(segs[1].fid).toBe(2);
  });

  test('parsePathToSegs with quoted field', () => {
    const segs = parsePathToSegs('"field name".sub');
    expect(segs.length).toBe(2);
    expect(segs[0].field).toBe('field name');
  });

  test('parsePathToSegs empty path', () => {
    expect(parsePathToSegs('')).toEqual([]);
  });

  test('parsePathToSegs error: trailing dot', () => {
    expect(() => parsePathToSegs('a.')).toThrow('path cannot end with dot');
  });

  test('parsePathToSegs error: starts with dot only', () => {
    expect(() => parsePathToSegs('.')).toThrow('path cannot end with dot');
  });

  test('parsePathToSegs error: non-numeric list index', () => {
    expect(() => parsePathToSegs('a[abc]')).toThrow('invalid list index');
  });

  test('parsePathToSegs error: unterminated bracket', () => {
    expect(() => parsePathToSegs('a[0')).toThrow('unterminated list index');
  });

  test('parsePathToSegs error: missing fid', () => {
    expect(() => parsePathToSegs('#')).toThrow('missing field id');
  });

  test('fieldSeg / listIdxSeg / mapKeySeg constructors', () => {
    const f = fieldSeg('name', 1);
    expect(f.kind).toBe('field');
    expect(f.field).toBe('name');
    expect(f.fid).toBe(1);

    const l = listIdxSeg(5);
    expect(l.kind).toBe('listIdx');
    expect(l.listIdx).toBe(5);

    const m = mapKeySeg('key');
    expect(m.kind).toBe('mapKey');
    expect(m.mapKey).toBe('key');
  });

  test('PatchBuilder insertAt', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .insertAt('events', 0, g.str('first'))
      .build();
    expect(patch.ops[0].op).toBe('+');
    expect(patch.ops[0].index).toBe(0);
  });

  test('PatchBuilder withTargetType', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .withTargetType('Match')
      .set('score', g.int(1))
      .build();
    expect(patch.targetType).toBe('Match');
  });

  test('PatchBuilder setWithSegs', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .setWithSegs([fieldSeg('x')], g.int(42))
      .build();
    expect(patch.ops[0].path[0].field).toBe('x');
  });

  test('emitPatch with insertAt index', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .insertAt('events', 2, g.str('middle'))
      .build();
    const emitted = emitPatch(patch);
    expect(emitted).toContain('@idx=2');
  });

  test('emitPatch with fid key mode', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .setWithSegs([{ kind: 'field', field: 'score', fid: 1 }], g.int(42))
      .build();
    const emitted = emitPatch(patch, { keyMode: 'fid' });
    expect(emitted).toContain('#1');
  });

  test('emitPatch with sortOps=false', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .set('z', g.int(1))
      .set('a', g.int(2))
      .build();
    const emitted = emitPatch(patch, { sortOps: false });
    const lines = emitted.split('\n');
    // z should come before a since we disabled sorting
    const zIdx = lines.findIndex(l => l.includes(' z '));
    const aIdx = lines.findIndex(l => l.includes(' a '));
    expect(zIdx).toBeLessThan(aIdx);
  });

  test('emitPatch with baseFingerprint', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .withBaseFingerprint('abcdef1234567890')
      .set('score', g.int(42))
      .build();
    const emitted = emitPatch(patch);
    expect(emitted).toContain('@base=abcdef1234567890');
  });

  test('parsePatch with @base', () => {
    const input = `@patch @keys=wire @target=m:TEST @base=abcdef1234567890
= score 42
@end`;
    const patch = parsePatch(input);
    expect(patch.baseFingerprint).toBe('abcdef1234567890');
  });

  test('parsePatch with list value', () => {
    const input = `@patch @keys=wire @target=m:TEST
= items [1 2 3]
@end`;
    const patch = parsePatch(input);
    expect(patch.ops[0].value?.type).toBe('list');
    expect(patch.ops[0].value?.len()).toBe(3);
  });

  test('parsePatch with struct value', () => {
    const input = `@patch @keys=wire @target=m:TEST
= data Info{x=1}
@end`;
    const patch = parsePatch(input);
    expect(patch.ops[0].value?.type).toBe('struct');
    expect(patch.ops[0].value?.asStruct().typeName).toBe('Info');
  });

  test('parsePatch with ref value', () => {
    const input = `@patch @keys=wire @target=m:TEST
= ref ^user:123
@end`;
    const patch = parsePatch(input);
    expect(patch.ops[0].value?.type).toBe('id');
  });

  test('parsePatch with bool values', () => {
    const input = `@patch @keys=wire @target=m:TEST
= active t
= hidden f
@end`;
    const patch = parsePatch(input);
    expect(patch.ops[0].value?.asBool()).toBe(true);
    expect(patch.ops[1].value?.asBool()).toBe(false);
  });

  test('parsePatch with null value', () => {
    const input = `@patch @keys=wire @target=m:TEST
= val ∅
@end`;
    const patch = parsePatch(input);
    expect(patch.ops[0].value?.isNull()).toBe(true);
  });

  test('parsePatch error: empty input', () => {
    expect(() => parsePatch('')).toThrow();
  });

  test('parsePatch error: not starting with @patch', () => {
    expect(() => parsePatch('invalid')).toThrow('patch must start with @patch');
  });

  test('parsePatch error: delta without value', () => {
    expect(() => parsePatch(`@patch @keys=wire @target=m:TEST
~ score
@end`)).toThrow('delta operation requires a value');
  });

  test('parsePatch error: unknown op', () => {
    expect(() => parsePatch(`@patch @keys=wire @target=m:TEST
X score 1
@end`)).toThrow('unknown operation');
  });

  // Apply coverage
  test('applyPatch delete from struct', () => {
    const value = g.struct('Data',
      field('keep', g.int(1)),
      field('remove', g.int(2))
    );
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .delete('remove')
      .build();
    const result = applyPatch(value, patch);
    expect(result.get('remove')).toBeFalsy();
    expect(result.get('keep')?.asInt()).toBe(1);
  });

  test('applyPatch delete from map', () => {
    const value = g.map(
      field('keep', g.int(1)),
      field('remove', g.int(2))
    );
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .delete('remove')
      .build();
    const result = applyPatch(value, patch);
    expect(result.get('remove')).toBeFalsy();
  });

  test('applyPatch insertAt specific index', () => {
    const value = g.struct('Data',
      field('items', g.list(g.str('a'), g.str('c')))
    );
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .insertAt('items', 1, g.str('b'))
      .build();
    const result = applyPatch(value, patch);
    expect(result.get('items')?.index(0).asStr()).toBe('a');
    expect(result.get('items')?.index(1).asStr()).toBe('b');
    expect(result.get('items')?.index(2).asStr()).toBe('c');
  });

  test('applyPatch append to null creates new list', () => {
    const value = g.struct('Data',
      field('items', g.null())
    );
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .append('items', g.str('first'))
      .build();
    const result = applyPatch(value, patch);
    expect(result.get('items')?.type).toBe('list');
    expect(result.get('items')?.len()).toBe(1);
  });

  test('applyPatch delta on int field', () => {
    const value = g.struct('Data',
      field('count', g.int(10))
    );
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .delta('count', 5)
      .build();
    const result = applyPatch(value, patch);
    expect(result.get('count')?.asInt()).toBe(15);
  });

  test('applyPatch set at root', () => {
    const value = g.int(1);
    const patch: import('./index').Patch = {
      target: { prefix: '', value: 'x' },
      ops: [{ op: '=', path: [], value: g.int(42) }],
    };
    const result = applyPatch(value, patch);
    expect(result.asInt()).toBe(42);
  });

  test('applyPatch error: non-set at root', () => {
    const value = g.int(1);
    const patch: import('./index').Patch = {
      target: { prefix: '', value: 'x' },
      ops: [{ op: '-', path: [] }],
    };
    expect(() => applyPatch(value, patch)).toThrow('cannot apply - to root');
  });

  test('applyPatch with list index path', () => {
    const value = g.struct('Data',
      field('items', g.list(
        g.struct('Item', field('val', g.int(1))),
        g.struct('Item', field('val', g.int(2)))
      ))
    );
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .set('items[1].val', g.int(99))
      .build();
    const result = applyPatch(value, patch);
    expect(result.get('items')?.index(1).get('val')?.asInt()).toBe(99);
  });

  test('emitPatch with map key path segment', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .setWithSegs([fieldSeg('data'), mapKeySeg('key1')], g.int(42))
      .build();
    const emitted = emitPatch(patch);
    expect(emitted).toContain('data["key1"]');
  });

  test('emitPatch with list index path segment', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .setWithSegs([fieldSeg('items'), listIdxSeg(0)], g.int(42))
      .build();
    const emitted = emitPatch(patch);
    expect(emitted).toContain('items[0]');
  });

  test('emit and parse patch value types', () => {
    const patch = new PatchBuilder({ prefix: 'm', value: 'TEST' })
      .set('time', g.time(new Date('2025-12-19T10:30:00Z')))
      .set('null_val', g.null())
      .set('map_val', g.map(field('x', g.int(1))))
      .set('sum_val', g.sum('Ok', g.int(1)))
      .set('sum_empty', g.sum('None', null))
      .build();
    const emitted = emitPatch(patch);
    expect(emitted).toContain('2025-12-19');
    expect(emitted).toContain('∅');
    expect(emitted).toContain('{x:1}');
    expect(emitted).toContain('Ok(1)');
    expect(emitted).toContain('None()');
  });
});

// ============================================================
// Utility coverage
// ============================================================

describe('Utility coverage', () => {
  test('estimateTokens', () => {
    expect(estimateTokens('hello world')).toBe(2);
    expect(estimateTokens('')).toBe(0);
    expect(estimateTokens('single')).toBe(1);
  });
});
