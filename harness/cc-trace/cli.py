#!/usr/bin/env python3
"""cc-trace harness CLI.

    python cli.py normalize <raw.jsonl> [-o events.json]
    python cli.py bench     <raw.jsonl | events.json> [-o report.json]
    python cli.py replay    <raw.jsonl | events.json>

Input is auto-detected: a `.jsonl` file whose records carry a "raw"/hook shape
is treated as raw capture and normalized first; a `.json` array (or already-
normalized events) is used as-is.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agenttrace import bench, format_report, normalize, replay  # noqa: E402
from agenttrace.schema import FIELDS  # noqa: E402


def _looks_like_raw(records):
    if not records:
        return False
    r = records[0]
    if not isinstance(r, dict):
        return False
    # Normalized events have the full FIELDS set; raw capture records do not.
    if all(k in r for k in FIELDS):
        return False
    return "raw" in r or "hook_event_name" in r or "event" in r


def _load_events(path):
    """Load a file and return normalized TraceEvent[], normalizing if raw."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix == ".jsonl":
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        records = json.loads(text)
        if isinstance(records, dict):
            records = [records]
    if _looks_like_raw(records):
        return normalize(records)
    return records


def _write_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_normalize(args):
    p = Path(args.input)
    records = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    events = normalize(records)
    if args.output:
        _write_json(events, args.output)
        print(f"wrote {len(events)} events -> {args.output}")
    else:
        json.dump(events, sys.stdout, ensure_ascii=False, indent=2)
        print()


def cmd_bench(args):
    events = _load_events(args.input)
    result = bench(events)
    print(format_report(result))
    if args.output:
        _write_json(result, args.output)
        print(f"\nreport -> {args.output}")
    # Fail loud: non-zero exit if any format failed to round-trip.
    if any(not r["decode_ok"] or not r["replay_ok"] for r in result["rows"]):
        sys.exit(1)


def cmd_replay(args):
    events = _load_events(args.input)
    json.dump(replay(events), sys.stdout, ensure_ascii=False, indent=2)
    print()


def main():
    parser = argparse.ArgumentParser(prog="cc-trace", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_norm = sub.add_parser("normalize", help="raw hook capture -> TraceEvent[]")
    p_norm.add_argument("input")
    p_norm.add_argument("-o", "--output")
    p_norm.set_defaults(func=cmd_normalize)

    p_bench = sub.add_parser("bench", help="size/replay benchmark across formats")
    p_bench.add_argument("input")
    p_bench.add_argument("-o", "--output")
    p_bench.set_defaults(func=cmd_bench)

    p_replay = sub.add_parser("replay", help="reduce a trace to RunState")
    p_replay.add_argument("input")
    p_replay.set_defaults(func=cmd_replay)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
