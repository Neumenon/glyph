#!/usr/bin/env python3
"""GLYPH-vs-JSON model-comprehension benchmark.

    python run.py --preview                 # offline: show design + byte sizes, no API
    python run.py                           # live: needs ANTHROPIC_API_KEY (default haiku)
    python run.py --model claude-opus-4-8   # deployment-relevant tier
    python run.py --primer                  # prepend a GLYPH format primer
    python run.py --datasets 8 --concurrency 8

Measures, per format (json / glyph_loose / glyph_tabular), over the same
code-graded questions on the same data:
  - accuracy  (did the model read the data correctly?)
  - tokens    (real Claude tokenizer, via count_tokens)
The headline is the trade: tokens saved vs accuracy lost, relative to JSON.
"""
import argparse
import concurrent.futures as cf
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from comprehension import data as D  # noqa: E402
from comprehension import encode as E  # noqa: E402
from comprehension import model as M  # noqa: E402


def build_tasks(datasets, primer):
    """Flatten to (dataset_name, fmt, data_str, question) tasks + encodings."""
    encodings = {}  # (ds_name, fmt) -> data_str
    tasks = []
    for ds in datasets:
        questions = D.make_questions(ds)
        for fmt, enc in E.FORMATS.items():
            data_str = enc(ds["records"])
            encodings[(ds["name"], fmt)] = data_str
            pr = E.primer_for(fmt, primer)
            for q in questions:
                tasks.append({"ds": ds["name"], "fmt": fmt, "data": data_str,
                              "primer": pr, "q": q})
    return tasks, encodings


def preview(datasets, primer):
    tasks, encodings = build_tasks(datasets, primer)
    nq = len({(t["ds"], t["q"]["qid"]) for t in tasks})
    print(f"datasets: {len(datasets)}   questions/dataset: {nq // len(datasets)}   "
          f"total questions: {nq}")
    print(f"formats: {list(E.FORMATS)}   model calls if run live: {len(tasks)} "
          f"(+{len(encodings)} token-count calls)")
    print(f"primer: {'on' if primer else 'off'}")
    print("\nencoding sizes (bytes) for dataset 0:")
    d0 = datasets[0]["name"]
    base = len(encodings[(d0, "json")].encode())
    for fmt in E.FORMATS:
        b = len(encodings[(d0, fmt)].encode())
        vs = "—" if fmt == "json" else f"{100*(base-b)/base:+.1f}% vs json"
        print(f"  {fmt:<14}{b:>7} B   {vs}")
    print("\nsample questions (dataset 0):")
    for q in D.make_questions(datasets[0])[:6]:
        print(f"  [{q['kind']:<10}] {q['text']}  -> {q['expected_str']}")
    print("\nsample glyph_tabular encoding (dataset 0):")
    print("  " + encodings[(d0, "glyph_tabular")].replace("\n", "\n  ")[:600])


def run_live(args, datasets):
    tasks, encodings = build_tasks(datasets, args.primer)
    print(f"running {len(tasks)} questions x model={args.model} "
          f"(+{len(encodings)} token counts), primer={'on' if args.primer else 'off'}")

    # 1) token cost per (dataset, format)
    tokens = {}
    for (ds_name, fmt), s in encodings.items():
        tokens[(ds_name, fmt)] = M.count_tokens(args.model, s)

    # 2) ask every question, concurrently
    results = []

    def work(t):
        ans, in_tok, err = M.ask(args.model, t["data"], t["q"]["text"], t["primer"])
        correct = bool(ans is not None and t["q"]["check"](ans))
        return {"ds": t["ds"], "fmt": t["fmt"], "qid": t["q"]["qid"],
                "kind": t["q"]["kind"], "expected": t["q"]["expected_str"],
                "got": ans, "correct": correct, "error": err}

    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for r in ex.map(work, tasks):
            results.append(r)
            done += 1
            if done % 20 == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)}", file=sys.stderr)

    return aggregate(args, datasets, results, tokens)


def run_cli(args, datasets):
    """Subscription backend: one `claude -p` per (dataset, format), questions batched.

    Each subprocess is an independent Claude instance (a sub-agent); they run in
    parallel. usage.input_tokens (our prompt content; CC wrapper is cached out)
    gives a valid cross-format token comparison.
    """
    tasks = []
    for ds in datasets:
        qs = D.make_questions(ds)
        for fmt, enc in E.FORMATS.items():
            tasks.append((ds["name"], fmt, enc(ds["records"]), qs, E.primer_for(fmt, args.primer)))
    print(f"running {len(tasks)} batched claude -p sub-agents x model={args.model}, "
          f"primer={'on' if args.primer else 'off'}", file=sys.stderr)

    results, tokens = [], {}

    def work(t):
        ds, fmt, data, qs, pr = t
        ans, in_tok, err = M.ask_cli_batch(args.model, data, qs, pr)
        rows = []
        for i, q in enumerate(qs):
            a = ans.get(str(i + 1)) if ans else None
            rows.append({"ds": ds, "fmt": fmt, "qid": q["qid"], "kind": q["kind"],
                         "expected": q["expected_str"], "got": a,
                         "correct": bool(a is not None and q["check"](a)), "error": err})
        return ds, fmt, in_tok, rows, err

    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for ds, fmt, in_tok, rows, err in ex.map(work, tasks):
            tokens[(ds, fmt)] = in_tok
            results.extend(rows)
            status = f"ERR {err}" if err else f"{sum(r['correct'] for r in rows)}/{len(rows)}"
            print(f"  {ds}/{fmt}: {status}", file=sys.stderr)

    return aggregate(args, datasets, results, tokens)


def aggregate(args, datasets, results, tokens):
    fmts = list(E.FORMATS)
    ds_names = [d["name"] for d in datasets]
    rows = []
    for fmt in fmts:
        rs = [r for r in results if r["fmt"] == fmt]
        total = len(rs)
        correct = sum(r["correct"] for r in rs)
        errors = sum(1 for r in rs if r["error"])
        avg_tok = round(sum(tokens[(d, fmt)] for d in ds_names) / len(ds_names), 1)
        # per-kind accuracy
        kinds = {}
        for r in rs:
            k = kinds.setdefault(r["kind"], [0, 0])
            k[1] += 1
            k[0] += r["correct"]
        rows.append({"format": fmt, "total": total, "correct": correct,
                     "accuracy": round(100 * correct / total, 1) if total else 0.0,
                     "errors": errors, "avg_tokens": avg_tok,
                     "by_kind": {k: round(100 * c / n, 1) for k, (c, n) in kinds.items()}})

    base = next((r for r in rows if r["format"] == "json"), None)
    for r in rows:
        r["tokens_vs_json_pct"] = (round(100 * (base["avg_tokens"] - r["avg_tokens"]) / base["avg_tokens"], 1)
                                   if base and base["avg_tokens"] else 0.0)
        r["accuracy_delta_vs_json"] = round(r["accuracy"] - base["accuracy"], 1) if base else 0.0

    result = {"model": args.model, "primer": args.primer, "datasets": len(datasets),
              "rows": rows, "detail": results}
    print("\n" + render(result))
    out = Path(args.out) if args.out else Path(__file__).resolve().parent / "results" / f"{args.model}{'-primer' if args.primer else ''}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nreport -> {out}")
    return result


def render(result):
    lines = [f"model: {result['model']}   primer: {'on' if result['primer'] else 'off'}"
             f"   datasets: {result['datasets']}", ""]
    h = f"{'format':<14}{'questions':>10}{'correct':>9}{'accuracy':>10}{'avg_tokens':>12}{'tok vs json':>12}{'acc Δ':>8}"
    lines += [h, "-" * len(h)]
    for r in result["rows"]:
        vs = "—" if r["format"] == "json" else f"{r['tokens_vs_json_pct']:+.1f}%"
        accd = "—" if r["format"] == "json" else f"{r['accuracy_delta_vs_json']:+.1f}"
        lines.append(f"{r['format']:<14}{r['total']:>10}{r['correct']:>9}"
                     f"{r['accuracy']:>9.1f}%{r['avg_tokens']:>12}{vs:>12}{accd:>8}")
        if r["errors"]:
            lines.append(f"    ({r['errors']} call errors counted as wrong)")
    # per-kind accuracy table — shows WHERE a format fails (e.g. tabular on lookups)
    kinds = sorted({k for r in result["rows"] for k in r["by_kind"]})
    lines += ["", "accuracy by question kind:"]
    lines.append("  " + f"{'kind':<12}" + "".join(f"{f:>14}" for f in [r['format'] for r in result['rows']]))
    for k in kinds:
        cells = "".join(f"{r['by_kind'].get(k, 0):>13.0f}%" for r in result["rows"])
        lines.append("  " + f"{k:<12}" + cells)
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="claude-haiku-4-5",
                   help="model id (default: claude-haiku-4-5 — cheap + reveals comprehension gaps)")
    p.add_argument("--backend", choices=["api", "cli"], default="api",
                   help="api = Anthropic SDK (needs credits); cli = claude -p (subscription)")
    p.add_argument("--datasets", type=int, default=4)
    p.add_argument("--primer", action="store_true", help="prepend a GLYPH format primer")
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--preview", action="store_true", help="offline: show design, no API calls")
    p.add_argument("--out", help="path for the JSON report")
    args = p.parse_args()

    datasets = D.make_datasets(args.datasets)
    if args.preview:
        preview(datasets, args.primer)
        return
    if args.backend == "cli":
        run_cli(args, datasets)
    else:
        run_live(args, datasets)


if __name__ == "__main__":
    main()
