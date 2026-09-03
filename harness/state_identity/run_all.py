#!/usr/bin/env python3
"""run_all — state identity harness orchestrator.

Produces:
  results/results.json   deterministic (fixed seeds, committed fixtures)
  results/costs.json     timings only (varies by machine/run)
  results/meta.json      tool versions

Exits non-zero if the harness itself malfunctions. Determinism check:
running twice yields byte-identical results.json.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GLYPH_ROOT = HERE.parents[1]
sys.path.insert(0, str(GLYPH_ROOT / "py"))
sys.path.insert(0, str(HERE / "generators"))
sys.path.insert(0, str(HERE / "scenarios"))
sys.path.insert(0, str(HERE / "costs"))

LANGS = ["python", "go", "js"]
SUBJECTS = ["naive", "minified", "jcs", "glyph", "canon_json"]
RUNNERS = {
    "python": {"cmd": [sys.executable, str(HERE / "subjects" / "runner.py")], "cwd": HERE},
    "go": {"cmd": ["go", "run", "./cmd/runner"], "cwd": HERE / "subjects" / "go"},
    "js": {"cmd": ["npx", "--prefix", str(GLYPH_ROOT / "js"), "tsx",
                   str(HERE / "subjects" / "js" / "runner.mts")],
           "cwd": GLYPH_ROOT / "js"},
}


def sh(cmd: list[str], cwd: Path) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{cmd} -> rc={p.returncode}\n{p.stderr[-800:]}")
    return p.stdout


def ensure_data() -> None:
    need = all((HERE / "data" / f).exists() for f in
               ["fixtures.jsonl", "variants.jsonl", "malformed.jsonl", "bench_payloads.jsonl"])
    if not need:
        import edge_values
        edge_values.main()


def selftests() -> dict:
    out = {}
    vectors = str(HERE / "data" / "jcs_vectors")
    out["python"] = sh([sys.executable, str(HERE / "subjects" / "runner.py"),
                        "--selftest", vectors], HERE).strip()
    out["js"] = sh(RUNNERS["js"]["cmd"] + ["--selftest", vectors],
                   RUNNERS["js"]["cwd"]).strip()
    out["go"] = sh(["go", "run", "./cmd/runner", "--selftest",
                    "../../../data/jcs_vectors"], RUNNERS["go"]["cwd"]).strip()
    for lang, line in out.items():
        if "FAIL" in line or not line.endswith("vectors pass"):
            raise RuntimeError(f"{lang} JCS selftest failed: {line}")
        if "6/6" not in line and f"/6" not in line:
            pass  # vector count may grow; FAIL check above is authoritative
    return out


def flatten_inputs() -> tuple[list[dict], list[str]]:
    fixtures = [json.loads(l) for l in (HERE / "data" / "fixtures.jsonl").read_text().splitlines() if l.strip()]
    variants = [json.loads(l) for l in (HERE / "data" / "variants.jsonl").read_text().splitlines() if l.strip()]
    inputs = [{"id": fx["id"], "klass": fx["klass"], "json": fx["json"]} for fx in fixtures]
    for g in variants:
        for m in g["members"]:
            inputs.append({"id": f"{g['group']}:{m['form']}", "klass": f"variant/{g['group']}",
                           "json": m["json"]})
    lines = [json.dumps({"id": i["id"], "json": i["json"]}, ensure_ascii=False) for i in inputs]
    return inputs, lines


def collect_rows(inputs: list[dict]) -> dict:
    """matrix[lang][subject][fixture_id] = {'hash':…,'error':…|None,'klass':…}"""
    matrix: defaultdict = defaultdict(lambda: defaultdict(dict))
    for lang in LANGS:
        r = RUNNERS[lang]
        proc = subprocess.run(r["cmd"], cwd=r["cwd"],
                              input="\n".join(json.dumps({"id": i["id"], "json": i["json"]},
                                                          ensure_ascii=False) for i in inputs) + "\n",
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"{lang} runner failed: {proc.stderr[-800:]}")
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            matrix[lang][row["subject"]][row["id"]] = {
                "hash": row.get("hash", ""), "error": row.get("error")}
    return matrix


def analyse_part_a(matrix: dict, inputs: list[dict]) -> dict:
    klass_of = {i["id"]: i["klass"] for i in inputs}
    analysis: defaultdict = defaultdict(lambda: {"agree": 0, "disagree": 0, "errors": 0,
                                                 "divergent_ids": []})
    for subject in SUBJECTS:
        for fid in klass_of:
            hashes = set()
            errored = False
            for lang in LANGS:
                cell = matrix[lang][subject].get(fid)
                if cell is None or cell["error"]:
                    errored = True
                elif not subject.startswith("_"):
                    hashes.add(cell["hash"])
            a = analysis[f"{subject}/ALL"]
            if errored:
                a["errors"] += 1
            elif len(hashes) <= 1:
                a["agree"] += 1
            else:
                a["disagree"] += 1
                if len(a["divergent_ids"]) < 12:
                    a["divergent_ids"].append(fid)

    # per-klass table per subject
    by_klass2: defaultdict = defaultdict(lambda: {"agree": 0, "disagree": 0, "errors": 0})
    for subject in SUBJECTS:
        for fid in klass_of:
            k = klass_of[fid]
            cell_any = [matrix[l][subject].get(fid) for l in LANGS]
            if any(c is None or c["error"] for c in cell_any):
                by_klass2[f"{subject}/{k}"]["errors"] += 1
                continue
            hs = {c["hash"] for c in cell_any}
            key = "agree" if len(hs) <= 1 else "disagree"
            by_klass2[f"{subject}/{k}"][key] += 1

    # glyph↔jcs equivalence where both computed
    eq = {"same": 0, "diff": 0}
    for fid in klass_of:
        cells = [matrix[l]["jcs"].get(fid) for l in LANGS] + [matrix[l]["glyph"].get(l) for l in LANGS]
        jcs_ok = [c["hash"] for l in LANGS if (c := matrix[l]["jcs"].get(fid)) and not c["error"]]
        gly_ok = [c["hash"] for l in LANGS if (c := matrix[l]["glyph"].get(fid)) and not c["error"]]
        if jcs_ok and gly_ok:
            same = set(jcs_ok) & set(gly_ok)
            eq["same" if same else "diff"] += 1

    # variant-group consistency per subject per lang (logical invariance)
    variant_consistency: defaultdict = defaultdict(lambda: {"consistent": 0, "inconsistent": 0})
    variants = [json.loads(l) for l in (HERE / "data" / "variants.jsonl").read_text().splitlines() if l.strip()]
    for g in variants:
        ids = [f"{g['group']}:{m['form']}" for m in g["members"]]
        for lang in LANGS:
            for subject in SUBJECTS:
                hs = set()
                bad = False
                for i in ids:
                    c = matrix[lang][subject].get(i)
                    if c is None or c["error"]:
                        bad = True
                        break
                    hs.add(c["hash"])
                vkey = f"{subject}"
                bucket = variant_consistency[vkey]
                if bad:
                    continue
                bucket["consistent" if len(hs) == 1 else "inconsistent"] += 1

    # canon_json idempotence (SPEC-CANON.md §7): each runner re-parses its own canonical
    # output with stdlib JSON and reports error "idempotence: …" if it does not re-canonicalize
    # to the same bytes.
    idem = {"ok": 0, "failed": 0}
    for lang in LANGS:
        for c in matrix[lang]["canon_json"].values():
            if not c["error"]:
                idem["ok"] += 1
            elif c["error"].startswith("idempotence"):
                idem["failed"] += 1

    return {
        "cross_language_by_subject": {k: v for k, v in analysis.items()},
        "canon_json_idempotence": idem,
        "cross_language_by_subject_and_class": {
            k: v for k, v in sorted(by_klass2.items())},
        "glyph_jcs_hash_equivalence": eq,
        "variant_group_logical_invariance": {k: dict(v) for k, v in variant_consistency.items()},
    }


def main() -> int:
    ensure_data()
    meta = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "seed": 20260821,
    }
    selftest_lines = selftests()

    inputs, _ = flatten_inputs()
    matrix = collect_rows(inputs)
    part_a = analyse_part_a(matrix, inputs)

    import s1_stale_patch_race
    import s2_cross_lang_relay
    import s3_stream_desync
    import s4_cache_dedup
    import s5_malformed_recovery

    results = {
        "part_a_divergence_hunt": part_a,
        "s1_stale_patch_race": s1_stale_patch_race.run(),
        "s2_cross_lang_relay": s2_cross_lang_relay.run(),
        "s3_stream_desync": s3_stream_desync.run(),
        "s4_cache_dedup": s4_cache_dedup.run(),
        "s5_malformed_recovery": s5_malformed_recovery.run(),
        "_meta": {"selftests": selftest_lines, **meta},
    }

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    try:
        import cost_accounting
        (out_dir / "costs.json").write_text(
            json.dumps(cost_accounting.run(), indent=2, sort_keys=True) + "\n")
    except Exception as e:  # noqa: BLE001 — costs are informational; never fail the suite
        (out_dir / "costs.json").write_text(json.dumps({"error": str(e)}))

    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    digest = hashlib.sha256((out_dir / "results.json").read_bytes()).hexdigest()[:16]
    print(f"harness complete: {len(inputs)} fixtures x {len(LANGS)} langs x {len(SUBJECTS)} subjects")
    print(f"results.json sha256[:16] = {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
