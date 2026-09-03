#!/usr/bin/env python3
"""Measure GLYPH vs JSON on *data-plane* MCP-shaped tool results.

The coding-traffic capture (harness/cc-trace) showed ~0% GLYPH savings because
those results are big unique text blobs in tiny dicts. The proven 40-50% win
needs homogeneous record lists — what *data-plane* MCP servers return (SQL rows,
search hits, file inventories, commit logs, catalogs). This builds such results
from real local sources and measures the real byte savings, with gzip as the
storage/transport competitor for contrast.

Bytes are exact; for record lists the comprehension run calibrated token savings
at roughly 0.75x the byte savings (e.g. -64% bytes ≈ -49% cl100k tokens).
"""
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comprehension.encode import enc_glyph_loose, enc_glyph_tabular, enc_json  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def git_commits(n=80):
    fmt = "%H%x1f%an%x1f%ae%x1f%aI%x1f%s"
    out = subprocess.run(["git", "-C", str(REPO), "log", f"-{n}", f"--pretty=format:{fmt}"],
                         capture_output=True, text=True).stdout
    recs = []
    for line in out.splitlines():
        h, an, ae, ai, s = (line.split("\x1f") + [""] * 5)[:5]
        recs.append({"hash": h[:12], "author": an, "email": ae, "date": ai, "subject": s})
    return recs


def file_inventory(limit=120):
    recs = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__",
                                                ".hypothesis", ".pytest_cache", "dist", "build", ".mypy_cache"}]
        for f in files:
            p = Path(root) / f
            try:
                b = p.stat().st_size
                lines = sum(1 for _ in p.open("rb")) if b < 2_000_000 else 0
            except Exception:
                continue
            recs.append({"path": str(p.relative_to(REPO)), "ext": p.suffix.lstrip(".") or "none",
                         "bytes": b, "lines": lines})
            if len(recs) >= limit:
                return recs
    return recs


def measure(name, recs):
    j = enc_json(recs)
    l = enc_glyph_loose(recs)
    t = enc_glyph_tabular(recs)
    jb, lb, tb = len(j.encode()), len(l.encode()), len(t.encode())
    gj, gt = len(gzip.compress(j.encode(), 9)), len(gzip.compress(t.encode(), 9))
    print(f"\n=== {name}  ({len(recs)} records) ===")
    print(f"  json (min)        {jb:>9} B")
    print(f"  glyph loose       {lb:>9} B   {100*(jb-lb)/jb:+.1f}% vs json")
    print(f"  glyph tabular     {tb:>9} B   {100*(jb-tb)/jb:+.1f}% vs json   (@tab: {'yes' if '@tab' in t else 'NO'})")
    print(f"  -- gzip --        json.gz {gj} B   vs   glyph_tab.gz {gt} B")
    return {"name": name, "records": len(recs), "json_bytes": jb,
            "glyph_loose_bytes": lb, "glyph_tabular_bytes": tb,
            "tabular_pct": round(100 * (jb - tb) / jb, 1),
            "tabular_engaged": "@tab" in t,
            "json_gz": gj, "glyph_tab_gz": gt}


def main():
    datasets = [("git_commits (git MCP)", git_commits()),
                ("file_inventory (fs/code-search MCP)", file_inventory())]
    # any on-disk JSON list of homogeneous objects = a real data payload
    extra = REPO / "go/glyph/testdata/equivalence_classes.json"
    if extra.exists():
        try:
            v = json.loads(extra.read_text())
            if isinstance(v, list) and len(v) >= 3 and all(isinstance(x, dict) for x in v):
                datasets.append((f"{extra.name} (on-disk records)", v))
        except Exception:
            pass

    results = [measure(n, r) for n, r in datasets]
    # any extra real result payloads passed as argv JSON files (e.g. captured MCP results)
    for arg in sys.argv[1:]:
        try:
            v = json.loads(Path(arg).read_text())
            recs = v if isinstance(v, list) else next((x for x in v.values() if isinstance(x, list)), None)
            if recs and all(isinstance(x, dict) for x in recs):
                results.append(measure(f"{Path(arg).name} (provided)", recs))
        except Exception as e:
            print(f"skip {arg}: {e}")

    print("\n" + "=" * 60)
    print("addressable record-list results: glyph_tabular vs json (bytes)")
    for r in results:
        print(f"  {r['name']:<42} {r['tabular_pct']:+.1f}%")


if __name__ == "__main__":
    main()
