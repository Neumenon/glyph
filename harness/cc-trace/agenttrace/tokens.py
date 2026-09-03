"""Token counting for the bench.

Bytes are the headline metric: they are exact and not in dispute. Tokens are
reported only when a *real* BPE tokenizer is available, because this repo has
already learned the hard way that the whitespace-split heuristic is "wildly
inaccurate" for dense, whitespace-free formats like GLYPH (see the deprecation
note on `estimateTokens` in js/src/index.ts). So: tiktoken if installed, else
`None` — never a fabricated estimate masquerading as a token count.
"""

_ENC = None
_MODEL = "cl100k_base"


def _encoder():
    global _ENC
    if _ENC is None:
        import tiktoken  # raises ImportError if not installed

        _ENC = tiktoken.get_encoding(_MODEL)
    return _ENC


def count_tokens(text):
    """Return (token_count, model_name) or (None, None) if no real tokenizer."""
    try:
        return len(_encoder().encode(text)), _MODEL
    except Exception:
        return None, None


def have_tokenizer():
    try:
        _encoder()
        return True
    except Exception:
        return False
