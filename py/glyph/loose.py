"""
GLYPH-Loose Mode

Schema-optional canonicalization for GLYPH values.
Provides deterministic string representation for hashing, comparison, and deduplication.

Canonical rules:
- null -> "_" (default) or "∅"
- bool -> "t" / "f"
- int -> decimal, no leading zeros, -0 -> 0
- float -> shortest roundtrip, E->e, -0->0
- string -> bare if safe, otherwise quoted
- bytes -> "b64" + quoted base64
- time -> ISO-8601 UTC
- id -> ^prefix:value or ^"quoted"
- list -> "[" + space-separated elements + "]"
- map -> "{" + sorted key=value pairs + "}"
  Keys sorted by bytewise UTF-8 of canonString(key)

Auto-Tabular:
- Homogeneous lists of objects can be emitted as @tab _ [cols]...|row|...@end
"""

from __future__ import annotations
import base64
import hashlib
import math
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .types import GValue, GType, MapEntry, RefID


# ============================================================
# Options
# ============================================================

class NullStyle(Enum):
    """How to emit null values."""
    SYMBOL = "symbol"      # ∅ (human-readable)
    UNDERSCORE = "underscore"  # _ (LLM-friendly, ASCII-safe)


@dataclass
class LooseCanonOpts:
    """Options for loose canonicalization."""
    auto_tabular: bool = True
    min_rows: int = 3
    max_cols: int = 20
    allow_missing: bool = True
    null_style: NullStyle = NullStyle.UNDERSCORE
    schema_ref: Optional[str] = None
    key_dict: Optional[List[str]] = None
    use_compact_keys: bool = False


def default_loose_canon_opts() -> LooseCanonOpts:
    """Default options with auto-tabular enabled."""
    return LooseCanonOpts()


def llm_loose_canon_opts() -> LooseCanonOpts:
    """Options optimized for LLM output (uses _ for null)."""
    return LooseCanonOpts(null_style=NullStyle.UNDERSCORE)


def no_tabular_loose_canon_opts() -> LooseCanonOpts:
    """Options with auto-tabular disabled (uses ∅ for null, matching Go/JS fingerprint path)."""
    return LooseCanonOpts(auto_tabular=False, null_style=NullStyle.SYMBOL)


# ============================================================
# Constants
# ============================================================

NULL_SYMBOL = "∅"
NULL_UNDERSCORE = "_"

# Security limits (Class 5: Resource Exhaustion)
MAX_JSON_DEPTH = 128
MAX_COLLECTION_LEN = 1_000_000  # 1M elements
MAX_STRING_LEN = 10 * 1024 * 1024  # 10MB

# Reserved words that must be quoted (D8: matches Go isValidBareString reject list)
RESERVED_WORDS = {"t", "f", "true", "false", "null", "none", "nil", "_", "NaN", "Inf",
                   "struct", "sum", "list", "map"}


# ============================================================
# Canonical Scalar Encoding
# ============================================================

def canon_null(style: NullStyle = NullStyle.UNDERSCORE) -> str:
    """Canonicalize null."""
    if style == NullStyle.UNDERSCORE:
        return NULL_UNDERSCORE
    return NULL_SYMBOL


def canon_bool(v: bool) -> str:
    """Canonicalize boolean."""
    return "t" if v else "f"


def canon_int(n: int) -> str:
    """Canonicalize integer."""
    if n == 0:
        return "0"
    return str(n)


def canon_float(f: float) -> str:
    """Canonicalize float with shortest roundtrip representation per D4.

    Byte-matches Go strconv.FormatFloat(f, 'g', -1, 64) then lowercases E
    and appends ".0" iff the result has neither '.' nor 'e'.

    Rules:
    - Non-finite (NaN/Inf) -> ValueError (Loose mode rejects them)
    - -0.0 and 0.0 both -> "0.0"  (always a decimal point, D4)
    - All other values: use shortest round-trip digits from repr(), then apply
      Go's decimal-vs-exponential rule: use exponential iff the magnitude
      exponent E = floor(log10(|f|)) satisfies E >= 6 OR E <= -5.
      Exponent format: e+06, e-05 (always 2-digit zero-padded, always signed).
    """
    if not math.isfinite(f):
        raise ValueError("non-finite floats are not supported")
    # -0.0 and 0.0 both canonicalize to "0.0" (D4: always decimal point)
    if f == 0.0:
        return "0.0"

    neg = math.copysign(1.0, f) < 0
    abs_f = abs(f)

    # repr() gives the shortest round-trip decimal string in Python 3.1+.
    r = repr(abs_f)

    if 'e' in r:
        # Python already chose exponential (e.g. "1e-05", "1.5e-10").
        # Go also uses exponential here — just reformat the exponent sign/padding.
        mant_str, exp_str = r.split('e')
        py_exp = int(exp_str)
        # Re-emit with Go-style exponent: e+06, e-05
        abs_exp = abs(py_exp)
        sign_char = '+' if py_exp >= 0 else '-'
        s = f"{mant_str}e{sign_char}{abs_exp:02d}"
    else:
        # Python gave decimal form. Compute the magnitude exponent E EXACTLY from
        # the decimal digits — math.log10 rounds the wrong way for values just
        # below a power of ten (e.g. repr 999999999999999.8 -> true E is 14, but
        # math.log10 yields 15.0), which would diverge from Go/JS.
        if '.' in r:
            _int_p, _frac_p = r.split('.')
        else:
            _int_p, _frac_p = r, ''
        if _int_p != '0':
            E = len(_int_p) - 1
        else:
            _stripped = _frac_p.lstrip('0')
            E = -(len(_frac_p) - len(_stripped)) - 1
        if E >= 6 or E <= -5:
            # Go uses exponential; Python used decimal.
            # Extract significant digits from Python's repr.
            if '.' in r:
                int_p, frac_p = r.split('.')
                if int_p == '0':
                    all_digits = frac_p.lstrip('0').rstrip('0') or '0'
                else:
                    all_digits = (int_p + frac_p).rstrip('0') or '0'
            else:
                all_digits = r.rstrip('0') or '0'

            if len(all_digits) == 1:
                mant = all_digits
            else:
                mant = all_digits[0] + '.' + all_digits[1:]

            abs_exp = abs(E)
            sign_char = '+' if E >= 0 else '-'
            s = f"{mant}e{sign_char}{abs_exp:02d}"
        else:
            # Go uses decimal; Python's repr is already correct.
            s = r
            # D4: ensure decimal point so token is unambiguously float.
            if '.' not in s and 'e' not in s:
                s += '.0'

    return ('-' if neg else '') + s


def is_bare_safe(s: str) -> bool:
    """Check if string can be emitted as bare (unquoted) identifier (D8).

    Matches Go isValidBareString exactly: ASCII-only, [A-Za-z_][A-Za-z0-9_]*,
    not a reserved keyword.  Unicode characters, '-', '.', '/' and any other
    non-ASCII/non-alnum-underscore byte force quoting.
    """
    if not s:
        return False
    if s in RESERVED_WORDS:
        return False

    first = s[0]
    if not (first == "_" or ("A" <= first <= "Z") or ("a" <= first <= "z")):
        return False

    for c in s[1:]:
        if not (("A" <= c <= "Z") or ("a" <= c <= "z") or ("0" <= c <= "9") or c == "_"):
            return False
    return True


def escape_string(s: str) -> str:
    """Escape a string for GLYPH output."""
    result = []
    for c in s:
        if c == '"':
            result.append('\\"')
        elif c == '\\':
            result.append('\\\\')
        elif c == '\n':
            result.append('\\n')
        elif c == '\r':
            result.append('\\r')
        elif c == '\t':
            result.append('\\t')
        elif ord(c) < 32:
            result.append(f"\\u{ord(c):04x}")
        else:
            result.append(c)
    return ''.join(result)


def canon_string(s: str) -> str:
    """Canonicalize string."""
    if is_bare_safe(s):
        return s
    return f'"{escape_string(s)}"'


def canon_bytes(b: bytes) -> str:
    """Canonicalize bytes as base64."""
    encoded = base64.b64encode(b).decode('ascii')
    return f'b64"{encoded}"'


def canon_time(t: datetime) -> str:
    """Canonicalize datetime as ISO-8601 UTC."""
    if t.tzinfo is None:
        # Assume UTC if no timezone
        t = t.replace(tzinfo=timezone.utc)
    utc = t.astimezone(timezone.utc)
    # Format: 2025-01-13T12:34:56Z
    s = utc.strftime("%Y-%m-%dT%H:%M:%S")
    if utc.microsecond:
        # Add fractional seconds, removing trailing zeros
        frac = f".{utc.microsecond:06d}".rstrip("0")
        s += frac
    return s + "Z"


def is_id_safe(s: str) -> bool:
    """Check if a ref part (prefix or value segment) is safe to emit unquoted (D7).

    Mirrors Go isRefChar: ASCII [A-Za-z0-9_] plus '-' and '.' only.
    '/' and all non-ASCII bytes are rejected — the Go typed lexer's isRefChar
    does not include '/' (token.go:581-583).
    """
    if not s:
        return False
    for c in s:
        if not (("A" <= c <= "Z") or ("a" <= c <= "z") or ("0" <= c <= "9")
                or c == "_" or c == "-" or c == "."):
            return False
    return True


def canon_id(ref: RefID) -> str:
    """Canonicalize ID reference per D7.

    Emits ^prefix:value bare when both parts pass is_id_safe AND the value
    contains no ':' (which would cause a mis-split on parse).  Otherwise
    quotes the full string.
    """
    if ref.prefix:
        # ':' in value would be mis-split by the parser; force quoting.
        if is_id_safe(ref.prefix) and is_id_safe(ref.value) and ":" not in ref.value:
            return f"^{ref.prefix}:{ref.value}"
        return f'^"{escape_string(ref.prefix + ":" + ref.value)}"'
    if is_id_safe(ref.value) and ":" not in ref.value:
        return f"^{ref.value}"
    return f'^"{escape_string(ref.value)}"'


# ============================================================
# Main Canonicalization
# ============================================================

def canonicalize_loose(v: GValue, opts: Optional[LooseCanonOpts] = None) -> str:
    """
    Canonicalize a GValue to GLYPH-Loose format.

    This is the main entry point for converting values to canonical GLYPH text.
    """
    if opts is None:
        opts = default_loose_canon_opts()
    return _canonicalize_value(v, opts)


def canonicalize_loose_no_tabular(v: GValue) -> str:
    """Canonicalize without auto-tabular mode."""
    return canonicalize_loose(v, no_tabular_loose_canon_opts())


def _canonicalize_value(v: GValue, opts: LooseCanonOpts) -> str:
    """Internal canonicalization dispatcher."""
    t = v.type

    if t == GType.NULL:
        return canon_null(opts.null_style)
    elif t == GType.BOOL:
        return canon_bool(v.as_bool())
    elif t == GType.INT:
        return canon_int(v.as_int())
    elif t == GType.FLOAT:
        return canon_float(v.as_float())
    elif t == GType.STR:
        return canon_string(v.as_str())
    elif t == GType.BYTES:
        return canon_bytes(v.as_bytes())
    elif t == GType.TIME:
        return canon_time(v.as_time())
    elif t == GType.ID:
        return canon_id(v.as_id())
    elif t == GType.LIST:
        return _canonicalize_list(v.as_list(), opts)
    elif t == GType.MAP:
        return _canonicalize_map(v.as_map(), opts)
    elif t == GType.STRUCT:
        sv = v.as_struct()
        return _canonicalize_struct(sv.type_name, sv.fields, opts)
    elif t == GType.SUM:
        sm = v.as_sum()
        return _canonicalize_sum(sm.tag, sm.value, opts)

    raise ValueError(f"unknown type: {t}")


def _canonicalize_list(items: List[GValue], opts: LooseCanonOpts) -> str:
    """Canonicalize a list, possibly as tabular."""
    if not items:
        return "[]"

    # Check for auto-tabular eligibility
    if opts.auto_tabular and len(items) >= opts.min_rows:
        tabular = _try_tabular(items, opts)
        if tabular:
            return tabular

    # Standard list format
    parts = [_canonicalize_value(item, opts) for item in items]
    return "[" + " ".join(parts) + "]"


def _canonicalize_map(entries: List[MapEntry], opts: LooseCanonOpts) -> str:
    """Canonicalize a map with sorted keys."""
    if not entries:
        return "{}"

    # Sort by canonical key
    sorted_entries = sorted(entries, key=lambda e: canon_string(e.key).encode('utf-8'))

    parts = []
    for e in sorted_entries:
        key_str = canon_string(e.key)
        val_str = _canonicalize_value(e.value, opts)
        parts.append(f"{key_str}={val_str}")

    return "{" + " ".join(parts) + "}"


def _canonicalize_struct(type_name: str, fields: List[MapEntry], opts: LooseCanonOpts) -> str:
    """Canonicalize a struct."""
    if not fields:
        return f"{type_name}{{}}"

    # Sort fields by canonical key
    sorted_fields = sorted(fields, key=lambda f: canon_string(f.key).encode('utf-8'))

    parts = []
    for f in sorted_fields:
        key_str = canon_string(f.key)
        val_str = _canonicalize_value(f.value, opts)
        parts.append(f"{key_str}={val_str}")

    return f"{type_name}{{" + " ".join(parts) + "}"


def _canonicalize_sum(tag: str, value: Optional[GValue], opts: LooseCanonOpts) -> str:
    """Canonicalize a sum (tagged union)."""
    tag_str = canon_string(tag)
    if value is None:
        return f"{tag_str}()"
    val_str = _canonicalize_value(value, opts)
    return f"{tag_str}({val_str})"


# ============================================================
# Auto-Tabular
# ============================================================

def _try_tabular(items: List[GValue], opts: LooseCanonOpts) -> Optional[str]:
    """Try to emit items as tabular format. Returns None if not eligible."""
    if len(items) < opts.min_rows:
        return None

    # Check if all items are maps or structs
    union_keys: Set[str] = set()
    common_keys: Optional[Set[str]] = None
    first_keys: Optional[Set[str]] = None

    for item in items:
        if item.type == GType.MAP:
            item_keys = {e.key for e in item.as_map()}
        elif item.type == GType.STRUCT:
            item_keys = {f.key for f in item.as_struct().fields}
        else:
            return None  # Not eligible

        if len(item_keys) == 0:
            return None

        union_keys |= item_keys

        if first_keys is None:
            first_keys = set(item_keys)
        elif not opts.allow_missing:
            if first_keys != item_keys:
                return None  # Keys don't match

        if common_keys is None:
            common_keys = set(item_keys)
        else:
            common_keys &= item_keys

    if len(union_keys) == 0:
        return None

    if len(union_keys) > opts.max_cols:
        return None

    # If allowing missing keys, require at least 50% common keys
    if opts.allow_missing:
        if common_keys is None or len(common_keys) * 2 < len(union_keys):
            return None

    # Use union keys for columns
    keys_set = union_keys

    # Sort columns
    cols = sorted(keys_set, key=lambda k: canon_string(k).encode('utf-8'))

    # Build tabular output
    lines = []

    # Header: @tab _ [col1 col2 col3]
    col_header = " ".join(canon_string(c) for c in cols)
    lines.append(f"@tab _ [{col_header}]")

    # Rows
    for item in items:
        if item.type == GType.MAP:
            entries = {e.key: e.value for e in item.as_map()}
        else:
            entries = {f.key: f.value for f in item.as_struct().fields}

        row_parts = []
        for col in cols:
            if col in entries:
                cell = _canonicalize_value(entries[col], opts)
                # Escape pipe characters in cells
                cell = _escape_tabular_cell(cell)
            else:
                cell = canon_null(opts.null_style)
            row_parts.append(cell)

        lines.append("|" + "|".join(row_parts) + "|")

    lines.append("@end")

    return "\n".join(lines)


def _escape_tabular_cell(s: str) -> str:
    """Escape a cell value for tabular format."""
    # Pipe and newline need escaping
    s = s.replace("\\", "\\\\")
    s = s.replace("|", "\\|")
    s = s.replace("\n", "\\n")
    return s


def unescape_tabular_cell(s: str) -> str:
    """Unescape a tabular cell value."""
    result = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            next_char = s[i + 1]
            if next_char == '|':
                result.append('|')
                i += 2
            elif next_char == 'n':
                result.append('\n')
                i += 2
            elif next_char == '\\':
                result.append('\\')
                i += 2
            else:
                result.append(s[i])
                i += 1
        else:
            result.append(s[i])
            i += 1
    return ''.join(result)


# ============================================================
# JSON Bridge (Loose Mode)
# ============================================================

def from_json_loose(data: Any, _depth: int = 0) -> GValue:
    """Convert a Python/JSON value to GValue."""
    if _depth > MAX_JSON_DEPTH:
        raise ValueError(f"maximum nesting depth exceeded ({MAX_JSON_DEPTH})")
    if data is None:
        return GValue.null()
    elif isinstance(data, bool):
        return GValue.bool_(data)
    elif isinstance(data, int):
        return GValue.int_(data)
    elif isinstance(data, float):
        if not math.isfinite(data):
            raise ValueError("non-finite floats are not supported")
        return GValue.float_(data)
    elif isinstance(data, str):
        if len(data) > MAX_STRING_LEN:
            raise ValueError(f"string too large ({len(data)} > {MAX_STRING_LEN})")
        return GValue.str_(data)
    elif isinstance(data, bytes):
        return GValue.bytes_(data)
    elif isinstance(data, datetime):
        return GValue.time(data)
    elif isinstance(data, list):
        if len(data) > MAX_COLLECTION_LEN:
            raise ValueError(f"list too large ({len(data)} > {MAX_COLLECTION_LEN})")
        return GValue.list_(*[from_json_loose(item, _depth + 1) for item in data])
    elif isinstance(data, dict):
        if len(data) > MAX_COLLECTION_LEN:
            raise ValueError(f"map too large ({len(data)} > {MAX_COLLECTION_LEN})")
        entries = [MapEntry(str(k), from_json_loose(v, _depth + 1)) for k, v in data.items()]
        return GValue.map_(*entries)
    else:
        return GValue.str_(str(data))


def to_json_loose(v: GValue) -> Any:
    """Convert a GValue to Python/JSON value."""
    t = v.type

    if t == GType.NULL:
        return None
    elif t == GType.BOOL:
        return v.as_bool()
    elif t == GType.INT:
        return v.as_int()
    elif t == GType.FLOAT:
        value = v.as_float()
        if not math.isfinite(value):
            raise ValueError("non-finite floats are not JSON-safe")
        return value
    elif t == GType.STR:
        return v.as_str()
    elif t == GType.BYTES:
        return base64.b64encode(v.as_bytes()).decode('ascii')
    elif t == GType.TIME:
        return canon_time(v.as_time())
    elif t == GType.ID:
        ref = v.as_id()
        if ref.prefix:
            return f"^{ref.prefix}:{ref.value}"
        return f"^{ref.value}"
    elif t == GType.LIST:
        return [to_json_loose(item) for item in v.as_list()]
    elif t == GType.MAP:
        result = {}
        for e in v.as_map():
            result[e.key] = to_json_loose(e.value)
        return result
    elif t == GType.STRUCT:
        sv = v.as_struct()
        result = {"$type": sv.type_name}
        for f in sv.fields:
            result[f.key] = to_json_loose(f.value)
        return result
    elif t == GType.SUM:
        sm = v.as_sum()
        return {"$tag": sm.tag, "$value": to_json_loose(sm.value) if sm.value is not None else None}

    return None


# ============================================================
# Fingerprinting
# ============================================================

def fingerprint_loose(v: GValue, opts: Optional[LooseCanonOpts] = None) -> str:
    """
    Compute SHA-256 fingerprint of canonical representation.
    Returns hex string.
    """
    if opts is None:
        opts = no_tabular_loose_canon_opts()  # Tabular affects fingerprint

    canonical = canonicalize_loose(v, opts)
    h = hashlib.sha256(canonical.encode('utf-8'))
    return h.hexdigest()


def equal_loose(a: GValue, b: GValue) -> bool:
    """Check if two values are equal in loose canonical form."""
    opts = no_tabular_loose_canon_opts()
    return canonicalize_loose(a, opts) == canonicalize_loose(b, opts)


# ============================================================
# Convenience Functions
# ============================================================

def parse_json_loose(json_str: str) -> GValue:
    """Parse JSON string to GValue."""
    import json
    return from_json_loose(json.loads(json_str))


def stringify_json_loose(v: GValue, indent: Optional[int] = None) -> str:
    """Convert GValue to JSON string."""
    import json
    return json.dumps(to_json_loose(v), indent=indent)


def json_to_glyph(data: Any, opts: Optional[LooseCanonOpts] = None) -> str:
    """Convert JSON/Python data directly to GLYPH canonical string."""
    return canonicalize_loose(from_json_loose(data), opts)


def glyph_to_json(glyph_str: str) -> Any:
    """Parse GLYPH string to Python/JSON value."""
    from .parse import parse_loose
    v = parse_loose(glyph_str)
    return to_json_loose(v)
