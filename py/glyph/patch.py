"""
GLYPH v2 Patch Parser and Applier.

Parses the canonical @patch format:

    @patch
    = .step 2
    + .items {id=1 name="item_1"}
    - .removed_field
    ~ .counter +5
    @end

Operations:
    = (set)    — Replace value at path
    + (append) — Append to list or add field
    - (delete) — Remove field or list element
    ~ (delta)  — Numeric increment/decrement
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .types import GType, GValue, MapEntry, StructValue
from .loose import (
    canonicalize_loose,
    canon_int,
    canon_float,
    canon_string,
    canon_id,
    canon_bytes,
    canon_time,
    escape_string,
)


class PatchOpKind(Enum):
    SET = "="
    APPEND = "+"
    DELETE = "-"
    DELTA = "~"


class PathSegKind(Enum):
    FIELD = "field"
    LIST_IDX = "list_idx"
    MAP_KEY = "map_key"


@dataclass
class PathSeg:
    kind: PathSegKind
    field: str = ""
    list_idx: int = 0
    map_key: str = ""


@dataclass
class PatchOp:
    op: PatchOpKind
    path: List[PathSeg]
    value: Optional[GValue] = None
    delta: float = 0.0


@dataclass
class Patch:
    ops: List[PatchOp] = field(default_factory=list)
    schema_id: str = ""
    target: str = ""
    # First 16 hex chars of sha256(canonicalize_loose(base_state)); empty when
    # the patch does not record a base. Matches Go BaseFingerprint / JS
    # baseFingerprint (Go is the cross-language source of truth for @base) so a
    # Python receiver can verify a Go/JS-emitted patch.
    base_fingerprint: str = ""
    # Root type name, set by diff() (mirrors Go Patch.TargetType / JS
    # patch.targetType). Python has no schema/FID resolution pass yet, so this
    # is carried for signature parity with Go's Diff(from, to, typeName) but
    # is not otherwise consumed.
    target_type: str = ""


# Base-fingerprint length (hex chars). Mirrors Go/JS: first 16 of the SHA-256.
BASE_FINGERPRINT_LEN = 16


class PatchBaseMismatch(ValueError):
    """Raised when a patch's recorded base fingerprint does not match the base
    state presented to verify_patch_base (mirrors Go's FingerprintMismatch)."""

    def __init__(self, got: str, want: str):
        self.got = got
        self.want = want
        super().__init__(
            f"patch base fingerprint mismatch: got {got!r}, want {want!r}"
        )


def compute_base_fingerprint(base: GValue) -> str:
    """Compute the 16-hex patch base fingerprint of a base state.

    base = sha256(canonicalize_loose(base))[:16] — the first 16 hex of the
    SHA-256 of the *canonical loose form* (LOOSE_MODE_SPEC, "Patch Base
    Fingerprint"). This is byte-identical to Go WithBaseValue / JS withBaseValue;
    Go is the cross-language source of truth for @base.

    Note: @base uses the tabular canonical form (null → '_'), which is distinct
    from fingerprint_loose(state) — the value-identity digest, which uses the
    no-tabular form (null → '∅'). The two coincide for null-free non-tabular
    states but diverge when the base contains nulls or is a bare auto-tabular
    list root.
    """
    canonical = canonicalize_loose(base)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:BASE_FINGERPRINT_LEN]


def verify_patch_base(base: GValue, patch: Patch) -> None:
    """Verify a patch's recorded base fingerprint against the base state.

    No-op when the patch records no base (mirrors Go VerifyPatchBase). Raises
    PatchBaseMismatch when the recomputed fingerprint differs.

    apply_patch calls this automatically (unless verify_base=False is passed)
    before applying any operation. This function remains public for callers
    who want to verify ahead of time, or who use apply_patch(..., verify_base=
    False) and want the check back.
    """
    if not patch.base_fingerprint:
        return
    got = compute_base_fingerprint(base)
    if got != patch.base_fingerprint:
        raise PatchBaseMismatch(got=got, want=patch.base_fingerprint)


def parse_patch(text: str) -> Patch:
    """Parse a @patch block from text.

    Input should include the @patch header and @end footer.
    """
    lines = text.split("\n")
    patch = Patch()

    if not lines:
        raise ValueError("empty patch input")

    # Parse header
    header = lines[0].strip()
    if not header.startswith("@patch"):
        raise ValueError("patch must start with @patch")

    # Parse header tokens
    tokens = header.split()
    for tok in tokens:
        if tok == "@patch":
            continue
        if tok.startswith("@schema#"):
            patch.schema_id = tok[8:]
        elif tok.startswith("@target="):
            patch.target = tok[8:]
        elif tok.startswith("@base="):
            patch.base_fingerprint = tok[6:]

    # Parse operations
    for i, line in enumerate(lines[1:], start=2):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "@end":
            break

        op = _parse_op(line, i)
        patch.ops.append(op)

    return patch


def _parse_op(line: str, line_num: int) -> PatchOp:
    """Parse a single patch operation line."""
    if not line:
        raise ValueError(f"line {line_num}: empty operation")

    op_char = line[0]
    op_map = {
        "=": PatchOpKind.SET,
        "+": PatchOpKind.APPEND,
        "-": PatchOpKind.DELETE,
        "~": PatchOpKind.DELTA,
    }

    op_kind = op_map.get(op_char)
    if op_kind is None:
        raise ValueError(f"line {line_num}: unknown operation: {op_char}")

    rest = line[1:].strip()
    if not rest:
        raise ValueError(f"line {line_num}: missing path")

    # Split into path and value
    path_str, value_str = _split_path_value(rest)
    path = _parse_path(path_str)

    op = PatchOp(op=op_kind, path=path)

    if op_kind == PatchOpKind.DELTA:
        if value_str:
            try:
                op.delta = float(value_str)
            except ValueError:
                raise ValueError(f"line {line_num}: invalid delta: {value_str}")
    elif op_kind != PatchOpKind.DELETE:
        if value_str:
            op.value = _parse_value(value_str)

    return op


def _split_path_value(rest: str) -> tuple[str, str]:
    """Split 'path value' into (path, value)."""
    # Path starts with . and continues until whitespace
    i = 0
    while i < len(rest):
        if rest[i] == " ":
            return rest[:i], rest[i:].strip()
        i += 1
    return rest, ""


def _parse_path(path_str: str) -> List[PathSeg]:
    """Parse a dotted path.

    Accepts both GLYPH-Python's leading-dot form ('.step', '.items[0]') and the
    bare form emitted by Go/JS ('step', 'home.score'), so a Python receiver can
    parse a patch produced by any implementation.
    """
    if not path_str:
        raise ValueError("empty path")

    body = path_str[1:] if path_str.startswith(".") else path_str
    segments = []
    parts = body.split(".")

    for part in parts:
        if not part:
            continue
        # Check for list index: field[N]
        if "[" in part:
            field_name = part[:part.index("[")]
            idx_str = part[part.index("[") + 1 : part.index("]")]
            if field_name:
                segments.append(PathSeg(kind=PathSegKind.FIELD, field=field_name))
            try:
                segments.append(PathSeg(kind=PathSegKind.LIST_IDX, list_idx=int(idx_str)))
            except ValueError:
                raise ValueError(f"invalid list index: {idx_str}")
        else:
            segments.append(PathSeg(kind=PathSegKind.FIELD, field=part))

    return segments


def _parse_value(value_str: str) -> GValue:
    """Parse a simple inline value from a patch operation."""
    s = value_str.strip()
    if not s:
        return GValue.null()

    # Null
    if s in ("_", "null", "∅"):
        return GValue.null()

    # Boolean
    if s in ("t", "true"):
        return GValue.bool_(True)
    if s in ("f", "false"):
        return GValue.bool_(False)

    # Quoted string
    if s.startswith('"') and s.endswith('"'):
        return GValue.str_(s[1:-1].replace('\\"', '"').replace("\\\\", "\\"))

    # Map/struct: {key=val ...}
    if s.startswith("{") and s.endswith("}"):
        return _parse_inline_map(s)

    # List: [a b c]
    if s.startswith("[") and s.endswith("]"):
        return _parse_inline_list(s)

    # Number
    try:
        if "." in s or "e" in s.lower():
            return GValue.float_(float(s))
        return GValue.int_(int(s))
    except ValueError:
        pass

    # Bare string
    return GValue.str_(s)


def _parse_inline_map(s: str) -> GValue:
    """Parse {key=val key2=val2} into a GValue map."""
    inner = s[1:-1].strip()
    entries = []
    while inner:
        inner = inner.strip()
        if not inner:
            break
        eq_idx = inner.find("=")
        if eq_idx < 0:
            break
        key = inner[:eq_idx].strip()
        rest = inner[eq_idx + 1:]
        val_str, rest = _split_next_value(rest)
        entries.append(MapEntry(key=key, value=_parse_value(val_str)))
        inner = rest
    return GValue.map_(*entries)


def _parse_inline_list(s: str) -> GValue:
    """Parse [a b c] into a GValue list."""
    inner = s[1:-1].strip()
    items = []
    while inner:
        inner = inner.strip()
        if not inner:
            break
        val_str, inner = _split_next_value(inner)
        items.append(_parse_value(val_str))
    return GValue.list_(*items)


def _split_next_value(s: str) -> tuple[str, str]:
    """Split out the next value token from a space-separated string."""
    s = s.strip()
    if not s:
        return "", ""

    if s[0] == '"':
        # Quoted string — find matching close quote
        i = 1
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s):
                i += 2
                continue
            if s[i] == '"':
                return s[: i + 1], s[i + 1 :]
            i += 1
        return s, ""

    if s[0] in ("{", "["):
        # Find matching brace
        open_char, close_char = s[0], "}" if s[0] == "{" else "]"
        depth = 0
        for i, c in enumerate(s):
            if c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    return s[: i + 1], s[i + 1 :]
        return s, ""

    # Bare token — split on space
    idx = s.find(" ")
    if idx < 0:
        return s, ""
    return s[:idx], s[idx:]


def apply_patch(value: GValue, patch: Patch, verify_base: bool = True) -> GValue:
    """Apply a patch to a GValue and return the modified copy.

    Base enforcement: when patch carries a base fingerprint
    (patch.base_fingerprint is non-empty) and verify_base is True (the
    default), this verifies it against value via verify_patch_base BEFORE
    applying any operation, raising PatchBaseMismatch on a stale base. A
    patch with no recorded fingerprint is applied unconditionally either way.

    Pass verify_base=False to skip the check entirely — e.g. a caller that
    has already verified the base out-of-band, or that intentionally wants
    to force-apply a stale patch.
    """
    if verify_base:
        verify_patch_base(value, patch)

    result = _deep_copy_gvalue(value)

    for op in patch.ops:
        result = _apply_op(result, op)

    return result


def _deep_copy_gvalue(v: GValue) -> GValue:
    """Deep copy a GValue."""
    return copy.deepcopy(v)


def _apply_op(v: GValue, op: PatchOp) -> GValue:
    """Apply a single operation."""
    if not op.path:
        if op.op == PatchOpKind.SET:
            return op.value
        raise ValueError(f"cannot apply {op.op.value} to root")

    if len(op.path) == 1:
        return _apply_to_parent(v, op.path[0], op)

    # Navigate to parent
    seg = op.path[0]
    rest_op = PatchOp(op=op.op, path=op.path[1:], value=op.value, delta=op.delta)

    if v.type == GType.STRUCT and seg.kind == PathSegKind.FIELD:
        for i, f in enumerate(v._struct.fields):
            if f.key == seg.field:
                v._struct.fields[i] = MapEntry(
                    key=f.key, value=_apply_op(f.value, rest_op)
                )
                return v
        raise ValueError(f"field not found: {seg.field}")

    if v.type == GType.MAP and seg.kind == PathSegKind.FIELD:
        for i, f in enumerate(v._map):
            if f.key == seg.field:
                v._map[i] = MapEntry(
                    key=f.key, value=_apply_op(f.value, rest_op)
                )
                return v
        raise ValueError(f"key not found: {seg.field}")

    if v.type == GType.LIST and seg.kind == PathSegKind.LIST_IDX:
        idx = seg.list_idx
        if idx < 0 or idx >= len(v._list):
            raise ValueError(f"index out of bounds: {idx}")
        v._list[idx] = _apply_op(v._list[idx], rest_op)
        return v

    raise ValueError(f"cannot navigate {seg.kind.value} in {v.type.value}")


def _apply_to_parent(v: GValue, seg: PathSeg, op: PatchOp) -> GValue:
    """Apply operation to a field of the parent value."""
    key = seg.field if seg.kind == PathSegKind.FIELD else seg.map_key

    if op.op == PatchOpKind.SET:
        _set_field(v, key, op.value)
        return v

    if op.op == PatchOpKind.APPEND:
        existing = _get_field(v, key)
        if existing is None:
            _set_field(v, key, GValue.list_(op.value))
        elif existing.type == GType.LIST:
            existing._list.append(op.value)
        else:
            raise ValueError(f"cannot append to {existing.type.value}")
        return v

    if op.op == PatchOpKind.DELETE:
        _delete_field(v, key)
        return v

    if op.op == PatchOpKind.DELTA:
        existing = _get_field(v, key)
        if existing is None:
            _set_field(v, key, GValue.float_(op.delta))
        elif existing.type == GType.INT:
            existing._int += int(op.delta)
        elif existing.type == GType.FLOAT:
            existing._float += op.delta
        else:
            raise ValueError(f"cannot apply delta to {existing.type.value}")
        return v

    raise ValueError(f"unknown operation: {op.op}")


def _get_field(v: GValue, key: str) -> Optional[GValue]:
    if v.type == GType.STRUCT:
        for f in v._struct.fields:
            if f.key == key:
                return f.value
    elif v.type == GType.MAP:
        for f in v._map:
            if f.key == key:
                return f.value
    return None


def _set_field(v: GValue, key: str, val: GValue) -> None:
    if v.type == GType.STRUCT:
        for i, f in enumerate(v._struct.fields):
            if f.key == key:
                v._struct.fields[i] = MapEntry(key=key, value=val)
                return
        v._struct.fields.append(MapEntry(key=key, value=val))
    elif v.type == GType.MAP:
        for i, f in enumerate(v._map):
            if f.key == key:
                v._map[i] = MapEntry(key=key, value=val)
                return
        v._map.append(MapEntry(key=key, value=val))
    else:
        raise ValueError(f"cannot set field on {v.type.value}")


def _delete_field(v: GValue, key: str) -> None:
    if v.type == GType.STRUCT:
        v._struct.fields = [f for f in v._struct.fields if f.key != key]
    elif v.type == GType.MAP:
        v._map = [f for f in v._map if f.key != key]
    else:
        raise ValueError(f"cannot delete field from {v.type.value}")


# ============================================================
# Patch Emit (schema-less / generic — mirrors Go EmitPatch(schema=nil) and
# JS emitPatch({}))
#
# Python has no schema-driven patch builder yet (no FID resolution, no
# packed-struct wire keys), so this only supports the "wire" key mode with
# plain field names — the same fallback path Go/JS use when no schema is
# given. This is enough to emit patches built by diff() below, and to
# round-trip anything parse_patch can read back.
# ============================================================


def _is_letter_patch(c: str) -> bool:
    return ("a" <= c <= "z") or ("A" <= c <= "Z")


def _is_digit_patch(c: str) -> bool:
    return "0" <= c <= "9"


def _path_needs_quoting(s: str) -> bool:
    """Mirrors Go emit_patch.go needsQuoting for PATH field segments — a
    separate, more permissive rule than canon_string's value-quoting rule
    (allows '-' after the first character; no reserved-word exclusion)."""
    if not s:
        return True
    for i, c in enumerate(s):
        if i == 0:
            if not _is_letter_patch(c) and c != "_":
                return True
        else:
            if not _is_letter_patch(c) and not _is_digit_patch(c) and c not in ("_", "-"):
                return True
    return False


def _emit_field_name(name: str) -> str:
    if _path_needs_quoting(name):
        return f'"{escape_string(name)}"'
    return name


def _path_to_string(path: List[PathSeg]) -> str:
    """Canonical string form of a path, used both for op emission and for
    sorting ops by path (mirrors Go pathSegsToString / JS pathSegsToString)."""
    parts: List[str] = []
    for i, seg in enumerate(path):
        if seg.kind == PathSegKind.FIELD:
            if i > 0:
                parts.append(".")
            parts.append(_emit_field_name(seg.field))
        elif seg.kind == PathSegKind.LIST_IDX:
            parts.append(f"[{seg.list_idx}]")
        else:  # MAP_KEY
            parts.append(f'["{escape_string(seg.map_key)}"]')
    return "".join(parts)


def _emit_value(v: Optional[GValue]) -> str:
    """Emit a value in the generic (schema-less) patch/packed form. Mirrors
    Go emitPackedValue and JS emitValue for the types they both support."""
    if v is None or v.type == GType.NULL:
        return "∅"  # canonNull() is always "∅" in packed/patch mode

    t = v.type
    if t == GType.BOOL:
        return "t" if v.as_bool() else "f"
    if t == GType.INT:
        return canon_int(v.as_int())
    if t == GType.FLOAT:
        return canon_float(v.as_float())
    if t == GType.STR:
        return canon_string(v.as_str())
    if t == GType.ID:
        return canon_id(v.as_id())
    if t == GType.TIME:
        return canon_time(v.as_time())
    if t == GType.BYTES:
        return canon_bytes(v.as_bytes())
    if t == GType.LIST:
        return "[" + " ".join(_emit_value(e) for e in v.as_list()) + "]"
    if t == GType.MAP:
        parts = [f"{canon_string(e.key)}:{_emit_value(e.value)}" for e in v.as_map()]
        return "{" + " ".join(parts) + "}"
    if t == GType.STRUCT:
        sv = v.as_struct()
        fparts = [f"{canon_string(f.key)}={_emit_value(f.value)}" for f in sv.fields]
        return f"{sv.type_name}{{{' '.join(fparts)}}}"
    if t == GType.SUM:
        sm = v.as_sum()
        if sm.value is None or sm.value.type == GType.NULL:
            return f"{sm.tag}()"
        if sm.value.type == GType.STRUCT:
            fparts = [f"{canon_string(f.key)}={_emit_value(f.value)}" for f in sm.value.as_struct().fields]
            return f"{sm.tag}{{{' '.join(fparts)}}}"
        return f"{sm.tag}({_emit_value(sm.value)})"

    raise ValueError(f"unsupported value type in patch emit: {t.value}")


def _emit_op(op: PatchOp) -> str:
    line = f"{op.op.value} {_path_to_string(op.path)}"
    if op.op in (PatchOpKind.SET, PatchOpKind.APPEND):
        if op.value is not None:
            line += " " + _emit_value(op.value)
    elif op.op == PatchOpKind.DELTA:
        sign = "+" if op.delta >= 0 else ""
        line += " " + sign + canon_float(op.delta)
    # DELETE: no value
    return line


def emit_patch(patch: Patch, sort_ops: bool = True) -> str:
    """Emit a @patch block from a Patch — the inverse of parse_patch.

    Mirrors Go EmitPatch(patch, schema=nil) / JS emitPatch(patch, {}): the
    "wire" key mode with plain field names (Python has no schema-driven
    packed/FID emission yet). Ops are sorted by canonical path string by
    default (sort_ops=True, matching Go/JS DefaultPatchOptions.SortOps),
    so a patch diffed independently in any of the three languages for the
    same from/to pair emits byte-identical text.
    """
    header = "@patch"
    if patch.schema_id:
        header += f" @schema#{patch.schema_id}"
    header += " @keys=wire"
    header += f" @target={patch.target}"
    if patch.base_fingerprint:
        header += f" @base={patch.base_fingerprint}"

    ops = list(patch.ops)
    if sort_ops:
        ops.sort(key=lambda op: (_path_to_string(op.path), op.op.value))

    lines = [header]
    lines.extend(_emit_op(op) for op in ops)
    lines.append("@end")
    return "\n".join(lines)


# ============================================================
# Diff Generation
#
# Port of Go's Diff (emit_patch.go): same semantics, including whole-list
# replace on any list change (no per-index diffing) and the narrow
# _values_equal type coverage below (map/bytes/time/sum values are never
# considered equal, so a list containing them is always replaced wholesale
# on any diff) — this mirrors Go's behavior exactly, not an improvement.
# ============================================================


def diff(from_value: Optional[GValue], to_value: Optional[GValue], type_name: str = "") -> Patch:
    """Compute the patch set needed to transform from_value into to_value.

    Port of Go's Diff(from, to, typeName) / JS's diff(from, to, typeName).
    The returned patch has an empty target (Diff does not scope to a target
    document) — set patch.target before emit_patch if the caller needs one.
    It carries the base fingerprint of from_value (same computation as
    compute_base_fingerprint), so apply_patch rejects it against other states.
    """
    patch = Patch()
    patch.target_type = type_name
    if from_value is not None:
        patch.base_fingerprint = compute_base_fingerprint(from_value)
    _diff_values(from_value, to_value, [], patch)
    return patch


def _copy_path(path: List[PathSeg]) -> List[PathSeg]:
    return list(path)


def _diff_values(
    from_v: Optional[GValue], to_v: Optional[GValue], path: List[PathSeg], patch: Patch
) -> None:
    if from_v is None and to_v is None:
        return
    if from_v is None:
        patch.ops.append(PatchOp(op=PatchOpKind.SET, path=_copy_path(path), value=to_v))
        return
    if to_v is None:
        if path:
            patch.ops.append(PatchOp(op=PatchOpKind.DELETE, path=_copy_path(path)))
        return
    if from_v.type != to_v.type:
        patch.ops.append(PatchOp(op=PatchOpKind.SET, path=_copy_path(path), value=to_v))
        return

    t = from_v.type
    if t == GType.NULL:
        return  # both null, no change
    if t == GType.BOOL:
        if from_v.as_bool() != to_v.as_bool():
            patch.ops.append(PatchOp(op=PatchOpKind.SET, path=_copy_path(path), value=to_v))
        return
    if t == GType.INT:
        if from_v.as_int() != to_v.as_int():
            patch.ops.append(PatchOp(op=PatchOpKind.SET, path=_copy_path(path), value=to_v))
        return
    if t == GType.FLOAT:
        if from_v.as_float() != to_v.as_float():
            patch.ops.append(PatchOp(op=PatchOpKind.SET, path=_copy_path(path), value=to_v))
        return
    if t == GType.STR:
        if from_v.as_str() != to_v.as_str():
            patch.ops.append(PatchOp(op=PatchOpKind.SET, path=_copy_path(path), value=to_v))
        return
    if t == GType.ID:
        if from_v.as_id() != to_v.as_id():
            patch.ops.append(PatchOp(op=PatchOpKind.SET, path=_copy_path(path), value=to_v))
        return
    if t == GType.STRUCT:
        _diff_struct_values(from_v, to_v, path, patch)
        return
    if t == GType.MAP:
        _diff_map_values(from_v, to_v, path, patch)
        return
    if t == GType.LIST:
        # Whole-list replace on any change (matches Go — no per-index diffing).
        if not _lists_equal(from_v.as_list(), to_v.as_list()):
            patch.ops.append(PatchOp(op=PatchOpKind.SET, path=_copy_path(path), value=to_v))
        return

    # Other types (bytes, time, sum): unconditional replace, mirroring Go's
    # diffValues default case exactly (it does not compare these for
    # equality either, despite the "replace if not equal" comment there).
    patch.ops.append(PatchOp(op=PatchOpKind.SET, path=_copy_path(path), value=to_v))


def _diff_struct_values(from_v: GValue, to_v: GValue, path: List[PathSeg], patch: Patch) -> None:
    from_fields = {f.key: f.value for f in from_v.as_struct().fields}
    to_fields = {f.key: f.value for f in to_v.as_struct().fields}

    for key, to_val in to_fields.items():
        from_val = from_fields.get(key)
        child_path = path + [PathSeg(kind=PathSegKind.FIELD, field=key)]
        _diff_values(from_val, to_val, child_path, patch)

    for key in from_fields:
        if key not in to_fields:
            child_path = path + [PathSeg(kind=PathSegKind.FIELD, field=key)]
            patch.ops.append(PatchOp(op=PatchOpKind.DELETE, path=child_path))


def _diff_map_values(from_v: GValue, to_v: GValue, path: List[PathSeg], patch: Patch) -> None:
    from_map = {e.key: e.value for e in from_v.as_map()}
    to_map = {e.key: e.value for e in to_v.as_map()}

    for key, to_val in to_map.items():
        from_val = from_map.get(key)
        child_path = path + [PathSeg(kind=PathSegKind.MAP_KEY, map_key=key)]
        _diff_values(from_val, to_val, child_path, patch)

    for key in from_map:
        if key not in to_map:
            child_path = path + [PathSeg(kind=PathSegKind.MAP_KEY, map_key=key)]
            patch.ops.append(PatchOp(op=PatchOpKind.DELETE, path=child_path))


def _lists_equal(a: List[GValue], b: List[GValue]) -> bool:
    if len(a) != len(b):
        return False
    return all(_values_equal(x, y) for x, y in zip(a, b))


def _values_equal(a: Optional[GValue], b: Optional[GValue]) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if a.type != b.type:
        return False

    t = a.type
    if t == GType.NULL:
        return True
    if t == GType.BOOL:
        return a.as_bool() == b.as_bool()
    if t == GType.INT:
        return a.as_int() == b.as_int()
    if t == GType.FLOAT:
        return a.as_float() == b.as_float()
    if t == GType.STR:
        return a.as_str() == b.as_str()
    if t == GType.ID:
        return a.as_id() == b.as_id()
    if t == GType.LIST:
        return _lists_equal(a.as_list(), b.as_list())
    if t == GType.STRUCT:
        as_, bs = a.as_struct(), b.as_struct()
        if as_.type_name != bs.type_name:
            return False
        if len(as_.fields) != len(bs.fields):
            return False
        a_fields = {f.key: f.value for f in as_.fields}
        for f in bs.fields:
            if not _values_equal(a_fields.get(f.key), f.value):
                return False
        return True
    # map/bytes/time/sum: not covered, mirrors Go's valuesEqual default case
    # (always unequal) — see the module doc comment above.
    return False
