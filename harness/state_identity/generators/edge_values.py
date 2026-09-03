#!/usr/bin/env python3
"""Generate the adversarial state-identity fixture corpus.

Deterministic: fixed seed, no network. Writes:
  data/fixtures.jsonl   — valid JSON values (one raw JSON text per line)
  data/variants.jsonl   — logical groups: same value, different textual forms
  data/malformed.jsonl  — realistic LLM syntax errors (scenario S5 only)

Fixture schema (fixtures.jsonl):
  {"id": str, "klass": str, "json": str, "note": str}

Variants schema (variants.jsonl):
  {"group": str, "members": [{"form": str, "json": str}], "note": str}

Malformed schema:
  {"id": str, "error_class": str, "text": str}
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 20260821
HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"


def dumps_min(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def dumps_pretty(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def dumps_escaped(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True)


FIXTURES = []


def add(fid: str, klass: str, obj_or_text, note: str = "", *, raw: bool = False) -> None:
    text = obj_or_text if raw else dumps_min(obj_or_text)
    FIXTURES.append({"id": fid, "klass": klass, "json": text, "note": note})


def build_fixtures() -> None:
    # --- floats -----------------------------------------------------------
    add("f_pos_zero", "float", 0.0)
    add("f_neg_zero_raw", "float", "-0.0", "negative zero literal", raw=True)
    add("f_point_1_plus_2", "float", 0.30000000000000004, "0.1+0.2 artifact")
    add("f_tenth", "float", 0.1)
    add("f_exp17", "float", 1e17)
    add("f_exp21", "float", "1e+21", "JS switches to exponent notation at 1e21", raw=True)
    add("f_exp_neg7", "float", 1e-7)
    add("f_max_double", "float", "1.7976931348623157e308", raw=True)
    add("f_denormal", "float", "5e-324", "smallest denormal", raw=True)
    add("f_pi_long", "float", 3.141592653589793)
    add("f_trailing_zeros", "float", "2.500", "trailing zeros in source text", raw=True)

    # --- big integers beyond float64 --------------------------------------
    add("i_2p53_plus1", "bigint", "9007199254740993", "2^53+1, first unparsable double", raw=True)
    add("i_2p53_plus1_neg", "bigint", "-9007199254740993", raw=True)
    add("i_huge", "bigint", "123456789012345678901234567890", raw=True)
    add("i_boundary", "bigint", "9223372036854775807", "int64 max", raw=True)
    add("i_leading_zeros_txt", "bigint", "007", "non-canonical source text; parsers differ", raw=True)

    # --- unicode ----------------------------------------------------------
    add("u_nfc", "unicode", dumps_min({"name": "\u00e9cole"}), "precomposed é")
    add("u_nfd", "unicode", dumps_min({"name": "e\u0301cole"}), "decomposed e + combining acute")
    add("u_cjk", "unicode", dumps_min({"city": "\u6771\u4eac"}))
    add("u_emoji_zwj", "unicode", dumps_min({"family": "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"}))
    add("u_flag", "unicode", dumps_min({"region": "\U0001F1EF\U0001F1F5"}))
    add("u_key_unicode", "unicode", dumps_min({"caf\u00e9": 1, "cafe\u0301": 2}, ), "distinct keys only after normalization-aware compare")

    # --- structural edges ---------------------------------------------------
    add("s_empty_obj", "structure", {})
    add("s_empty_arr", "structure", [])
    add("s_null_val", "structure", {"a": None})
    add("s_nested_empty", "structure", {"a": {"b": [{}, []]}})
    add("s_deep64", "structure", _deep(64))
    add("s_mixed", "structure", {
        "t": True, "f": False, "n": None,
        "arr": [1, "two", None, True, [2, 3], {"x": -0.5}],
        "nested": {"deep": {"deeper": {"deepest": [1e17, "s", 0]}}},
    })
    add("s_dup_keys_raw", "dupkeys", '{"a":1,"a":2}', "duplicate keys; last-wins per CANONICAL_FORMS 10.2", raw=True)
    add("s_dup_keys_3way", "dupkeys", '{"k":1,"j":{"k":2},"k":3}', "duplicate at two levels", raw=True)

    # --- string edges -------------------------------------------------------
    add("str_empty", "strings", "")
    add("str_numeric_looking", "strings", {"v": "123"})
    add("str_needs_quotes_glyph", "strings", {"msg": "hello world = trouble {brace} [brk]"})
    add("str_long", "strings", {"blob": "x" * 512})
    add("str_newline_tab", "strings", {"multi": "line1\nline2\tend"})
    add("str_html_escape", "strings", {"s": "a&b<c>d \"q\" 'sq'", "path": "/x?y=1&z=2"}, "Go encoding/json HTML-escapes by default")
    add("str_html_key", "strings", {"a<b>c&": 1}, "escapable characters in key position")

    # key-order permutations of one logical value (same-hash requirement)
    base_a = {"alpha": 1, "beta": [1, 2], "gamma": {"g1": True, "g2": None}}
    add("perm_asc", "permutation", dumps_min(base_a), raw=True)
    add("perm_desc", "permutation", dumps_min(_reverse_keys(base_a)), raw=True)
    add("perm_mid", "permutation", json.dumps(
        {"gamma": {"g2": None, "g1": True}, "beta": [1, 2], "alpha": 1},
        separators=(", ", ": "), ensure_ascii=False), raw=True)

    # a few hundred randomized nested values (seeded)
    rng = random.Random(SEED)
    for n in range(240):
        add(f"r_{n:03d}", "random", _rand_value(rng, 0))


def _deep(n: int) -> dict:
    node = {"leaf": 1}
    for i in range(n):
        node = {f"l{i}": node}
    return node


def _reverse_keys(v):
    if isinstance(v, dict):
        return {k: _reverse_keys(v[k]) for k in reversed(list(v.keys()))}
    if isinstance(v, list):
        return [_reverse_keys(x) for x in v]
    return v


_LEAF_VALUES = [
    lambda r: r.randint(-10**6, 10**6),
    lambda r: round(r.uniform(-1000, 1000), 6),
    lambda r: r.choice([True, False, None]),
    lambda r: "".join(r.choice("abcdefg hij={}") for _ in range(r.randint(0, 12))),
    lambda r: [_rand_value(r, 3) for _ in range(r.randint(0, 3))],
]


def _rand_value(rng: random.Random, depth: int):
    if depth >= 3 or rng.random() < 0.35:
        return rng.choice(_LEAF_VALUES)(rng)
    size = rng.randint(0, 4)
    if rng.random() < 0.5:
        return {_key(rng, i): _rand_value(rng, depth + 1) for i in range(size)}
    return [_rand_value(rng, depth + 1) for _ in range(size)]


def _key(rng: random.Random, i: int) -> str:
    return f"{rng.choice('xyzw')}{i}_{rng.randint(0, 99)}"


# ---------------------------------------------------------------------------
# formatting variants (logical groups) — S4 cache-dedup + Part A cross-form
# ---------------------------------------------------------------------------

VARIANT_GROUPS = [
    ("agent_state", {"agent": "planner", "step": 41, "mem": {"goal": "find keys", "confidence": 0.82},
                     "history": [{"tool": "search", "ok": True}, {"tool": "read", "ok": True}]}),
    ("trace_rows", {"rows": [{"id": i, "latency_ms": 3.5 * i, "ok": i % 3 != 0} for i in range(8)]}),
    ("config", {"model": "claude", "temp": 0.7, "max_tokens": 1024, "stream": True, "stop": ["\n"]}),
]


def build_variants() -> list[dict]:
    groups = []
    for name, val in VARIANT_GROUPS:
        members = [
            {"form": "minified", "json": dumps_min(val)},
            {"form": "pretty", "json": dumps_pretty(val)},
            {"form": "escaped", "json": dumps_escaped(val)},
            {"form": "reordered", "json": dumps_min(_shuffle_keys(val, random.Random(SEED)))},
            {"form": "spaced", "json": json.dumps(val, separators=(", ", ": "), ensure_ascii=False)},
        ]
        groups.append({"group": name, "members": members,
                       "note": "logically identical; every subject must hash all identically"})
    # float textual variants that parse to the SAME double
    groups.append({
        "group": "float_textual",
        "members": [
            {"form": "plain", "json": dumps_min({"score": 0.5})},
            {"form": "exp", "json": '{"score":5e-1}'},
            {"form": "padded", "json": '{"score":0.5000}'},
        ],
        "note": "parse to identical IEEE doubles; canonical forms must agree",
    })
    return groups


def _shuffle_keys(v, rng):
    if isinstance(v, dict):
        items = [(k, _shuffle_keys(val, rng)) for k, val in v.items()]
        rng.shuffle(items)
        return dict(items)
    if isinstance(v, list):
        return [_shuffle_keys(x, rng) for x in v]
    return v


# ---------------------------------------------------------------------------
# malformed corpus (S5) — realistic LLM syntax slips
# ---------------------------------------------------------------------------

MALFORMED = [
    # (id, error_class, text, expected_recovered_value_or_None)
    ("trail_comma_obj", "trailing-comma", '{"action":"search","limit":5,}', {"action": "search", "limit": 5}),
    ("trail_comma_arr", "trailing-comma", "[1,2,3,]", [1, 2, 3]),
    ("single_quotes", "quote-style", "{'action':'search','limit':5}", {"action": "search", "limit": 5}),
    ("unquoted_keys", "quote-style", '{action:"search", limit:5}', {"action": "search", "limit": 5}),
    ("colon_eq_mix", "separator-mix", '{"action"="search", "limit":5}', {"action": "search", "limit": 5}),
    ("eq_only", "separator-mix", "{action=search limit=5}", {"action": "search", "limit": 5}),
    ("true_capital", "literal-case", '{"verbose":True,"retry":False}', {"verbose": True, "retry": False}),
    ("none_literal", "literal-case", '{"value":None}', None),
    ("js_undefined", "literal-case", '{"value":undefined}', None),
    ("comment_line", "comments", '{"action":"search" // find stuff\n}', None),
    ("misspelled_key", "misspelled-key", '{"actoin":"search","limit":5}', None),
    ("missing_close", "structural", '{"action":"search","limit":5', None),
    ("double_comma", "structural", '{"a":1,, "b":2}', None),
    ("smart_quotes", "quote-style", '{"action":\\"search\\", \\"limit\\":5}', None),
    ("loose_ok_plain", "control-valid", '{"action":"search","limit":5}', {"action": "search", "limit": 5}),
]


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    build_fixtures()

    with (DATA / "fixtures.jsonl").open("w", encoding="utf-8") as fh:
        for fx in FIXTURES:
            fh.write(json.dumps(fx, ensure_ascii=False) + "\n")

    with (DATA / "variants.jsonl").open("w", encoding="utf-8") as fh:
        for grp in build_variants():
            fh.write(json.dumps(grp, ensure_ascii=False) + "\n")

    with (DATA / "malformed.jsonl").open("w", encoding="utf-8") as fh:
        for mid, eclass, text, expected in MALFORMED:
            fh.write(json.dumps({
                "id": mid, "error_class": eclass, "text": text,
                "expected": expected,
            }) + "\n")

    # bench payloads for Part C
    payloads = [
        {"id": "small_state", "json": dumps_min(VARIANT_GROUPS[0][1])},
        {"id": "tabular_batch", "json": dumps_min(
            {"rows": [{"id": i, "tool": f"tool_{i % 4}", "ok": i % 3 == 0,
                       "latency_ms": round(3.5 * i, 2), "score": 0.5 + i * 0.001}
                      for i in range(40)]})},
        {"id": "nested_trace", "json": dumps_min(_deep(24))},
    ]
    with (DATA / "bench_payloads.jsonl").open("w", encoding="utf-8") as fh:
        for p in payloads:
            fh.write(json.dumps(p) + "\n")

    print(f"fixtures={len(FIXTURES)} variant_groups=4 malformed={len(MALFORMED)} bench=3")


if __name__ == "__main__":
    main()
