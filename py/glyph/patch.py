"""
Glyph patch: JSON wire form (SPEC-CANON.md §7).

    {"glyph_patch":1,
     "ops":[{"op":"=","path":["step"],"value":2},
            {"op":"+","path":["items"],"value":{"id":1,"name":"item_1"}},
            {"op":"-","path":["removed_field"]},
            {"op":"~","path":["counter"],"value":5}],
     "base":"<64 hex>"?, "target":"prefix:value"?, "schema":"<id>"?, "type":"<TypeName>"?}

Operations:
    = (set)    — Replace value at path
    + (append) — Append to list (insert before "index" when given) or add field
    - (delete) — Remove field
    ~ (delta)  — Numeric increment/decrement

Path segments are strings (struct field or map key) or non-negative ints (list
index). parse_patch accepts any JSON spelling; canonical bytes are enforced at
the GS1 cursor (SPEC-CANON.md §5), and emit_patch always produces them.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .types import GType, GValue, MapEntry
from .canon import canon_json, fingerprint
from .loose import from_json_loose

PATCH_WIRE_VERSION = 1


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
    # APPEND only: insert before this list position; -1 means append.
    index: int = -1


@dataclass
class Patch:
    ops: List[PatchOp] = field(default_factory=list)
    schema_id: str = ""
    target: str = ""
    # glyph.fingerprint(base), 64 hex (SPEC-CANON.md §5); empty when the patch
    # does not record a base. Same digest in Go BaseFingerprint / JS
    # baseFingerprint, so any receiver can verify any emitter's patch.
    base_fingerprint: str = ""
    # Root type name, set by diff() (mirrors Go Patch.TargetType / JS
    # patch.targetType). Python has no schema/FID resolution pass yet, so this
    # is carried for signature parity with Go's Diff(from, to, typeName) but
    # is not otherwise consumed.
    target_type: str = ""


# Base fingerprint = glyph.fingerprint(base): full 64-hex sha256(canon_json) (SPEC-CANON.md §5).
BASE_FINGERPRINT_LEN = 64


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
    """Patch base fingerprint: glyph.fingerprint(base), the one digest (SPEC-CANON.md §5)."""
    return fingerprint(base)


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


# ============================================================
# Parse (SPEC-CANON.md §7)
# ============================================================

_OP_KINDS = {k.value: k for k in PatchOpKind}
_HEADER_KEYS = {"glyph_patch", "ops", "base", "schema", "target", "type"}
_HEADER_STRINGS = (("base", "base_fingerprint"), ("schema", "schema_id"),
                   ("target", "target"), ("type", "target_type"))
_OP_KEYS = {"op", "path", "value", "index"}


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def parse_patch(data: Union[str, bytes]) -> Patch:
    """Parse the JSON patch wire form (SPEC-CANON.md §7).

    Accepts any JSON spelling (whitespace, key order); canonical bytes are the
    GS1 cursor's job. Unknown keys at either level are errors.
    """
    try:
        doc = json.loads(data)
    except ValueError as e:
        raise ValueError(f"patch is not JSON: {e}") from None
    if not isinstance(doc, dict):
        raise ValueError("patch must be a JSON object")
    unknown = set(doc) - _HEADER_KEYS
    if unknown:
        raise ValueError(f"unknown patch key(s): {sorted(unknown)}")
    if not _is_int(doc.get("glyph_patch")) or doc["glyph_patch"] != PATCH_WIRE_VERSION:
        raise ValueError(f"patch must carry glyph_patch: {PATCH_WIRE_VERSION}")
    ops = doc.get("ops")
    if not isinstance(ops, list):
        raise ValueError("patch ops must be a list")

    patch = Patch()
    for key, attr in _HEADER_STRINGS:
        if key in doc:
            if not isinstance(doc[key], str):
                raise ValueError(f"patch {key} must be a string")
            if key == "target" and doc[key] and ":" not in doc[key]:
                # Wire form is "prefix:value" (SPEC-CANON.md §7). The raw
                # string is kept as-is (no API break) — only the shape is
                # validated here.
                raise ValueError(f"patch target must be \"prefix:value\": {doc[key]!r}")
            setattr(patch, attr, doc[key])
    patch.ops = [_parse_op(raw, i) for i, raw in enumerate(ops)]
    return patch


def _parse_op(raw: Any, i: int) -> PatchOp:
    if not isinstance(raw, dict):
        raise ValueError(f"op {i}: must be an object")
    unknown = set(raw) - _OP_KEYS
    if unknown:
        raise ValueError(f"op {i}: unknown key(s): {sorted(unknown)}")
    kind = _OP_KINDS.get(raw.get("op"))
    if kind is None:
        raise ValueError(f"op {i}: unknown operation: {raw.get('op')!r}")
    path = raw.get("path")
    if not isinstance(path, list):
        raise ValueError(f"op {i}: path must be a list")
    op = PatchOp(op=kind, path=[_parse_seg(seg, i) for seg in path])

    if kind == PatchOpKind.DELETE:
        if "value" in raw:
            raise ValueError(f"op {i}: '-' takes no value")
    elif "value" not in raw:
        raise ValueError(f"op {i}: '{kind.value}' requires a value")
    elif kind == PatchOpKind.DELTA:
        v = raw["value"]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"op {i}: invalid delta: {v!r}")
        op.delta = float(v)
    else:
        op.value = from_json_loose(raw["value"])

    if "index" in raw:
        if kind != PatchOpKind.APPEND:
            raise ValueError(f"op {i}: index is only allowed on '+'")
        if not _is_int(raw["index"]) or raw["index"] < 0:
            raise ValueError(f"op {i}: index must be a non-negative integer")
        op.index = raw["index"]
    return op


def _parse_seg(seg: Any, i: int) -> PathSeg:
    if isinstance(seg, str):
        return PathSeg(kind=PathSegKind.FIELD, field=seg)
    if _is_int(seg) and seg >= 0:
        return PathSeg(kind=PathSegKind.LIST_IDX, list_idx=seg)
    raise ValueError(f"op {i}: path segment must be a string or non-negative integer: {seg!r}")


# ============================================================
# Emit (SPEC-CANON.md §7)
# ============================================================


def _seg_gv(seg: PathSeg) -> GValue:
    if seg.kind == PathSegKind.LIST_IDX:
        return GValue.int_(seg.list_idx)
    return GValue.str_(seg.field if seg.kind == PathSegKind.FIELD else seg.map_key)


def _path_gv(path: List[PathSeg]) -> GValue:
    return GValue.list_(*(_seg_gv(s) for s in path))


def _op_gv(op: PatchOp) -> GValue:
    entries = [MapEntry("op", GValue.str_(op.op.value)), MapEntry("path", _path_gv(op.path))]
    if op.op == PatchOpKind.DELTA:
        entries.append(MapEntry("value", GValue.float_(op.delta)))
    elif op.op != PatchOpKind.DELETE:
        entries.append(MapEntry("value", op.value if op.value is not None else GValue.null()))
    if op.op == PatchOpKind.APPEND and op.index >= 0:
        entries.append(MapEntry("index", GValue.int_(op.index)))
    return GValue.map_(*entries)


def emit_patch(patch: Patch) -> str:
    """Emit the canonical JSON wire form — the inverse of parse_patch.

    Ops are sorted by (canon_json(path), op) so a patch diffed independently
    in any of the three languages for the same from/to pair emits identical
    bytes. Empty header fields are omitted.
    """
    ops = sorted(patch.ops, key=lambda op: (canon_json(_path_gv(op.path)), op.op.value))
    entries = [
        MapEntry("glyph_patch", GValue.int_(PATCH_WIRE_VERSION)),
        MapEntry("ops", GValue.list_(*(_op_gv(op) for op in ops))),
    ]
    for key, attr in _HEADER_STRINGS:
        if getattr(patch, attr):
            entries.append(MapEntry(key, GValue.str_(getattr(patch, attr))))
    return canon_json(GValue.map_(*entries))


# ============================================================
# Apply
# ============================================================


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
            if op.value is None:
                raise ValueError("cannot apply set with no value to root")
            return op.value
        raise ValueError(f"cannot apply {op.op.value} to root")

    if len(op.path) == 1:
        return _apply_to_parent(v, op.path[0], op)

    # Navigate to parent
    seg = op.path[0]
    rest_op = PatchOp(op=op.op, path=op.path[1:], value=op.value, delta=op.delta, index=op.index)

    if v.type == GType.STRUCT and seg.kind == PathSegKind.FIELD:
        for i, f in enumerate(v._struct.fields):
            if f.key == seg.field:
                v._struct.fields[i] = MapEntry(
                    key=f.key, value=_apply_op(f.value, rest_op)
                )
                return v
        raise ValueError(f"field not found: {seg.field}")

    if v.type == GType.MAP and seg.kind in (PathSegKind.FIELD, PathSegKind.MAP_KEY):
        key = seg.field if seg.kind == PathSegKind.FIELD else seg.map_key
        for i, f in enumerate(v._map):
            if f.key == key:
                v._map[i] = MapEntry(
                    key=f.key, value=_apply_op(f.value, rest_op)
                )
                return v
        raise ValueError(f"key not found: {key}")

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
            if op.index >= 0:
                existing._list.insert(op.index, op.value)
            else:
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
            # Mirror Go ("delta %v would truncate when applied to int field"):
            # a fractional delta on an int field is an error, never a silent
            # int() truncation.
            if not float(op.delta).is_integer():
                raise ValueError(
                    f"delta {op.delta} would truncate when applied to int field {key!r}"
                )
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
