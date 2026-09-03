"""S3 — stream desync detection.

Sender streams K state-evolution frames over three channel types; a fault is
injected at a random frame. Who notices, and where?

Channels:
  gs1-crc     GS1-T framing, CRC-32 on payloads, seq numbers, per-patch base hash
  gs1-nocrc   same without payload CRC (isolation: what catches what)
  jsonl       newline-delimited full JSON states (typical DIY event stream)
  jsonl+hash  JSONL plus sidecar sha256 per line (DIY with discipline)

Faults: drop | replay | swap | bitflip
"""
from __future__ import annotations

import hashlib
import io
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
GLYPH_ROOT = HERE.parents[1]
sys.path.insert(0, str(GLYPH_ROOT / "py"))

import glyph  # noqa: E402
from glyph.stream.gs1t import Writer, Reader, encode_frame  # noqa: E402
from glyph.stream.types import Frame, KIND_DOC, KIND_PATCH  # noqa: E402
from glyph.stream.cursor import StreamCursor  # noqa: E402
from glyph.stream.hash import state_hash_loose, verify_base  # noqa: E402


def _states(k: int, rng: random.Random) -> list[dict]:
    states = [{"turn": 0, "mem": {"goal": "start"}, "score": 0.5}]
    for i in range(1, k):
        s = dict(states[-1])
        s["turn"] = i
        s["score"] = round(0.5 + rng.uniform(-0.05, 0.05), 4)
        s["mem"] = {"goal": f"step-{i}", "last": rng.randint(0, 99)}
        states.append(s)
    return states


def build_gs1_stream(states: list[dict], *, with_crc: bool) -> bytes:
    buf = io.BytesIO()
    w = Writer(buf, with_crc=with_crc)
    prev_hash: bytes | None = None
    for i, st in enumerate(states):
        gv = glyph.from_json_loose(st)
        if i == 0:
            w.write_frame(Frame(version=1, sid=1, seq=0, kind=KIND_DOC,
                                payload=glyph.canon_json(gv).encode()))
            prev_hash = state_hash_loose(gv)
        else:
            patch = glyph.diff(glyph.from_json_loose(states[i - 1]), gv)
            ptxt = glyph.emit_patch(patch).encode()
            w.write_frame(Frame(version=1, sid=1, seq=i, kind=KIND_PATCH,
                                payload=ptxt, base=prev_hash))
            prev_hash = state_hash_loose(gv)
    return buf.getvalue()


def split_frames(stream: bytes) -> list[bytes]:
    """Split GS1 wire into per-frame byte chunks (header+payload)."""
    out: list[bytes] = []
    bio = io.BytesIO(stream)
    r = Reader(bio, verify_crc=False)  # same underlying buffer -> tell() tracks reads
    while True:
        try:
            start = bio.tell()
            fr = r.next()
            if fr is None:
                break
            out.append(stream[start:bio.tell()])
        except Exception:  # noqa: BLE001 — trailing garbage terminates split
            break
    return out


def inject_fault(frames: list[bytes], fault: str, idx: int) -> list[bytes]:
    fs = list(frames)
    if fault == "drop" and len(fs) > idx:
        fs.pop(idx)
    elif fault == "replay" and 0 < idx < len(fs):
        fs.insert(idx + 1, fs[idx])
    elif fault == "swap" and idx + 1 < len(fs):
        fs[idx], fs[idx + 1] = fs[idx + 1], fs[idx]
    elif fault == "bitflip" and len(fs) > idx:
        b = bytearray(fs[idx])
        for p in range(len(b) - 1, -1, -1):  # flip last payload-ish byte
            if b[p:] != b"\n":
                b[p] ^= 0x01
                break
        fs[idx] = bytes(b)
    return fs


def consume_gs1(stream: bytes) -> dict:
    r = Reader(io.BytesIO(stream))
    cursor = StreamCursor()
    state_gv: glyph.GValue | None = None
    n = 0
    try:
        while True:
            fr = r.next()
            if fr is None:
                break
            n += 1
            cursor.process_frame(fr)
            if fr.kind == KIND_DOC:
                state_gv = glyph.from_json_loose(json.loads(fr.payload))
                cursor.set_state(1, state_gv)
                cursor.set_state_hash(1, state_hash_loose(state_gv))
            elif fr.kind == KIND_PATCH and state_gv is not None:
                patch = glyph.parse_patch(fr.payload)
                state_gv = glyph.apply_patch(state_gv, patch, verify_base=True)
                cursor.set_state(1, state_gv)
                cursor.set_state_hash(1, state_hash_loose(state_gv))
    except Exception as e:  # noqa: BLE001 — any refusal counts as detection
        return {"detected": True, "at_frame": n, "why": f"{type(e).__name__}: {e}"[:100]}
    return {"detected": False, "at_frame": n, "why": None}


def run_jsonl(states: list[dict], fault: str, idx: int, sidecar: bool) -> dict:
    lines = [json.dumps(s, separators=(",", ":")) for s in states]
    if sidecar:
        # sender appends "|sha256(line)" to each record BEFORE transport
        lines = [ln + "|" + hashlib.sha256(ln.encode()).hexdigest() for ln in lines]

    if fault == "drop" and len(lines) > idx:
        lines.pop(idx)
    elif fault == "replay":
        lines.insert(idx + 1, lines[idx])
    elif fault == "swap" and idx + 1 < len(lines):
        lines[idx], lines[idx + 1] = lines[idx + 1], lines[idx]
    elif fault == "bitflip" and len(lines) > idx:
        s = lines[idx]
        # corrupt one digit BEFORE the sidecar tag if present, else any digit
        limit = s.rfind("|") if sidecar else len(s)
        for c in range(limit - 1, 0, -1):
            if s[c].isdigit():
                d = str((int(s[c]) + 1) % 10)
                lines[idx] = s[:c] + d + s[c + 1:]
                break

    detected_at = None
    seen_bodies: set[str] = set()
    consumed = 0
    for ln in lines:
        if sidecar:
            body, sep, tag = ln.rpartition("|")
            if not sep or hashlib.sha256(body.encode()).hexdigest() != tag:
                detected_at = consumed
                break
            seen_bodies.add(body)  # content hashes cannot flag replays/swaps/drops
            consumed += 1
        else:
            consumed += 1  # consumer applies blindly; nothing to check
    return {"detected": detected_at is not None,
            "at_line": detected_at if detected_at is not None else consumed,
            "corrupt_states_consumed": max(consumed - (detected_at or 0), 0)}


def run(trials: int = 120, seed: int = 20260821) -> dict:
    rng = random.Random(seed)
    faults = ["drop", "replay", "swap", "bitflip"]
    results: dict[str, dict[str, dict]] = {ch: {} for ch in
                                           ["gs1-crc", "gs1-nocrc", "jsonl", "jsonl+hash"]}

    for fault in faults:
        det_counts = {ch: 0 for ch in results}
        at = {ch: [] for ch in results}
        for t in range(trials // len(faults)):
            k = 10 + t % 3
            states = _states(k, rng)
            fi = 2 + rng.randint(0, k - 4)  # never the last frame: a tail drop is unobservable, a tail swap is a no-op

            for ch, crc in [("gs1-crc", True), ("gs1-nocrc", False)]:
                stream = build_gs1_stream(states, with_crc=crc)
                frames = split_frames(stream)
                mutated = b"".join(inject_fault(frames, fault, fi))
                res = consume_gs1(mutated)
                det_counts[ch] += int(res["detected"])
                if res["detected"]:
                    at[ch].append(res["at_frame"])

            # jsonl baselines (fault index aligned: line i == post-op-i state)
            plain = run_jsonl(states, fault, fi, sidecar=False)
            tagged = run_jsonl(states, fault, fi, sidecar=True)
            det_counts["jsonl"] += int(plain["detected"])
            det_counts["jsonl+hash"] += int(tagged["detected"])
            if plain["detected"]:
                at["jsonl"].append(plain["at_line"])
            if tagged["detected"]:
                at["jsonl+hash"].append(tagged["at_line"])

        n_per = trials // len(faults)
        for ch in results:
            results[ch][fault] = {
                "detection_rate": round(det_counts[ch] / n_per, 3),
                "median_detect_position": sorted(at[ch])[len(at[ch]) // 2] if at[ch] else None,
            }

    return {
        "trials_per_fault": trials // len(faults),
        "seed": seed,
        "results": results,
        "note": ("jsonl detects nothing by construction; jsonl+hash can only catch "
                 "bitflips (content hashes) — drops/replays/swaps carry no signal "
                 "without sequence numbers. GS1's seq+base checks cover all four."),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
