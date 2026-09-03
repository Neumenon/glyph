"""Encode a record list in each format under test (drives the real glyph codec).

json          compact, key-sorted JSON — the strongest/smallest JSON baseline,
              which is conservative (makes GLYPH's token win look smaller, not bigger)
glyph_loose   canonical GLYPH-Loose list, one object per record
glyph_tabular canonical GLYPH with auto-tabular — the @tab block (biggest token
              win, and the hardest for a model to read positionally)
"""
import json

from glyph import canonicalize_loose, canonicalize_loose_no_tabular, from_json_loose


def enc_json(recs):
    return json.dumps(recs, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def enc_glyph_loose(recs):
    return canonicalize_loose_no_tabular(from_json_loose(recs))


def enc_glyph_tabular(recs):
    return canonicalize_loose(from_json_loose(recs))


FORMATS = {
    "json": enc_json,
    "glyph_loose": enc_glyph_loose,
    "glyph_tabular": enc_glyph_tabular,
}

# Optional one-paragraph format primer (used only with --primer). JSON needs none
# (the model knows JSON); the question is whether a primer rescues GLYPH.
GLYPH_PRIMER = (
    "The data below is in GLYPH, a compact JSON-equivalent text format. "
    "`{k=v ...}` is an object; bare tokens are strings, quoted only if they contain "
    "spaces; `t`/`f` mean true/false and `_`/`∅` mean null. A block of the form "
    "`@tab _ rows=R cols=C [c1 c2 ...]` followed by `|v1|v2|...|` rows is a table: "
    "in each row the values map positionally to the column names listed in the header, "
    "and `@end` closes the block.\n\n"
)


def primer_for(fmt, enabled):
    if not enabled:
        return ""
    return GLYPH_PRIMER if fmt.startswith("glyph") else ""
