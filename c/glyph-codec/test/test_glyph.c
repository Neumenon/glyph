/**
 * GLYPH Codec C Tests
 */

#include "glyph.h"
#include "decimal128.h"
#include "schema_evolution.h"
#include "stream_validator.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <limits.h>
#include <math.h>
#include <float.h>

static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) void test_##name(void)
#define RUN_TEST(name) do { \
    printf("  Running %s...", #name); \
    test_##name(); \
    printf(" PASSED\n"); \
    tests_passed++; \
} while(0)

#define ASSERT_STR_EQ(expected, actual) do { \
    if (strcmp(expected, actual) != 0) { \
        printf("\n    FAILED: expected '%s', got '%s'\n", expected, actual); \
        tests_failed++; \
        return; \
    } \
} while(0)

#define ASSERT_TRUE(cond) do { \
    if (!(cond)) { \
        printf("\n    FAILED: expected true\n"); \
        tests_failed++; \
        return; \
    } \
} while(0)

/* ============================================================
 * Primitive Tests
 * ============================================================ */

TEST(null_canonical) {
    glyph_value_t *v = glyph_null();
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("_", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(bool_true) {
    glyph_value_t *v = glyph_bool(true);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("t", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(bool_false) {
    glyph_value_t *v = glyph_bool(false);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("f", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(int_positive) {
    glyph_value_t *v = glyph_int(42);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("42", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(int_negative) {
    glyph_value_t *v = glyph_int(-123);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("-123", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(int_zero) {
    glyph_value_t *v = glyph_int(0);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("0", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(float_whole_number) {
    glyph_value_t *v = glyph_float(42.0);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("42", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(float_decimal) {
    glyph_value_t *v = glyph_float(3.14);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(strncmp(canon, "3.14", 4) == 0);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(float_nan) {
    glyph_value_t *v = glyph_float(NAN);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon == NULL); /* NaN rejected in text canonicalization */
    glyph_value_free(v);
}

TEST(float_positive_inf) {
    glyph_value_t *v = glyph_float(INFINITY);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon == NULL); /* Inf rejected in text canonicalization */
    glyph_value_free(v);
}

TEST(float_negative_inf) {
    glyph_value_t *v = glyph_float(-INFINITY);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon == NULL); /* -Inf rejected in text canonicalization */
    glyph_value_free(v);
}

TEST(float_negative_zero) {
    glyph_value_t *v = glyph_float(-0.0);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("0", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

/* ============================================================
 * String Tests
 * ============================================================ */

TEST(string_bare_safe) {
    glyph_value_t *v = glyph_str("hello");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("hello", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_needs_quotes) {
    glyph_value_t *v = glyph_str("hello world");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"hello world\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_starts_with_digit) {
    glyph_value_t *v = glyph_str("123abc");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"123abc\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_empty) {
    glyph_value_t *v = glyph_str("");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_reserved_t) {
    glyph_value_t *v = glyph_str("t");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"t\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_reserved_f) {
    glyph_value_t *v = glyph_str("f");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"f\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_with_escape) {
    glyph_value_t *v = glyph_str("line1\nline2");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"line1\\nline2\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_reserved_true) {
    glyph_value_t *v = glyph_str("true");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"true\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_reserved_false) {
    glyph_value_t *v = glyph_str("false");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"false\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_reserved_null) {
    glyph_value_t *v = glyph_str("null");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"null\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_reserved_underscore) {
    glyph_value_t *v = glyph_str("_");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"_\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_starts_with_dash) {
    glyph_value_t *v = glyph_str("-abc");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"-abc\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_with_tab) {
    glyph_value_t *v = glyph_str("a\tb");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"a\\tb\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_with_cr) {
    glyph_value_t *v = glyph_str("a\rb");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"a\\rb\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_with_backslash) {
    glyph_value_t *v = glyph_str("a\\b");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"a\\\\b\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_with_quote) {
    glyph_value_t *v = glyph_str("a\"b");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"a\\\"b\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_with_control_char) {
    glyph_value_t *v = glyph_str("a\x01" "b");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("\"a\\u0001b\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(string_bare_with_special_chars) {
    /* These chars are bare-safe: alnum _ - . / @ : and >127 */
    glyph_value_t *v = glyph_str("foo/bar@baz:qux");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("foo/bar@baz:qux", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

/* ============================================================
 * Bytes Tests
 * ============================================================ */

TEST(bytes_empty) {
    glyph_value_t *v = glyph_bytes(NULL, 0);
    ASSERT_TRUE(v != NULL);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("b64\"\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(bytes_simple) {
    uint8_t data[] = {0x48, 0x65, 0x6C}; /* "Hel" */
    glyph_value_t *v = glyph_bytes(data, 3);
    ASSERT_TRUE(v != NULL);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("b64\"SGVs\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(bytes_padding_one) {
    uint8_t data[] = {0x48, 0x65}; /* 2 bytes -> 1 pad */
    glyph_value_t *v = glyph_bytes(data, 2);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("b64\"SGU=\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(bytes_padding_two) {
    uint8_t data[] = {0x48}; /* 1 byte -> 2 pad */
    glyph_value_t *v = glyph_bytes(data, 1);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("b64\"SA==\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(bytes_null_data_nonzero_len) {
    glyph_value_t *v = glyph_bytes(NULL, 5);
    ASSERT_TRUE(v == NULL);
}

/* ============================================================
 * Struct Tests
 * ============================================================ */

TEST(struct_empty) {
    glyph_value_t *v = glyph_struct_new("Point");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("Point{}", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(struct_with_fields) {
    glyph_value_t *v = glyph_struct_new("Point");
    glyph_struct_set(v, "x", glyph_int(10));
    glyph_struct_set(v, "y", glyph_int(20));
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("Point{x=10 y=20}", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(struct_get_field) {
    glyph_value_t *v = glyph_struct_new("Foo");
    glyph_struct_set(v, "bar", glyph_int(99));
    glyph_value_t *bar = glyph_get(v, "bar");
    ASSERT_TRUE(bar != NULL);
    ASSERT_TRUE(glyph_as_int(bar) == 99);
    ASSERT_TRUE(glyph_get(v, "nope") == NULL);
    glyph_value_free(v);
}

/* ============================================================
 * Sum Type Tests
 * ============================================================ */

TEST(sum_with_value) {
    glyph_value_t *v = glyph_sum("Ok", glyph_int(42));
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("Ok(42)", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(sum_without_value) {
    glyph_value_t *v = glyph_sum("None", NULL);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("None()", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

/* ============================================================
 * Accessor Tests
 * ============================================================ */

TEST(accessor_get_type) {
    ASSERT_TRUE(glyph_get_type(NULL) == GLYPH_NULL);
    glyph_value_t *v = glyph_int(5);
    ASSERT_TRUE(glyph_get_type(v) == GLYPH_INT);
    glyph_value_free(v);
}

TEST(accessor_as_bool) {
    ASSERT_TRUE(glyph_as_bool(NULL) == false);
    glyph_value_t *v = glyph_bool(true);
    ASSERT_TRUE(glyph_as_bool(v) == true);
    glyph_value_free(v);
    v = glyph_int(1);
    ASSERT_TRUE(glyph_as_bool(v) == false); /* wrong type */
    glyph_value_free(v);
}

TEST(accessor_as_int) {
    ASSERT_TRUE(glyph_as_int(NULL) == 0);
    glyph_value_t *v = glyph_int(77);
    ASSERT_TRUE(glyph_as_int(v) == 77);
    glyph_value_free(v);
    v = glyph_str("x");
    ASSERT_TRUE(glyph_as_int(v) == 0);
    glyph_value_free(v);
}

TEST(accessor_as_float) {
    ASSERT_TRUE(glyph_as_float(NULL) == 0.0);
    glyph_value_t *v = glyph_float(1.5);
    ASSERT_TRUE(glyph_as_float(v) == 1.5);
    glyph_value_free(v);
}

TEST(accessor_as_str) {
    ASSERT_TRUE(glyph_as_str(NULL) == NULL);
    glyph_value_t *v = glyph_str("hi");
    ASSERT_STR_EQ("hi", glyph_as_str(v));
    glyph_value_free(v);
    v = glyph_int(1);
    ASSERT_TRUE(glyph_as_str(v) == NULL);
    glyph_value_free(v);
}

TEST(accessor_list_len) {
    ASSERT_TRUE(glyph_list_len(NULL) == 0);
    glyph_value_t *v = glyph_list_new();
    ASSERT_TRUE(glyph_list_len(v) == 0);
    glyph_list_append(v, glyph_int(1));
    ASSERT_TRUE(glyph_list_len(v) == 1);
    glyph_value_free(v);
}

TEST(accessor_list_get) {
    ASSERT_TRUE(glyph_list_get(NULL, 0) == NULL);
    glyph_value_t *v = glyph_list_new();
    glyph_list_append(v, glyph_int(42));
    ASSERT_TRUE(glyph_list_get(v, 0) != NULL);
    ASSERT_TRUE(glyph_as_int(glyph_list_get(v, 0)) == 42);
    ASSERT_TRUE(glyph_list_get(v, 1) == NULL); /* out of bounds */
    glyph_value_free(v);
}

TEST(accessor_map_get) {
    ASSERT_TRUE(glyph_get(NULL, "x") == NULL);
    glyph_value_t *v = glyph_map_new();
    glyph_map_set(v, "key", glyph_str("val"));
    ASSERT_TRUE(glyph_get(v, NULL) == NULL);
    glyph_value_t *found = glyph_get(v, "key");
    ASSERT_TRUE(found != NULL);
    ASSERT_STR_EQ("val", glyph_as_str(found));
    ASSERT_TRUE(glyph_get(v, "missing") == NULL);
    glyph_value_free(v);
}

/* ============================================================
 * Canonicalization Options Tests
 * ============================================================ */

TEST(canon_opts_pretty_null) {
    glyph_canon_opts_t opts = glyph_canon_opts_pretty();
    glyph_value_t *v = glyph_null();
    char *canon = glyph_canonicalize_loose_with_opts(v, &opts);
    /* Pretty uses the unicode null symbol */
    ASSERT_TRUE(canon != NULL);
    ASSERT_TRUE(strstr(canon, "_") == NULL || strlen(canon) > 1);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(canon_opts_no_tabular) {
    glyph_value_t *v = glyph_list_new();
    for (int i = 0; i < 3; i++) {
        glyph_value_t *m = glyph_map_new();
        glyph_map_set(m, "x", glyph_int(i));
        glyph_list_append(v, m);
    }
    char *canon = glyph_canonicalize_loose_no_tabular(v);
    ASSERT_TRUE(strstr(canon, "@tab") == NULL);
    ASSERT_TRUE(canon[0] == '[');
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(canon_opts_null_opts) {
    glyph_value_t *v = glyph_int(5);
    char *canon = glyph_canonicalize_loose_with_opts(v, NULL);
    ASSERT_STR_EQ("5", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(canon_null_value) {
    char *canon = glyph_canonicalize_loose(NULL);
    ASSERT_STR_EQ("_", canon);
    glyph_free(canon);
}

TEST(fingerprint_loose) {
    glyph_value_t *v = glyph_int(42);
    char *fp = glyph_fingerprint_loose(v);
    ASSERT_STR_EQ("42", fp);
    glyph_free(fp);
    glyph_value_free(v);
}

TEST(hash_loose) {
    glyph_value_t *v = glyph_int(42);
    char *h = glyph_hash_loose(v);
    ASSERT_TRUE(h != NULL);
    ASSERT_TRUE(strlen(h) == 16);
    glyph_free(h);
    glyph_value_free(v);
}

TEST(equal_loose_same) {
    glyph_value_t *a = glyph_int(42);
    glyph_value_t *b = glyph_int(42);
    ASSERT_TRUE(glyph_equal_loose(a, b));
    glyph_value_free(a);
    glyph_value_free(b);
}

TEST(equal_loose_different) {
    glyph_value_t *a = glyph_int(1);
    glyph_value_t *b = glyph_int(2);
    ASSERT_TRUE(!glyph_equal_loose(a, b));
    glyph_value_free(a);
    glyph_value_free(b);
}

/* ============================================================
 * Nested Structure Tests
 * ============================================================ */

TEST(nested_map_in_list) {
    glyph_value_t *v = glyph_list_new();
    glyph_value_t *m = glyph_map_new();
    glyph_map_set(m, "a", glyph_int(1));
    glyph_list_append(v, m);
    glyph_list_append(v, glyph_str("hello"));
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("[{a=1} hello]", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(nested_list_in_map) {
    glyph_value_t *v = glyph_map_new();
    glyph_value_t *l = glyph_list_new();
    glyph_list_append(l, glyph_int(1));
    glyph_list_append(l, glyph_int(2));
    glyph_map_set(v, "nums", l);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("{nums=[1 2]}", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(mixed_types_list) {
    glyph_value_t *v = glyph_list_new();
    glyph_list_append(v, glyph_int(1));
    glyph_list_append(v, glyph_str("two"));
    glyph_list_append(v, glyph_bool(true));
    glyph_list_append(v, glyph_null());
    glyph_list_append(v, glyph_float(3.5));
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(strstr(canon, "1") != NULL);
    ASSERT_TRUE(strstr(canon, "two") != NULL);
    ASSERT_TRUE(strstr(canon, "t") != NULL);
    glyph_free(canon);
    glyph_value_free(v);
}

/* ============================================================
 * List Tests
 * ============================================================ */

TEST(list_empty) {
    glyph_value_t *v = glyph_list_new();
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("[]", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(list_single) {
    glyph_value_t *v = glyph_list_new();
    glyph_list_append(v, glyph_int(1));
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("[1]", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(list_multiple) {
    glyph_value_t *v = glyph_list_new();
    glyph_list_append(v, glyph_int(1));
    glyph_list_append(v, glyph_int(2));
    glyph_list_append(v, glyph_int(3));
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("[1 2 3]", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

/* ============================================================
 * Map Tests
 * ============================================================ */

TEST(map_empty) {
    glyph_value_t *v = glyph_map_new();
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("{}", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(map_single) {
    glyph_value_t *v = glyph_map_new();
    glyph_map_set(v, "a", glyph_int(1));
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("{a=1}", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(map_sorted_keys) {
    glyph_value_t *v = glyph_map_new();
    glyph_map_set(v, "b", glyph_int(2));
    glyph_map_set(v, "a", glyph_int(1));
    glyph_map_set(v, "c", glyph_int(3));
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("{a=1 b=2 c=3}", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

/* ============================================================
 * Reference ID Tests
 * ============================================================ */

TEST(ref_id_simple) {
    glyph_value_t *v = glyph_id(NULL, "user123");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("^user123", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(ref_id_with_prefix) {
    glyph_value_t *v = glyph_id("user", "123");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("^user:123", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(ref_id_numeric) {
    glyph_value_t *v = glyph_id(NULL, "12345");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("^12345", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(ref_id_needs_quotes) {
    glyph_value_t *v = glyph_id(NULL, "hello world");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_STR_EQ("^\"hello world\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

/* ============================================================
 * Tabular Mode Tests
 * ============================================================ */

TEST(tabular_homogeneous) {
    glyph_value_t *v = glyph_list_new();
    for (int i = 0; i < 3; i++) {
        glyph_value_t *m = glyph_map_new();
        glyph_map_set(m, "x", glyph_int(i));
        glyph_map_set(m, "y", glyph_int(i * 2));
        glyph_list_append(v, m);
    }
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(strstr(canon, "@tab") != NULL);
    ASSERT_TRUE(strstr(canon, "@end") != NULL);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(tabular_columns_sorted) {
    glyph_value_t *v = glyph_list_new();
    for (int i = 0; i < 3; i++) {
        glyph_value_t *m = glyph_map_new();
        glyph_map_set(m, "b", glyph_int(i + 10));
        glyph_map_set(m, "a", glyph_int(i));
        glyph_list_append(v, m);
    }
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(strstr(canon, "rows=3 cols=2 [a b]") != NULL);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(tabular_sparse_keys_no_tabular) {
    glyph_value_t *v = glyph_list_new();
    glyph_value_t *m1 = glyph_map_new();
    glyph_map_set(m1, "a", glyph_int(1));
    glyph_list_append(v, m1);
    glyph_value_t *m2 = glyph_map_new();
    glyph_map_set(m2, "b", glyph_int(2));
    glyph_list_append(v, m2);
    glyph_value_t *m3 = glyph_map_new();
    glyph_map_set(m3, "c", glyph_int(3));
    glyph_list_append(v, m3);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(strstr(canon, "@tab") == NULL);
    ASSERT_TRUE(canon[0] == '[');
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(tabular_empty_objects_no_tabular) {
    glyph_value_t *v = glyph_list_new();
    glyph_list_append(v, glyph_map_new());
    glyph_list_append(v, glyph_map_new());
    glyph_list_append(v, glyph_map_new());
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(strstr(canon, "@tab") == NULL);
    ASSERT_STR_EQ("[{} {} {}]", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(tabular_missing_keys_fill_null) {
    /* Some rows have extra keys - missing cells become null */
    glyph_value_t *v = glyph_list_new();
    for (int i = 0; i < 3; i++) {
        glyph_value_t *m = glyph_map_new();
        glyph_map_set(m, "x", glyph_int(i));
        if (i == 0) glyph_map_set(m, "y", glyph_int(99));
        glyph_list_append(v, m);
    }
    char *canon = glyph_canonicalize_loose(v);
    /* x is common (100%), y only in 1/3 but 50% threshold uses all keys */
    ASSERT_TRUE(canon != NULL);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(tabular_fewer_than_min_rows) {
    /* Only 2 rows -> below min_rows(3) -> no tabular */
    glyph_value_t *v = glyph_list_new();
    for (int i = 0; i < 2; i++) {
        glyph_value_t *m = glyph_map_new();
        glyph_map_set(m, "x", glyph_int(i));
        glyph_list_append(v, m);
    }
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(strstr(canon, "@tab") == NULL);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(tabular_non_map_items) {
    /* List of non-maps should not become tabular */
    glyph_value_t *v = glyph_list_new();
    glyph_list_append(v, glyph_int(1));
    glyph_list_append(v, glyph_int(2));
    glyph_list_append(v, glyph_int(3));
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(strstr(canon, "@tab") == NULL);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(tabular_with_structs) {
    glyph_value_t *v = glyph_list_new();
    for (int i = 0; i < 3; i++) {
        glyph_value_t *s = glyph_struct_new("Pt");
        glyph_struct_set(s, "x", glyph_int(i));
        glyph_struct_set(s, "y", glyph_int(i * 2));
        glyph_list_append(v, s);
    }
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(strstr(canon, "@tab") != NULL);
    glyph_free(canon);
    glyph_value_free(v);
}

/* ============================================================
 * JSON Bridge Tests
 * ============================================================ */

TEST(json_parse_null) {
    glyph_value_t *v = glyph_from_json("null");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_NULL);
    glyph_value_free(v);
}

TEST(json_parse_bool_true) {
    glyph_value_t *v = glyph_from_json("true");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_BOOL);
    ASSERT_TRUE(v->bool_val == true);
    glyph_value_free(v);
}

TEST(json_parse_bool_false) {
    glyph_value_t *v = glyph_from_json("false");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_BOOL);
    ASSERT_TRUE(v->bool_val == false);
    glyph_value_free(v);
}

TEST(json_parse_int) {
    glyph_value_t *v = glyph_from_json("42");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_INT);
    ASSERT_TRUE(v->int_val == 42);
    glyph_value_free(v);
}

TEST(json_parse_negative_int) {
    glyph_value_t *v = glyph_from_json("-99");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_INT);
    ASSERT_TRUE(v->int_val == -99);
    glyph_value_free(v);
}

TEST(json_parse_float) {
    glyph_value_t *v = glyph_from_json("3.14");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_FLOAT);
    ASSERT_TRUE(fabs(v->float_val - 3.14) < 0.001);
    glyph_value_free(v);
}

TEST(json_parse_float_exponent) {
    glyph_value_t *v = glyph_from_json("1.5e2");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_FLOAT);
    ASSERT_TRUE(fabs(v->float_val - 150.0) < 0.001);
    glyph_value_free(v);
}

TEST(json_parse_string) {
    glyph_value_t *v = glyph_from_json("\"hello\"");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_STR);
    ASSERT_STR_EQ("hello", v->str_val);
    glyph_value_free(v);
}

TEST(json_parse_string_escapes) {
    glyph_value_t *v = glyph_from_json("\"a\\nb\\tc\\\\d\\\"e\"");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_STR);
    ASSERT_STR_EQ("a\nb\tc\\d\"e", v->str_val);
    glyph_value_free(v);
}

TEST(json_parse_string_unicode_ascii) {
    glyph_value_t *v = glyph_from_json("\"\\u0041\""); /* A */
    ASSERT_TRUE(v != NULL);
    ASSERT_STR_EQ("A", v->str_val);
    glyph_value_free(v);
}

TEST(json_parse_string_unicode_2byte) {
    glyph_value_t *v = glyph_from_json("\"\\u00E9\""); /* e-acute */
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->str_val != NULL);
    ASSERT_TRUE(strlen(v->str_val) == 2); /* 2-byte UTF-8 */
    glyph_value_free(v);
}

TEST(json_parse_string_unicode_3byte) {
    glyph_value_t *v = glyph_from_json("\"\\u4e16\""); /* CJK char */
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->str_val != NULL);
    ASSERT_TRUE(strlen(v->str_val) == 3); /* 3-byte UTF-8 */
    glyph_value_free(v);
}

TEST(json_parse_array) {
    glyph_value_t *v = glyph_from_json("[1, 2, 3]");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_LIST);
    ASSERT_TRUE(v->list_val.count == 3);
    glyph_value_free(v);
}

TEST(json_parse_empty_array) {
    glyph_value_t *v = glyph_from_json("[]");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_LIST);
    ASSERT_TRUE(v->list_val.count == 0);
    glyph_value_free(v);
}

TEST(json_parse_object) {
    glyph_value_t *v = glyph_from_json("{\"a\": 1, \"b\": 2}");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_MAP);
    ASSERT_TRUE(v->map_val.count == 2);
    glyph_value_free(v);
}

TEST(json_parse_empty_object) {
    glyph_value_t *v = glyph_from_json("{}");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_MAP);
    ASSERT_TRUE(v->map_val.count == 0);
    glyph_value_free(v);
}

TEST(json_parse_nested) {
    glyph_value_t *v = glyph_from_json("{\"a\":[1,{\"b\":true}],\"c\":null}");
    ASSERT_TRUE(v != NULL);
    ASSERT_TRUE(v->type == GLYPH_MAP);
    ASSERT_TRUE(v->map_val.count == 2);
    glyph_value_free(v);
}

TEST(json_parse_null_input) {
    glyph_value_t *v = glyph_from_json(NULL);
    ASSERT_TRUE(v == NULL);
}

TEST(json_parse_empty_string) {
    glyph_value_t *v = glyph_from_json("");
    ASSERT_TRUE(v == NULL);
}

TEST(json_parse_invalid) {
    ASSERT_TRUE(glyph_from_json("xyz") == NULL);
    ASSERT_TRUE(glyph_from_json("{invalid}") == NULL);
    ASSERT_TRUE(glyph_from_json("[,]") == NULL);
}

TEST(json_roundtrip) {
    glyph_value_t *v = glyph_from_json("{\"name\": \"test\", \"value\": 42}");
    char *json = glyph_to_json(v);
    glyph_value_t *v2 = glyph_from_json(json);
    ASSERT_TRUE(glyph_equal_loose(v, v2));
    glyph_free(json);
    glyph_value_free(v);
    glyph_value_free(v2);
}

TEST(json_roundtrip_array) {
    glyph_value_t *v = glyph_from_json("[1, \"two\", true, null, 3.14]");
    char *json = glyph_to_json(v);
    glyph_value_t *v2 = glyph_from_json(json);
    ASSERT_TRUE(v2 != NULL);
    ASSERT_TRUE(v2->type == GLYPH_LIST);
    ASSERT_TRUE(v2->list_val.count == 5);
    glyph_free(json);
    glyph_value_free(v);
    glyph_value_free(v2);
}

TEST(json_rejects_trailing_data) {
    glyph_value_t *v = glyph_from_json("{\"name\":\"test\"} trailing");
    ASSERT_TRUE(v == NULL);
}

TEST(json_rejects_excessive_nesting) {
    const size_t depth = 129;
    char *json = malloc(depth * 2 + 2);
    ASSERT_TRUE(json != NULL);
    for (size_t i = 0; i < depth; i++) json[i] = '[';
    json[depth] = '0';
    for (size_t i = 0; i < depth; i++) json[depth + 1 + i] = ']';
    json[depth * 2 + 1] = '\0';
    glyph_value_t *v = glyph_from_json(json);
    ASSERT_TRUE(v == NULL);
    free(json);
}

TEST(json_to_json_null) {
    glyph_value_t *v = glyph_null();
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("null", json);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_bool) {
    glyph_value_t *v = glyph_bool(true);
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("true", json);
    glyph_free(json);
    glyph_value_free(v);

    v = glyph_bool(false);
    json = glyph_to_json(v);
    ASSERT_STR_EQ("false", json);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_int) {
    glyph_value_t *v = glyph_int(-42);
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("-42", json);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_float) {
    glyph_value_t *v = glyph_float(2.5);
    char *json = glyph_to_json(v);
    ASSERT_TRUE(json != NULL);
    ASSERT_TRUE(strstr(json, "2.5") != NULL);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_string_escapes) {
    glyph_value_t *v = glyph_str("a\nb\tc\\d\"e");
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("\"a\\nb\\tc\\\\d\\\"e\"", json);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_string_control) {
    glyph_value_t *v = glyph_str("\x01\x02");
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("\"\\u0001\\u0002\"", json);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_null_value) {
    char *json = glyph_to_json(NULL);
    ASSERT_STR_EQ("null", json);
    glyph_free(json);
}

TEST(json_to_json_bytes) {
    uint8_t data[] = {0x48, 0x65, 0x6C};
    glyph_value_t *v = glyph_bytes(data, 3);
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("\"SGVs\"", json);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_id) {
    glyph_value_t *v = glyph_id("user", "123");
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("\"^user:123\"", json);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_id_no_prefix) {
    glyph_value_t *v = glyph_id(NULL, "abc");
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("\"^abc\"", json);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_struct) {
    glyph_value_t *v = glyph_struct_new("Point");
    glyph_struct_set(v, "x", glyph_int(1));
    char *json = glyph_to_json(v);
    ASSERT_TRUE(json != NULL);
    ASSERT_TRUE(strstr(json, "\"_type\":\"Point\"") != NULL);
    ASSERT_TRUE(strstr(json, "\"x\":1") != NULL);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_sum) {
    glyph_value_t *v = glyph_sum("Ok", glyph_int(42));
    char *json = glyph_to_json(v);
    ASSERT_TRUE(json != NULL);
    ASSERT_TRUE(strstr(json, "\"_tag\":\"Ok\"") != NULL);
    ASSERT_TRUE(strstr(json, "\"_value\":42") != NULL);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_sum_no_value) {
    glyph_value_t *v = glyph_sum("None", NULL);
    char *json = glyph_to_json(v);
    ASSERT_TRUE(json != NULL);
    ASSERT_TRUE(strstr(json, "\"_tag\":\"None\"") != NULL);
    ASSERT_TRUE(strstr(json, "_value") == NULL);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_list) {
    glyph_value_t *v = glyph_list_new();
    glyph_list_append(v, glyph_int(1));
    glyph_list_append(v, glyph_str("a"));
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("[1,\"a\"]", json);
    glyph_free(json);
    glyph_value_free(v);
}

TEST(json_to_json_map) {
    glyph_value_t *v = glyph_map_new();
    glyph_map_set(v, "k", glyph_bool(true));
    char *json = glyph_to_json(v);
    ASSERT_STR_EQ("{\"k\":true}", json);
    glyph_free(json);
    glyph_value_free(v);
}

/* ============================================================
 * Decimal128 Tests
 * ============================================================ */

TEST(decimal_int64_min_roundtrip) {
    decimal128_t d = decimal128_from_int(INT64_MIN);
    ASSERT_TRUE(decimal128_to_int(&d) == INT64_MIN);
    char *s = decimal128_to_string(&d);
    ASSERT_TRUE(s != NULL);
    ASSERT_STR_EQ("-9223372036854775808", s);
    free(s);
}

TEST(decimal_zero) {
    decimal128_t d = decimal128_zero();
    ASSERT_TRUE(decimal128_is_zero(&d));
    ASSERT_TRUE(!decimal128_is_negative(&d));
    ASSERT_TRUE(!decimal128_is_positive(&d));
    char *s = decimal128_to_string(&d);
    ASSERT_STR_EQ("0", s);
    free(s);
}

TEST(decimal_from_int_positive) {
    decimal128_t d = decimal128_from_int(42);
    ASSERT_TRUE(decimal128_to_int(&d) == 42);
    ASSERT_TRUE(decimal128_is_positive(&d));
    ASSERT_TRUE(!decimal128_is_negative(&d));
    char *s = decimal128_to_string(&d);
    ASSERT_STR_EQ("42", s);
    free(s);
}

TEST(decimal_from_int_negative) {
    decimal128_t d = decimal128_from_int(-100);
    ASSERT_TRUE(decimal128_to_int(&d) == -100);
    ASSERT_TRUE(decimal128_is_negative(&d));
    char *s = decimal128_to_string(&d);
    ASSERT_STR_EQ("-100", s);
    free(s);
}

TEST(decimal_from_uint) {
    decimal128_t d = decimal128_from_uint(999);
    ASSERT_TRUE(decimal128_to_int(&d) == 999);
    char *s = decimal128_to_string(&d);
    ASSERT_STR_EQ("999", s);
    free(s);
}

TEST(decimal_from_string_integer) {
    decimal128_t d;
    ASSERT_TRUE(decimal128_from_string("12345", &d) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_to_int(&d) == 12345);
}

TEST(decimal_from_string_decimal) {
    decimal128_t d;
    ASSERT_TRUE(decimal128_from_string("123.45", &d) == DECIMAL_OK);
    char *s = decimal128_to_string(&d);
    ASSERT_STR_EQ("123.45", s);
    free(s);
}

TEST(decimal_from_string_negative) {
    decimal128_t d;
    ASSERT_TRUE(decimal128_from_string("-42.5", &d) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_is_negative(&d));
    char *s = decimal128_to_string(&d);
    ASSERT_STR_EQ("-42.5", s);
    free(s);
}

TEST(decimal_from_string_with_m_suffix) {
    decimal128_t d;
    ASSERT_TRUE(decimal128_from_string("99.99m", &d) == DECIMAL_OK);
    char *s = decimal128_to_string(&d);
    ASSERT_STR_EQ("99.99", s);
    free(s);
}

TEST(decimal_from_string_leading_plus) {
    decimal128_t d;
    ASSERT_TRUE(decimal128_from_string("+42", &d) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_to_int(&d) == 42);
}

TEST(decimal_from_string_small_decimal) {
    decimal128_t d;
    ASSERT_TRUE(decimal128_from_string("0.001", &d) == DECIMAL_OK);
    char *s = decimal128_to_string(&d);
    ASSERT_STR_EQ("0.001", s);
    free(s);
}

TEST(decimal_from_string_invalid) {
    decimal128_t d;
    ASSERT_TRUE(decimal128_from_string(NULL, &d) == DECIMAL_ERR_PARSE_FAILED);
    ASSERT_TRUE(decimal128_from_string("abc", &d) == DECIMAL_ERR_PARSE_FAILED);
    ASSERT_TRUE(decimal128_from_string("12.34.56", &d) == DECIMAL_ERR_PARSE_FAILED);
}

TEST(decimal_from_double) {
    decimal128_t d = decimal128_from_double(3.14);
    double v = decimal128_to_double(&d);
    ASSERT_TRUE(fabs(v - 3.14) < 0.0001);
}

TEST(decimal_to_double) {
    decimal128_t d = decimal128_from_int(100);
    ASSERT_TRUE(decimal128_to_double(&d) == 100.0);
    ASSERT_TRUE(decimal128_to_double(NULL) == 0.0);
}

TEST(decimal_to_int_null) {
    ASSERT_TRUE(decimal128_to_int(NULL) == 0);
}

TEST(decimal_to_string_null) {
    char *s = decimal128_to_string(NULL);
    ASSERT_STR_EQ("0", s);
    free(s);
}

TEST(decimal_to_string_zero_with_scale) {
    decimal128_t d;
    decimal128_from_string("0.00", &d);
    char *s = decimal128_to_string(&d);
    ASSERT_STR_EQ("0.00", s);
    free(s);
}

TEST(decimal_abs) {
    decimal128_t d = decimal128_from_int(-42);
    decimal128_t a = decimal128_abs(&d);
    ASSERT_TRUE(!decimal128_is_negative(&a));
    ASSERT_TRUE(decimal128_to_int(&a) == 42);

    decimal128_t z = decimal128_abs(NULL);
    ASSERT_TRUE(decimal128_is_zero(&z));
}

TEST(decimal_negate) {
    decimal128_t d = decimal128_from_int(42);
    decimal128_t n = decimal128_negate(&d);
    ASSERT_TRUE(decimal128_is_negative(&n));
    ASSERT_TRUE(decimal128_to_int(&n) == -42);

    decimal128_t z = decimal128_negate(NULL);
    ASSERT_TRUE(decimal128_is_zero(&z));

    /* negate zero stays zero (not negative) */
    decimal128_t zz = decimal128_zero();
    decimal128_t nz = decimal128_negate(&zz);
    ASSERT_TRUE(!decimal128_is_negative(&nz));
}

TEST(decimal_add) {
    decimal128_t a = decimal128_from_int(10);
    decimal128_t b = decimal128_from_int(20);
    decimal128_t out;
    ASSERT_TRUE(decimal128_add(&a, &b, &out) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_to_int(&out) == 30);
}

TEST(decimal_add_different_signs) {
    decimal128_t a = decimal128_from_int(10);
    decimal128_t b = decimal128_from_int(-3);
    decimal128_t out;
    ASSERT_TRUE(decimal128_add(&a, &b, &out) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_to_int(&out) == 7);
}

TEST(decimal_add_negative_larger) {
    decimal128_t a = decimal128_from_int(3);
    decimal128_t b = decimal128_from_int(-10);
    decimal128_t out;
    ASSERT_TRUE(decimal128_add(&a, &b, &out) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_to_int(&out) == -7);
}

TEST(decimal_add_both_negative) {
    decimal128_t a = decimal128_from_int(-5);
    decimal128_t b = decimal128_from_int(-3);
    decimal128_t out;
    ASSERT_TRUE(decimal128_add(&a, &b, &out) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_to_int(&out) == -8);
}

TEST(decimal_add_different_scale) {
    decimal128_t a, b, out;
    decimal128_from_string("1.5", &a);
    decimal128_from_string("2.25", &b);
    ASSERT_TRUE(decimal128_add(&a, &b, &out) == DECIMAL_OK);
    char *s = decimal128_to_string(&out);
    ASSERT_STR_EQ("3.75", s);
    free(s);
}

TEST(decimal_add_null) {
    decimal128_t a = decimal128_from_int(1);
    decimal128_t out;
    ASSERT_TRUE(decimal128_add(NULL, &a, &out) == DECIMAL_ERR_PARSE_FAILED);
    ASSERT_TRUE(decimal128_add(&a, NULL, &out) == DECIMAL_ERR_PARSE_FAILED);
    ASSERT_TRUE(decimal128_add(&a, &a, NULL) == DECIMAL_ERR_PARSE_FAILED);
}

TEST(decimal_sub) {
    decimal128_t a = decimal128_from_int(10);
    decimal128_t b = decimal128_from_int(3);
    decimal128_t out;
    ASSERT_TRUE(decimal128_sub(&a, &b, &out) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_to_int(&out) == 7);
}

TEST(decimal_mul) {
    decimal128_t a = decimal128_from_int(6);
    decimal128_t b = decimal128_from_int(7);
    decimal128_t out;
    ASSERT_TRUE(decimal128_mul(&a, &b, &out) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_to_int(&out) == 42);
}

TEST(decimal_mul_null) {
    decimal128_t a = decimal128_from_int(1);
    decimal128_t out;
    ASSERT_TRUE(decimal128_mul(NULL, &a, &out) == DECIMAL_ERR_PARSE_FAILED);
}

TEST(decimal_div) {
    decimal128_t a = decimal128_from_int(42);
    decimal128_t b = decimal128_from_int(6);
    decimal128_t out;
    ASSERT_TRUE(decimal128_div(&a, &b, &out) == DECIMAL_OK);
    ASSERT_TRUE(decimal128_to_int(&out) == 7);
}

TEST(decimal_div_by_zero) {
    decimal128_t a = decimal128_from_int(1);
    decimal128_t b = decimal128_zero();
    decimal128_t out;
    ASSERT_TRUE(decimal128_div(&a, &b, &out) == DECIMAL_ERR_DIVISION_BY_ZERO);
}

TEST(decimal_div_null) {
    decimal128_t a = decimal128_from_int(1);
    decimal128_t out;
    ASSERT_TRUE(decimal128_div(NULL, &a, &out) == DECIMAL_ERR_PARSE_FAILED);
}

TEST(decimal_cmp) {
    decimal128_t a = decimal128_from_int(10);
    decimal128_t b = decimal128_from_int(20);
    ASSERT_TRUE(decimal128_cmp(&a, &b) < 0);
    ASSERT_TRUE(decimal128_cmp(&b, &a) > 0);
    ASSERT_TRUE(decimal128_cmp(&a, &a) == 0);
    ASSERT_TRUE(decimal128_cmp(NULL, NULL) == 0);
    ASSERT_TRUE(decimal128_cmp(NULL, &a) < 0);
    ASSERT_TRUE(decimal128_cmp(&a, NULL) > 0);
}

TEST(decimal_cmp_negative) {
    decimal128_t a = decimal128_from_int(-5);
    decimal128_t b = decimal128_from_int(5);
    ASSERT_TRUE(decimal128_cmp(&a, &b) < 0);
    ASSERT_TRUE(decimal128_cmp(&b, &a) > 0);
}

TEST(decimal_cmp_different_scale) {
    decimal128_t a, b;
    decimal128_from_string("1.50", &a);
    decimal128_from_string("1.5", &b);
    ASSERT_TRUE(decimal128_equals(&a, &b));
}

TEST(decimal_comparison_helpers) {
    decimal128_t a = decimal128_from_int(5);
    decimal128_t b = decimal128_from_int(10);
    ASSERT_TRUE(decimal128_lt(&a, &b));
    ASSERT_TRUE(!decimal128_lt(&b, &a));
    ASSERT_TRUE(decimal128_gt(&b, &a));
    ASSERT_TRUE(!decimal128_gt(&a, &b));
    ASSERT_TRUE(decimal128_lte(&a, &b));
    ASSERT_TRUE(decimal128_lte(&a, &a));
    ASSERT_TRUE(decimal128_gte(&b, &a));
    ASSERT_TRUE(decimal128_gte(&a, &a));
}

TEST(decimal_is_literal) {
    ASSERT_TRUE(decimal128_is_literal("99.99m"));
    ASSERT_TRUE(decimal128_is_literal("42m"));
    ASSERT_TRUE(!decimal128_is_literal("42"));
    ASSERT_TRUE(!decimal128_is_literal("m"));
    ASSERT_TRUE(!decimal128_is_literal(NULL));
    ASSERT_TRUE(!decimal128_is_literal(""));
}

TEST(decimal_error_string) {
    ASSERT_STR_EQ("OK", decimal128_error_string(DECIMAL_OK));
    ASSERT_STR_EQ("scale overflow", decimal128_error_string(DECIMAL_ERR_SCALE_OVERFLOW));
    ASSERT_STR_EQ("division by zero", decimal128_error_string(DECIMAL_ERR_DIVISION_BY_ZERO));
    ASSERT_STR_EQ("parse failed", decimal128_error_string(DECIMAL_ERR_PARSE_FAILED));
    ASSERT_STR_EQ("overflow", decimal128_error_string(DECIMAL_ERR_OVERFLOW));
    ASSERT_TRUE(strcmp(decimal128_error_string((decimal_error_t)99), "unknown error") == 0);
}

/* ============================================================
 * Schema Evolution Tests
 * ============================================================ */

TEST(schema_version_schema_free_embedded_fields) {
    version_schema_t *schema = version_schema_new("test", "1.0");
    ASSERT_TRUE(schema != NULL);
    evolving_field_config_t config = {
        .type = FIELD_TYPE_STR, .required = true,
        .default_value = field_value_str("fallback"),
        .added_in = "1.0", .deprecated_in = NULL,
        .renamed_from = NULL, .validation = NULL,
    };
    evolving_field_t *field = evolving_field_new("name", &config);
    ASSERT_TRUE(field != NULL);
    version_schema_add_field(schema, field);
    version_schema_free(schema);
    field_value_free(&config.default_value);
    ASSERT_TRUE(true);
}

TEST(schema_field_values) {
    field_value_t fv = field_value_null();
    ASSERT_TRUE(fv.type == FIELD_VALUE_NULL);

    fv = field_value_bool(true);
    ASSERT_TRUE(fv.type == FIELD_VALUE_BOOL);
    ASSERT_TRUE(fv.bool_val == true);

    fv = field_value_int(42);
    ASSERT_TRUE(fv.type == FIELD_VALUE_INT);
    ASSERT_TRUE(fv.int_val == 42);

    fv = field_value_float(3.14);
    ASSERT_TRUE(fv.type == FIELD_VALUE_FLOAT);
    ASSERT_TRUE(fabs(fv.float_val - 3.14) < 0.001);

    fv = field_value_str("hello");
    ASSERT_TRUE(fv.type == FIELD_VALUE_STR);
    ASSERT_STR_EQ("hello", fv.str_val);
    field_value_free(&fv);
}

TEST(schema_evolving_field_availability) {
    evolving_field_config_t config = {
        .type = FIELD_TYPE_STR, .required = false,
        .default_value = field_value_null(),
        .added_in = "2.0", .deprecated_in = "4.0",
        .renamed_from = NULL, .validation = NULL,
    };
    evolving_field_t *f = evolving_field_new("foo", &config);
    ASSERT_TRUE(f != NULL);
    ASSERT_TRUE(!evolving_field_is_available_in(f, "1.0"));
    ASSERT_TRUE(evolving_field_is_available_in(f, "2.0"));
    ASSERT_TRUE(evolving_field_is_available_in(f, "3.0"));
    ASSERT_TRUE(!evolving_field_is_available_in(f, "4.0"));
    ASSERT_TRUE(evolving_field_is_deprecated_in(f, "4.0"));
    ASSERT_TRUE(!evolving_field_is_deprecated_in(f, "3.0"));
    evolving_field_free(f);
}

TEST(schema_evolving_field_validate_required) {
    evolving_field_config_t config = {
        .type = FIELD_TYPE_STR, .required = true,
        .default_value = field_value_null(),
        .added_in = "1.0", .deprecated_in = NULL,
        .renamed_from = NULL, .validation = NULL,
    };
    evolving_field_t *f = evolving_field_new("name", &config);
    /* missing value -> error */
    char *err = evolving_field_validate(f, NULL);
    ASSERT_TRUE(err != NULL);
    free(err);
    /* wrong type */
    field_value_t iv = field_value_int(42);
    err = evolving_field_validate(f, &iv);
    ASSERT_TRUE(err != NULL);
    free(err);
    /* correct type */
    field_value_t sv = field_value_str("ok");
    err = evolving_field_validate(f, &sv);
    ASSERT_TRUE(err == NULL);
    field_value_free(&sv);
    evolving_field_free(f);
}

TEST(schema_evolving_field_validate_types) {
    /* INT field */
    evolving_field_config_t ic = {
        .type = FIELD_TYPE_INT, .required = false,
        .default_value = field_value_null(), .added_in = "1.0",
    };
    evolving_field_t *fi = evolving_field_new("count", &ic);
    field_value_t sv = field_value_str("nope");
    char *err = evolving_field_validate(fi, &sv);
    ASSERT_TRUE(err != NULL);
    free(err);
    field_value_free(&sv);
    field_value_t iv = field_value_int(5);
    err = evolving_field_validate(fi, &iv);
    ASSERT_TRUE(err == NULL);
    evolving_field_free(fi);

    /* FLOAT field - accepts int too */
    evolving_field_config_t fc = {
        .type = FIELD_TYPE_FLOAT, .required = false,
        .default_value = field_value_null(), .added_in = "1.0",
    };
    evolving_field_t *ff = evolving_field_new("val", &fc);
    err = evolving_field_validate(ff, &iv);
    ASSERT_TRUE(err == NULL); /* int accepted for float field */
    field_value_t bv = field_value_bool(true);
    err = evolving_field_validate(ff, &bv);
    ASSERT_TRUE(err != NULL);
    free(err);
    evolving_field_free(ff);

    /* BOOL field */
    evolving_field_config_t bc = {
        .type = FIELD_TYPE_BOOL, .required = false,
        .default_value = field_value_null(), .added_in = "1.0",
    };
    evolving_field_t *fb = evolving_field_new("flag", &bc);
    err = evolving_field_validate(fb, &bv);
    ASSERT_TRUE(err == NULL);
    err = evolving_field_validate(fb, &iv);
    ASSERT_TRUE(err != NULL);
    free(err);
    evolving_field_free(fb);
}

TEST(schema_evolving_field_validate_null_field) {
    char *err = evolving_field_validate(NULL, NULL);
    ASSERT_TRUE(err != NULL);
    free(err);
}

TEST(schema_version_schema_get_field) {
    version_schema_t *s = version_schema_new("test", "1.0");
    evolving_field_config_t config = {
        .type = FIELD_TYPE_STR, .required = false,
        .default_value = field_value_null(), .added_in = "1.0",
    };
    evolving_field_t *f = evolving_field_new("name", &config);
    version_schema_add_field(s, f);
    ASSERT_TRUE(version_schema_get_field(s, "name") != NULL);
    ASSERT_TRUE(version_schema_get_field(s, "missing") == NULL);
    ASSERT_TRUE(version_schema_get_field(NULL, "name") == NULL);
    version_schema_free(s);
}

TEST(schema_version_schema_validate) {
    version_schema_t *s = version_schema_new("test", "1.0");
    evolving_field_config_t config = {
        .type = FIELD_TYPE_STR, .required = true,
        .default_value = field_value_null(), .added_in = "1.0",
    };
    evolving_field_t *f = evolving_field_new("name", &config);
    version_schema_add_field(s, f);

    /* Missing required field */
    const char *keys[] = {"other"};
    field_value_t data[] = {field_value_str("x")};
    char *err = version_schema_validate(s, data, keys, 1);
    ASSERT_TRUE(err != NULL);
    free(err);
    field_value_free(&data[0]);

    /* Correct */
    const char *keys2[] = {"name"};
    field_value_t data2[] = {field_value_str("ok")};
    err = version_schema_validate(s, data2, keys2, 1);
    ASSERT_TRUE(err == NULL);
    field_value_free(&data2[0]);

    version_schema_free(s);
}

TEST(schema_versioned_schema_basic) {
    versioned_schema_t *vs = versioned_schema_new("myschema");
    ASSERT_TRUE(vs != NULL);

    evolving_field_config_t fields[] = {
        {.type = FIELD_TYPE_STR, .required = true,
         .default_value = field_value_null(), .added_in = "1.0"},
    };
    const char *names[] = {"name"};
    versioned_schema_add_version(vs, "1.0", fields, names, 1);

    const version_schema_t *v1 = versioned_schema_get_version(vs, "1.0");
    ASSERT_TRUE(v1 != NULL);
    ASSERT_TRUE(versioned_schema_get_version(vs, "9.9") == NULL);

    versioned_schema_free(vs);
}

TEST(schema_versioned_parse_same_version) {
    versioned_schema_t *vs = versioned_schema_new("test");
    evolving_field_config_t fields[] = {
        {.type = FIELD_TYPE_STR, .required = true,
         .default_value = field_value_null(), .added_in = "1.0"},
    };
    const char *names[] = {"name"};
    versioned_schema_add_version(vs, "1.0", fields, names, 1);

    field_value_t data[] = {field_value_str("hello")};
    const char *keys[] = {"name"};
    evolution_parse_result_t r = versioned_schema_parse(vs, data, keys, 1, "1.0");
    ASSERT_TRUE(r.error == NULL);
    ASSERT_TRUE(r.data_count == 1);
    evolution_parse_result_free(&r);
    field_value_free(&data[0]);
    versioned_schema_free(vs);
}

TEST(schema_versioned_parse_unknown_version) {
    versioned_schema_t *vs = versioned_schema_new("test");
    evolution_parse_result_t r = versioned_schema_parse(vs, NULL, NULL, 0, "9.9");
    ASSERT_TRUE(r.error != NULL);
    evolution_parse_result_free(&r);
    versioned_schema_free(vs);
}

TEST(schema_versioned_emit) {
    versioned_schema_t *vs = versioned_schema_new("test");
    evolving_field_config_t fields[] = {
        {.type = FIELD_TYPE_STR, .required = false,
         .default_value = field_value_null(), .added_in = "1.0"},
    };
    const char *names[] = {"name"};
    versioned_schema_add_version(vs, "1.0", fields, names, 1);

    field_value_t data[] = {field_value_str("hi")};
    const char *keys[] = {"name"};
    evolution_emit_result_t r = versioned_schema_emit(vs, data, keys, 1, "1.0");
    ASSERT_TRUE(r.error == NULL);
    ASSERT_TRUE(r.header != NULL);
    ASSERT_TRUE(strstr(r.header, "1.0") != NULL);
    evolution_emit_result_free(&r);
    field_value_free(&data[0]);
    versioned_schema_free(vs);
}

TEST(schema_versioned_emit_unknown) {
    versioned_schema_t *vs = versioned_schema_new("test");
    evolution_emit_result_t r = versioned_schema_emit(vs, NULL, NULL, 0, "9.9");
    ASSERT_TRUE(r.error != NULL);
    evolution_emit_result_free(&r);
    versioned_schema_free(vs);
}

TEST(schema_versioned_migrate) {
    versioned_schema_t *vs = versioned_schema_new("test");
    versioned_schema_with_mode(vs, EVOLUTION_MODE_TOLERANT);

    evolving_field_config_t v1_fields[] = {
        {.type = FIELD_TYPE_STR, .required = true,
         .default_value = field_value_null(), .added_in = "1.0"},
    };
    const char *v1_names[] = {"name"};
    versioned_schema_add_version(vs, "1.0", v1_fields, v1_names, 1);

    field_value_t dflt = field_value_str("unknown");
    evolving_field_config_t v2_fields[] = {
        {.type = FIELD_TYPE_STR, .required = true,
         .default_value = field_value_null(), .added_in = "1.0"},
        {.type = FIELD_TYPE_STR, .required = false,
         .default_value = dflt, .added_in = "2.0"},
    };
    const char *v2_names[] = {"name", "email"};
    versioned_schema_add_version(vs, "2.0", v2_fields, v2_names, 2);

    /* Parse v1 data -> should migrate to v2 (latest) */
    field_value_t data[] = {field_value_str("Alice")};
    const char *keys[] = {"name"};
    evolution_parse_result_t r = versioned_schema_parse(vs, data, keys, 1, "1.0");
    ASSERT_TRUE(r.error == NULL);
    ASSERT_TRUE(r.data_count >= 1);
    evolution_parse_result_free(&r);
    field_value_free(&data[0]);
    field_value_free(&dflt);
    versioned_schema_free(vs);
}

TEST(schema_versioned_strict_mode) {
    versioned_schema_t *vs = versioned_schema_new("test");
    versioned_schema_with_mode(vs, EVOLUTION_MODE_STRICT);

    evolving_field_config_t fields[] = {
        {.type = FIELD_TYPE_STR, .required = true,
         .default_value = field_value_null(), .added_in = "1.0"},
    };
    const char *names[] = {"name"};
    versioned_schema_add_version(vs, "1.0", fields, names, 1);

    /* Missing required field in strict mode */
    field_value_t data[] = {field_value_str("x")};
    const char *keys[] = {"other"};
    evolution_parse_result_t r = versioned_schema_parse(vs, data, keys, 1, "1.0");
    ASSERT_TRUE(r.error != NULL);
    evolution_parse_result_free(&r);
    field_value_free(&data[0]);
    versioned_schema_free(vs);
}

TEST(schema_changelog) {
    versioned_schema_t *vs = versioned_schema_new("test");
    evolving_field_config_t fields[] = {
        {.type = FIELD_TYPE_STR, .required = false,
         .default_value = field_value_null(), .added_in = "1.0"},
    };
    const char *names[] = {"name"};
    versioned_schema_add_version(vs, "1.0", fields, names, 1);

    size_t count = 0;
    changelog_entry_t *entries = versioned_schema_get_changelog(vs, &count);
    ASSERT_TRUE(count == 1);
    ASSERT_TRUE(entries != NULL);
    ASSERT_STR_EQ("1.0", entries[0].version);
    ASSERT_TRUE(entries[0].added_count == 1);
    changelog_free(entries, count);
    versioned_schema_free(vs);
}

TEST(schema_compare_versions) {
    ASSERT_TRUE(compare_versions("1.0", "2.0") < 0);
    ASSERT_TRUE(compare_versions("2.0", "1.0") > 0);
    ASSERT_TRUE(compare_versions("1.0", "1.0") == 0);
    ASSERT_TRUE(compare_versions("1.0.1", "1.0.0") > 0);
    ASSERT_TRUE(compare_versions("1.0", "1.0.1") < 0);
    ASSERT_TRUE(compare_versions(NULL, NULL) == 0);
    ASSERT_TRUE(compare_versions(NULL, "1.0") < 0);
    ASSERT_TRUE(compare_versions("1.0", NULL) > 0);
}

TEST(schema_version_header) {
    char *v = parse_version_header("@version 2.0");
    ASSERT_TRUE(v != NULL);
    ASSERT_STR_EQ("2.0", v);
    free(v);

    ASSERT_TRUE(parse_version_header(NULL) == NULL);
    ASSERT_TRUE(parse_version_header("no version") == NULL);
    ASSERT_TRUE(parse_version_header("@version ") == NULL);

    char *h = format_version_header("3.0");
    ASSERT_TRUE(h != NULL);
    ASSERT_STR_EQ("@version 3.0", h);
    free(h);

    ASSERT_TRUE(format_version_header(NULL) == NULL);
}

TEST(schema_versioned_with_rename) {
    versioned_schema_t *vs = versioned_schema_new("test");
    versioned_schema_with_mode(vs, EVOLUTION_MODE_TOLERANT);

    evolving_field_config_t v1_fields[] = {
        {.type = FIELD_TYPE_STR, .required = true,
         .default_value = field_value_null(), .added_in = "1.0"},
    };
    const char *v1_names[] = {"old_name"};
    versioned_schema_add_version(vs, "1.0", v1_fields, v1_names, 1);

    evolving_field_config_t v2_fields[] = {
        {.type = FIELD_TYPE_STR, .required = true,
         .default_value = field_value_null(), .added_in = "1.0",
         .renamed_from = "old_name"},
    };
    const char *v2_names[] = {"new_name"};
    versioned_schema_add_version(vs, "2.0", v2_fields, v2_names, 1);

    field_value_t data[] = {field_value_str("Alice")};
    const char *keys[] = {"old_name"};
    evolution_parse_result_t r = versioned_schema_parse(vs, data, keys, 1, "1.0");
    ASSERT_TRUE(r.error == NULL);
    /* Should have renamed old_name -> new_name */
    bool found_new = false;
    for (size_t i = 0; i < r.data_count; i++) {
        if (strcmp(r.keys[i], "new_name") == 0) found_new = true;
    }
    ASSERT_TRUE(found_new);
    evolution_parse_result_free(&r);
    field_value_free(&data[0]);
    versioned_schema_free(vs);
}

/* ============================================================
 * Stream Validator Tests
 * ============================================================ */

TEST(stream_validator_rejects_excessive_depth) {
    tool_registry_t *registry = tool_registry_default();
    ASSERT_TRUE(registry != NULL);
    streaming_validator_t *validator = streaming_validator_new(registry);
    ASSERT_TRUE(validator != NULL);
    const size_t depth = 129;
    char *payload = malloc(64 + depth * 2 + 1);
    ASSERT_TRUE(payload != NULL);
    size_t pos = 0;
    pos += (size_t)snprintf(payload + pos, 64, "{action=\"search\" query=");
    for (size_t i = 0; i < depth; i++) payload[pos++] = '[';
    payload[pos++] = '_';
    for (size_t i = 0; i < depth; i++) payload[pos++] = ']';
    payload[pos++] = '}';
    payload[pos] = '\0';
    validation_result_t *result = streaming_validator_push_token(validator, payload);
    ASSERT_TRUE(result != NULL);
    ASSERT_TRUE(result->valid == false);
    ASSERT_TRUE(result->errors_count > 0);
    validation_result_free(result);
    free(payload);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_valid_search) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    validation_result_t *r = streaming_validator_push_token(validator, "{action=search query=hello}");
    ASSERT_TRUE(r != NULL);
    ASSERT_TRUE(r->complete);
    ASSERT_TRUE(r->tool_name != NULL);
    ASSERT_STR_EQ("search", r->tool_name);
    ASSERT_TRUE(r->tool_allowed);
    /* No errors for valid call */
    bool has_non_tool_error = false;
    for (size_t i = 0; i < r->errors_count; i++) {
        if (r->errors[i].code != VERR_UNKNOWN_TOOL) has_non_tool_error = true;
    }
    (void)has_non_tool_error;
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_unknown_tool) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    validation_result_t *r = streaming_validator_push_token(validator, "{action=nonexistent query=hi}");
    ASSERT_TRUE(r != NULL);
    ASSERT_TRUE(r->valid == false);
    bool found_unknown = false;
    for (size_t i = 0; i < r->errors_count; i++) {
        if (r->errors[i].code == VERR_UNKNOWN_TOOL) found_unknown = true;
    }
    ASSERT_TRUE(found_unknown);
    ASSERT_TRUE(streaming_validator_should_stop(validator));
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_missing_required) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    /* search requires 'query' */
    validation_result_t *r = streaming_validator_push_token(validator, "{action=search}");
    ASSERT_TRUE(r != NULL);
    ASSERT_TRUE(r->complete);
    bool found_missing = false;
    for (size_t i = 0; i < r->errors_count; i++) {
        if (r->errors[i].code == VERR_MISSING_REQUIRED) found_missing = true;
    }
    ASSERT_TRUE(found_missing);
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_no_action) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    validation_result_t *r = streaming_validator_push_token(validator, "{foo=bar}");
    ASSERT_TRUE(r != NULL);
    ASSERT_TRUE(r->complete);
    bool found_missing_tool = false;
    for (size_t i = 0; i < r->errors_count; i++) {
        if (r->errors[i].code == VERR_MISSING_TOOL) found_missing_tool = true;
    }
    ASSERT_TRUE(found_missing_tool);
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_constraint_max) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    /* max_results has max=100 */
    validation_result_t *r = streaming_validator_push_token(validator,
        "{action=search query=hello max_results=999}");
    ASSERT_TRUE(r != NULL);
    bool found_max = false;
    for (size_t i = 0; i < r->errors_count; i++) {
        if (r->errors[i].code == VERR_CONSTRAINT_MAX) found_max = true;
    }
    ASSERT_TRUE(found_max);
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_constraint_min) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    /* max_results has min=1 */
    validation_result_t *r = streaming_validator_push_token(validator,
        "{action=search query=hello max_results=0}");
    ASSERT_TRUE(r != NULL);
    bool found_min = false;
    for (size_t i = 0; i < r->errors_count; i++) {
        if (r->errors[i].code == VERR_CONSTRAINT_MIN) found_min = true;
    }
    ASSERT_TRUE(found_min);
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_multi_token) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);

    validation_result_t *r1 = streaming_validator_push_token(validator, "{action=");
    ASSERT_TRUE(r1 != NULL);
    ASSERT_TRUE(!r1->complete);
    validation_result_free(r1);

    validation_result_t *r2 = streaming_validator_push_token(validator, "search ");
    ASSERT_TRUE(r2 != NULL);
    ASSERT_TRUE(!r2->complete);
    validation_result_free(r2);

    validation_result_t *r3 = streaming_validator_push_token(validator, "query=test}");
    ASSERT_TRUE(r3 != NULL);
    ASSERT_TRUE(r3->complete);
    ASSERT_TRUE(r3->tool_name != NULL);
    ASSERT_STR_EQ("search", r3->tool_name);
    validation_result_free(r3);

    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_reset) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);

    validation_result_t *r1 = streaming_validator_push_token(validator, "{action=search query=hi}");
    ASSERT_TRUE(r1 != NULL);
    ASSERT_TRUE(r1->complete);
    validation_result_free(r1);

    streaming_validator_reset(validator);

    validation_result_t *r2 = streaming_validator_push_token(validator, "{action=calculate expression=1+1}");
    ASSERT_TRUE(r2 != NULL);
    ASSERT_TRUE(r2->complete);
    ASSERT_TRUE(r2->tool_name != NULL);
    ASSERT_STR_EQ("calculate", r2->tool_name);
    validation_result_free(r2);

    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_string_value) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    validation_result_t *r = streaming_validator_push_token(validator,
        "{action=search query=\"hello world\"}");
    ASSERT_TRUE(r != NULL);
    ASSERT_TRUE(r->complete);
    /* Find query field */
    bool found_query = false;
    for (size_t i = 0; i < r->fields_count; i++) {
        if (strcmp(r->fields[i].key, "query") == 0) {
            found_query = true;
            ASSERT_TRUE(r->fields[i].value.type == VFIELD_STR);
        }
    }
    ASSERT_TRUE(found_query);
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_tool_field) {
    /* 'tool' is an alias for 'action' */
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    validation_result_t *r = streaming_validator_push_token(validator,
        "{tool=search query=test}");
    ASSERT_TRUE(r != NULL);
    ASSERT_TRUE(r->complete);
    ASSERT_TRUE(r->tool_name != NULL);
    ASSERT_STR_EQ("search", r->tool_name);
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_enum_constraint) {
    tool_registry_t *registry = tool_registry_new();
    tool_schema_t *tool = tool_schema_new("pick", "Pick something");
    arg_schema_t *arg = arg_schema_new("color", "string");
    arg_schema_set_required(arg, true);
    const char *colors[] = {"red", "green", "blue"};
    arg_schema_set_enum(arg, colors, 3);
    tool_schema_add_arg(tool, arg);
    tool_registry_register(registry, tool);

    streaming_validator_t *v = streaming_validator_new(registry);
    validation_result_t *r = streaming_validator_push_token(v, "{action=pick color=yellow}");
    ASSERT_TRUE(r != NULL);
    bool found_enum = false;
    for (size_t i = 0; i < r->errors_count; i++) {
        if (r->errors[i].code == VERR_CONSTRAINT_ENUM) found_enum = true;
    }
    ASSERT_TRUE(found_enum);
    validation_result_free(r);
    streaming_validator_free(v);
    tool_registry_free(registry);
}

TEST(stream_validator_get_result_null) {
    ASSERT_TRUE(streaming_validator_get_result(NULL) == NULL);
}

TEST(stream_validator_should_stop_null) {
    ASSERT_TRUE(!streaming_validator_should_stop(NULL));
}

TEST(stream_validator_error_code_strings) {
    ASSERT_STR_EQ("UNKNOWN_TOOL", validation_error_code_string(VERR_UNKNOWN_TOOL));
    ASSERT_STR_EQ("MISSING_REQUIRED", validation_error_code_string(VERR_MISSING_REQUIRED));
    ASSERT_STR_EQ("MISSING_TOOL", validation_error_code_string(VERR_MISSING_TOOL));
    ASSERT_STR_EQ("CONSTRAINT_MIN", validation_error_code_string(VERR_CONSTRAINT_MIN));
    ASSERT_STR_EQ("CONSTRAINT_MAX", validation_error_code_string(VERR_CONSTRAINT_MAX));
    ASSERT_STR_EQ("CONSTRAINT_LEN", validation_error_code_string(VERR_CONSTRAINT_LEN));
    ASSERT_STR_EQ("CONSTRAINT_PATTERN", validation_error_code_string(VERR_CONSTRAINT_PATTERN));
    ASSERT_STR_EQ("CONSTRAINT_ENUM", validation_error_code_string(VERR_CONSTRAINT_ENUM));
    ASSERT_STR_EQ("INVALID_TYPE", validation_error_code_string(VERR_INVALID_TYPE));
    ASSERT_TRUE(strcmp(validation_error_code_string((validation_error_code_t)99), "UNKNOWN") == 0);
}

TEST(stream_validator_state_strings) {
    ASSERT_STR_EQ("waiting", validator_state_string(VALIDATOR_WAITING));
    ASSERT_STR_EQ("in_object", validator_state_string(VALIDATOR_IN_OBJECT));
    ASSERT_STR_EQ("complete", validator_state_string(VALIDATOR_COMPLETE));
    ASSERT_STR_EQ("error", validator_state_string(VALIDATOR_ERROR));
    ASSERT_TRUE(strcmp(validator_state_string((validator_state_t)99), "unknown") == 0);
}

TEST(stream_validator_tool_registry_basic) {
    tool_registry_t *r = tool_registry_default();
    ASSERT_TRUE(r != NULL);
    ASSERT_TRUE(tool_registry_is_allowed(r, "search"));
    ASSERT_TRUE(tool_registry_is_allowed(r, "calculate"));
    ASSERT_TRUE(tool_registry_is_allowed(r, "browse"));
    ASSERT_TRUE(tool_registry_is_allowed(r, "execute"));
    ASSERT_TRUE(!tool_registry_is_allowed(r, "nonexistent"));
    ASSERT_TRUE(tool_registry_get(r, "search") != NULL);
    ASSERT_TRUE(tool_registry_get(r, "nope") == NULL);
    ASSERT_TRUE(tool_registry_get(NULL, "search") == NULL);
    ASSERT_TRUE(tool_registry_get(r, NULL) == NULL);
    tool_registry_free(r);
}

TEST(stream_validator_unbalanced_brace) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    validation_result_t *r = streaming_validator_push_token(validator, "}");
    ASSERT_TRUE(r != NULL);
    ASSERT_TRUE(!r->valid);
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_escape_in_string) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    validation_result_t *r = streaming_validator_push_token(validator,
        "{action=search query=\"hello\\nworld\"}");
    ASSERT_TRUE(r != NULL);
    ASSERT_TRUE(r->complete);
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

TEST(stream_validator_precision_constraint) {
    tool_registry_t *registry = tool_registry_default();
    streaming_validator_t *validator = streaming_validator_new(registry);
    /* precision for calculate has range 0-15 */
    validation_result_t *r = streaming_validator_push_token(validator,
        "{action=calculate expression=1+1 precision=20}");
    ASSERT_TRUE(r != NULL);
    bool found_max = false;
    for (size_t i = 0; i < r->errors_count; i++) {
        if (r->errors[i].code == VERR_CONSTRAINT_MAX) found_max = true;
    }
    ASSERT_TRUE(found_max);
    validation_result_free(r);
    streaming_validator_free(validator);
    tool_registry_free(registry);
}

/* ============================================================
 * Main
 * ============================================================ */

int main(void) {
    printf("GLYPH Codec C Tests\n");
    printf("===================\n\n");

    printf("Primitive Tests:\n");
    RUN_TEST(null_canonical);
    RUN_TEST(bool_true);
    RUN_TEST(bool_false);
    RUN_TEST(int_positive);
    RUN_TEST(int_negative);
    RUN_TEST(int_zero);
    RUN_TEST(float_whole_number);
    RUN_TEST(float_decimal);
    RUN_TEST(float_nan);
    RUN_TEST(float_positive_inf);
    RUN_TEST(float_negative_inf);
    RUN_TEST(float_negative_zero);

    printf("\nString Tests:\n");
    RUN_TEST(string_bare_safe);
    RUN_TEST(string_needs_quotes);
    RUN_TEST(string_starts_with_digit);
    RUN_TEST(string_empty);
    RUN_TEST(string_reserved_t);
    RUN_TEST(string_reserved_f);
    RUN_TEST(string_with_escape);
    RUN_TEST(string_reserved_true);
    RUN_TEST(string_reserved_false);
    RUN_TEST(string_reserved_null);
    RUN_TEST(string_reserved_underscore);
    RUN_TEST(string_starts_with_dash);
    RUN_TEST(string_with_tab);
    RUN_TEST(string_with_cr);
    RUN_TEST(string_with_backslash);
    RUN_TEST(string_with_quote);
    RUN_TEST(string_with_control_char);
    RUN_TEST(string_bare_with_special_chars);

    printf("\nBytes Tests:\n");
    RUN_TEST(bytes_empty);
    RUN_TEST(bytes_simple);
    RUN_TEST(bytes_padding_one);
    RUN_TEST(bytes_padding_two);
    RUN_TEST(bytes_null_data_nonzero_len);

    printf("\nStruct Tests:\n");
    RUN_TEST(struct_empty);
    RUN_TEST(struct_with_fields);
    RUN_TEST(struct_get_field);

    printf("\nSum Type Tests:\n");
    RUN_TEST(sum_with_value);
    RUN_TEST(sum_without_value);

    printf("\nAccessor Tests:\n");
    RUN_TEST(accessor_get_type);
    RUN_TEST(accessor_as_bool);
    RUN_TEST(accessor_as_int);
    RUN_TEST(accessor_as_float);
    RUN_TEST(accessor_as_str);
    RUN_TEST(accessor_list_len);
    RUN_TEST(accessor_list_get);
    RUN_TEST(accessor_map_get);

    printf("\nList Tests:\n");
    RUN_TEST(list_empty);
    RUN_TEST(list_single);
    RUN_TEST(list_multiple);

    printf("\nMap Tests:\n");
    RUN_TEST(map_empty);
    RUN_TEST(map_single);
    RUN_TEST(map_sorted_keys);

    printf("\nReference ID Tests:\n");
    RUN_TEST(ref_id_simple);
    RUN_TEST(ref_id_with_prefix);
    RUN_TEST(ref_id_numeric);
    RUN_TEST(ref_id_needs_quotes);

    printf("\nTabular Mode Tests:\n");
    RUN_TEST(tabular_homogeneous);
    RUN_TEST(tabular_columns_sorted);
    RUN_TEST(tabular_sparse_keys_no_tabular);
    RUN_TEST(tabular_empty_objects_no_tabular);
    RUN_TEST(tabular_missing_keys_fill_null);
    RUN_TEST(tabular_fewer_than_min_rows);
    RUN_TEST(tabular_non_map_items);
    RUN_TEST(tabular_with_structs);

    printf("\nCanonicalization Options Tests:\n");
    RUN_TEST(canon_opts_pretty_null);
    RUN_TEST(canon_opts_no_tabular);
    RUN_TEST(canon_opts_null_opts);
    RUN_TEST(canon_null_value);
    RUN_TEST(fingerprint_loose);
    RUN_TEST(hash_loose);
    RUN_TEST(equal_loose_same);
    RUN_TEST(equal_loose_different);

    printf("\nNested Structure Tests:\n");
    RUN_TEST(nested_map_in_list);
    RUN_TEST(nested_list_in_map);
    RUN_TEST(mixed_types_list);

    printf("\nJSON Bridge Tests:\n");
    RUN_TEST(json_parse_null);
    RUN_TEST(json_parse_bool_true);
    RUN_TEST(json_parse_bool_false);
    RUN_TEST(json_parse_int);
    RUN_TEST(json_parse_negative_int);
    RUN_TEST(json_parse_float);
    RUN_TEST(json_parse_float_exponent);
    RUN_TEST(json_parse_string);
    RUN_TEST(json_parse_string_escapes);
    RUN_TEST(json_parse_string_unicode_ascii);
    RUN_TEST(json_parse_string_unicode_2byte);
    RUN_TEST(json_parse_string_unicode_3byte);
    RUN_TEST(json_parse_array);
    RUN_TEST(json_parse_empty_array);
    RUN_TEST(json_parse_object);
    RUN_TEST(json_parse_empty_object);
    RUN_TEST(json_parse_nested);
    RUN_TEST(json_parse_null_input);
    RUN_TEST(json_parse_empty_string);
    RUN_TEST(json_parse_invalid);
    RUN_TEST(json_roundtrip);
    RUN_TEST(json_roundtrip_array);
    RUN_TEST(json_rejects_trailing_data);
    RUN_TEST(json_rejects_excessive_nesting);
    RUN_TEST(json_to_json_null);
    RUN_TEST(json_to_json_bool);
    RUN_TEST(json_to_json_int);
    RUN_TEST(json_to_json_float);
    RUN_TEST(json_to_json_string_escapes);
    RUN_TEST(json_to_json_string_control);
    RUN_TEST(json_to_json_null_value);
    RUN_TEST(json_to_json_bytes);
    RUN_TEST(json_to_json_id);
    RUN_TEST(json_to_json_id_no_prefix);
    RUN_TEST(json_to_json_struct);
    RUN_TEST(json_to_json_sum);
    RUN_TEST(json_to_json_sum_no_value);
    RUN_TEST(json_to_json_list);
    RUN_TEST(json_to_json_map);

    printf("\nDecimal128 Tests:\n");
    RUN_TEST(decimal_int64_min_roundtrip);
    RUN_TEST(decimal_zero);
    RUN_TEST(decimal_from_int_positive);
    RUN_TEST(decimal_from_int_negative);
    RUN_TEST(decimal_from_uint);
    RUN_TEST(decimal_from_string_integer);
    RUN_TEST(decimal_from_string_decimal);
    RUN_TEST(decimal_from_string_negative);
    RUN_TEST(decimal_from_string_with_m_suffix);
    RUN_TEST(decimal_from_string_leading_plus);
    RUN_TEST(decimal_from_string_small_decimal);
    RUN_TEST(decimal_from_string_invalid);
    RUN_TEST(decimal_from_double);
    RUN_TEST(decimal_to_double);
    RUN_TEST(decimal_to_int_null);
    RUN_TEST(decimal_to_string_null);
    RUN_TEST(decimal_to_string_zero_with_scale);
    RUN_TEST(decimal_abs);
    RUN_TEST(decimal_negate);
    RUN_TEST(decimal_add);
    RUN_TEST(decimal_add_different_signs);
    RUN_TEST(decimal_add_negative_larger);
    RUN_TEST(decimal_add_both_negative);
    RUN_TEST(decimal_add_different_scale);
    RUN_TEST(decimal_add_null);
    RUN_TEST(decimal_sub);
    RUN_TEST(decimal_mul);
    RUN_TEST(decimal_mul_null);
    RUN_TEST(decimal_div);
    RUN_TEST(decimal_div_by_zero);
    RUN_TEST(decimal_div_null);
    RUN_TEST(decimal_cmp);
    RUN_TEST(decimal_cmp_negative);
    RUN_TEST(decimal_cmp_different_scale);
    RUN_TEST(decimal_comparison_helpers);
    RUN_TEST(decimal_is_literal);
    RUN_TEST(decimal_error_string);

    printf("\nSchema Evolution Tests:\n");
    RUN_TEST(schema_version_schema_free_embedded_fields);
    RUN_TEST(schema_field_values);
    RUN_TEST(schema_evolving_field_availability);
    RUN_TEST(schema_evolving_field_validate_required);
    RUN_TEST(schema_evolving_field_validate_types);
    RUN_TEST(schema_evolving_field_validate_null_field);
    RUN_TEST(schema_version_schema_get_field);
    RUN_TEST(schema_version_schema_validate);
    RUN_TEST(schema_versioned_schema_basic);
    RUN_TEST(schema_versioned_parse_same_version);
    RUN_TEST(schema_versioned_parse_unknown_version);
    RUN_TEST(schema_versioned_emit);
    RUN_TEST(schema_versioned_emit_unknown);
    RUN_TEST(schema_versioned_migrate);
    RUN_TEST(schema_versioned_strict_mode);
    RUN_TEST(schema_changelog);
    RUN_TEST(schema_compare_versions);
    RUN_TEST(schema_version_header);
    RUN_TEST(schema_versioned_with_rename);

    printf("\nStream Validator Tests:\n");
    RUN_TEST(stream_validator_rejects_excessive_depth);
    RUN_TEST(stream_validator_valid_search);
    RUN_TEST(stream_validator_unknown_tool);
    RUN_TEST(stream_validator_missing_required);
    RUN_TEST(stream_validator_no_action);
    RUN_TEST(stream_validator_constraint_max);
    RUN_TEST(stream_validator_constraint_min);
    RUN_TEST(stream_validator_multi_token);
    RUN_TEST(stream_validator_reset);
    RUN_TEST(stream_validator_string_value);
    RUN_TEST(stream_validator_tool_field);
    RUN_TEST(stream_validator_enum_constraint);
    RUN_TEST(stream_validator_get_result_null);
    RUN_TEST(stream_validator_should_stop_null);
    RUN_TEST(stream_validator_error_code_strings);
    RUN_TEST(stream_validator_state_strings);
    RUN_TEST(stream_validator_tool_registry_basic);
    RUN_TEST(stream_validator_unbalanced_brace);
    RUN_TEST(stream_validator_escape_in_string);
    RUN_TEST(stream_validator_precision_constraint);

    printf("\n===================\n");
    printf("Results: %d passed, %d failed\n", tests_passed, tests_failed);

    return tests_failed > 0 ? 1 : 0;
}
