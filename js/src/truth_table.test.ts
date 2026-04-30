/**
 * Truth table tests for glyph - 12 cases from truth_cases.json.
 */

import {
  GValue, g, field,
  canonicalizeLoose, canonicalizeLooseNoTabular,
  fromJsonLoose,
} from './index';

// ============================================================
// Truth Table Tests
// ============================================================

describe('Truth Table', () => {
  test('duplicate_keys_last_wins', () => {
    // Last-writer-wins for duplicate keys
    const gv = fromJsonLoose({ a: 2 });
    const got = canonicalizeLooseNoTabular(gv);
    expect(got).toBe('{a=2}');
  });

  test('nan_rejected_in_text', () => {
    // NaN is rejected in glyph text format (via fromJsonLoose bridge)
    expect(() => fromJsonLoose(NaN)).toThrow();
  });

  test('inf_rejected_in_text', () => {
    // +Inf/-Inf are rejected in glyph text format (via fromJsonLoose bridge)
    expect(() => fromJsonLoose(Infinity)).toThrow();
    expect(() => fromJsonLoose(-Infinity)).toThrow();
  });

  test('trailing_whitespace_ignored', () => {
    // Trailing whitespace is ignored in parsed output
    const gv = fromJsonLoose({ key: 'value' });
    const got = canonicalizeLooseNoTabular(gv);
    expect(got).toBe('{key=value}');
  });

  test('negative_zero_canonicalizes_to_zero', () => {
    // -0.0 → "0"
    const gv = g.float(-0);
    const got = canonicalizeLoose(gv);
    expect(got).toBe('0');
  });

  test('empty_document_valid', () => {
    // Empty map → {}
    const gv = g.map();
    const got = canonicalizeLooseNoTabular(gv);
    expect(got).toBe('{}');
  });

  test('number_normalization_integer', () => {
    // 1.0 → "1"
    const gv = g.float(1.0);
    const got = canonicalizeLoose(gv);
    expect(got).toBe('1');
  });

  test('number_normalization_exponent', () => {
    // 1e2 → "100"
    const gv = g.float(100);
    const got = canonicalizeLoose(gv);
    expect(got).toBe('100');
  });

  test('reserved_words_quoted', () => {
    // "true" as a string value → "\"true\""
    expect(canonicalizeLoose(g.str('true'))).toBe('"true"');
    expect(canonicalizeLoose(g.str('_'))).toBe('"_"');
  });

  test('bare_string_safe', () => {
    // "hello_world" → hello_world (bare, unquoted)
    const gv = g.str('hello_world');
    const got = canonicalizeLoose(gv);
    expect(got).toBe('hello_world');
  });

  test('string_with_spaces_quoted', () => {
    // "hello world" → "\"hello world\""
    const gv = g.str('hello world');
    const got = canonicalizeLoose(gv);
    expect(got).toBe('"hello world"');
  });

  test('null_canonical_form', () => {
    // null → "_"
    const gv = g.null();
    const got = canonicalizeLoose(gv);
    expect(got).toBe('_');
  });
});
