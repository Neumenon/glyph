#!/usr/bin/env python3
"""Python subject runner — state identity harness.

Contract (all three language runners implement the same):
  stdin : JSONL  {"id": str, "json": "<json text>"}
  stdout: JSONL  {"id", "subject", "hash", "error"}   (one line per subject)

Subjects:
  naive    sha256(json.dumps(v, sort_keys=True))            (stdlib defaults)
  minified sha256(json.dumps(v, sort_keys=True, separators=(",", ":")))
  jcs      sha256(rfc8785.dumps(v))
  glyph    fingerprint(from_json_loose(v))
  canon_json sha256(canon_json(from_json_loose(v))); error "idempotence: …" unless
           is_canonical(output) (SPEC-CANON.md §7)

--selftest <vectors_dir> validates rfc8785 against official RFC 8785 vectors.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import rfc8785

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "py"))
import glyph  # noqa: E402


def h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run_subjects(raw: str) -> list[dict]:
    out = []
    v = json.loads(raw)

    out.append({"id": None, "subject": "naive",
                "hash": h(json.dumps(v, sort_keys=True).encode()), "error": None})
    out.append({"id": None, "subject": "minified",
                "hash": h(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()),
                "error": None})
    try:
        out.append({"id": None, "subject": "jcs",
                    "hash": h(bytes(rfc8785.dumps(v))), "error": None})
    except Exception as e:  # noqa: BLE001
        out.append({"id": None, "subject": "jcs", "hash": "", "error": f"{type(e).__name__}: {e}"})
    try:
        fp = glyph.fingerprint(glyph.from_json_loose(v))
        out.append({"id": None, "subject": "glyph", "hash": fp, "error": None})
    except Exception as e:  # noqa: BLE001
        out.append({"id": None, "subject": "glyph", "hash": "", "error": f"{type(e).__name__}: {e}"})
    try:
        c = glyph.canon_json(glyph.from_json_loose(v))
        if glyph.is_canonical(c):
            out.append({"id": None, "subject": "canon_json", "hash": h(c.encode()), "error": None})
        else:
            out.append({"id": None, "subject": "canon_json", "hash": "",
                        "error": "idempotence: re-canonicalization differs"})
    except Exception as e:  # noqa: BLE001
        out.append({"id": None, "subject": "canon_json", "hash": "", "error": f"{type(e).__name__}: {e}"})
    return out


def selftest(vectors_dir: Path) -> int:
    failures = 0
    total = 0
    for inp in sorted(vectors_dir.glob("*.input.json")):
        expected = (inp.parent / inp.name.replace(".input.json", ".expected.json")).read_bytes()
        got = bytes(rfc8785.dumps(json.loads(inp.read_text(encoding="utf-8"))))
        total += 1
        if got != expected.rstrip(b"\n"):
            failures += 1
            print(f"JCS VECTOR FAIL: {inp.name}", file=sys.stderr)
    print(f"python/rfc8785 selftest: {total - failures}/{total} vectors pass")
    return 1 if failures else 0


def bench(payloads_path: Path) -> int:
    """ns/op per subject over fixed payloads. Informational (Part C)."""
    import time

    iters = 300
    for line in payloads_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        v = json.loads(p["json"])
        row = {"id": p["id"], "iters": iters}

        t0 = time.perf_counter_ns()
        for _ in range(iters):
            hashlib.sha256(json.dumps(v, sort_keys=True).encode()).digest()
        row["naive_ns"] = (time.perf_counter_ns() - t0) // iters

        t0 = time.perf_counter_ns()
        for _ in range(iters):
            hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).digest()
        row["minified_ns"] = (time.perf_counter_ns() - t0) // iters

        try:
            t0 = time.perf_counter_ns()
            for _ in range(iters):
                hashlib.sha256(bytes(rfc8785.dumps(v))).digest()
            row["jcs_ns"] = (time.perf_counter_ns() - t0) // iters
        except Exception:  # noqa: BLE001
            row["jcs_ns"] = None

        gv = glyph.from_json_loose(v)
        t0 = time.perf_counter_ns()
        for _ in range(iters):
            glyph.fingerprint(gv)
        row["glyph_ns"] = (time.perf_counter_ns() - t0) // iters
        print(json.dumps(row))
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "--selftest":
        return selftest(Path(argv[1]))

    if argv and argv[0] == "--mode":
        mode = argv[1]
        if mode == "gtext":
            # stdin: {"id","text"} — fingerprint GLYPH-T text (relay scenario)
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                fx = json.loads(line)
                try:
                    fp = glyph.fingerprint(glyph.parse_loose(fx["text"]))
                    print(json.dumps({"id": fx["id"], "subject": "glyph", "hash": fp, "error": None}))
                except Exception as e:  # noqa: BLE001
                    print(json.dumps({"id": fx["id"], "subject": "glyph", "hash": "",
                                      "error": f"{type(e).__name__}: {e}"}))
            return 0
        if mode == "bench":
            return bench(Path(argv[2]))

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        fx = json.loads(line)
        try:
            results = run_subjects(fx["json"])
        except Exception as e:  # noqa: BLE001 — parse-layer failure applies to all subjects
            msg = f"parse: {type(e).__name__}: {e}"
            for subj in ("naive", "minified", "jcs", "glyph", "canon_json"):
                print(json.dumps({"id": fx["id"], "subject": subj, "hash": "", "error": msg}))
            continue
        for r in results:
            r["id"] = fx["id"]
            print(json.dumps(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
