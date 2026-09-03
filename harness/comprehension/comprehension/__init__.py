"""GLYPH-vs-JSON model-comprehension benchmark.

The decisive experiment for the "GLYPH in the loop" thesis: when structured data
is placed in an LLM's context, does the model answer questions about it as
*accurately* in GLYPH as in JSON — and how many tokens does each encoding cost
(measured with Claude's real tokenizer, not a heuristic)?

Bytes and even BPE token savings are meaningless if the model reads the compact
format worse: a few points of accuracy lost is not worth ~15% tokens saved. This
harness measures both on the same questions over the same data.

It drives the real in-repo GLYPH codec under `py/`; we add it to sys.path on
import so the harness runs from a checkout without installing glyph-py.
"""
import pathlib
import sys

# harness/comprehension/comprehension/__init__.py -> repo root is parents[3]
_PY = pathlib.Path(__file__).resolve().parents[3] / "py"
if _PY.is_dir() and str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))
