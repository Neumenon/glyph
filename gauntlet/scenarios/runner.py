#!/usr/bin/env python3
"""
Python scenario runner for the GLYPH cross-language gauntlet.

Reads the shared inputs.json, runs every scenario applicable to the Python
implementation, and prints a single JSON evidence object to stdout. It does NOT
decide pass/fail — that is the orchestrator's job (one evaluator, applied
identically to every language → "consistent evaluation method").

Applicable scenarios: S1, S2, S3, S4, S5, S6, S8.
(S7 / GS1 stream framing is Go+JS only — Python has no GS1 surface.)

Usage:  python3 runner.py <inputs.json>
"""
import json
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "py"))

import glyph  # noqa: E402
from glyph import (  # noqa: E402
    from_json_loose, to_json_loose, canonicalize_loose,
    canonicalize_loose_no_tabular, parse_loose, fingerprint_loose,
    equal_loose, parse_patch, apply_patch, compute_base_fingerprint,
    verify_patch_base, PatchBaseMismatch, StreamingValidator, ToolRegistry,
)


def _cjson(value):
    """Compact, key-sorted JSON bytes count helper input."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def scenario(fn):
    try:
        return {"ok": True, "evidence": fn()}
    except Exception as exc:  # fail loud, per-scenario isolation
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ── S1 ──────────────────────────────────────────────────────────────────────
def s1(inp):
    snap = inp["S1_json_bridge"]["snapshot"]
    gv = from_json_loose(snap)
    back = to_json_loose(gv)
    return {"roundtrip": back, "equals_input": back == snap}


# ── S2 ──────────────────────────────────────────────────────────────────────
def s2(inp):
    data = inp["S2_canonical"]
    canons = [canonicalize_loose(from_json_loose(v)) for v in data["variants"]]
    floats = {t: canonicalize_loose(parse_loose(t)) for t in data["floats_text"]}
    return {
        "canonical": canons[0],
        "variants_consistent": all(c == canons[0] for c in canons),
        "floats": floats,
    }


# ── S3 ──────────────────────────────────────────────────────────────────────
def s3(inp):
    d = inp["S3_fingerprint"]
    return {
        "fp_base": fingerprint_loose(from_json_loose(d["base"])),
        "fp_equiv": fingerprint_loose(from_json_loose(d["equiv"])),
        "fp_mutated": fingerprint_loose(from_json_loose(d["mutated"])),
    }


# ── S4 ──────────────────────────────────────────────────────────────────────
def s4(inp):
    trace = inp["S4_tabular"]["trace"]
    gv = from_json_loose(trace)
    tab = canonicalize_loose(gv)
    lst = canonicalize_loose_no_tabular(gv)
    recovered = parse_loose(tab)
    return {
        "is_tabular": "@tab" in tab,
        "canonical_tab": tab,
        "bytes_json": len(_cjson(trace).encode()),
        "bytes_list": len(lst.encode()),
        "bytes_tab": len(tab.encode()),
        "roundtrip_ok": equal_loose(gv, recovered),
        "fp_recovered": fingerprint_loose(recovered),
    }


# ── S5 ──────────────────────────────────────────────────────────────────────
def s5(inp):
    d = inp["S5_patch_apply"]
    base = from_json_loose(d["base"])
    before = to_json_loose(base)
    patch = parse_patch(d["patch_text"])
    result = apply_patch(base, patch)
    return {
        "result": to_json_loose(result),
        "fp_result": fingerprint_loose(result),
        "base_unchanged": to_json_loose(base) == before,
    }


# ── S6 ──────────────────────────────────────────────────────────────────────
def s6(inp):
    d = inp["S6_patch_base"]
    state = from_json_loose(d["state"])
    base16 = compute_base_fingerprint(state)
    ops = "\n".join(d["patch_op_lines"])

    happy = parse_patch(f"@patch @base={base16} @target={d['target']}\n{ops}\n@end")
    try:
        verify_patch_base(state, happy)
        accept = True
    except PatchBaseMismatch:
        accept = False

    stale = parse_patch(f"@patch @base={d['stale_base']} @target={d['target']}\n{ops}\n@end")
    try:
        verify_patch_base(state, stale)
        reject = False
    except PatchBaseMismatch:
        reject = True

    return {"base16": base16, "verify_accept": accept, "verify_reject": reject}


# ── S8 ──────────────────────────────────────────────────────────────────────
def _registry(spec):
    reg = ToolRegistry()
    for name, fields in spec.items():
        reg.add_tool(name, {k: {"type": v} for k, v in fields.items()})
    return reg


def _feed(spec, text):
    v = StreamingValidator(_registry(spec))
    stop_index = -1
    res = None
    for ch in text:
        res = v.push_token(ch)
        if res.errors and stop_index == -1:
            stop_index = v.char_count
    return v, res, stop_index


def s8(inp):
    d = inp["S8_firewall"]
    spec = d["registry"]

    _, ar, _ = _feed(spec, d["allowed_py"])
    allowed_unknown = any("UNKNOWN_TOOL" in e for e in ar.errors)
    allowed_accepted = ar.complete and ar.valid and not allowed_unknown

    bv, br, stop = _feed(spec, d["blocked_py"])
    blocked_unknown = any("UNKNOWN_TOOL" in e for e in br.errors)
    total = len(d["blocked_py"])
    return {
        "allowed_accepted": allowed_accepted,
        "allowed_tool": ar.tool_name,
        "blocked_rejected": bool(br.should_cancel and blocked_unknown),
        "blocked_code": "UNKNOWN_TOOL" if blocked_unknown else (br.errors[0] if br.errors else ""),
        "blocked_tool_seen": br.tool_name,
        "stop_index": stop,
        "total_len": total,
        "bytes_avoided": (total - stop) if stop >= 0 else 0,
    }


def main():
    inputs_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "inputs.json")
    with open(inputs_path, encoding="utf-8") as fh:
        inp = json.load(fh)

    out = {
        "lang": "py",
        "version": f"Python {platform.python_version()}",
        "scenarios": {
            "S1": scenario(lambda: s1(inp)),
            "S2": scenario(lambda: s2(inp)),
            "S3": scenario(lambda: s3(inp)),
            "S4": scenario(lambda: s4(inp)),
            "S5": scenario(lambda: s5(inp)),
            "S6": scenario(lambda: s6(inp)),
            "S8": scenario(lambda: s8(inp)),
        },
    }
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
