"""Part C — cost accounting.

CPU ns/op per subject per language over fixed payloads (informational; wall
clock varies run to run, so timings live in results/costs.json, NOT in the
determinism-checked results.json). Token/byte counts are deterministic and
return here.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
GLYPH_ROOT = HERE.parents[1]
sys.path.insert(0, str(GLYPH_ROOT / "py"))

PAYLOADS = HERE / "data" / "bench_payloads.jsonl"
SUBJ_GO = HERE / "subjects" / "go"
JS_DIR = GLYPH_ROOT / "js"


def bench_all() -> dict:
    rows: dict[str, list] = {}

    py_rows = subprocess.run(
        [sys.executable, str(HERE / "subjects" / "runner.py"), "--mode", "bench", str(PAYLOADS)],
        capture_output=True, text=True, check=True)
    rows["python"] = [json.loads(l) for l in py_rows.stdout.splitlines() if l.strip()]

    js_rows = subprocess.run(
        ["npx", "--prefix", str(JS_DIR), "tsx",
         str(HERE / "subjects" / "js" / "runner.mts"), "--mode", "bench", str(PAYLOADS)],
        cwd=JS_DIR, capture_output=True, text=True, check=True)
    rows["js"] = [json.loads(l) for l in js_rows.stdout.splitlines() if l.strip()]

    go_rows = subprocess.run(
        ["go", "run", "./cmd/runner", "--mode", "bench", str(PAYLOADS)],
        cwd=SUBJ_GO, capture_output=True, text=True, check=True)
    rows["go"] = [json.loads(l) for l in go_rows.stdout.splitlines() if l.strip()]

    return rows


def token_counts() -> dict:
    import tiktoken
    import glyph

    enc = tiktoken.get_encoding("cl100k_base")
    out = {}
    for line in PAYLOADS.read_text().splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        v = json.loads(p["json"])
        json_min = json.dumps(v, separators=(",", ":"))
        glyph_text = glyph.canonicalize_loose(glyph.from_json_loose(v))
        j_tok, g_tok = len(enc.encode(json_min)), len(enc.encode(glyph_text))
        out[p["id"]] = {
            "json_tokens": j_tok,
            "glyph_tokens": g_tok,
            "glyph_vs_json_pct": round(100 * (g_tok - j_tok) / j_tok, 1),
            "json_bytes": len(json_min.encode()),
            "glyph_bytes": len(glyph_text.encode()),
            "bytes_vs_json_pct": round(100 * (len(glyph_text.encode()) - len(json_min.encode())) / len(json_min.encode()), 1),
        }
    return out


def run() -> dict:
    return {"bench_ns_per_op": bench_all(), "tokens_bytes_cl100k": token_counts(),
            "note": "timings informational only; see README reproducibility contract"}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
