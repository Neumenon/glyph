/**
 * SPEC-CANON.md conformance. Every expected string here is shared verbatim with
 * py/tests/test_canon.py and go/glyph/canonjson_test.go: the one digest must be
 * byte-identical across languages, so a divergence fails in all three.
 */
import { createHash } from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { GValue, MapEntry } from './types';
import { canonJson, fingerprint, isCanonical, tensorRef, CanonError } from './canon';
import { fromJsonLoose } from './loose';
import { computeBaseFingerprint } from './patch';
import { stateHashLooseSync, hashToHex } from './stream/hash';

const e = (key: string, value: GValue): MapEntry => ({ key, value });

describe('canonJson', () => {
  test('scalars and containers, JCS escaping', () => {
    const v = GValue.map(
      e('b', GValue.list(GValue.int(1), GValue.float(2.5), GValue.null(), GValue.bool(true))),
      e('a', GValue.str('q"\\\n\t\x01é😀')),
    );
    expect(canonJson(v)).toBe('{"a":"q\\"\\\\\\n\\t\\u0001é😀","b":[1,2.5,null,true]}');
  });

  test('numbers collapse to the JSON domain', () => {
    expect(canonJson(GValue.float(1.0))).toBe('1');
    expect(canonJson(GValue.float(-0))).toBe('0');
    expect(canonJson(GValue.int(0))).toBe('0');
    expect(canonJson(GValue.float(1e300))).toBe('1e+300');
    expect(canonJson(GValue.float(2 ** 53))).toBe('9.007199254740992e+15');
    expect(canonJson(GValue.float(1e-7))).toBe('1e-07');
    expect(canonJson(GValue.int(2 ** 53 - 1))).toBe('9007199254740991');
  });

  test('int beyond safe range and NaN are errors, not lies', () => {
    expect(() => canonJson(GValue.int(2 ** 53))).toThrow(CanonError);
    expect(() => canonJson(GValue.float(NaN))).toThrow(CanonError);
  });

  test('keys sort by code point, not UTF-16 unit', () => {
    // U+FFFD (BMP) must sort BELOW U+1F600; naive JS string compare puts it above.
    const v = GValue.map(e('�', GValue.int(3)), e('😀', GValue.int(2)), e('', GValue.int(1)));
    expect(canonJson(v)).toBe('{"":1,"�":3,"😀":2}');
    expect(() => canonJson(GValue.map(e('k', GValue.int(1)), e('k', GValue.int(2))))).toThrow(CanonError);
  });

  test('non-JSON scalars use reserved keys', () => {
    expect(canonJson(GValue.bytes(new Uint8Array([0, 0xff])))).toBe('{"$bytes":"AP8="}');
    expect(canonJson(GValue.time(new Date(Date.UTC(2025, 0, 13, 12, 34, 56, 500))))).toBe(
      '{"$time":"2025-01-13T12:34:56.5Z"}',
    );
    expect(canonJson(GValue.id('m', '1'))).toBe('{"$id":["m","1"]}');
    expect(canonJson(GValue.struct('Team', e('z', GValue.int(1)), e('a', GValue.int(2))))).toBe('{"a":2,"z":1}');
    expect(canonJson(GValue.sum('Ok', GValue.int(1)))).toBe('{"Ok":1}');
    expect(canonJson(GValue.sum('None', null))).toBe('{"None":null}');
  });

  test('depth limit', () => {
    let v = GValue.list();
    for (let i = 0; i < 999; i++) v = GValue.list(v);
    canonJson(v); // depth 1000 ok
    expect(() => canonJson(GValue.list(v))).toThrow(CanonError);
  });
});

test('one digest everywhere', () => {
  const v = fromJsonLoose({ b: [1, 2.0, null], a: 'x' });
  const fp = fingerprint(v);
  expect(fp).toBe(createHash('sha256').update(canonJson(v), 'utf8').digest('hex'));
  expect(computeBaseFingerprint(v)).toBe(fp);
  expect(hashToHex(stateHashLooseSync(v))).toBe(fp);
});

test('isCanonical is the strict check', () => {
  expect(isCanonical('{"a":1,"b":[true,null]}')).toBe(true);
  expect(isCanonical(new TextEncoder().encode('{"a":1,"b":[true,null]}'))).toBe(true);
  expect(isCanonical('{"b":[true,null],"a":1}')).toBe(false); // order
  expect(isCanonical('{"a": 1}')).toBe(false); // whitespace
  expect(isCanonical('{"a":1.0}')).toBe(false); // number form
  expect(isCanonical('{"a":1,"a":2}')).toBe(false); // duplicate key
  expect(isCanonical('nope')).toBe(false);
});

// SPEC-CANON.md §4: a tensor is identified by sha256 of its raw element bytes.
// The fixtures are cowrie's 8 tensor cases with the bytes lifted from its golden
// encodings, so glyph and cowrie name the same tensor by the same hash.
describe('tensor refs (SPEC-CANON §4)', () => {
  const fixtures: any[] = fs
    .readFileSync(path.join(__dirname, '..', '..', 'harness', 'state_identity', 'data', 'tensor_refs.jsonl'), 'utf-8')
    .split('\n')
    .filter((l: string) => l.trim())
    .map((l: string) => JSON.parse(l));

  test('tensorRef matches cowrie bytes', () => {
    expect(fixtures).toHaveLength(8);
    for (const fx of fixtures) {
      for (const t of fx.tensors) {
        const ref = tensorRef(t.dtype, t.shape, Uint8Array.from(Buffer.from(t.data_hex, 'hex')));
        const want = { $tensor: { dtype: t.dtype, sha256: t.sha256, shape: t.shape } };
        expect(canonJson(ref)).toBe(JSON.stringify(want));
      }
      const v = fromJsonLoose(JSON.parse(fx.json));
      expect(canonJson(v)).toBe(fx.json);
      expect(fingerprint(v)).toBe(fx.fingerprint);
    }
  });

  test('tensorRef rejects wrong packed size', () => {
    tensorRef('qint4', [3], Uint8Array.from([0x21, 0x03])); // 12 bits -> 2 bytes
    expect(() => tensorRef('qint4', [3], new Uint8Array(3))).toThrow(CanonError);
    expect(() => tensorRef('float32', [2], new Uint8Array(7))).toThrow(CanonError);
    expect(() => tensorRef('f32', [2], new Uint8Array(8))).toThrow(CanonError); // cowrie names only
  });

  test('bridge rejects malformed $tensor', () => {
    // An uppercase or short sha256 would fingerprint differently from the same
    // tensor written correctly: the bridge refuses to mint that second identity.
    const ok = { dtype: 'float32', shape: [1], sha256: '0'.repeat(64) };
    fromJsonLoose({ $tensor: ok });
    for (const bad of [
      { ...ok, sha256: 'A'.repeat(64) },
      { ...ok, sha256: '0'.repeat(63) },
      { ...ok, shape: [-1] },
      { ...ok, shape: [true] },
      { ...ok, dtype: 'f32' },
      { ...ok, dtype: 'constructor' },
      { dtype: 'float32', shape: [1] },
      { ...ok, extra: 1 },
      'x',
    ]) {
      expect(() => fromJsonLoose({ $tensor: bad })).toThrow('$tensor payload');
    }
  });
});
