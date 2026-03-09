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
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .types import GType, GValue, MapEntry, StructValue


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
    """Parse a dot-separated path like '.step' or '.items'."""
    if not path_str.startswith("."):
        raise ValueError(f"path must start with '.': {path_str}")

    segments = []
    parts = path_str[1:].split(".")

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


def apply_patch(value: GValue, patch: Patch) -> GValue:
    """Apply a patch to a GValue and return the modified copy."""
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
