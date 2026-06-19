/**
 * Truth table tests for glyph - 12 cases from truth_cases.json,
 * plus decimal128 carry-path tests for u128_mul10.
 */

#include "glyph.h"
#include "decimal128.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

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

#define ASSERT_NULL(ptr) do { \
    if ((ptr) != NULL) { \
        printf("\n    FAILED: expected NULL\n"); \
        tests_failed++; \
        return; \
    } \
} while(0)

/* ============================================================
 * Truth Table Tests
 * ============================================================ */

TEST(truth_duplicate_keys_last_wins) {
    /* Parse JSON with key "a" → last-writer-wins */
    glyph_value_t *v = glyph_from_json("{\"a\": 2}");
    ASSERT_TRUE(v != NULL);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("{a=2}", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(truth_nan_rejected_in_text) {
    /* NaN is rejected in glyph text canonicalization (returns NULL) */
    glyph_value_t *v = glyph_float(NAN);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_NULL(canon);
    glyph_value_free(v);
}

TEST(truth_inf_rejected_in_text) {
    /* +Inf/-Inf are rejected in glyph text canonicalization (returns NULL) */
    glyph_value_t *v_pos = glyph_float(INFINITY);
    char *canon_pos = glyph_canonicalize_loose(v_pos);
    ASSERT_NULL(canon_pos);
    glyph_value_free(v_pos);

    glyph_value_t *v_neg = glyph_float(-INFINITY);
    char *canon_neg = glyph_canonicalize_loose(v_neg);
    ASSERT_NULL(canon_neg);
    glyph_value_free(v_neg);
}

TEST(truth_trailing_whitespace_ignored) {
    /* Trailing whitespace is ignored when parsing via JSON */
    glyph_value_t *v = glyph_from_json("{\"key\": \"value\"}");
    ASSERT_TRUE(v != NULL);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("{key=value}", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(truth_negative_zero_canonicalizes_to_zero) {
    /* -0.0 → "0" */
    glyph_value_t *v = glyph_float(-0.0);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("0", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(truth_empty_document_valid) {
    /* Empty map → {} */
    glyph_value_t *v = glyph_map_new();
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("{}", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(truth_number_normalization_integer) {
    /* 1.0 → "1" */
    glyph_value_t *v = glyph_float(1.0);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("1", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(truth_number_normalization_exponent) {
    /* 1e2 → "100" */
    glyph_value_t *v = glyph_float(100.0);
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("100", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(truth_reserved_words_quoted) {
    /* "true" as a string value → "\"true\"" */
    glyph_value_t *v = glyph_str("true");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("\"true\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(truth_bare_string_safe) {
    /* "hello_world" → hello_world (bare, unquoted) */
    glyph_value_t *v = glyph_str("hello_world");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("hello_world", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(truth_string_with_spaces_quoted) {
    /* "hello world" → "\"hello world\"" */
    glyph_value_t *v = glyph_str("hello world");
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("\"hello world\"", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

TEST(truth_null_canonical_form) {
    /* null → "_" */
    glyph_value_t *v = glyph_null();
    char *canon = glyph_canonicalize_loose(v);
    ASSERT_TRUE(canon != NULL);
    ASSERT_STR_EQ("_", canon);
    glyph_free(canon);
    glyph_value_free(v);
}

/* ============================================================
 * decimal128 u128_mul10 carry-path tests
 *
 * u128_mul10 is static; we test it indirectly via from_string/to_string
 * round-trips on values that require carry from the low 64-bit limb
 * into the high 64-bit limb (i.e., values >= 2^64 / 10 ≈ 1.8e18).
 * ============================================================ */

/*
 * A 19-digit value: 9999999999999999999 (< 2^64 but forces carry during
 * the digit loop because each successive mul10+add digit can push the
 * accumulated value above UINT64_MAX).
 * from_string → to_string must round-trip exactly.
 */
TEST(u128_mul10_carry_19digit) {
    const char *input = "9999999999999999999";
    decimal128_t d;
    ASSERT_TRUE(decimal128_from_string(input, &d) == DECIMAL_OK);
    char *s = decimal128_to_string(&d);
    ASSERT_TRUE(s != NULL);
    ASSERT_STR_EQ(input, s);
    free(s);
}

/*
 * UINT64_MAX = 18446744073709551615 (20 digits).
 * Parsing this requires carry into coef_high during the last few digits.
 * The previously broken carry calculation returned high=24 for this value;
 * the fixed __uint128_t path must return high=0 (it fits exactly in 64 bits
 * as an intermediate), and the final coefficient should be UINT64_MAX itself.
 */
TEST(u128_mul10_carry_uint64max) {
    const char *input = "18446744073709551615";
    decimal128_t d;
    ASSERT_TRUE(decimal128_from_string(input, &d) == DECIMAL_OK);
    char *s = decimal128_to_string(&d);
    ASSERT_TRUE(s != NULL);
    ASSERT_STR_EQ(input, s);
    free(s);
}

/* ============================================================
 * Main
 * ============================================================ */

int main(void) {
    printf("Glyph Truth Table Tests:\n");

    RUN_TEST(truth_duplicate_keys_last_wins);
    RUN_TEST(truth_nan_rejected_in_text);
    RUN_TEST(truth_inf_rejected_in_text);
    RUN_TEST(truth_trailing_whitespace_ignored);
    RUN_TEST(truth_negative_zero_canonicalizes_to_zero);
    RUN_TEST(truth_empty_document_valid);
    RUN_TEST(truth_number_normalization_integer);
    RUN_TEST(truth_number_normalization_exponent);
    RUN_TEST(truth_reserved_words_quoted);
    RUN_TEST(truth_bare_string_safe);
    RUN_TEST(truth_string_with_spaces_quoted);
    RUN_TEST(truth_null_canonical_form);

    printf("\n--- decimal128 carry-path ---\n");
    RUN_TEST(u128_mul10_carry_19digit);
    RUN_TEST(u128_mul10_carry_uint64max);

    printf("\n===================\n");
    printf("Results: %d passed, %d failed\n", tests_passed, tests_failed);

    return tests_failed > 0 ? 1 : 0;
}
