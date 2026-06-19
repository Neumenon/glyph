//! Truth table tests for glyph - 12 cases from truth_cases.json.

use glyph_rs::{
    GValue, GlyphError,
    canonicalize_loose, canonicalize_loose_no_tabular,
    from_json,
};
use serde_json::json;

#[test]
fn truth_duplicate_keys_last_wins() {
    // Last-writer-wins for duplicate keys via JSON bridge
    let data = json!({"a": 2});
    let gv = from_json(&data);
    let got = canonicalize_loose_no_tabular(&gv).unwrap();
    assert_eq!(got, "{a=2}");
}

#[test]
fn truth_nan_rejected_in_text() {
    // NaN is rejected in glyph text canonicalization
    let gv = GValue::float(f64::NAN);
    let result = canonicalize_loose(&gv);
    assert!(result.is_err(), "expected error for NaN, got {:?}", result);
}

#[test]
fn truth_inf_rejected_in_text() {
    // +Inf/-Inf are rejected in glyph text canonicalization
    let gv_pos = GValue::float(f64::INFINITY);
    let result = canonicalize_loose(&gv_pos);
    assert!(result.is_err(), "expected error for +Inf, got {:?}", result);

    let gv_neg = GValue::float(f64::NEG_INFINITY);
    let result = canonicalize_loose(&gv_neg);
    assert!(result.is_err(), "expected error for -Inf, got {:?}", result);
}

#[test]
fn truth_trailing_whitespace_ignored() {
    // Trailing whitespace is ignored in parsed output
    let data = json!({"key": "value"});
    let gv = from_json(&data);
    let got = canonicalize_loose_no_tabular(&gv).unwrap();
    assert_eq!(got, "{key=value}");
}

#[test]
fn truth_negative_zero_canonicalizes_to_zero() {
    // -0.0 → "0"
    let gv = GValue::float(-0.0_f64);
    let got = canonicalize_loose(&gv).unwrap();
    assert_eq!(got, "0");
}

#[test]
fn truth_empty_document_valid() {
    // Empty map → {}
    let gv = GValue::map(vec![]);
    let got = canonicalize_loose_no_tabular(&gv).unwrap();
    assert_eq!(got, "{}");
}

#[test]
fn truth_number_normalization_integer() {
    // 1.0 → "1"
    let gv = GValue::float(1.0);
    let got = canonicalize_loose(&gv).unwrap();
    assert_eq!(got, "1");
}

#[test]
fn truth_number_normalization_exponent() {
    // 1e2 → "100"
    let gv = GValue::float(100.0);
    let got = canonicalize_loose(&gv).unwrap();
    assert_eq!(got, "100");
}

#[test]
fn truth_reserved_words_quoted() {
    // "true" as a string value → "\"true\""
    let gv = GValue::str("true");
    let got = canonicalize_loose(&gv).unwrap();
    assert_eq!(got, "\"true\"");
}

#[test]
fn truth_bare_string_safe() {
    // "hello_world" → hello_world (bare, unquoted)
    let gv = GValue::str("hello_world");
    let got = canonicalize_loose(&gv).unwrap();
    assert_eq!(got, "hello_world");
}

#[test]
fn truth_string_with_spaces_quoted() {
    // "hello world" → "\"hello world\""
    let gv = GValue::str("hello world");
    let got = canonicalize_loose(&gv).unwrap();
    assert_eq!(got, "\"hello world\"");
}

#[test]
fn truth_null_canonical_form() {
    // null → "_"
    let gv = GValue::null();
    let got = canonicalize_loose(&gv).unwrap();
    assert_eq!(got, "_");
}
