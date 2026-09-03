"""Comprehensive tests for glyph.patch module."""

import json

import pytest

from glyph.patch import (
    Patch,
    PatchOp,
    PatchOpKind,
    PathSeg,
    PathSegKind,
    apply_patch,
    parse_patch,
    emit_patch,
    diff,
    verify_patch_base,
    compute_base_fingerprint,
    PatchBaseMismatch,
    _apply_op,
    _apply_to_parent,
    _get_field,
    _set_field,
    _delete_field,
)
from glyph import from_json_loose, is_canonical
from glyph.types import GType, GValue, MapEntry


def _wire(*ops, **hdr) -> str:
    """Patch wire string from (op, path[, value]) tuples; hdr = base/target/schema/type."""
    doc = {"glyph_patch": 1, "ops": [dict(op=o, path=p, **({"value": v[0]} if v else {}))
                                     for o, p, *v in ops]}
    doc.update({k: v for k, v in hdr.items() if v})
    return json.dumps(doc)


# ============================================================
# parse_patch — JSON wire form (SPEC-CANON.md §7)
# ============================================================


class TestParsePatchHeader:
    def test_minimal_patch(self):
        p = parse_patch('{"glyph_patch":1,"ops":[]}')
        assert isinstance(p, Patch)
        assert (p.ops, p.schema_id, p.target, p.base_fingerprint, p.target_type) == ([], "", "", "", "")

    def test_header_fields(self):
        p = parse_patch(_wire(schema="Foo", target="bar", base="ab" * 32, type="T"))
        assert (p.schema_id, p.target, p.base_fingerprint, p.target_type) == ("Foo", "bar", "ab" * 32, "T")

    def test_bytes_input_and_any_spelling(self):
        # Parsing is lenient about spelling; canonical bytes are the GS1 cursor's job (§5).
        p = parse_patch(b'{ "ops" : [ ] ,\n "glyph_patch" : 1 }')
        assert p.ops == []

    @pytest.mark.parametrize("bad, msg", [
        ("not json", "not JSON"),
        ("[]", "must be a JSON object"),
        ('{"ops":[]}', "glyph_patch"),
        ('{"glyph_patch":2,"ops":[]}', "glyph_patch"),
        ('{"glyph_patch":true,"ops":[]}', "glyph_patch"),
        ('{"glyph_patch":1}', "ops must be a list"),
        ('{"glyph_patch":1,"ops":[],"extra":1}', "unknown patch key"),
        ('{"glyph_patch":1,"ops":[],"base":7}', "base must be a string"),
    ])
    def test_rejects(self, bad, msg):
        with pytest.raises(ValueError, match=msg):
            parse_patch(bad)


class TestParsePatchOps:
    def test_set_op(self):
        op = parse_patch(_wire(("=", ["step"], 2))).ops[0]
        assert op.op == PatchOpKind.SET
        assert op.value.type == GType.INT and op.value.as_int() == 2

    def test_append_op(self):
        op = parse_patch(_wire(("+", ["items"], "hello"))).ops[0]
        assert op.op == PatchOpKind.APPEND
        assert op.value.as_str() == "hello"
        assert op.index == -1

    def test_append_with_index(self):
        op = parse_patch('{"glyph_patch":1,"ops":[{"op":"+","path":["items"],"value":1,"index":0}]}').ops[0]
        assert op.index == 0

    def test_delete_op(self):
        op = parse_patch(_wire(("-", ["removed_field"]))).ops[0]
        assert op.op == PatchOpKind.DELETE
        assert op.value is None

    @pytest.mark.parametrize("v, want", [(5, 5.0), (-3, -3.0), (1.5, 1.5)])
    def test_delta_op(self, v, want):
        op = parse_patch(_wire(("~", ["counter"], v))).ops[0]
        assert op.op == PatchOpKind.DELTA
        assert op.delta == want

    def test_multiple_ops_keep_wire_order(self):
        p = parse_patch(_wire(("=", ["a"], 1), ("+", ["b"], 2), ("-", ["c"]), ("~", ["d"], 10)))
        assert [o.op for o in p.ops] == [
            PatchOpKind.SET, PatchOpKind.APPEND, PatchOpKind.DELETE, PatchOpKind.DELTA]

    def test_typed_scalars_ride_as_reserved_objects(self):
        # SPEC-CANON §3: a single-key {"$bytes"|"$time"|"$id"} value is a typed scalar, not a map.
        p = parse_patch(_wire(("=", ["b"], {"$bytes": "AP8="}), ("=", ["i"], {"$id": ["m", "1"]})))
        assert p.ops[0].value.type == GType.BYTES and p.ops[0].value.as_bytes() == b"\x00\xff"
        assert p.ops[1].value.type == GType.ID

    @pytest.mark.parametrize("op, msg", [
        ({"op": "?", "path": ["x"], "value": 1}, "unknown operation"),
        ({"op": "=", "value": 1}, "path must be a list"),
        ({"op": "=", "path": "x", "value": 1}, "path must be a list"),
        ({"op": "=", "path": ["x"]}, "requires a value"),
        ({"op": "-", "path": ["x"], "value": 1}, "takes no value"),
        ({"op": "~", "path": ["x"], "value": "notanumber"}, "invalid delta"),
        ({"op": "~", "path": ["x"], "value": True}, "invalid delta"),
        ({"op": "=", "path": ["x"], "value": 1, "index": 0}, "only allowed on"),
        ({"op": "+", "path": ["x"], "value": 1, "index": -1}, "non-negative"),
        ({"op": "=", "path": ["x"], "value": 1, "extra": 1}, "unknown key"),
        ("notanobject", "must be an object"),
    ])
    def test_op_errors(self, op, msg):
        with pytest.raises(ValueError, match=msg):
            parse_patch(json.dumps({"glyph_patch": 1, "ops": [op]}))


class TestWirePaths:
    def test_strings_are_fields_ints_are_list_indices(self):
        segs = parse_patch(_wire(("=", ["data", "items", 2, "name", "a b", "c.d"], 1))).ops[0].path
        assert [(s.kind, s.field or s.list_idx) for s in segs] == [
            (PathSegKind.FIELD, "data"), (PathSegKind.FIELD, "items"), (PathSegKind.LIST_IDX, 2),
            (PathSegKind.FIELD, "name"), (PathSegKind.FIELD, "a b"), (PathSegKind.FIELD, "c.d")]

    def test_empty_path_is_root(self):
        assert parse_patch(_wire(("=", [], 1))).ops[0].path == []

    @pytest.mark.parametrize("seg", [-1, 1.5, True, None, ["x"]])
    def test_bad_segment_rejected(self, seg):
        with pytest.raises(ValueError, match="path segment"):
            parse_patch(_wire(("=", [seg], 1)))

    def test_map_key_and_field_are_one_kind_on_the_wire(self):
        # diff() emits MAP_KEY for maps; the wire has one string kind and it re-parses as FIELD,
        # which apply navigates on both maps and structs.
        p = diff(from_json_loose({"k v": 1}), from_json_loose({"k v": 2}))
        assert p.ops[0].path[0].kind == PathSegKind.MAP_KEY
        assert parse_patch(emit_patch(p)).ops[0].path[0] == PathSeg(PathSegKind.FIELD, field="k v")


# ============================================================
# emit_patch — canonical bytes, sorted ops
# ============================================================


class TestEmitPatch:
    def test_emits_canonical_bytes_with_sorted_ops(self):
        p = Patch(
            ops=[
                PatchOp(PatchOpKind.SET, [PathSeg(PathSegKind.FIELD, field="z")], GValue.int_(1)),
                PatchOp(PatchOpKind.DELETE, [PathSeg(PathSegKind.MAP_KEY, map_key="a")]),
                PatchOp(PatchOpKind.SET, [PathSeg(PathSegKind.FIELD, field="a")], GValue.null()),
            ],
            target="m:1",
            base_fingerprint="ab" * 32,
        )
        s = emit_patch(p)
        assert is_canonical(s)
        assert s == (
            '{"base":"' + "ab" * 32 + '","glyph_patch":1,"ops":['
            '{"op":"-","path":["a"]},{"op":"=","path":["a"],"value":null},'
            '{"op":"=","path":["z"],"value":1}],"target":"m:1"}'
        )

    def test_delta_and_index(self):
        p = Patch(ops=[
            PatchOp(PatchOpKind.DELTA, [PathSeg(PathSegKind.FIELD, field="n")], delta=2.5),
            PatchOp(PatchOpKind.APPEND, [PathSeg(PathSegKind.FIELD, field="l")], GValue.int_(1), index=0),
        ])
        assert emit_patch(p) == (
            '{"glyph_patch":1,"ops":[{"index":0,"op":"+","path":["l"],"value":1},'
            '{"op":"~","path":["n"],"value":2.5}]}'
        )

    def test_round_trip_is_stable(self):
        s = emit_patch(parse_patch(_wire(
            ("=", ["a", 0, "b"], {"x": [1, 2.5, None, True], "t": {"$time": "2025-01-13T12:34:56Z"}}),
            ("~", ["c"], -1), ("+", ["l"], "v"), ("-", ["d"]), base="cd" * 32, schema="S", type="T")))
        assert is_canonical(s)
        assert emit_patch(parse_patch(s)) == s


# ============================================================
# apply_patch — SET operations
# ============================================================


class TestApplySet:
    def _make_map(self, **kwargs):
        entries = []
        for k, v in kwargs.items():
            if isinstance(v, int):
                entries.append(MapEntry(key=k, value=GValue.int_(v)))
            elif isinstance(v, str):
                entries.append(MapEntry(key=k, value=GValue.str_(v)))
            elif isinstance(v, float):
                entries.append(MapEntry(key=k, value=GValue.float_(v)))
            elif isinstance(v, GValue):
                entries.append(MapEntry(key=k, value=v))
        return GValue.map_(*entries)

    def test_set_existing_field_on_map(self):
        doc = self._make_map(step=1, name="test")
        patch = parse_patch(_wire(('=', ['step'], 2)))
        result = apply_patch(doc, patch)
        assert result.get("step").as_int() == 2

    def test_set_new_field_on_map(self):
        doc = self._make_map(step=1)
        patch = parse_patch(_wire(('=', ['newfield'], 99)))
        result = apply_patch(doc, patch)
        assert result.get("newfield").as_int() == 99

    def test_set_on_struct(self):
        doc = GValue.struct("MyType", MapEntry("x", GValue.int_(1)))
        patch = parse_patch(_wire(('=', ['x'], 42)))
        result = apply_patch(doc, patch)
        assert result.get("x").as_int() == 42

    def test_set_new_field_on_struct(self):
        doc = GValue.struct("MyType", MapEntry("x", GValue.int_(1)))
        patch = parse_patch(_wire(('=', ['y'], 99)))
        result = apply_patch(doc, patch)
        assert result.get("y").as_int() == 99

    def test_set_root_level(self):
        """SET on root (empty path after dot) replaces entire value."""
        doc = GValue.int_(1)
        op = PatchOp(op=PatchOpKind.SET, path=[], value=GValue.int_(42))
        patch = Patch(ops=[op])
        result = apply_patch(doc, patch)
        assert result.as_int() == 42

    def test_set_nested_field(self):
        inner = GValue.map_(MapEntry("val", GValue.int_(1)))
        doc = GValue.map_(MapEntry("inner", inner))
        patch = parse_patch(_wire(('=', ['inner', 'val'], 99)))
        result = apply_patch(doc, patch)
        assert result.get("inner").get("val").as_int() == 99


# ============================================================
# apply_patch — APPEND operations
# ============================================================


class TestApplyAppend:
    def test_append_to_existing_list(self):
        lst = GValue.list_(GValue.int_(1), GValue.int_(2))
        doc = GValue.map_(MapEntry("items", lst))
        patch = parse_patch(_wire(('+', ['items'], 3)))
        result = apply_patch(doc, patch)
        items = result.get("items").as_list()
        assert len(items) == 3
        assert items[2].as_int() == 3

    def test_append_creates_new_list(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = parse_patch(_wire(('+', ['newlist'], 42)))
        result = apply_patch(doc, patch)
        lst = result.get("newlist")
        assert lst.type == GType.LIST
        assert lst.as_list()[0].as_int() == 42

    def test_append_with_index_inserts(self):
        doc = GValue.map_(MapEntry("items", GValue.list_(GValue.int_(1), GValue.int_(3))))
        op = PatchOp(PatchOpKind.APPEND, [PathSeg(PathSegKind.FIELD, field="items")], GValue.int_(2), index=1)
        result = apply_patch(doc, Patch(ops=[op]))
        assert [v.as_int() for v in result.get("items").as_list()] == [1, 2, 3]

    def test_append_to_non_list_raises(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = parse_patch(_wire(('+', ['x'], 5)))
        with pytest.raises(ValueError, match="cannot append"):
            apply_patch(doc, patch)

    def test_append_map_value(self):
        lst = GValue.list_()
        doc = GValue.map_(MapEntry("items", lst))
        patch = parse_patch(_wire(('+', ['items'], {'id': 1, 'name': 'item_1'})))
        result = apply_patch(doc, patch)
        items = result.get("items").as_list()
        assert len(items) == 1
        assert items[0].get("id").as_int() == 1


# ============================================================
# apply_patch — DELETE operations
# ============================================================


class TestApplyDelete:
    def test_delete_from_map(self):
        doc = GValue.map_(
            MapEntry("a", GValue.int_(1)), MapEntry("b", GValue.int_(2))
        )
        patch = parse_patch(_wire(('-', ['a'])))
        result = apply_patch(doc, patch)
        assert result.get("a") is None
        assert result.get("b").as_int() == 2

    def test_delete_from_struct(self):
        doc = GValue.struct(
            "T", MapEntry("a", GValue.int_(1)), MapEntry("b", GValue.int_(2))
        )
        patch = parse_patch(_wire(('-', ['a'])))
        result = apply_patch(doc, patch)
        assert result.get("a") is None

    def test_delete_from_non_container_raises(self):
        doc = GValue.int_(42)
        op = PatchOp(
            op=PatchOpKind.DELETE,
            path=[PathSeg(kind=PathSegKind.FIELD, field="x")],
        )
        with pytest.raises(ValueError, match="cannot delete"):
            _apply_to_parent(doc, op.path[0], op)


# ============================================================
# apply_patch — DELTA operations
# ============================================================


class TestApplyDelta:
    def test_delta_on_int(self):
        doc = GValue.map_(MapEntry("counter", GValue.int_(10)))
        patch = parse_patch(_wire(('~', ['counter'], 5)))
        result = apply_patch(doc, patch)
        assert result.get("counter").as_int() == 15

    def test_delta_on_float(self):
        doc = GValue.map_(MapEntry("score", GValue.float_(1.0)))
        patch = parse_patch(_wire(('~', ['score'], 0.5)))
        result = apply_patch(doc, patch)
        assert abs(result.get("score").as_float() - 1.5) < 1e-10

    def test_delta_creates_field_if_missing(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = parse_patch(_wire(('~', ['newcounter'], 10)))
        result = apply_patch(doc, patch)
        assert result.get("newcounter").as_float() == 10.0

    def test_delta_on_non_numeric_raises(self):
        doc = GValue.map_(MapEntry("name", GValue.str_("hello")))
        patch = parse_patch(_wire(('~', ['name'], 1)))
        with pytest.raises(ValueError, match="cannot apply delta"):
            apply_patch(doc, patch)

    def test_delta_negative(self):
        doc = GValue.map_(MapEntry("counter", GValue.int_(10)))
        patch = parse_patch(_wire(('~', ['counter'], -3)))
        result = apply_patch(doc, patch)
        assert result.get("counter").as_int() == 7


# ============================================================
# apply_patch — nested navigation
# ============================================================


class TestApplyNested:
    def test_nested_map_set(self):
        inner = GValue.map_(MapEntry("val", GValue.int_(1)))
        doc = GValue.map_(MapEntry("outer", inner))
        patch = parse_patch(_wire(('=', ['outer', 'val'], 42)))
        result = apply_patch(doc, patch)
        assert result.get("outer").get("val").as_int() == 42

    def test_nested_struct_set(self):
        inner = GValue.struct("Inner", MapEntry("val", GValue.int_(1)))
        doc = GValue.struct("Outer", MapEntry("nested", inner))
        patch = parse_patch(_wire(('=', ['nested', 'val'], 42)))
        result = apply_patch(doc, patch)
        assert result.get("nested").get("val").as_int() == 42

    def test_nested_list_index(self):
        items = GValue.list_(
            GValue.map_(MapEntry("name", GValue.str_("a"))),
            GValue.map_(MapEntry("name", GValue.str_("b"))),
        )
        doc = GValue.map_(MapEntry("items", items))
        patch = parse_patch(_wire(('=', ['items', 1, 'name'], 'updated')))
        result = apply_patch(doc, patch)
        assert result.get("items").as_list()[1].get("name").as_str() == "updated"

    def test_deeply_nested_path(self):
        c = GValue.map_(MapEntry("val", GValue.int_(0)))
        b = GValue.map_(MapEntry("c", c))
        a = GValue.map_(MapEntry("b", b))
        doc = GValue.map_(MapEntry("a", a))
        patch = parse_patch(_wire(('=', ['a', 'b', 'c', 'val'], 999)))
        result = apply_patch(doc, patch)
        assert result.get("a").get("b").get("c").get("val").as_int() == 999

    def test_navigate_missing_field_in_map_raises(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = parse_patch(_wire(('=', ['missing', 'val'], 1)))
        with pytest.raises(ValueError, match="key not found"):
            apply_patch(doc, patch)

    def test_navigate_missing_field_in_struct_raises(self):
        doc = GValue.struct("T", MapEntry("x", GValue.int_(1)))
        patch = parse_patch(_wire(('=', ['missing', 'val'], 1)))
        with pytest.raises(ValueError, match="field not found"):
            apply_patch(doc, patch)

    def test_list_index_out_of_bounds_raises(self):
        items = GValue.list_(GValue.int_(1))
        doc = GValue.map_(MapEntry("items", items))
        patch = parse_patch(_wire(('=', ['items', 5, 'val'], 1)))
        with pytest.raises(ValueError, match="index out of bounds"):
            apply_patch(doc, patch)

    def test_navigate_type_mismatch_raises(self):
        """Try to navigate list index on a non-list value."""
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        op = PatchOp(
            op=PatchOpKind.SET,
            path=[
                PathSeg(kind=PathSegKind.LIST_IDX, list_idx=0),
                PathSeg(kind=PathSegKind.FIELD, field="y"),
            ],
            value=GValue.int_(1),
        )
        with pytest.raises(ValueError, match="cannot navigate"):
            _apply_op(doc, op)


# ============================================================
# apply_patch — root-level operations
# ============================================================


class TestApplyRootOps:
    def test_root_set(self):
        doc = GValue.int_(1)
        op = PatchOp(op=PatchOpKind.SET, path=[], value=GValue.str_("replaced"))
        patch = Patch(ops=[op])
        result = apply_patch(doc, patch)
        assert result.as_str() == "replaced"

    def test_root_non_set_raises(self):
        doc = GValue.int_(1)
        op = PatchOp(op=PatchOpKind.DELETE, path=[])
        patch = Patch(ops=[op])
        with pytest.raises(ValueError, match="cannot apply"):
            apply_patch(doc, patch)

    def test_root_append_raises(self):
        doc = GValue.int_(1)
        op = PatchOp(op=PatchOpKind.APPEND, path=[], value=GValue.int_(2))
        patch = Patch(ops=[op])
        with pytest.raises(ValueError, match="cannot apply"):
            apply_patch(doc, patch)


# ============================================================
# _get_field / _set_field / _delete_field
# ============================================================


class TestFieldHelpers:
    def test_get_field_map(self):
        doc = GValue.map_(MapEntry("a", GValue.int_(1)))
        assert _get_field(doc, "a").as_int() == 1

    def test_get_field_struct(self):
        doc = GValue.struct("T", MapEntry("a", GValue.int_(1)))
        assert _get_field(doc, "a").as_int() == 1

    def test_get_field_missing(self):
        doc = GValue.map_(MapEntry("a", GValue.int_(1)))
        assert _get_field(doc, "b") is None

    def test_get_field_non_container(self):
        doc = GValue.int_(1)
        assert _get_field(doc, "x") is None

    def test_set_field_on_non_container_raises(self):
        doc = GValue.int_(1)
        with pytest.raises(ValueError, match="cannot set field"):
            _set_field(doc, "x", GValue.int_(1))

    def test_set_field_existing_map(self):
        doc = GValue.map_(MapEntry("a", GValue.int_(1)))
        _set_field(doc, "a", GValue.int_(99))
        assert doc.get("a").as_int() == 99

    def test_set_field_new_on_map(self):
        doc = GValue.map_()
        _set_field(doc, "x", GValue.int_(1))
        assert doc.get("x").as_int() == 1

    def test_set_field_existing_struct(self):
        doc = GValue.struct("T", MapEntry("a", GValue.int_(1)))
        _set_field(doc, "a", GValue.int_(99))
        assert doc.get("a").as_int() == 99

    def test_delete_field_map(self):
        doc = GValue.map_(MapEntry("a", GValue.int_(1)), MapEntry("b", GValue.int_(2)))
        _delete_field(doc, "a")
        assert doc.get("a") is None

    def test_delete_field_struct(self):
        doc = GValue.struct("T", MapEntry("a", GValue.int_(1)))
        _delete_field(doc, "a")
        assert doc.get("a") is None

    def test_delete_field_non_container_raises(self):
        doc = GValue.int_(1)
        with pytest.raises(ValueError, match="cannot delete"):
            _delete_field(doc, "x")


# ============================================================
# Deep copy / immutability
# ============================================================


class TestDeepCopy:
    def test_apply_patch_does_not_mutate_original(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = parse_patch(_wire(('=', ['x'], 99)))
        result = apply_patch(doc, patch)
        assert result.get("x").as_int() == 99
        assert doc.get("x").as_int() == 1


# ============================================================
# Integration / end-to-end
# ============================================================


class TestIntegration:
    def test_full_patch(self):
        doc = GValue.map_(
            MapEntry("step", GValue.int_(1)),
            MapEntry("items", GValue.list_(GValue.str_("a"))),
            MapEntry("to_remove", GValue.str_("bye")),
            MapEntry("counter", GValue.int_(10)),
        )
        text = _wire(("=", ["step"], 2), ("+", ["items"], "b"), ("-", ["to_remove"]),
                     ("~", ["counter"], 5), schema="GameState", target="obj1")
        patch = parse_patch(text)
        assert patch.schema_id == "GameState"
        assert patch.target == "obj1"

        result = apply_patch(doc, patch)
        assert result.get("step").as_int() == 2
        assert len(result.get("items").as_list()) == 2
        assert result.get("items").as_list()[1].as_str() == "b"
        assert result.get("to_remove") is None
        assert result.get("counter").as_int() == 15

    def test_empty_patch_returns_copy(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = Patch()
        result = apply_patch(doc, patch)
        assert result.get("x").as_int() == 1

    def test_set_with_map_value(self):
        doc = GValue.map_(MapEntry("config", GValue.map_()))
        patch = parse_patch(_wire(('=', ['config'], {'a': 1, 'b': 'two'})))
        result = apply_patch(doc, patch)
        cfg = result.get("config")
        assert cfg.get("a").as_int() == 1
        assert cfg.get("b").as_str() == "two"

    def test_set_with_list_value(self):
        doc = GValue.map_(MapEntry("data", GValue.list_()))
        patch = parse_patch(_wire(('=', ['data'], [1, 2, 3])))
        result = apply_patch(doc, patch)
        items = result.get("data").as_list()
        assert len(items) == 3

    def test_nested_map_in_list_value(self):
        v = parse_patch(_wire(("=", ["x"], [{"a": 1}, {"b": 2}]))).ops[0].value
        assert v.type == GType.LIST
        items = v.as_list()
        assert len(items) == 2
        assert items[0].get("a").as_int() == 1
        assert items[1].get("b").as_int() == 2


# ============================================================
# Patch base fingerprint — cross-implementation contract
# ============================================================


class TestPatchBaseFingerprint:
    """The "base" fingerprint is the cross-impl patch-base contract: the one
    digest, sha256(canon_json(base)) as 64 hex (SPEC-CANON.md §5), byte-identical
    to Go WithBaseValue and JS withBaseValue. These golden values are shared with
    the Go/JS suites and pinned here, so the test fails loudly if Python drifts."""

    # Golden fingerprints (verified equal to Go/JS output).
    GOLDEN = {
        # {a=1 b=2} — same canonical form in every impl.
        ("a", 1, "b", 2): "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777",
    }

    def test_compute_matches_go_js_golden_simple(self):
        base = from_json_loose({"a": 1, "b": 2})
        assert compute_base_fingerprint(base) == "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
        assert len(compute_base_fingerprint(base)) == 64

    def test_compute_matches_go_js_golden_nested(self):
        # {away={score=0} home={score=1} rating=1} — integer-valued float 1.0
        # collapses to 1 under the unified number rule, exactly as Go/JS.
        base = from_json_loose({"home": {"score": 1}, "away": {"score": 0}, "rating": 1.0})
        assert compute_base_fingerprint(base) == "25a671159ff4f11cb1e7b2c722d3604cb44a4f67fcdbbd83373be1108fe57c85"

    def test_parse_base_token(self):
        patch = parse_patch(_wire(("=", ["home", "score"], 2), schema="abc", target="m:1", base="deadbeef12345678"))
        assert patch.base_fingerprint == "deadbeef12345678"

    def test_verify_matching_base_passes(self):
        base = from_json_loose({"a": 1, "b": 2})
        patch = parse_patch(_wire(('=', ['a'], 9), target='m:1', base=compute_base_fingerprint(base)))
        verify_patch_base(base, patch)  # must not raise

    def test_verify_wrong_base_raises(self):
        base = from_json_loose({"a": 1, "b": 2})
        patch = parse_patch(_wire(('=', ['a'], 9), target='m:1', base=compute_base_fingerprint(base)))
        with pytest.raises(PatchBaseMismatch):
            verify_patch_base(from_json_loose({"a": 9}), patch)

    def test_verify_no_base_is_noop(self):
        base = from_json_loose({"a": 1, "b": 2})
        patch = parse_patch(_wire(('=', ['a'], 9), target='m:1'))
        assert patch.base_fingerprint == ""
        verify_patch_base(base, patch)  # no base recorded -> no-op, must not raise


# ============================================================
# apply_patch — base fingerprint enforcement at apply time
# ============================================================


class TestApplyPatchBaseEnforcement:
    """apply_patch must verify a patch's recorded base fingerprint against the
    value being patched BEFORE applying any operation — callers must no
    longer remember to call verify_patch_base separately. Mirrors Go's
    TestPatchRoundTripProperty/apply-enforces-base-by-default subcase."""

    def test_apply_matching_base_applies(self):
        base = from_json_loose({"a": 1, "b": 2})
        patch = parse_patch(_wire(('=', ['a'], 9), target='m:1', base=compute_base_fingerprint(base)))
        result = apply_patch(base, patch)
        assert result.get("a").as_int() == 9

    def test_apply_stale_base_raises_without_explicit_verify_call(self):
        base = from_json_loose({"a": 1, "b": 2})
        patch = parse_patch(_wire(('=', ['a'], 9), target='m:1', base=compute_base_fingerprint(base)))
        stale = from_json_loose({"a": 1, "b": 999})

        with pytest.raises(PatchBaseMismatch) as exc_info:
            apply_patch(stale, patch)

        assert exc_info.value.want == patch.base_fingerprint
        # No operation must have been applied, and the caller's value must be
        # untouched (apply_patch never mutates its input regardless, but this
        # also guards against a check that runs too late).
        assert stale.get("b").as_int() == 999

    def test_apply_no_base_recorded_applies_unconditionally(self):
        patch = parse_patch(_wire(('=', ['a'], 9), target='m:1'))
        result = apply_patch(from_json_loose({"a": 1}), patch)
        assert result.get("a").as_int() == 9

    def test_apply_verify_base_false_is_explicit_opt_out(self):
        base = from_json_loose({"a": 1, "b": 2})
        patch = parse_patch(_wire(('=', ['a'], 9), target='m:1', base=compute_base_fingerprint(base)))
        stale = from_json_loose({"a": 1, "b": 999})

        # Sanity: the default (checked) path rejects this combination.
        with pytest.raises(PatchBaseMismatch):
            apply_patch(stale, patch)

        # verify_base=False forces the apply through despite the stale base.
        result = apply_patch(stale, patch, verify_base=False)
        assert result.get("a").as_int() == 9


# ============================================================
# diff() — auto-generate a patch from two states
#
# Port of Go's TestDiff / TestDiffWithDeletion: diff() must detect changed,
# added, and deleted fields and leave unchanged fields untouched, matching Go
# Diff(from, to, typeName)'s semantics exactly (including whole-list replace
# on any list change — no per-index diffing).
# ============================================================


class TestDiff:
    def test_scalar_changes_and_additions(self):
        frm = GValue.struct(
            "Match",
            MapEntry("id", GValue.int_(123)),
            MapEntry("score", GValue.int_(0)),
            MapEntry("status", GValue.str_("pending")),
        )
        to = GValue.struct(
            "Match",
            MapEntry("id", GValue.int_(123)),
            MapEntry("score", GValue.int_(3)),
            MapEntry("status", GValue.str_("finished")),
            MapEntry("winner", GValue.str_("home")),
        )
        patch = diff(frm, to, "Match")
        by_field = {op.path[0].field: op for op in patch.ops}

        assert "id" not in by_field  # unchanged field: no op emitted
        assert by_field["score"].op == PatchOpKind.SET
        assert by_field["score"].value.as_int() == 3
        assert by_field["status"].value.as_str() == "finished"
        assert by_field["winner"].value.as_str() == "home"

    def test_deleted_fields_emit_delete_ops(self):
        frm = GValue.struct(
            "Match",
            MapEntry("id", GValue.int_(123)),
            MapEntry("odds", GValue.float_(1.5)),
            MapEntry("pred", GValue.str_("home")),
        )
        to = GValue.struct("Match", MapEntry("id", GValue.int_(123)))

        patch = diff(frm, to, "Match")
        deletes = {op.path[0].field for op in patch.ops if op.op == PatchOpKind.DELETE}
        assert deletes == {"odds", "pred"}

    def test_no_change_produces_empty_patch(self):
        frm = GValue.struct("M", MapEntry("x", GValue.int_(1)))
        to = GValue.struct("M", MapEntry("x", GValue.int_(1)))
        assert diff(frm, to, "M").ops == []

    def test_list_change_is_whole_list_replace(self):
        # Diff does not per-index diff lists: any change replaces the whole
        # list with a single SET op (parity with Go, not an improvement).
        frm = GValue.struct("M", MapEntry("items", GValue.list_(GValue.int_(1), GValue.int_(2), GValue.int_(3))))
        to = GValue.struct(
            "M", MapEntry("items", GValue.list_(GValue.int_(1), GValue.int_(9), GValue.int_(3), GValue.int_(4)))
        )
        patch = diff(frm, to, "M")
        assert len(patch.ops) == 1
        op = patch.ops[0]
        assert op.op == PatchOpKind.SET
        assert op.path[0].field == "items"
        assert [v.as_int() for v in op.value.as_list()] == [1, 9, 3, 4]

    def test_nested_struct_change(self):
        frm = GValue.struct(
            "M", MapEntry("outer", GValue.struct("N", MapEntry("inner", GValue.struct("O", MapEntry("x", GValue.int_(1))))))
        )
        to = GValue.struct(
            "M", MapEntry("outer", GValue.struct("N", MapEntry("inner", GValue.struct("O", MapEntry("x", GValue.int_(99))))))
        )
        patch = diff(frm, to, "M")
        assert len(patch.ops) == 1
        op = patch.ops[0]
        assert [seg.field for seg in op.path] == ["outer", "inner", "x"]
        assert op.value.as_int() == 99


# ============================================================
# diff() + apply_patch() round trip
#
# Invariant (mirrors Go's TestPatchRoundTripProperty):
#   apply_patch(base, parse_patch(emit_patch(diff(base, next)))) == next
# ============================================================


class TestDiffApplyRoundTrip:
    def _round_trip(self, base: GValue, nxt: GValue, type_name: str = "M") -> GValue:
        patch = diff(base, nxt, type_name)
        emitted = emit_patch(patch)
        parsed = parse_patch(emitted)
        return apply_patch(base, parsed)

    def test_scalar_fields_round_trip(self):
        base = GValue.struct(
            "M",
            MapEntry("ok", GValue.bool_(False)),
            MapEntry("count", GValue.int_(10)),
            MapEntry("rate", GValue.float_(1.5)),
            MapEntry("label", GValue.str_("old")),
        )
        nxt = GValue.struct(
            "M",
            MapEntry("ok", GValue.bool_(True)),
            MapEntry("count", GValue.int_(42)),
            MapEntry("rate", GValue.float_(3.14)),
            MapEntry("label", GValue.str_("new")),
        )
        result = self._round_trip(base, nxt)
        assert result.get("ok").as_bool() is True
        assert result.get("count").as_int() == 42
        assert result.get("rate").as_float() == 3.14
        assert result.get("label").as_str() == "new"

    def test_added_and_deleted_fields_round_trip(self):
        base = GValue.struct(
            "M",
            MapEntry("id", GValue.int_(123)),
            MapEntry("odds", GValue.float_(1.5)),
        )
        nxt = GValue.struct(
            "M",
            MapEntry("id", GValue.int_(123)),
            MapEntry("winner", GValue.str_("home")),
        )
        result = self._round_trip(base, nxt)
        assert result.get("id").as_int() == 123
        assert result.get("odds") is None
        assert result.get("winner").as_str() == "home"

    def test_list_replace_round_trip(self):
        base = GValue.struct("M", MapEntry("items", GValue.list_(GValue.int_(1), GValue.int_(2), GValue.int_(3))))
        nxt = GValue.struct(
            "M", MapEntry("items", GValue.list_(GValue.int_(1), GValue.int_(9), GValue.int_(3), GValue.int_(4)))
        )
        result = self._round_trip(base, nxt)
        assert [v.as_int() for v in result.get("items").as_list()] == [1, 9, 3, 4]

    def test_nested_struct_round_trip(self):
        base = GValue.struct(
            "M", MapEntry("outer", GValue.struct("N", MapEntry("inner", GValue.struct("O", MapEntry("x", GValue.int_(1))))))
        )
        nxt = GValue.struct(
            "M", MapEntry("outer", GValue.struct("N", MapEntry("inner", GValue.struct("O", MapEntry("x", GValue.int_(99))))))
        )
        result = self._round_trip(base, nxt)
        assert result.get("outer").get("inner").get("x").as_int() == 99


# ============================================================
# diff() + emit_patch() — cross-language identical text
#
# The exact bytes emitted for this from/to pair are pinned here and in the Go
# (go/glyph/patch_roundtrip_test.go TestDiffEmitCrossLanguageGolden) and JS
# (js/src/glyph.test.ts) suites — the whole point of a shared wire format.
# ============================================================


class TestDiffEmitCrossLanguageGolden:
    GOLDEN = '{"base":"202baf1ae34e2dce839197f13e2fb5866a33f3dd552632154dc359763c60ab57","glyph_patch":1,"ops":[{"op":"-","path":["active"]},{"op":"=","path":["count"],"value":42},{"op":"=","path":["extra"],"value":"added"},{"op":"=","path":["label"],"value":"new"}],"target":"m:123","type":"M"}'

    def test_matches_go_and_js(self):
        frm = GValue.struct(
            "M",
            MapEntry("count", GValue.int_(10)),
            MapEntry("label", GValue.str_("old")),
            MapEntry("rate", GValue.float_(1.5)),
            MapEntry("active", GValue.bool_(False)),
        )
        to = GValue.struct(
            "M",
            MapEntry("count", GValue.int_(42)),
            MapEntry("label", GValue.str_("new")),
            MapEntry("rate", GValue.float_(1.5)),
            MapEntry("extra", GValue.str_("added")),
        )
        patch = diff(frm, to, "M")
        patch.target = "m:123"
        assert emit_patch(patch) == self.GOLDEN


# ============================================================
# Regression (2026-08-21): MAP_KEY navigation
#
# Found by harness/state_identity S1 sanity check: diff() emits MAP_KEY
# segments, but _apply_op only navigated FIELD segments on maps (depth>=2
# failed). Go/JS were unaffected. Kept on the JSON wire: hostile keys need
# no quoting grammar now, but they still have to round-trip.
# See harness/state_identity/findings/2026-08-21-py-nested-map-key-remove.md
# ============================================================


class TestNestedMapKeyRegression:
    def _apply(self, base, tgt):
        patch = diff(from_json_loose(base), from_json_loose(tgt))
        result = apply_patch(from_json_loose(base), patch, verify_base=True)
        import glyph as _g

        return _g.to_json_loose(result)

    def test_nested_remove(self):
        assert self._apply({"x": {"a": 1, "b": 2}}, {"x": {"a": 1}}) == {"x": {"a": 1}}

    def test_subtree_emptied(self):
        assert self._apply({"x": {"a": 1}}, {"x": {}}) == {"x": {}}

    def test_nested_set(self):
        assert self._apply({"x": {"a": 1, "b": 2}}, {"x": {"a": 9, "b": 2}}) == {
            "x": {"a": 9, "b": 2}
        }

    def test_deep_mixed_containers(self):
        base = {"a": {"b": {"c": [1, 2]}}}
        tgt = {"a": {"b": {"c": [1, 3], "d": True}}}
        assert self._apply(base, tgt) == tgt

    def test_emit_parse_apply_roundtrip_hostile_keys(self):
        import glyph as _g

        base = {"weIRD key.with dots": {'inner "q"': 1, "sp ace": [1, 2]}, "plain": 5}
        tgt = {
            "weIRD key.with dots": {"inner \"q\"": 2, "sp ace": [1, 2, 3], "new": True},
            "plain": 5,
        }
        wire = emit_patch(diff(from_json_loose(base), from_json_loose(tgt)))
        parsed = parse_patch(wire)
        result = apply_patch(from_json_loose(base), parsed, verify_base=True)
        assert _g.to_json_loose(result) == tgt
