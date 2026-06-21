#!/usr/bin/env python3
"""
GLYPH 8-Scenario Cross-Language Gauntlet — orchestrator / evaluator.

Runs the three per-language runners (Go, Python, JS) under identical conditions
against the shared inputs.json, then applies one set of pass/fail criteria to all
of them (the single evaluator → "consistent evaluation method"). Prints a human
evidence report, writes report.json, and exits non-zero if any scenario fails.

    python3 gauntlet/scenarios/gauntlet.py [--no-build]

Each scenario is PASS iff every applicable language ran without error AND every
check (per-language + byte-for-byte cross-language) holds. Evidence for every
outcome is recorded in report.json.

Capability coverage:
  S1 JSON bridge · S2 canonicalization · S3 fingerprint+parity · S4 tabular
  compaction · S5 patch apply · S6 patch-base fail-closed · S7 GS1 framing+wire
  parity · S8 streaming firewall. Cross-language conformance is woven through
  S1-S5 (Go/Py/JS), S6 (base parity Go/Py/JS), S7 (Go/JS), S8 (Py/JS).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
INPUTS = os.path.join(HERE, "inputs.json")
REPORT = os.path.join(HERE, "report.json")

GO_DIR = os.path.join(ROOT, "go")
JS_DIR = os.path.join(ROOT, "js")

# ── ANSI ──────────────────────────────────────────────────────────────────
def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else s

GREEN = lambda s: _c("32", s)
RED = lambda s: _c("31", s)
YEL = lambda s: _c("33", s)
DIM = lambda s: _c("2", s)
BOLD = lambda s: _c("1", s)


# ── run the language runners ────────────────────────────────────────────────
def run_runner(cmd, cwd, label):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)
    except Exception as exc:  # noqa: BLE001
        return {"lang": label, "version": "?", "scenarios": {}, "_runner_error": str(exc)}
    if p.returncode != 0:
        return {"lang": label, "version": "?", "scenarios": {},
                "_runner_error": f"exit {p.returncode}: {p.stderr.strip()[:500]}"}
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        return {"lang": label, "version": "?", "scenarios": {},
                "_runner_error": f"bad JSON: {exc}; stderr={p.stderr.strip()[:300]}"}


def collect(no_build):
    if not no_build:
        print(DIM("· building JS (tsc) ..."))
        b = subprocess.run(["npm", "run", "build"], cwd=JS_DIR, capture_output=True, text=True)
        if b.returncode != 0:
            print(RED("JS build failed:\n") + b.stdout[-2000:] + b.stderr[-2000:])
            sys.exit(2)
    results = {}
    results["py"] = run_runner([sys.executable, os.path.join(HERE, "runner.py"), INPUTS], HERE, "py")
    results["js"] = run_runner(["node", os.path.join(HERE, "runner.cjs"), INPUTS], HERE, "js")
    results["go"] = run_runner(["go", "run", "./cmd/gauntletrunner", INPUTS], GO_DIR, "go")
    return results


# ── evaluation helpers ──────────────────────────────────────────────────────
def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


class Eval:
    """Collects per-scenario checks; a scenario passes iff all checks pass."""
    def __init__(self, title, langs):
        self.title = title
        self.langs = langs
        self.checks = []      # (name, passed, detail)
        self.evidence = {}    # lang -> compact evidence shown in report

    def check(self, name, passed, detail=""):
        self.checks.append((name, bool(passed), detail))
        return bool(passed)

    @property
    def passed(self):
        return all(p for _, p, _ in self.checks) and len(self.checks) > 0


def ev_of(results, key, langs):
    """Return {lang: evidence}; record missing/errored langs as a failing note."""
    got, errs = {}, {}
    for L in langs:
        if results.get(L, {}).get("_runner_error"):
            errs[L] = "runner: " + results[L]["_runner_error"]
            continue
        entry = results.get(L, {}).get("scenarios", {}).get(key)
        if entry is None:
            errs[L] = "scenario missing"
        elif not entry.get("ok"):
            errs[L] = entry.get("error", "errored")
        else:
            got[L] = entry["evidence"]
    return got, errs


def equal_across(ev, key, transform=lambda x: x):
    vals = {L: transform(e[key]) for L, e in ev.items()}
    uniq = set(vals.values())
    return len(uniq) <= 1, vals


# ── per-scenario evaluators ─────────────────────────────────────────────────
def eval_S1(ev, inp):
    e = Eval("JSON bridge round-trip fidelity", ["go", "py", "js"])
    for L, d in ev.items():
        e.check(f"{L}: round-trip == input", d["equals_input"])
        e.evidence[L] = {"equals_input": d["equals_input"]}
    ok, vals = equal_across(ev, "roundtrip", canon)
    e.check("cross-lang: round-trip values identical", ok,
            "" if ok else "differing round-trips")
    snap_c = canon(inp["S1_json_bridge"]["snapshot"])
    e.check("round-trip == source snapshot (all langs)",
            all(canon(d["roundtrip"]) == snap_c for d in ev.values()))
    return e


def eval_S2(ev, inp):
    e = Eval("Canonicalization determinism + cross-language agreement", ["go", "py", "js"])
    for L, d in ev.items():
        e.check(f"{L}: key-order variants → one canonical form", d["variants_consistent"])
        e.evidence[L] = {"canonical": d["canonical"]}
    ok, _ = equal_across(ev, "canonical")
    e.check("cross-lang: canonical form identical", ok)
    okf, _ = equal_across(ev, "floats", canon)
    e.check("cross-lang: number canonicalization identical", okf)
    return e


def eval_S3(ev, inp):
    e = Eval("State fingerprint identity, sensitivity & cross-language parity", ["go", "py", "js"])
    for L, d in ev.items():
        e.check(f"{L}: equal states → equal fingerprint (identity)", d["fp_base"] == d["fp_equiv"])
        e.check(f"{L}: changed state → different fingerprint (sensitivity)", d["fp_base"] != d["fp_mutated"])
        e.check(f"{L}: 64-hex digest", len(d["fp_base"]) == 64)
        e.evidence[L] = {"fp_base": d["fp_base"][:16] + "…"}
    okb, _ = equal_across(ev, "fp_base")
    e.check("cross-lang: fp(base) byte-for-byte identical", okb)
    okm, _ = equal_across(ev, "fp_mutated")
    e.check("cross-lang: fp(mutated) byte-for-byte identical", okm)
    return e


def eval_S4(ev, inp):
    e = Eval("Tabular packing compaction + recovery + cross-language parity", ["go", "py", "js"])
    thr = inp["S4_tabular"]["min_savings_vs_json"]
    for L, d in ev.items():
        savings = 1 - d["bytes_tab"] / d["bytes_json"]
        e.check(f"{L}: emits @tab block", d["is_tabular"])
        e.check(f"{L}: tabular < JSON ({savings:.0%} ≥ {thr:.0%})", d["bytes_tab"] < d["bytes_json"] and savings >= thr)
        e.check(f"{L}: tabular < list form", d["bytes_tab"] < d["bytes_list"])
        e.check(f"{L}: parse(tabular) recovers value", d["roundtrip_ok"])
        e.evidence[L] = {"bytes_tab": d["bytes_tab"], "savings": f"{savings:.0%}",
                         "header": d["canonical_tab"].split("\n", 1)[0]}
    okc, vals = equal_across(ev, "canonical_tab")
    e.check("cross-lang: tabular canonical form identical", okc,
            "" if okc else "headers: " + " | ".join(sorted({d["canonical_tab"].split(chr(10),1)[0] for d in ev.values()})))
    okf, _ = equal_across(ev, "fp_recovered")
    e.check("cross-lang: recovered fingerprint identical", okf)
    return e


def eval_S5(ev, inp):
    e = Eval("Patch apply correctness (set / append / delete / numeric-delta)", ["go", "py", "js"])
    expected = canon(inp["S5_patch_apply"]["expected"])
    for L, d in ev.items():
        e.check(f"{L}: applied state == expected", canon(d["result"]) == expected)
        e.check(f"{L}: base document not mutated", d["base_unchanged"])
        e.evidence[L] = {"result_ok": canon(d["result"]) == expected}
    okr, _ = equal_across(ev, "result", canon)
    e.check("cross-lang: applied state identical", okr)
    okf, _ = equal_across(ev, "fp_result")
    e.check("cross-lang: result fingerprint identical", okf)
    return e


def eval_S6(ev, inp):
    e = Eval("Standalone patch base verification / fail-closed", ["go", "py", "js"])
    # Standalone verify exists in Go + Py; JS contributes the base fingerprint only.
    for L in ("go", "py"):
        if L in ev:
            e.check(f"{L}: correct base accepted", ev[L]["verify_accept"])
            e.check(f"{L}: stale base rejected (fail-closed)", ev[L]["verify_reject"])
    for L, d in ev.items():
        e.evidence[L] = {"base16": d["base16"]}
    okb, vals = equal_across(ev, "base16")
    e.check("cross-lang: base fingerprint identical (Go/Py/JS)", okb,
            "" if okb else "; ".join(f"{L}={v}" for L, v in sorted(vals.items())))
    return e


def eval_S7(ev, inp):
    e = Eval("GS1 stream framing: wire parity + decode round-trip + base-enforced cursor", ["go", "js"])
    frames = inp["S7_gs1_stream"]["frames"]
    exp_kinds = [f["kind"] for f in frames]
    for L, d in ev.items():
        e.check(f"{L}: all frames decode (payloads intact)", d["payloads_ok"])
        e.check(f"{L}: frame count == {len(frames)}", d["frame_count"] == len(frames))
        e.check(f"{L}: kinds in order", d["kinds"] == exp_kinds)
        e.check(f"{L}: cursor accepts correct base", d["base_accept"])
        e.check(f"{L}: cursor rejects stale base (fail-closed)", d["base_reject"])
        e.evidence[L] = {"stream_sha256": d["stream_sha256"][:16] + "…"}
    oks, _ = equal_across(ev, "stream_sha256")
    e.check("cross-lang: encoded wire bytes byte-for-byte identical (Go==JS)", oks)
    okh, _ = equal_across(ev, "statehash_hex")
    e.check("cross-lang: stream state hash identical (Go==JS)", okh)
    return e


def eval_S8(ev, inp):
    e = Eval("Streaming validator / tool firewall (early rejection) + verdict parity", ["py", "js"])
    for L, d in ev.items():
        e.check(f"{L}: allowed tool ({d['allowed_tool']}) accepted", d["allowed_accepted"])
        e.check(f"{L}: blocked tool rejected (unknown-tool, fail-closed)", d["blocked_rejected"])
        e.check(f"{L}: stops early (bytes avoided = {d['bytes_avoided']})", d["bytes_avoided"] > 0)
        e.evidence[L] = {"bytes_avoided": d["bytes_avoided"], "code": d["blocked_code"]}
    pa = all(d["allowed_accepted"] for d in ev.values())
    pb = all(d["blocked_rejected"] for d in ev.values())
    e.check("cross-lang: verdict parity (both accept allowed, both reject blocked)", pa and pb)
    return e


EVALUATORS = [
    ("S1", ["go", "py", "js"], eval_S1),
    ("S2", ["go", "py", "js"], eval_S2),
    ("S3", ["go", "py", "js"], eval_S3),
    ("S4", ["go", "py", "js"], eval_S4),
    ("S5", ["go", "py", "js"], eval_S5),
    ("S6", ["go", "py", "js"], eval_S6),
    ("S7", ["go", "js"], eval_S7),
    ("S8", ["py", "js"], eval_S8),
]


def evaluate(results, inp):
    report = {"scenarios": {}, "versions": {L: results.get(L, {}).get("version", "?") for L in ("go", "py", "js")}}
    passed_count = 0
    for key, langs, fn in EVALUATORS:
        ev, errs = ev_of(results, key, langs)
        if errs:
            e = Eval("(runner/scenario error)", langs)
            for L, msg in errs.items():
                e.check(f"{L}: ran cleanly", False, msg)
            if ev:  # still evaluate the langs that did run
                e2 = fn(ev, inp)
                e.title = e2.title
                e.checks = [(f"{L}: ran cleanly", False, m) for L, m in errs.items()] + e2.checks
                e.evidence = e2.evidence
        else:
            e = fn(ev, inp)
        report["scenarios"][key] = {
            "title": e.title, "langs": langs, "passed": e.passed,
            "checks": [{"name": n, "passed": p, "detail": d} for n, p, d in e.checks],
            "evidence": e.evidence,
        }
        if e.passed:
            passed_count += 1
    report["summary"] = {"passed": passed_count, "total": len(EVALUATORS),
                         "all_passed": passed_count == len(EVALUATORS)}
    return report


# ── render ──────────────────────────────────────────────────────────────────
def render(report):
    print()
    print(BOLD("  GLYPH 8-Scenario Cross-Language Gauntlet"))
    v = report["versions"]
    print(DIM(f"  go={v['go']}  py={v['py']}  js={v['js']}"))
    print(DIM("  " + "─" * 70))
    for key, sc in report["scenarios"].items():
        badge = GREEN(" PASS ") if sc["passed"] else RED(" FAIL ")
        langs = "/".join(sc["langs"])
        print(f"\n  [{badge}] {BOLD(key)} · {sc['title']}  {DIM('(' + langs + ')')}")
        for ck in sc["checks"]:
            mark = GREEN("✓") if ck["passed"] else RED("✗")
            line = f"      {mark} {ck['name']}"
            if ck["detail"] and not ck["passed"]:
                line += DIM("  — " + ck["detail"])
            print(line)
        if sc["evidence"]:
            for L, evd in sc["evidence"].items():
                print(DIM(f"        {L}: {json.dumps(evd, ensure_ascii=False)}"))
    s = report["summary"]
    print(DIM("\n  " + "─" * 70))
    tag = GREEN("ALL SCENARIOS PASS") if s["all_passed"] else RED(f"{s['total']-s['passed']} SCENARIO(S) FAILING")
    print(f"  {BOLD(str(s['passed']) + '/' + str(s['total']))} scenarios passed — {tag}\n")


def main():
    no_build = "--no-build" in sys.argv
    with open(INPUTS, encoding="utf-8") as fh:
        inp = json.load(fh)
    results = collect(no_build)
    report = evaluate(results, inp)
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump({"report": report, "raw": results}, fh, ensure_ascii=False, indent=2)
    render(report)
    sys.exit(0 if report["summary"]["all_passed"] else 1)


if __name__ == "__main__":
    main()
