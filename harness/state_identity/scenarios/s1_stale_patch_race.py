"""S1 — stale-patch race.

A worker snapshots state S, computes a merge-patch P toward its intended
result T, and ships it. Meanwhile the state has already moved to M != S.
What happens when P lands?

Subjects:
  glyph-unchecked-apply  apply_patch(M, P, verify_base=True)  [default]
  glyph-noverify         apply_patch(M, P, verify_base=False) [opted out]
  baseline-unchecked     blind RFC-7396-style merge-patch     [typical DIY]
  baseline-recheck       recompute hash(M), compare to stored hash(S) first

Oracle: a stale apply that silently succeeds is `silent-corrupt` (lost update:
the merged value is no sequential history anyone intended). Detection is a
typed/checked refusal.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "py"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generators"))

import glyph  # noqa: E402
from edge_values import _rand_value  # noqa: E402


def merge_diff(old: dict, new: dict) -> dict:
    """RFC-7396-style merge patch capturing old -> new."""
    patch: dict = {}
    for k, nv in new.items():
        ov = old.get(k)
        if isinstance(nv, dict) and isinstance(ov, dict):
            sub = merge_diff(ov, nv)
            if sub:
                patch[k] = sub
        elif nv != ov or k not in old:
            patch[k] = nv
    for k in old:
        if k not in new:
            patch[k] = None
    return patch


def merge_apply(target: dict, patch: dict) -> dict:
    out = dict(target)
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_apply(out[k], v)
        else:
            out[k] = v
    return out


def edit(rng: random.Random, state: dict) -> dict:
    """One plausible worker edit: set/update/remove/rename-ish."""
    s = {k: (dict(v) if isinstance(v, dict) else v) for k, v in state.items()}
    keys = list(s.keys()) or ["k0"]
    op = rng.random()
    if op < 0.4:
        s[f"field_{rng.randint(0, 8)}"] = _rand_value(rng, 1)
    elif op < 0.7 and keys:
        s[rng.choice(keys)] = _rand_value(rng, 1)
    elif op < 0.85 and len(keys) > 1:
        s.pop(rng.choice(keys), None)
    else:
        s["counter"] = rng.randint(0, 10**6)
    return s


def run(trials: int = 3000, seed: int = 20260821) -> dict:
    rng = random.Random(seed)
    counts = {
        "glyph-default": {"detected": 0, "silent": 0, "error": 0},
        "glyph-noverify": {"detected": 0, "silent": 0, "error": 0},
        "baseline-unchecked": {"detected": 0, "silent": 0, "error": 0},
        "baseline-recheck": {"detected": 0, "silent": 0, "error": 0},
    }
    extra_hashes_baseline = 0
    error_samples: dict[str, int] = {}

    def note_error(mode: str, msg: str) -> None:
        if mode not in counts:
            counts[mode] = {"detected": 0, "silent": 0, "error": 0}
        counts[mode]["error"] += 1
        key = msg.split("\n")[0][:120]
        error_samples[key] = error_samples.get(key, 0) + 1

    for i in range(trials):
        v1 = _rand_value(rng, 1)
        if not isinstance(v1, dict):
            v1 = {"state": v1}
        snapshot = v1
        intended = edit(rng, snapshot)          # worker's target T
        drifted = edit(rng, snapshot)           # main loop moved to M meanwhile
        if drifted == snapshot:
            drifted = edit(rng, snapshot)

        patch_gv = glyph.diff(
            glyph.from_json_loose(snapshot), glyph.from_json_loose(intended))
        m_gv = glyph.from_json_loose(drifted)

        # glyph default (base verification ON)
        try:
            glyph.apply_patch(m_gv, patch_gv, verify_base=True)
            counts["glyph-default"]["silent"] += 1
        except glyph.PatchBaseMismatch:
            counts["glyph-default"]["detected"] += 1
        except Exception as e:  # noqa: BLE001
            note_error("glyph-default", f"{type(e).__name__}: {e}")

        # sanity: same patch applies cleanly against its true base (harness self-check,
        # counted separately so it cannot pollute the glyph-default numbers)
        try:
            glyph.apply_patch(glyph.from_json_loose(snapshot), patch_gv, verify_base=True)
        except Exception as e:  # noqa: BLE001
            note_error("sanity-apply-on-true-base", f"{type(e).__name__}: {e}")

        # glyph with verification opted out
        try:
            glyph.apply_patch(m_gv, patch_gv, verify_base=False)
            counts["glyph-noverify"]["silent"] += 1
        except glyph.PatchBaseMismatch:
            counts["glyph-noverify"]["detected"] += 1
        except Exception as e:  # noqa: BLE001
            note_error("glyph-noverify", f"{type(e).__name__}: {e}")

        # baseline: blind merge-patch (DIY)
        p_merge = merge_diff(snapshot, intended)
        merge_apply(drifted, p_merge)
        counts["baseline-unchecked"]["silent"] += 1  # always silently "succeeds"

        # baseline + discipline: re-hash before applying
        h_snap = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        h_now = json.dumps(drifted, sort_keys=True, separators=(",", ":"))
        extra_hashes_baseline += 2
        if h_snap != h_now:
            counts["baseline-recheck"]["detected"] += 1
        else:
            counts["baseline-recheck"]["silent"] += 1

    summary = {}
    for mode, c in counts.items():
        if mode.startswith("sanity"):
            continue
        total = sum(c.values())
        summary[mode] = {
            **c,
            "total": total,
            "detection_rate": round(c["detected"] / max(total, 1), 4),
            "silent_corruption_rate": round(c["silent"] / max(total, 1), 4),
        }
    return {
        "trials": trials,
        "error_samples": error_samples,
        "seed": seed,
        "summary": summary,
        "extra_hashes_for_baseline_recheck": extra_hashes_baseline,
        "notes": "baseline-unchecked cannot detect by construction; included as the realistic DIY floor",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
