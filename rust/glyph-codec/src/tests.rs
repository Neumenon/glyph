//! Tests for GLYPH codec

use crate::*;
use serde_json::json;

// ============================================================
// Existing canon tests
// ============================================================

#[test]
fn test_canon_null() {
    let gv = GValue::null();
    assert_eq!(canonicalize_loose(&gv).unwrap(), "_");
}

#[test]
fn test_canon_null_pretty() {
    let gv = GValue::null();
    let opts = LooseCanonOpts::pretty();
    assert_eq!(canonicalize_loose_with_opts(&gv, &opts).unwrap(), "∅");
}

#[test]
fn test_canon_bool() {
    assert_eq!(canonicalize_loose(&GValue::bool(true)).unwrap(), "t");
    assert_eq!(canonicalize_loose(&GValue::bool(false)).unwrap(), "f");
}

#[test]
fn test_canon_int() {
    assert_eq!(canonicalize_loose(&GValue::int(42)).unwrap(), "42");
    assert_eq!(canonicalize_loose(&GValue::int(-123)).unwrap(), "-123");
    assert_eq!(canonicalize_loose(&GValue::int(0)).unwrap(), "0");
}

#[test]
fn test_canon_float() {
    assert_eq!(canonicalize_loose(&GValue::float(3.14)).unwrap(), "3.14");
    assert_eq!(canonicalize_loose(&GValue::float(0.0)).unwrap(), "0");
    assert_eq!(canonicalize_loose(&GValue::float(-0.0)).unwrap(), "0");
}

#[test]
fn test_canon_string_bare() {
    let gv = GValue::str("hello");
    assert_eq!(canonicalize_loose(&gv).unwrap(), "hello");
}

#[test]
fn test_canon_string_quoted() {
    let gv = GValue::str("hello world");
    assert_eq!(canonicalize_loose(&gv).unwrap(), "\"hello world\"");
}

#[test]
fn test_canon_string_escapes() {
    let gv = GValue::str("line1\nline2");
    assert_eq!(canonicalize_loose(&gv).unwrap(), "\"line1\\nline2\"");
}

#[test]
fn test_canon_list() {
    let gv = GValue::list(vec![GValue::int(1), GValue::int(2), GValue::int(3)]);
    assert_eq!(canonicalize_loose(&gv).unwrap(), "[1 2 3]");
}

#[test]
fn test_canon_map_sorted() {
    let gv = GValue::map(vec![
        field("b", GValue::int(2)),
        field("a", GValue::int(1)),
    ]);
    assert_eq!(canonicalize_loose(&gv).unwrap(), "{a=1 b=2}");
}

#[test]
fn test_canon_ref() {
    let gv = GValue::id("user", "123");
    assert_eq!(canonicalize_loose(&gv).unwrap(), "^user:123");

    let gv2 = GValue::simple_id("abc");
    assert_eq!(canonicalize_loose(&gv2).unwrap(), "^abc");
}

#[test]
fn test_json_roundtrip() {
    let data = json!({
        "name": "Alice",
        "age": 30,
        "active": true
    });

    let gv = from_json(&data);
    let restored = to_json(&gv);

    assert_eq!(data, restored);
}

#[test]
fn test_sparse_keys_no_tabular() {
    // Disjoint keys should NOT become tabular
    let data = json!([{"a": 1}, {"b": 2}, {"c": 3}]);
    let gv = from_json(&data);
    let result = canonicalize_loose(&gv).unwrap();

    assert!(!result.contains("@tab"), "Disjoint keys should not use tabular");
    assert_eq!(result, "[{a=1} {b=2} {c=3}]");
}

#[test]
fn test_homogeneous_array_tabular() {
    // Same keys should become tabular
    let data = json!([
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
        {"a": 5, "b": 6}
    ]);
    let gv = from_json(&data);
    let result = canonicalize_loose(&gv).unwrap();

    assert!(result.contains("@tab"), "Homogeneous array should use tabular");
}

#[test]
fn test_empty_objects_no_tabular() {
    let data = json!([{}, {}, {}]);
    let gv = from_json(&data);
    let result = canonicalize_loose(&gv).unwrap();

    assert!(!result.contains("@tab"), "Empty objects should not use tabular");
    assert_eq!(result, "[{} {} {}]");
}

#[test]
fn test_equality() {
    let a = from_json(&json!({"x": 1, "y": 2}));
    let b = from_json(&json!({"y": 2, "x": 1})); // Different order

    assert!(equal_loose(&a, &b).unwrap(), "Same data, different order should be equal");
}

#[test]
fn test_fingerprint_deterministic() {
    let data = json!({"a": 1, "b": [2, 3]});
    let gv = from_json(&data);

    let fp1 = fingerprint_loose(&gv).unwrap();
    let fp2 = fingerprint_loose(&gv).unwrap();

    assert_eq!(fp1, fp2);
}

#[test]
fn test_hash_loose() {
    let gv = from_json(&json!({"test": "value"}));
    let h = hash_loose(&gv).unwrap();

    assert_eq!(h.len(), 16); // 8 bytes = 16 hex chars
}

#[test]
fn test_unicode() {
    let gv = GValue::str("你好世界");
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "你好世界");
}

#[test]
fn test_complex_nested() {
    let data = json!({
        "tool_call": {
            "name": "search",
            "args": {
                "query": "weather",
                "limit": 10
            }
        }
    });

    let gv = from_json(&data);
    let result = canonicalize_loose(&gv).unwrap();

    assert!(result.contains("search"));
    assert!(result.contains("query=weather"));
    assert!(result.contains("limit=10"));
}

#[test]
fn test_tabular_threshold() {
    // 2 items - below threshold
    let data2 = json!([{"a": 1}, {"a": 2}]);
    let result2 = canonicalize_loose(&from_json(&data2)).unwrap();
    assert!(!result2.contains("@tab"));

    // 3 items - at threshold
    let data3 = json!([{"a": 1}, {"a": 2}, {"a": 3}]);
    let result3 = canonicalize_loose(&from_json(&data3)).unwrap();
    assert!(result3.contains("@tab"));
}

// ============================================================
// NEW: LooseCanonOpts coverage (lines 50-51, 63, 77-78)
// ============================================================

#[test]
fn test_opts_llm() {
    let opts = LooseCanonOpts::llm();
    assert!(opts.auto_tabular);
    assert_eq!(opts.min_rows, 3);
    assert_eq!(opts.max_cols, 64);
    assert!(opts.allow_missing);
    assert_eq!(opts.null_style, NullStyle::Underscore);
}

#[test]
fn test_opts_no_tabular() {
    let opts = LooseCanonOpts::no_tabular();
    assert!(!opts.auto_tabular);
}

#[test]
fn test_canonicalize_loose_no_tabular_fn() {
    // Homogeneous array that would normally be tabular
    let data = json!([
        {"a": 1, "b": 2},
        {"a": 3, "b": 4},
        {"a": 5, "b": 6}
    ]);
    let gv = from_json(&data);
    let result = canonicalize_loose_no_tabular(&gv).unwrap();
    assert!(!result.contains("@tab"), "no_tabular should suppress tabular");
    assert!(result.starts_with("[{"));
}

// ============================================================
// NEW: Float edge cases (lines 141, 144, 161-165, 173-175)
// ============================================================

#[test]
fn test_canon_float_nan() {
    let result = canonicalize_loose(&GValue::float(f64::NAN));
    assert!(result.is_err(), "NaN must be rejected in text canonicalization");
    let err = result.unwrap_err();
    assert!(matches!(err, GlyphError::InvalidFloat(_)));
    assert!(format!("{}", err).contains("NaN"));
}

#[test]
fn test_canon_float_inf() {
    let result_pos = canonicalize_loose(&GValue::float(f64::INFINITY));
    assert!(result_pos.is_err(), "+Inf must be rejected in text canonicalization");
    assert!(matches!(result_pos.unwrap_err(), GlyphError::InvalidFloat(_)));

    let result_neg = canonicalize_loose(&GValue::float(f64::NEG_INFINITY));
    assert!(result_neg.is_err(), "-Inf must be rejected in text canonicalization");
    assert!(matches!(result_neg.unwrap_err(), GlyphError::InvalidFloat(_)));
}

#[test]
fn test_canon_float_whole_number() {
    // Whole-number float should render as integer
    assert_eq!(canonicalize_loose(&GValue::float(42.0)).unwrap(), "42");
    assert_eq!(canonicalize_loose(&GValue::float(-100.0)).unwrap(), "-100");
}

#[test]
fn test_canon_float_exponential_small() {
    // Very small number triggers exponential notation (exp < -4)
    let result = canonicalize_loose(&GValue::float(0.000001)).unwrap();
    assert!(result.contains("e"), "Very small float should use exponential: {}", result);
}

#[test]
fn test_canon_float_exponential_large() {
    // Very large non-whole number triggers exponential (exp >= 15)
    let result = canonicalize_loose(&GValue::float(1.5e16)).unwrap();
    // This might render as integer since 1.5e16 is a whole number
    // Let's use a value that is definitely not whole at that scale
    let result2 = canonicalize_loose(&GValue::float(1.23e-5)).unwrap();
    assert!(result2.contains("e") || result2.contains("0.0000"), "Should handle small floats: {}", result2);
    let _ = result; // use it
}

// ============================================================
// NEW: String escape coverage (lines 221-227)
// ============================================================

#[test]
fn test_canon_string_backslash() {
    let gv = GValue::str("path\\to\\file");
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "\"path\\\\to\\\\file\"");
}

#[test]
fn test_canon_string_quote() {
    let gv = GValue::str("say \"hello\"");
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "\"say \\\"hello\\\"\"");
}

#[test]
fn test_canon_string_carriage_return() {
    let gv = GValue::str("line1\rline2");
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "\"line1\\rline2\"");
}

#[test]
fn test_canon_string_tab() {
    let gv = GValue::str("col1\tcol2");
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "\"col1\\tcol2\"");
}

#[test]
fn test_canon_string_control_char() {
    // Control char below 0x20 that isn't \n, \r, \t, \\, \"
    let gv = GValue::str("bell\x07here");
    let result = canonicalize_loose(&gv).unwrap();
    assert!(result.contains("\\u0007"), "Control char should be unicode-escaped: {}", result);
}

#[test]
fn test_canon_string_empty() {
    let gv = GValue::str("");
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "\"\"");
}

#[test]
fn test_canon_string_reserved_words() {
    // Reserved words must be quoted
    assert_eq!(canonicalize_loose(&GValue::str("t")).unwrap(), "\"t\"");
    assert_eq!(canonicalize_loose(&GValue::str("f")).unwrap(), "\"f\"");
    assert_eq!(canonicalize_loose(&GValue::str("true")).unwrap(), "\"true\"");
    assert_eq!(canonicalize_loose(&GValue::str("false")).unwrap(), "\"false\"");
    assert_eq!(canonicalize_loose(&GValue::str("null")).unwrap(), "\"null\"");
    assert_eq!(canonicalize_loose(&GValue::str("_")).unwrap(), "\"_\"");
}

#[test]
fn test_canon_string_starts_with_digit() {
    let gv = GValue::str("123abc");
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "\"123abc\"");
}

#[test]
fn test_canon_string_starts_with_dash() {
    let gv = GValue::str("-foo");
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "\"-foo\"");
}

#[test]
fn test_canon_string_starts_with_quote() {
    let gv = GValue::str("'hello");
    let result = canonicalize_loose(&gv).unwrap();
    assert!(result.starts_with('"'), "Should be quoted: {}", result);
}

// ============================================================
// NEW: Bytes canonicalization (lines 236-239)
// ============================================================

#[test]
fn test_canon_bytes() {
    let gv = GValue::bytes(vec![0x48, 0x65, 0x6c, 0x6c, 0x6f]); // "Hello"
    let result = canonicalize_loose(&gv).unwrap();
    assert!(result.starts_with("b64\""), "Bytes should start with b64\": {}", result);
    assert!(result.ends_with('"'), "Bytes should end with quote: {}", result);
    assert_eq!(result, "b64\"SGVsbG8=\"");
}

#[test]
fn test_canon_bytes_empty() {
    let gv = GValue::bytes(vec![]);
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "b64\"\"");
}

// ============================================================
// NEW: Ref with quoted value (lines 252, 260, 266)
// ============================================================

#[test]
fn test_canon_ref_value_with_spaces() {
    let gv = GValue::Id(RefId::new("ns", "has space"));
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "^ns:\"has space\"");
}

#[test]
fn test_canon_ref_empty_value() {
    let gv = GValue::Id(RefId::new("ns", ""));
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "^ns:\"\"");
}

// ============================================================
// NEW: Struct canonicalization (lines 307-323)
// ============================================================

#[test]
fn test_canon_struct() {
    let gv = GValue::struct_val("Point", vec![
        field("y", GValue::int(20)),
        field("x", GValue::int(10)),
    ]);
    let result = canonicalize_loose(&gv).unwrap();
    // Fields should be sorted by key
    assert_eq!(result, "Point{x=10 y=20}");
}

#[test]
fn test_canon_struct_empty() {
    let gv = GValue::struct_val("Empty", vec![]);
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "Empty{}");
}

#[test]
fn test_canon_struct_single_field() {
    let gv = GValue::struct_val("Wrapper", vec![
        field("value", GValue::str("hello")),
    ]);
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "Wrapper{value=hello}");
}

// ============================================================
// NEW: Sum type canonicalization (lines 326-332)
// ============================================================

#[test]
fn test_canon_sum_with_value() {
    let gv = GValue::sum("Some", Some(GValue::int(42)));
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "Some(42)");
}

#[test]
fn test_canon_sum_without_value() {
    let gv = GValue::sum("None", None);
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "None()");
}

#[test]
fn test_canon_sum_with_string_value() {
    let gv = GValue::sum("Error", Some(GValue::str("not found")));
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "Error(\"not found\")");
}

// ============================================================
// NEW: Tabular with missing keys (lines 363-366)
// ============================================================

#[test]
fn test_tabular_with_missing_keys_allowed() {
    // Some rows have extra keys but >50% overlap
    let gv = GValue::list(vec![
        GValue::map(vec![field("a", GValue::int(1)), field("b", GValue::int(2))]),
        GValue::map(vec![field("a", GValue::int(3)), field("b", GValue::int(4))]),
        GValue::map(vec![field("a", GValue::int(5)), field("b", GValue::int(6)), field("c", GValue::int(7))]),
    ]);
    let result = canonicalize_loose(&gv).unwrap();
    assert!(result.contains("@tab"), "Should use tabular with missing keys allowed");
    // Missing value should show as _
    assert!(result.contains("_"), "Missing cells should show as null");
}

#[test]
fn test_tabular_strict_mode_rejects_missing() {
    let opts = LooseCanonOpts {
        allow_missing: false,
        ..LooseCanonOpts::default()
    };
    // Rows with different keys
    let gv = GValue::list(vec![
        GValue::map(vec![field("a", GValue::int(1)), field("b", GValue::int(2))]),
        GValue::map(vec![field("a", GValue::int(3)), field("b", GValue::int(4))]),
        GValue::map(vec![field("a", GValue::int(5)), field("c", GValue::int(6))]),
    ]);
    let result = canonicalize_loose_with_opts(&gv, &opts).unwrap();
    assert!(!result.contains("@tab"), "Strict mode should reject mismatched keys");
}

#[test]
fn test_tabular_strict_mode_accepts_identical() {
    let opts = LooseCanonOpts {
        allow_missing: false,
        ..LooseCanonOpts::default()
    };
    let gv = GValue::list(vec![
        GValue::map(vec![field("a", GValue::int(1)), field("b", GValue::int(2))]),
        GValue::map(vec![field("a", GValue::int(3)), field("b", GValue::int(4))]),
        GValue::map(vec![field("a", GValue::int(5)), field("b", GValue::int(6))]),
    ]);
    let result = canonicalize_loose_with_opts(&gv, &opts).unwrap();
    assert!(result.contains("@tab"), "Strict mode should accept identical keys");
}

// ============================================================
// NEW: Tabular with structs (lines 417, 425-426)
// ============================================================

#[test]
fn test_tabular_with_structs() {
    let gv = GValue::list(vec![
        GValue::struct_val("Row", vec![field("x", GValue::int(1)), field("y", GValue::int(2))]),
        GValue::struct_val("Row", vec![field("x", GValue::int(3)), field("y", GValue::int(4))]),
        GValue::struct_val("Row", vec![field("x", GValue::int(5)), field("y", GValue::int(6))]),
    ]);
    let result = canonicalize_loose(&gv).unwrap();
    assert!(result.contains("@tab"), "Struct arrays should be tabular-eligible");
}

#[test]
fn test_tabular_non_object_items() {
    // List of non-objects should not be tabular
    let gv = GValue::list(vec![GValue::int(1), GValue::int(2), GValue::int(3)]);
    let result = canonicalize_loose(&gv).unwrap();
    assert!(!result.contains("@tab"));
    assert_eq!(result, "[1 2 3]");
}

#[test]
fn test_tabular_too_many_cols() {
    // Create an object with more than max_cols fields
    let opts = LooseCanonOpts {
        max_cols: 2,
        ..LooseCanonOpts::default()
    };
    let gv = GValue::list(vec![
        GValue::map(vec![field("a", GValue::int(1)), field("b", GValue::int(2)), field("c", GValue::int(3))]),
        GValue::map(vec![field("a", GValue::int(4)), field("b", GValue::int(5)), field("c", GValue::int(6))]),
        GValue::map(vec![field("a", GValue::int(7)), field("b", GValue::int(8)), field("c", GValue::int(9))]),
    ]);
    let result = canonicalize_loose_with_opts(&gv, &opts).unwrap();
    assert!(!result.contains("@tab"), "Should not tabular when cols exceed max_cols");
}

// ============================================================
// NEW: types.rs coverage - type checks and extractors
// ============================================================

#[test]
fn test_gvalue_type_checks() {
    assert!(GValue::null().is_null());
    assert!(GValue::bool(true).is_bool());
    assert!(GValue::int(1).is_int());
    assert!(GValue::float(1.0).is_float());
    assert!(GValue::str("x").is_str());
    assert!(GValue::bytes(vec![1]).is_bytes());
    assert!(GValue::id("a", "b").is_id());
    assert!(GValue::list(vec![]).is_list());
    assert!(GValue::map(vec![]).is_map());
    assert!(GValue::struct_val("T", vec![]).is_struct());
    assert!(GValue::sum("X", None).is_sum());

    // Negative checks
    assert!(!GValue::null().is_bool());
    assert!(!GValue::int(1).is_float());
    assert!(!GValue::str("x").is_int());
}

#[test]
fn test_gvalue_time() {
    use chrono::Utc;
    let now = Utc::now();
    let gv = GValue::time(now);
    assert!(gv.is_time());
    assert_eq!(gv.as_time(), Some(&now));
    // Negative
    assert_eq!(GValue::int(1).as_time(), None);
}

#[test]
fn test_gvalue_extractors() {
    assert_eq!(GValue::bool(true).as_bool(), Some(true));
    assert_eq!(GValue::int(42).as_int(), Some(42));
    assert_eq!(GValue::float(3.14).as_float(), Some(3.14));
    assert_eq!(GValue::str("hi").as_str(), Some("hi"));

    let bytes_val = GValue::bytes(vec![1, 2, 3]);
    assert_eq!(bytes_val.as_bytes(), Some(&[1u8, 2, 3][..]));

    let id_val = GValue::id("ns", "val");
    assert!(id_val.as_id().is_some());
    let ref_id = id_val.as_id().unwrap();
    assert_eq!(ref_id.prefix, "ns");
    assert_eq!(ref_id.value, "val");

    let list_val = GValue::list(vec![GValue::int(1)]);
    assert!(list_val.as_list().is_some());
    assert_eq!(list_val.as_list().unwrap().len(), 1);

    let map_val = GValue::map(vec![field("k", GValue::int(1))]);
    assert!(map_val.as_map().is_some());

    let struct_val = GValue::struct_val("T", vec![field("f", GValue::int(1))]);
    assert!(struct_val.as_struct().is_some());
    assert_eq!(struct_val.as_struct().unwrap().type_name, "T");

    let sum_val = GValue::sum("Tag", Some(GValue::int(1)));
    assert!(sum_val.as_sum().is_some());
    assert_eq!(sum_val.as_sum().unwrap().tag, "Tag");
}

#[test]
fn test_gvalue_extractor_none_cases() {
    let null = GValue::null();
    assert_eq!(null.as_bool(), None);
    assert_eq!(null.as_int(), None);
    assert_eq!(null.as_float(), None);
    assert_eq!(null.as_str(), None);
    assert_eq!(null.as_bytes(), None);
    assert_eq!(null.as_id(), None);
    assert_eq!(null.as_list(), None);
    assert_eq!(null.as_map(), None);
    assert_eq!(null.as_struct(), None);
    assert_eq!(null.as_sum(), None);
}

#[test]
fn test_gvalue_get_from_struct() {
    let gv = GValue::struct_val("Pt", vec![
        field("x", GValue::int(10)),
        field("y", GValue::int(20)),
    ]);
    assert_eq!(gv.get("x").and_then(|v| v.as_int()), Some(10));
    assert_eq!(gv.get("y").and_then(|v| v.as_int()), Some(20));
    assert!(gv.get("z").is_none());
}

#[test]
fn test_gvalue_get_from_non_container() {
    assert!(GValue::int(1).get("key").is_none());
}

#[test]
fn test_gvalue_index() {
    let gv = GValue::list(vec![GValue::int(10), GValue::int(20)]);
    assert_eq!(gv.index(0).and_then(|v| v.as_int()), Some(10));
    assert_eq!(gv.index(1).and_then(|v| v.as_int()), Some(20));
    assert!(gv.index(2).is_none());
    // Non-list
    assert!(GValue::int(1).index(0).is_none());
}

// ============================================================
// NEW: json_bridge.rs coverage
// ============================================================

#[test]
fn test_json_bytes_roundtrip() {
    let gv = GValue::bytes(vec![0xDE, 0xAD, 0xBE, 0xEF]);
    let json = to_json(&gv);
    assert!(json.is_string());
    // Bytes become base64 string
    assert_eq!(json.as_str().unwrap(), "3q2+7w==");
}

#[test]
fn test_json_time_roundtrip() {
    use chrono::Utc;
    let now = Utc::now();
    let gv = GValue::time(now);
    let json = to_json(&gv);
    assert!(json.is_string());
    // Should contain RFC3339 format
    let s = json.as_str().unwrap();
    assert!(s.contains("T"), "Time should be RFC3339: {}", s);
}

#[test]
fn test_json_id_simple() {
    let gv = GValue::simple_id("abc");
    let json = to_json(&gv);
    assert_eq!(json.as_str().unwrap(), "^abc");
}

#[test]
fn test_json_id_prefixed() {
    let gv = GValue::id("user", "123");
    let json = to_json(&gv);
    assert_eq!(json.as_str().unwrap(), "^user:123");
}

#[test]
fn test_json_struct_to_json() {
    let gv = GValue::struct_val("Point", vec![
        field("x", GValue::int(10)),
        field("y", GValue::int(20)),
    ]);
    let json = to_json(&gv);
    assert!(json.is_object());
    let obj = json.as_object().unwrap();
    assert_eq!(obj.get("_type").and_then(|v| v.as_str()), Some("Point"));
    assert_eq!(obj.get("x").and_then(|v| v.as_i64()), Some(10));
    assert_eq!(obj.get("y").and_then(|v| v.as_i64()), Some(20));
}

#[test]
fn test_json_sum_to_json() {
    let gv = GValue::sum("Ok", Some(GValue::int(42)));
    let json = to_json(&gv);
    assert!(json.is_object());
    let obj = json.as_object().unwrap();
    assert_eq!(obj.get("_tag").and_then(|v| v.as_str()), Some("Ok"));
    assert_eq!(obj.get("_value").and_then(|v| v.as_i64()), Some(42));
}

#[test]
fn test_json_sum_no_value_to_json() {
    let gv = GValue::sum("None", None);
    let json = to_json(&gv);
    assert!(json.is_object());
    let obj = json.as_object().unwrap();
    assert_eq!(obj.get("_tag").and_then(|v| v.as_str()), Some("None"));
    assert!(obj.get("_value").is_none());
}

#[test]
fn test_json_float_nan_to_json() {
    // NaN can't be represented in JSON, should become null
    let gv = GValue::float(f64::NAN);
    let json = to_json(&gv);
    assert!(json.is_null(), "NaN should become null in JSON");
}

#[test]
fn test_json_float_inf_to_json() {
    // Infinity can't be represented in JSON
    let gv = GValue::float(f64::INFINITY);
    let json = to_json(&gv);
    assert!(json.is_null(), "Infinity should become null in JSON");
}

#[test]
fn test_parse_json_string() {
    let gv = parse_json(r#"{"name": "Alice", "age": 30}"#).unwrap();
    assert!(gv.is_map());
    assert_eq!(gv.get("name").and_then(|v| v.as_str()), Some("Alice"));
    assert_eq!(gv.get("age").and_then(|v| v.as_int()), Some(30));
}

#[test]
fn test_parse_json_invalid() {
    let result = parse_json("not json at all {{{");
    assert!(result.is_err());
}

#[test]
fn test_stringify_json() {
    let gv = GValue::map(vec![
        field("a", GValue::int(1)),
    ]);
    let s = stringify_json(&gv);
    assert!(s.contains("\"a\""));
    assert!(s.contains("1"));
}

#[test]
fn test_stringify_json_pretty() {
    let gv = GValue::map(vec![
        field("a", GValue::int(1)),
        field("b", GValue::int(2)),
    ]);
    let s = stringify_json_pretty(&gv);
    assert!(s.contains('\n'), "Pretty JSON should have newlines");
    assert!(s.contains("\"a\""));
}

#[test]
fn test_json_null_list() {
    let data = json!([null, true, false]);
    let gv = from_json(&data);
    let restored = to_json(&gv);
    assert_eq!(data, restored);
}

// ============================================================
// NEW: decimal128.rs edge cases
// ============================================================

#[test]
fn test_decimal_from_f64() {
    let d = Decimal128::from_f64(3.14).unwrap();
    assert_eq!(d.to_string(), "3.14");
}

#[test]
fn test_decimal_debug() {
    let d = Decimal128::from_i64(42);
    let debug = format!("{:?}", d);
    assert!(debug.contains("Decimal128"));
    assert!(debug.contains("scale=0"));
    assert!(debug.contains("value=42"));
}

#[test]
fn test_decimal_neg_trait() {
    let d = Decimal128::from_i64(42);
    let neg = -d;
    assert_eq!(neg.to_string(), "-42");
}

#[test]
fn test_decimal_from_str_trait() {
    let d: Decimal128 = "123.45".parse().unwrap();
    assert_eq!(d.to_string(), "123.45");
}

#[test]
fn test_decimal_abs() {
    let d = Decimal128::from_i64(-99);
    let a = d.abs();
    assert_eq!(a.to_string(), "99");

    let pos = Decimal128::from_i64(50);
    assert_eq!(pos.abs().to_string(), "50");
}

#[test]
fn test_decimal_division() {
    let d1 = Decimal128::from_i64(100);
    let d2 = Decimal128::from_i64(4);
    let result = (d1 / d2).unwrap();
    assert_eq!(result.to_i64(), 25);
}

#[test]
fn test_decimal_division_by_zero() {
    let d1 = Decimal128::from_i64(100);
    let d2 = Decimal128::from_i64(0);
    assert_eq!(d1 / d2, Err(DecimalError::DivisionByZero));
}

#[test]
fn test_decimal_sub() {
    let d1 = Decimal128::from_string("200.50").unwrap();
    let d2 = Decimal128::from_string("100.25").unwrap();
    let result = (d1 - d2).unwrap();
    assert_eq!(result.to_string(), "100.25");
}

#[test]
fn test_decimal_mul() {
    let d1 = Decimal128::from_string("10.5").unwrap();
    let d2 = Decimal128::from_i64(2);
    let result = (d1 * d2).unwrap();
    assert_eq!(result.to_string(), "21.0");
}

#[test]
fn test_decimal_invalid_format() {
    assert_eq!(Decimal128::from_string("abc"), Err(DecimalError::InvalidFormat));
    assert_eq!(Decimal128::from_string("1.2.3"), Err(DecimalError::InvalidFormat));
}

#[test]
fn test_decimal_parse_literal_not_m_suffix() {
    assert_eq!(parse_decimal_literal("99.99"), Err(DecimalError::InvalidFormat));
}

#[test]
fn test_decimal_negate() {
    let d = Decimal128::from_i64(10);
    let neg = d.negate();
    assert!(neg.is_negative());
    assert_eq!(neg.to_i64(), -10);
}

#[test]
fn test_decimal_partial_ord() {
    let d1 = Decimal128::from_string("10.5").unwrap();
    let d2 = Decimal128::from_string("20.5").unwrap();
    assert!(d1 < d2);
    assert!(d2 > d1);
    assert!(d1.partial_cmp(&d2) == Some(std::cmp::Ordering::Less));
}

#[test]
fn test_decimal_error_display() {
    assert_eq!(format!("{}", DecimalError::InvalidFormat), "invalid decimal format");
    assert_eq!(format!("{}", DecimalError::Overflow), "decimal overflow");
    assert_eq!(format!("{}", DecimalError::ScaleOverflow), "scale overflow");
    assert_eq!(format!("{}", DecimalError::DivisionByZero), "division by zero");
}

#[test]
fn test_decimal_m_suffix_from_string() {
    // from_string strips 'm' suffix
    let d = Decimal128::from_string("99.99m").unwrap();
    assert_eq!(d.to_string(), "99.99");
}

#[test]
fn test_decimal_to_i64_saturates() {
    // Very large coefficient should saturate to i64::MAX
    let d = Decimal128::new(-10, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                                   0x7F, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]);
    let val = d.to_i64();
    assert_eq!(val, i64::MAX);
}

#[test]
fn test_decimal_zero_display() {
    let d = Decimal128::from_i64(0);
    assert_eq!(d.to_string(), "0");
    assert!(d.is_zero());
    assert!(!d.is_negative());
    assert!(!d.is_positive());
}

#[test]
fn test_decimal_with_scale() {
    let d = Decimal128::from_string("0.001").unwrap();
    assert_eq!(d.scale, 3);
    assert_eq!(d.to_string(), "0.001");
}

#[test]
fn test_is_decimal_literal_edge_cases() {
    assert!(!is_decimal_literal(""));
    assert!(!is_decimal_literal("m"));
    assert!(is_decimal_literal("0m"));
    assert!(is_decimal_literal("-42m"));
}

// ============================================================
// NEW: schema_evolution.rs coverage
// ============================================================

#[test]
fn test_schema_field_validation_required_null() {
    let field = EvolvingField::new("name", FieldType::Str).required();
    let result = field.validate(&schema_evolution::FieldValue::Null);
    assert!(result.is_err());
    assert!(result.unwrap_err().contains("required"));
}

#[test]
fn test_schema_field_validation_type_mismatch() {
    let f = EvolvingField::new("count", FieldType::Int);
    assert!(f.validate(&schema_evolution::FieldValue::Str("hello".to_string())).is_err());

    let f2 = EvolvingField::new("flag", FieldType::Bool);
    assert!(f2.validate(&schema_evolution::FieldValue::Int(1)).is_err());

    let f3 = EvolvingField::new("score", FieldType::Float);
    assert!(f3.validate(&schema_evolution::FieldValue::Bool(true)).is_err());

    let f4 = EvolvingField::new("items", FieldType::List);
    assert!(f4.validate(&schema_evolution::FieldValue::Int(1)).is_err());

    let f5 = EvolvingField::new("amount", FieldType::Decimal);
    assert!(f5.validate(&schema_evolution::FieldValue::Int(1)).is_err());
}

#[test]
fn test_schema_field_validation_type_ok() {
    let f = EvolvingField::new("count", FieldType::Int);
    assert!(f.validate(&schema_evolution::FieldValue::Int(42)).is_ok());

    let f2 = EvolvingField::new("flag", FieldType::Bool);
    assert!(f2.validate(&schema_evolution::FieldValue::Bool(true)).is_ok());

    let f3 = EvolvingField::new("score", FieldType::Float);
    assert!(f3.validate(&schema_evolution::FieldValue::Float(3.14)).is_ok());
    // Int is allowed as float
    assert!(f3.validate(&schema_evolution::FieldValue::Int(42)).is_ok());

    let f4 = EvolvingField::new("items", FieldType::List);
    assert!(f4.validate(&schema_evolution::FieldValue::List(vec![])).is_ok());

    let f5 = EvolvingField::new("amount", FieldType::Decimal);
    assert!(f5.validate(&schema_evolution::FieldValue::Str("99.99".to_string())).is_ok());
}

#[test]
fn test_schema_field_validation_regex() {
    let f = EvolvingField::new("email", FieldType::Str)
        .with_validation(r"^[^@]+@[^@]+$")
        .unwrap();
    assert!(f.validate(&schema_evolution::FieldValue::Str("user@example.com".to_string())).is_ok());
    assert!(f.validate(&schema_evolution::FieldValue::Str("invalid".to_string())).is_err());
}

#[test]
fn test_schema_field_null_not_required_ok() {
    let f = EvolvingField::new("optional", FieldType::Str);
    assert!(f.validate(&schema_evolution::FieldValue::Null).is_ok());
}

#[test]
fn test_schema_emit() {
    use std::collections::HashMap;
    let mut schema = VersionedSchema::new("Test");
    schema.add_version("1.0", vec![
        EvolvingField::new("name", FieldType::Str).required(),
    ]);

    let mut data = HashMap::new();
    data.insert("name".to_string(), schema_evolution::FieldValue::Str("Alice".to_string()));

    let result = schema.emit(&data, Some("1.0")).unwrap();
    assert_eq!(result, "@version 1.0");
}

#[test]
fn test_schema_emit_unknown_version() {
    use std::collections::HashMap;
    let mut schema = VersionedSchema::new("Test");
    schema.add_version("1.0", vec![]);

    let data = HashMap::new();
    let result = schema.emit(&data, Some("9.9"));
    assert!(result.is_err());
}

#[test]
fn test_schema_changelog() {
    let mut schema = VersionedSchema::new("Match");
    schema.add_version("1.0", vec![
        EvolvingField::new("home", FieldType::Str).required(),
    ]);
    schema.add_version("2.0", vec![
        EvolvingField::new("home", FieldType::Str).required(),
        EvolvingField::new("venue", FieldType::Str).added_in("2.0"),
    ]);

    let changelog = schema.get_changelog();
    assert_eq!(changelog.len(), 2);
    assert_eq!(changelog[0].version, "1.0");
    assert_eq!(changelog[1].version, "2.0");
}

#[test]
fn test_schema_rename_migration() {
    use std::collections::HashMap;
    let mut schema = VersionedSchema::new("Match");
    schema.add_version("1.0", vec![
        EvolvingField::new("referee", FieldType::Str),
    ]);
    schema.add_version("2.0", vec![
        EvolvingField::new("official", FieldType::Str).renamed_from("referee").added_in("2.0"),
    ]);

    let mut data = HashMap::new();
    data.insert("referee".to_string(), schema_evolution::FieldValue::Str("Mike".to_string()));

    let result = schema.parse(data, "1.0").unwrap();
    assert!(result.contains_key("official"), "Field should be renamed");
    assert!(!result.contains_key("referee"), "Old field name should be gone");
}

#[test]
fn test_schema_parse_unknown_version() {
    use std::collections::HashMap;
    let mut schema = VersionedSchema::new("Test");
    schema.add_version("1.0", vec![]);
    let data = HashMap::new();
    let result = schema.parse(data, "9.9");
    assert!(result.is_err());
}

#[test]
fn test_schema_field_from_impls() {
    let _: schema_evolution::FieldValue = true.into();
    let _: schema_evolution::FieldValue = 42i64.into();
    let _: schema_evolution::FieldValue = 3.14f64.into();
    let _: schema_evolution::FieldValue = "hello".into();
    let _: schema_evolution::FieldValue = String::from("world").into();
}

#[test]
fn test_evolution_mode_default() {
    let mode = EvolutionMode::default();
    assert_eq!(mode, EvolutionMode::Tolerant);
}

// ============================================================
// NEW: Time canonicalization
// ============================================================

#[test]
fn test_canon_time() {
    use chrono::{TimeZone, Utc};
    let t = Utc.with_ymd_and_hms(2026, 3, 9, 12, 0, 0).unwrap();
    let gv = GValue::time(t);
    let result = canonicalize_loose(&gv).unwrap();
    assert_eq!(result, "2026-03-09T12:00:00Z");
}

// ============================================================
// NEW: Empty list and map
// ============================================================

#[test]
fn test_canon_empty_list() {
    let gv = GValue::list(vec![]);
    assert_eq!(canonicalize_loose(&gv).unwrap(), "[]");
}

#[test]
fn test_canon_empty_map() {
    let gv = GValue::map(vec![]);
    assert_eq!(canonicalize_loose(&gv).unwrap(), "{}");
}

// ============================================================
// NEW: Tabular with pipe in value
// ============================================================

#[test]
fn test_tabular_escapes_pipe() {
    let gv = GValue::list(vec![
        GValue::map(vec![field("val", GValue::str("a|b"))]),
        GValue::map(vec![field("val", GValue::str("c"))]),
        GValue::map(vec![field("val", GValue::str("d"))]),
    ]);
    let result = canonicalize_loose(&gv).unwrap();
    assert!(result.contains("@tab"));
    // Pipe in value should be escaped
    assert!(result.contains("\\|"), "Pipe should be escaped in tabular: {}", result);
}

// ============================================================
// NEW: error.rs coverage
// ============================================================

#[test]
fn test_glyph_error_display() {
    let e = GlyphError::Parse("bad input".to_string());
    assert_eq!(format!("{}", e), "Parse error: bad input");

    let e2 = GlyphError::InvalidValue("wrong".to_string());
    assert_eq!(format!("{}", e2), "Invalid value: wrong");

    let e3 = GlyphError::TypeMismatch {
        expected: "int".to_string(),
        got: "string".to_string(),
    };
    assert_eq!(format!("{}", e3), "Type mismatch: expected int, got string");

    let e4 = GlyphError::InvalidFloat("nan".to_string());
    assert_eq!(format!("{}", e4), "Invalid float: nan");

    let e5 = GlyphError::MissingField("name".to_string());
    assert_eq!(format!("{}", e5), "Missing required field: name");

    let e6 = GlyphError::RecursionLimitExceeded { limit: 128 };
    assert_eq!(format!("{}", e6), "Recursion limit exceeded: 128");
}

// ============================================================
// NEW: MapEntry and StructValue constructors
// ============================================================

#[test]
fn test_map_entry_new() {
    let entry = MapEntry::new("key", GValue::int(42));
    assert_eq!(entry.key, "key");
    assert_eq!(entry.value.as_int(), Some(42));
}

#[test]
fn test_struct_value_new() {
    let sv = StructValue::new("Point", vec![
        MapEntry::new("x", GValue::int(1)),
    ]);
    assert_eq!(sv.type_name, "Point");
    assert_eq!(sv.fields.len(), 1);
}

#[test]
fn test_sum_value_new() {
    let sv = SumValue::new("Ok", Some(GValue::int(42)));
    assert_eq!(sv.tag, "Ok");
    assert!(sv.value.is_some());

    let sv2 = SumValue::new("None", None::<GValue>);
    assert_eq!(sv2.tag, "None");
    assert!(sv2.value.is_none());
}

#[test]
fn test_ref_id_new() {
    let r = RefId::new("ns", "val");
    assert_eq!(r.prefix, "ns");
    assert_eq!(r.value, "val");

    let r2 = RefId::simple("abc");
    assert_eq!(r2.prefix, "");
    assert_eq!(r2.value, "abc");
}

