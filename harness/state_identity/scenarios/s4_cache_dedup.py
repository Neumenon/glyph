"""S4 — context-cache dedup under formatting variance.

Within-language axis: a cache is filled with one textual form of each logical
state; queries arrive in different but logically identical forms (pretty,
escaped, reordered, spaced). A cache keyed by a non-canonical hash pays
false-negative recomputes.

Cross-language axis (reported by run_all from Part A rows): the same cache
shared between services written in different languages only works if the key
function agrees everywhere.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys_path = str(HERE.parents[1] / "py")
import sys  # noqa: E402

sys.path.insert(0, sys_path)

import glyph  # noqa: E402
import rfc8785  # noqa: E402


def _key(subject: str, json_text: str) -> str:
    if subject == "rawtext":
        # what many systems actually do: hash the bytes as received, no parse.
        # normalized lightly (strip) because that's the charitable version.
        return hashlib.sha256(json_text.strip().encode()).hexdigest()
    v = json.loads(json_text)
    if subject == "naive":
        return hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()
    if subject == "minified":
        return hashlib.sha256(
            json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if subject == "jcs":
        return hashlib.sha256(bytes(rfc8785.dumps(v))).hexdigest()
    if subject == "glyph":
        return glyph.fingerprint(glyph.from_json_loose(v))
    if subject == "canon_json":
        return hashlib.sha256(glyph.canon_json(glyph.from_json_loose(v)).encode()).hexdigest()
    raise ValueError(subject)


def run() -> dict:
    groups = [json.loads(l) for l in (HERE / "data" / "variants.jsonl").read_text().splitlines() if l.strip()]
    subjects = ["rawtext", "naive", "minified", "jcs", "glyph", "canon_json"]
    out: dict[str, dict] = {}

    for subject in subjects:
        # fill with the group's first form, query with every other form
        cache: dict[str, str] = {}
        for g in groups:
            fill = g["members"][0]
            cache[_key(subject, fill["json"])] = g["group"]

        hits = misses = 0
        miss_detail: list[dict] = []
        for g in groups:
            for m in g["members"]:
                k = _key(subject, m["json"])
                if cache.get(k) == g["group"]:
                    hits += 1
                else:
                    misses += 1
                    miss_detail.append({"group": g["group"], "missed_form": m["form"]})
        total = hits + misses
        out[subject] = {
            "queries": total,
            "hits": hits,
            "false_negative_misses": misses,
            "hit_rate": round(hits / total, 4),
            "wasted_recompute_pct": round(100 * misses / total, 1),
            "miss_detail": miss_detail,
        }
    return {"design": "fill=minified form; probe=all forms incl. itself", "results": out}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
