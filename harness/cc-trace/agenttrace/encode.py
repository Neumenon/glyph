"""Encode/decode TraceEvent[] in each format under test.

The GLYPH encoders call the real in-repo codec (`py/glyph`); they do not
reimplement the format. That is the entire point — we are measuring the actual
codec on a real workload, so a private re-encoder would prove nothing.

Formats:
  ndjson         one minified, key-sorted JSON object per line (the honest
                 baseline — traces and logs are line-oriented in practice)
  glyph_loose    one canonical GLYPH-Loose object per line (tabular disabled)
  glyph_tabular  the whole list as one canonical GLYPH document; auto-tabular
                 collapses the repeated keys into a single `@tab` block
"""
import json

from glyph import (
    canonicalize_loose,
    canonicalize_loose_no_tabular,
    from_json_loose,
    parse_loose,
    to_json_loose,
)


# ── encoders ─────────────────────────────────────────────────────────────────
def encode_ndjson(events):
    return "\n".join(
        json.dumps(e, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        for e in events
    )


def encode_glyph_loose(events):
    return "\n".join(canonicalize_loose_no_tabular(from_json_loose(e)) for e in events)


def encode_glyph_tabular(events):
    # A list of homogeneous objects -> auto-tabular `@tab` block.
    return canonicalize_loose(from_json_loose(events))


# ── decoders (round-trip back to plain dicts for the replay oracle) ───────────
def decode_ndjson(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def decode_glyph_loose(text):
    return [to_json_loose(parse_loose(line)) for line in text.splitlines() if line.strip()]


def decode_glyph_tabular(text):
    return to_json_loose(parse_loose(text))


FORMATS = {
    "ndjson": (encode_ndjson, decode_ndjson),
    "glyph_loose": (encode_glyph_loose, decode_glyph_loose),
    "glyph_tabular": (encode_glyph_tabular, decode_glyph_tabular),
}


def encode(name, events):
    return FORMATS[name][0](events)


def decode(name, text):
    return FORMATS[name][1](text)
