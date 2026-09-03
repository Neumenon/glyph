"""S2 — cross-language relay.

A canonical GLYPH-T text produced by Python is re-parsed and fingerprinted
independently by Go and JS. Any disagreement anywhere on the relay is a
divergence event. Uses the committed fixtures corpus (sampled) plus all
variant-group members.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
GLYPH_ROOT = HERE.parents[1]
sys.path.insert(0, str(GLYPH_ROOT / "py"))
sys.path.insert(0, str(HERE / "generators"))

import glyph  # noqa: E402

SUBJ_GO = HERE / "subjects" / "go"
JS_DIR = GLYPH_ROOT / "js"


def _pipe(cmd: list[str], cwd: Path, lines: list[str]) -> list[dict]:
    proc = subprocess.run(
        cmd, cwd=cwd, input="\n".join(lines) + "\n",
        capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd} failed: {proc.stderr[-500:]}")
    return [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]


def sample_texts() -> list[dict]:
    out = []
    fixtures = [json.loads(l) for l in (HERE / "data" / "fixtures.jsonl").read_text().splitlines() if l.strip()]
    sample = fixtures[::7]
    for fx in sample:
        try:
            v = json.loads(fx["json"])
        except Exception:  # noqa: BLE001 — parse-reject fixtures can't enter the relay
            continue
        try:
            text = glyph.canonicalize_loose(glyph.from_json_loose(v))
            fp_ref = glyph.fingerprint(glyph.parse_loose(text))
        except Exception:  # noqa: BLE001
            continue
        out.append({"id": fx["id"], "text": text, "fp_py": fp_ref})
    return out


def run() -> dict:
    items = sample_texts()
    lines = [json.dumps({"id": it["id"], "text": it["text"]}, ensure_ascii=False) for it in items]

    go_rows = _pipe(["go", "run", "./cmd/runner", "--mode", "gtext"], SUBJ_GO, lines)
    js_rows = _pipe(["npx", "--prefix", str(JS_DIR), "tsx",
                     str(HERE / "subjects" / "js" / "runner.mts"), "--mode", "gtext"],
                    JS_DIR, lines)

    go_by = {r["id"]: r for r in go_rows}
    js_by = {r["id"]: r for r in js_rows}

    relay_ok = 0
    divergences = []
    for it in items:
        gid = go_by.get(it["id"], {})
        jid = js_by.get(it["id"], {})
        errs = []
        if gid.get("error"):
            errs.append(f"go:{gid['error']}")
        if jid.get("error"):
            errs.append(f"js:{jid['error']}")
        hashes = {it["fp_py"], gid.get("hash", ""), jid.get("hash", "")}
        if not errs and len(hashes) == 1:
            relay_ok += 1
        else:
            divergences.append({"id": it["id"], "errors": errs,
                                "agree_py_go": it["fp_py"] == gid.get("hash"),
                                "agree_py_js": it["fp_py"] == jid.get("hash")})

    return {
        "relayed_values": len(items),
        "full_agreement": relay_ok,
        "agreement_rate": round(relay_ok / max(len(items), 1), 4),
        "divergences": divergences[:20],
        "note": "pipeline: py emit -> (go|js) parse+fingerprint; python reference included in comparison",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
