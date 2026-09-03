"""Benchmark each format on a single normalized trace.

Per format we report:
  bytes        UTF-8 byte length of the encoding (the headline metric)
  tokens       BPE token count (cl100k_base) if tiktoken is installed, else null
  decode_ok    the encoding parsed back to events without error
  replay_ok    those events reduce to the same RunState as the reference

plus savings vs the NDJSON baseline. A format only "wins" if it is both smaller
*and* replay_ok — size without preserved semantics is not a win.
"""
from .encode import FORMATS
from .replay import replay
from .tokens import count_tokens


def bench(events):
    reference = replay(events)
    token_model = None
    rows = []
    for name, (enc, dec) in FORMATS.items():
        encoded = enc(events)
        nbytes = len(encoded.encode("utf-8"))
        toks, model = count_tokens(encoded)
        if model:
            token_model = model

        decode_ok, replay_ok, error = True, False, None
        try:
            decoded = dec(encoded)
            replay_ok = replay(decoded) == reference
        except Exception as exc:  # fail loud, per-format isolation
            decode_ok, error = False, f"{type(exc).__name__}: {exc}"

        rows.append(
            {
                "format": name,
                "bytes": nbytes,
                "tokens": toks,
                "decode_ok": decode_ok,
                "replay_ok": replay_ok,
                "error": error,
            }
        )

    base = next((r for r in rows if r["format"] == "ndjson"), None)
    for r in rows:
        if base and base["bytes"]:
            r["bytes_vs_ndjson_pct"] = round(100 * (base["bytes"] - r["bytes"]) / base["bytes"], 1)
        else:
            r["bytes_vs_ndjson_pct"] = 0.0
        if base and base["tokens"] and r["tokens"] is not None:
            r["tokens_vs_ndjson_pct"] = round(100 * (base["tokens"] - r["tokens"]) / base["tokens"], 1)
        else:
            r["tokens_vs_ndjson_pct"] = None

    return {
        "events": len(events),
        "reference_state": reference,
        "token_model": token_model,
        "rows": rows,
    }


def format_report(result):
    """Render a bench result as a plain-text table for the terminal."""
    lines = []
    n = result["events"]
    lines.append(f"events: {n}")
    tm = result["token_model"]
    lines.append(
        f"tokens: {tm} (BPE)" if tm else "tokens: n/a (install tiktoken for token figures)"
    )
    lines.append("")
    header = f"{'format':<14}{'bytes':>10}{'tokens':>10}{'vs ndjson':>11}  {'decode':>6} {'replay':>6}"
    lines.append(header)
    lines.append("-" * len(header))
    for r in result["rows"]:
        toks = "-" if r["tokens"] is None else str(r["tokens"])
        vs = f"{r['bytes_vs_ndjson_pct']:+.1f}%" if r["format"] != "ndjson" else "—"
        dok = "ok" if r["decode_ok"] else "FAIL"
        rok = "ok" if r["replay_ok"] else "FAIL"
        lines.append(
            f"{r['format']:<14}{r['bytes']:>10}{toks:>10}{vs:>11}  {dok:>6} {rok:>6}"
        )
        if r["error"]:
            lines.append(f"    error: {r['error']}")

    # Headline: GLYPH vs the line-oriented baseline.
    by = {r["format"]: r for r in result["rows"]}
    lines.append("")

    def _headline(fmt, label):
        r = by[fmt]
        s = f"{label} vs ndjson: {r['bytes_vs_ndjson_pct']:+.1f}% bytes"
        if r.get("tokens_vs_ndjson_pct") is not None:
            s += f", {r['tokens_vs_ndjson_pct']:+.1f}% tokens"
        return s

    if "glyph_loose" in by:
        lines.append(_headline("glyph_loose", "glyph_loose  "))
    if "glyph_tabular" in by:
        lines.append(_headline("glyph_tabular", "glyph_tabular"))
    return "\n".join(lines)
