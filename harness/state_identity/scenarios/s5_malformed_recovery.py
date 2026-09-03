"""S5 — malformed LLM output recovery.

Strict `json.loads` is the baseline every engineer has. GLYPH loose-mode
parsing was designed around realistic model syntax slips. For samples with a
known intended value we also check semantic fidelity (recovered == intended).
Python-only by design: error tolerance is a parser property, not an
identity-across-languages property.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
GLYPH_ROOT = HERE.parents[1]
sys.path.insert(0, str(GLYPH_ROOT / "py"))

import glyph  # noqa: E402


def run() -> dict:
    samples = [json.loads(l) for l in (HERE / "data" / "malformed.jsonl").read_text().splitlines() if l.strip()]
    strict_ok = loose_ok = 0
    per_class: dict[str, dict[str, int]] = {}
    fidelity_checked = fidelity_ok = 0
    rows = []

    for s in samples:
        cls = s["error_class"]
        pc = per_class.setdefault(cls, {"strict": 0, "loose": 0})

        strict_parsed = None
        try:
            strict_parsed = json.loads(s["text"])
            strict_ok += 1
            pc["strict"] += 1
        except Exception:  # noqa: BLE001
            pass

        loose_value = None
        try:
            gv = glyph.parse_loose(s["text"])
            loose_value = glyph.to_json_loose(gv)
            loose_ok += 1
            pc["loose"] += 1
        except Exception:  # noqa: BLE001
            pass

        fidelity = None
        if s.get("expected") is not None and loose_value is not None:
            fidelity_checked += 1
            fidelity_ok += int(loose_value == s["expected"])
            fidelity = loose_value == s["expected"]

        rows.append({"id": s["id"], "class": cls,
                     "strict": strict_parsed is not None,
                     "loose": loose_value is not None,
                     "fidelity": fidelity})

    return {
        "samples": len(samples),
        "strict_json_recovered": strict_ok,
        "glyph_loose_recovered": loose_ok,
        "fidelity_checked": fidelity_checked,
        "fidelity_ok": fidelity_ok,
        "per_class": per_class,
        "rows": rows,
        "note": ("control-valid sample parses under both; expected=None marks "
                 "samples where recovery semantics are ambiguous or the slip "
                 "is judged unrecoverable-by-design"),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
