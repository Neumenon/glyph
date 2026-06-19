/**
 * P0 round-trip golden table for the JS codec.
 *
 * Mirrors go/glyph/roundtrip_golden_test.go for the round-trippable JS paths.
 * The typed GLYPH-T parser is the packed parser (parsePacked), so the typed
 * round-trip invariant is parsePacked(emitPacked(v, schema), schema) == v. The
 * scalar parser (parseScalarValue) is the loose-cell inverse. These tests pin
 * the cross-language P0 behaviors brought to parity with Go: bytes round-trip,
 * \u control-char decode, dup-key last-wins, and the NaN/Inf reject policy in
 * the JSON bridge.
 */

import {
  g, field, SchemaBuilder, t,
  emitPacked, parsePacked,
  canonicalizeLoose, toJsonLoose, fromJsonLoose, equalLoose,
} from './index';
import { parseScalarValue } from './parse';

// A string containing sub-0x20 control chars, which the emitter writes as \uXXXX
// and the parser must decode back identically.
const CTRL = 'ctl\u0001\u0002end';

describe('P0 round-trip: typed packed path', () => {
  const schema = new SchemaBuilder()
    .addPackedStruct('Rec', 'v1')
      .field('rid', t.id(), { fid: 1 })
      .field('label', t.str(), { fid: 2 })
      .field('count', t.int(), { fid: 3 })
      .field('ratio', t.float(), { fid: 4 })
      .field('active', t.bool(), { fid: 5 })
      .field('blob', t.bytes(), { fid: 6 })
    .build();

  test('struct with bytes + control-char string round-trips', () => {
    const v = g.struct('Rec',
      field('rid', g.id('m', '123')),
      field('label', g.str(CTRL)),
      field('count', g.int(42)),
      field('ratio', g.float(2.5)),
      field('active', g.bool(true)),
      field('blob', g.bytes(new Uint8Array([0, 1, 2, 254, 255]))),
    );

    const packed = emitPacked(v, schema);
    const parsed = parsePacked(packed, schema);

    expect(equalLoose(parsed, v)).toBe(true);
    // Explicit P0 checks (not just canonical equality):
    expect(Array.from(parsed.get('blob')!.asBytes())).toEqual([0, 1, 2, 254, 255]);
    expect(parsed.get('label')!.asStr()).toBe(CTRL);
  });
});

describe('P0 round-trip: bytes via the loose scalar inverse', () => {
  // The original divergence: canonicalizeLoose emits b64"..." but the JS scalar
  // parser could not read it back. Now it round-trips, matching Python.
  test.each([
    ['empty', []],
    ['simple', [104, 101, 108, 108, 111]],
    ['binary', [0, 1, 2, 254, 255]],
    ['all', Array.from({ length: 256 }, (_, i) => i)],
  ])('bytes %s', (_name, arr) => {
    const bytes = new Uint8Array(arr as number[]);
    const emitted = canonicalizeLoose(g.bytes(bytes));
    const parsed = parseScalarValue(emitted);
    expect(parsed.type).toBe('bytes');
    expect(Array.from(parsed.asBytes())).toEqual(arr);
  });
});

describe('P0: \\u escape decodes in the scalar parser', () => {
  test('control chars decode back', () => {
    const v = parseScalarValue('"ctl\\u0001\\u0002end"');
    expect(v.type).toBe('str');
    expect(v.asStr()).toBe(CTRL);
  });
});

describe('P0: duplicate map keys are last-wins', () => {
  test('{a=1 a=2} -> a == 2', () => {
    const m = parseScalarValue('{a=1 a=2}');
    expect(m.get('a')!.asInt()).toBe(2);
  });
});

describe('P0: NaN/Inf rejected by the JSON bridge (maintainer decision)', () => {
  test('toJsonLoose rejects non-finite floats', () => {
    expect(() => toJsonLoose(g.float(NaN))).toThrow();
    expect(() => toJsonLoose(g.float(Infinity))).toThrow();
    expect(() => toJsonLoose(g.float(-Infinity))).toThrow();
  });
  test('fromJsonLoose rejects non-finite numbers', () => {
    expect(() => fromJsonLoose(Infinity)).toThrow();
  });
});
