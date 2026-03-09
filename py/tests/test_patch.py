"""Comprehensive tests for glyph.patch module."""

import pytest

from glyph.patch import (
    Patch,
    PatchOp,
    PatchOpKind,
    PathSeg,
    PathSegKind,
    apply_patch,
    parse_patch,
    _parse_op,
    _parse_path,
    _parse_value,
    _parse_inline_map,
    _parse_inline_list,
    _split_path_value,
    _split_next_value,
    _apply_op,
    _apply_to_parent,
    _get_field,
    _set_field,
    _delete_field,
)
from glyph.types import GType, GValue, MapEntry, StructValue


# ============================================================
# parse_patch — header parsing
# ============================================================


class TestParsePatchHeader:
    def test_minimal_patch(self):
        p = parse_patch("@patch\n@end")
        assert isinstance(p, Patch)
        assert p.ops == []
        assert p.schema_id == ""
        assert p.target == ""

    def test_patch_with_schema(self):
        p = parse_patch("@patch @schema#MyType\n@end")
        assert p.schema_id == "MyType"

    def test_patch_with_target(self):
        p = parse_patch("@patch @target=obj123\n@end")
        assert p.target == "obj123"

    def test_patch_with_schema_and_target(self):
        p = parse_patch("@patch @schema#Foo @target=bar\n@end")
        assert p.schema_id == "Foo"
        assert p.target == "bar"

    def test_missing_header_raises(self):
        with pytest.raises(ValueError, match="must start with @patch"):
            parse_patch("not a patch")

    def test_empty_lines_and_comments_skipped(self):
        text = "@patch\n\n# comment\n= .x 1\n\n@end"
        p = parse_patch(text)
        assert len(p.ops) == 1

    def test_no_end_marker(self):
        """Lines after ops but no @end — parser just stops at EOF."""
        p = parse_patch("@patch\n= .x 1")
        assert len(p.ops) == 1


# ============================================================
# parse_patch — operations
# ============================================================


class TestParsePatchOps:
    def test_set_op(self):
        p = parse_patch("@patch\n= .step 2\n@end")
        assert len(p.ops) == 1
        op = p.ops[0]
        assert op.op == PatchOpKind.SET
        assert op.value.type == GType.INT
        assert op.value.as_int() == 2

    def test_append_op(self):
        p = parse_patch('@patch\n+ .items "hello"\n@end')
        op = p.ops[0]
        assert op.op == PatchOpKind.APPEND
        assert op.value.as_str() == "hello"

    def test_delete_op(self):
        p = parse_patch("@patch\n- .removed_field\n@end")
        op = p.ops[0]
        assert op.op == PatchOpKind.DELETE
        assert op.value is None

    def test_delta_op(self):
        p = parse_patch("@patch\n~ .counter +5\n@end")
        op = p.ops[0]
        assert op.op == PatchOpKind.DELTA
        assert op.delta == 5.0

    def test_delta_negative(self):
        p = parse_patch("@patch\n~ .counter -3\n@end")
        assert p.ops[0].delta == -3.0

    def test_delta_float(self):
        p = parse_patch("@patch\n~ .score +1.5\n@end")
        assert p.ops[0].delta == 1.5

    def test_delta_no_value(self):
        """Delta with path only, no value — delta stays 0."""
        p = parse_patch("@patch\n~ .counter\n@end")
        assert p.ops[0].delta == 0.0

    def test_multiple_ops(self):
        text = "@patch\n= .a 1\n+ .b 2\n- .c\n~ .d +10\n@end"
        p = parse_patch(text)
        assert len(p.ops) == 4
        assert [o.op for o in p.ops] == [
            PatchOpKind.SET,
            PatchOpKind.APPEND,
            PatchOpKind.DELETE,
            PatchOpKind.DELTA,
        ]

    def test_delete_ignores_value(self):
        """DELETE op doesn't capture value even if present (value_str goes unused)."""
        p = parse_patch("@patch\n- .field something\n@end")
        assert p.ops[0].value is None


# ============================================================
# _parse_op — error cases
# ============================================================


class TestParseOpErrors:
    def test_unknown_op_char(self):
        with pytest.raises(ValueError, match="unknown operation"):
            _parse_op("? .path", 1)

    def test_missing_path(self):
        with pytest.raises(ValueError, match="missing path"):
            _parse_op("=", 1)

    def test_missing_path_spaces_only(self):
        with pytest.raises(ValueError, match="missing path"):
            _parse_op("=   ", 1)

    def test_invalid_delta_value(self):
        with pytest.raises(ValueError, match="invalid delta"):
            _parse_op("~ .counter notanumber", 1)


# ============================================================
# _parse_path
# ============================================================


class TestParsePath:
    def test_single_field(self):
        segs = _parse_path(".step")
        assert len(segs) == 1
        assert segs[0].kind == PathSegKind.FIELD
        assert segs[0].field == "step"

    def test_nested_fields(self):
        segs = _parse_path(".a.b.c")
        assert len(segs) == 3
        assert [s.field for s in segs] == ["a", "b", "c"]

    def test_list_index(self):
        segs = _parse_path(".items[0]")
        assert len(segs) == 2
        assert segs[0].kind == PathSegKind.FIELD
        assert segs[0].field == "items"
        assert segs[1].kind == PathSegKind.LIST_IDX
        assert segs[1].list_idx == 0

    def test_list_index_only(self):
        """Path like .[3] — no field name before bracket."""
        segs = _parse_path(".[3]")
        assert len(segs) == 1
        assert segs[0].kind == PathSegKind.LIST_IDX
        assert segs[0].list_idx == 3

    def test_nested_with_index(self):
        segs = _parse_path(".data.items[2].name")
        assert len(segs) == 4
        assert segs[0].field == "data"
        assert segs[1].field == "items"
        assert segs[2].kind == PathSegKind.LIST_IDX
        assert segs[2].list_idx == 2
        assert segs[3].field == "name"

    def test_path_not_starting_with_dot(self):
        with pytest.raises(ValueError, match="path must start with '.'"):
            _parse_path("noprefix")

    def test_invalid_list_index(self):
        with pytest.raises(ValueError, match="invalid list index"):
            _parse_path(".items[abc]")

    def test_root_path(self):
        """Just a dot — results in empty segments (empty part skipped)."""
        segs = _parse_path(".")
        assert segs == []


# ============================================================
# _parse_value — inline value parsing
# ============================================================


class TestParseValue:
    def test_null_underscore(self):
        v = _parse_value("_")
        assert v.type == GType.NULL

    def test_null_word(self):
        v = _parse_value("null")
        assert v.type == GType.NULL

    def test_null_empty_set(self):
        v = _parse_value("\u2205")
        assert v.type == GType.NULL

    def test_empty_string_becomes_null(self):
        v = _parse_value("")
        assert v.type == GType.NULL

    def test_whitespace_only_becomes_null(self):
        v = _parse_value("   ")
        assert v.type == GType.NULL

    def test_bool_true_short(self):
        assert _parse_value("t").as_bool() is True

    def test_bool_true_long(self):
        assert _parse_value("true").as_bool() is True

    def test_bool_false_short(self):
        assert _parse_value("f").as_bool() is False

    def test_bool_false_long(self):
        assert _parse_value("false").as_bool() is False

    def test_quoted_string(self):
        v = _parse_value('"hello world"')
        assert v.as_str() == "hello world"

    def test_quoted_string_with_escaped_quote(self):
        v = _parse_value('"say \\"hi\\""')
        assert v.as_str() == 'say "hi"'

    def test_quoted_string_with_escaped_backslash(self):
        v = _parse_value('"path\\\\to"')
        assert v.as_str() == "path\\to"

    def test_integer(self):
        v = _parse_value("42")
        assert v.type == GType.INT
        assert v.as_int() == 42

    def test_negative_integer(self):
        v = _parse_value("-7")
        assert v.type == GType.INT
        assert v.as_int() == -7

    def test_float_with_dot(self):
        v = _parse_value("3.14")
        assert v.type == GType.FLOAT
        assert abs(v.as_float() - 3.14) < 1e-10

    def test_float_with_exponent(self):
        v = _parse_value("1e10")
        assert v.type == GType.FLOAT
        assert v.as_float() == 1e10

    def test_float_with_uppercase_exponent(self):
        v = _parse_value("2.5E3")
        assert v.type == GType.FLOAT
        assert v.as_float() == 2500.0

    def test_bare_string(self):
        v = _parse_value("hello")
        assert v.type == GType.STR
        assert v.as_str() == "hello"

    def test_bare_string_not_matching_number(self):
        """Something that looks like it could be numeric but isn't."""
        v = _parse_value("12abc")
        assert v.type == GType.STR
        assert v.as_str() == "12abc"

    def test_inline_map(self):
        v = _parse_value('{id=1 name="item_1"}')
        assert v.type == GType.MAP
        entries = v.as_map()
        assert len(entries) == 2
        assert entries[0].key == "id"
        assert entries[0].value.as_int() == 1
        assert entries[1].key == "name"
        assert entries[1].value.as_str() == "item_1"

    def test_inline_list(self):
        v = _parse_value("[1 2 3]")
        assert v.type == GType.LIST
        items = v.as_list()
        assert len(items) == 3
        assert [i.as_int() for i in items] == [1, 2, 3]

    def test_empty_map(self):
        v = _parse_value("{}")
        assert v.type == GType.MAP
        assert len(v.as_map()) == 0

    def test_empty_list(self):
        v = _parse_value("[]")
        assert v.type == GType.LIST
        assert len(v.as_list()) == 0

    def test_inline_list_with_strings(self):
        v = _parse_value('[a "b c" d]')
        items = v.as_list()
        assert len(items) == 3
        assert items[0].as_str() == "a"
        assert items[1].as_str() == "b c"
        assert items[2].as_str() == "d"


# ============================================================
# _split_path_value
# ============================================================


class TestSplitPathValue:
    def test_path_and_value(self):
        assert _split_path_value(".step 2") == (".step", "2")

    def test_path_only(self):
        assert _split_path_value(".field") == (".field", "")

    def test_path_with_complex_value(self):
        p, v = _split_path_value('.items {id=1 name="x"}')
        assert p == ".items"
        assert v == '{id=1 name="x"}'


# ============================================================
# _split_next_value
# ============================================================


class TestSplitNextValue:
    def test_empty(self):
        assert _split_next_value("") == ("", "")

    def test_bare_token(self):
        assert _split_next_value("abc def") == ("abc", " def")

    def test_bare_token_no_rest(self):
        assert _split_next_value("abc") == ("abc", "")

    def test_quoted_string(self):
        val, rest = _split_next_value('"hello" world')
        assert val == '"hello"'
        assert rest == " world"

    def test_quoted_string_with_escape(self):
        val, rest = _split_next_value('"a\\"b" c')
        assert val == '"a\\"b"'
        assert rest == " c"

    def test_unclosed_quote(self):
        val, rest = _split_next_value('"unclosed')
        assert val == '"unclosed'
        assert rest == ""

    def test_nested_braces(self):
        val, rest = _split_next_value("{a={b=1}} more")
        assert val == "{a={b=1}}"
        assert rest == " more"

    def test_nested_brackets(self):
        val, rest = _split_next_value("[1 [2 3]] more")
        assert val == "[1 [2 3]]"
        assert rest == " more"

    def test_unclosed_brace(self):
        val, rest = _split_next_value("{unclosed")
        assert val == "{unclosed"
        assert rest == ""

    def test_unclosed_bracket(self):
        val, rest = _split_next_value("[unclosed")
        assert val == "[unclosed"
        assert rest == ""


# ============================================================
# _parse_inline_map
# ============================================================


class TestParseInlineMap:
    def test_single_entry(self):
        v = _parse_inline_map("{x=1}")
        entries = v.as_map()
        assert len(entries) == 1
        assert entries[0].key == "x"
        assert entries[0].value.as_int() == 1

    def test_multiple_entries(self):
        v = _parse_inline_map('{a=1 b="two"}')
        entries = v.as_map()
        assert len(entries) == 2

    def test_empty_map(self):
        v = _parse_inline_map("{}")
        assert len(v.as_map()) == 0

    def test_no_equals_breaks(self):
        """If inner has no '=' sign, loop breaks gracefully."""
        v = _parse_inline_map("{noequals}")
        assert len(v.as_map()) == 0


# ============================================================
# _parse_inline_list
# ============================================================


class TestParseInlineList:
    def test_ints(self):
        v = _parse_inline_list("[1 2 3]")
        assert len(v.as_list()) == 3

    def test_mixed(self):
        v = _parse_inline_list('[1 "two" true]')
        items = v.as_list()
        assert items[0].as_int() == 1
        assert items[1].as_str() == "two"
        assert items[2].as_bool() is True

    def test_empty(self):
        v = _parse_inline_list("[]")
        assert len(v.as_list()) == 0


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
        patch = parse_patch("@patch\n= .step 2\n@end")
        result = apply_patch(doc, patch)
        assert result.get("step").as_int() == 2

    def test_set_new_field_on_map(self):
        doc = self._make_map(step=1)
        patch = parse_patch("@patch\n= .newfield 99\n@end")
        result = apply_patch(doc, patch)
        assert result.get("newfield").as_int() == 99

    def test_set_on_struct(self):
        doc = GValue.struct("MyType", MapEntry("x", GValue.int_(1)))
        patch = parse_patch("@patch\n= .x 42\n@end")
        result = apply_patch(doc, patch)
        assert result.get("x").as_int() == 42

    def test_set_new_field_on_struct(self):
        doc = GValue.struct("MyType", MapEntry("x", GValue.int_(1)))
        patch = parse_patch("@patch\n= .y 99\n@end")
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
        patch = parse_patch("@patch\n= .inner.val 99\n@end")
        result = apply_patch(doc, patch)
        assert result.get("inner").get("val").as_int() == 99


# ============================================================
# apply_patch — APPEND operations
# ============================================================


class TestApplyAppend:
    def test_append_to_existing_list(self):
        lst = GValue.list_(GValue.int_(1), GValue.int_(2))
        doc = GValue.map_(MapEntry("items", lst))
        patch = parse_patch("@patch\n+ .items 3\n@end")
        result = apply_patch(doc, patch)
        items = result.get("items").as_list()
        assert len(items) == 3
        assert items[2].as_int() == 3

    def test_append_creates_new_list(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = parse_patch("@patch\n+ .newlist 42\n@end")
        result = apply_patch(doc, patch)
        lst = result.get("newlist")
        assert lst.type == GType.LIST
        assert lst.as_list()[0].as_int() == 42

    def test_append_to_non_list_raises(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = parse_patch("@patch\n+ .x 5\n@end")
        with pytest.raises(ValueError, match="cannot append"):
            apply_patch(doc, patch)

    def test_append_map_value(self):
        lst = GValue.list_()
        doc = GValue.map_(MapEntry("items", lst))
        patch = parse_patch('@patch\n+ .items {id=1 name="item_1"}\n@end')
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
        patch = parse_patch("@patch\n- .a\n@end")
        result = apply_patch(doc, patch)
        assert result.get("a") is None
        assert result.get("b").as_int() == 2

    def test_delete_from_struct(self):
        doc = GValue.struct(
            "T", MapEntry("a", GValue.int_(1)), MapEntry("b", GValue.int_(2))
        )
        patch = parse_patch("@patch\n- .a\n@end")
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
        patch = parse_patch("@patch\n~ .counter +5\n@end")
        result = apply_patch(doc, patch)
        assert result.get("counter").as_int() == 15

    def test_delta_on_float(self):
        doc = GValue.map_(MapEntry("score", GValue.float_(1.0)))
        patch = parse_patch("@patch\n~ .score +0.5\n@end")
        result = apply_patch(doc, patch)
        assert abs(result.get("score").as_float() - 1.5) < 1e-10

    def test_delta_creates_field_if_missing(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = parse_patch("@patch\n~ .newcounter +10\n@end")
        result = apply_patch(doc, patch)
        assert result.get("newcounter").as_float() == 10.0

    def test_delta_on_non_numeric_raises(self):
        doc = GValue.map_(MapEntry("name", GValue.str_("hello")))
        patch = parse_patch("@patch\n~ .name +1\n@end")
        with pytest.raises(ValueError, match="cannot apply delta"):
            apply_patch(doc, patch)

    def test_delta_negative(self):
        doc = GValue.map_(MapEntry("counter", GValue.int_(10)))
        patch = parse_patch("@patch\n~ .counter -3\n@end")
        result = apply_patch(doc, patch)
        assert result.get("counter").as_int() == 7


# ============================================================
# apply_patch — nested navigation
# ============================================================


class TestApplyNested:
    def test_nested_map_set(self):
        inner = GValue.map_(MapEntry("val", GValue.int_(1)))
        doc = GValue.map_(MapEntry("outer", inner))
        patch = parse_patch("@patch\n= .outer.val 42\n@end")
        result = apply_patch(doc, patch)
        assert result.get("outer").get("val").as_int() == 42

    def test_nested_struct_set(self):
        inner = GValue.struct("Inner", MapEntry("val", GValue.int_(1)))
        doc = GValue.struct("Outer", MapEntry("nested", inner))
        patch = parse_patch("@patch\n= .nested.val 42\n@end")
        result = apply_patch(doc, patch)
        assert result.get("nested").get("val").as_int() == 42

    def test_nested_list_index(self):
        items = GValue.list_(
            GValue.map_(MapEntry("name", GValue.str_("a"))),
            GValue.map_(MapEntry("name", GValue.str_("b"))),
        )
        doc = GValue.map_(MapEntry("items", items))
        patch = parse_patch('@patch\n= .items[1].name "updated"\n@end')
        result = apply_patch(doc, patch)
        assert result.get("items").as_list()[1].get("name").as_str() == "updated"

    def test_deeply_nested_path(self):
        c = GValue.map_(MapEntry("val", GValue.int_(0)))
        b = GValue.map_(MapEntry("c", c))
        a = GValue.map_(MapEntry("b", b))
        doc = GValue.map_(MapEntry("a", a))
        patch = parse_patch("@patch\n= .a.b.c.val 999\n@end")
        result = apply_patch(doc, patch)
        assert result.get("a").get("b").get("c").get("val").as_int() == 999

    def test_navigate_missing_field_in_map_raises(self):
        doc = GValue.map_(MapEntry("x", GValue.int_(1)))
        patch = parse_patch("@patch\n= .missing.val 1\n@end")
        with pytest.raises(ValueError, match="key not found"):
            apply_patch(doc, patch)

    def test_navigate_missing_field_in_struct_raises(self):
        doc = GValue.struct("T", MapEntry("x", GValue.int_(1)))
        patch = parse_patch("@patch\n= .missing.val 1\n@end")
        with pytest.raises(ValueError, match="field not found"):
            apply_patch(doc, patch)

    def test_list_index_out_of_bounds_raises(self):
        items = GValue.list_(GValue.int_(1))
        doc = GValue.map_(MapEntry("items", items))
        patch = parse_patch("@patch\n= .items[5].val 1\n@end")
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
        patch = parse_patch("@patch\n= .x 99\n@end")
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
        text = """@patch @schema#GameState @target=obj1
= .step 2
+ .items "b"
- .to_remove
~ .counter +5
@end"""
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
        patch = parse_patch('@patch\n= .config {a=1 b="two"}\n@end')
        result = apply_patch(doc, patch)
        cfg = result.get("config")
        assert cfg.get("a").as_int() == 1
        assert cfg.get("b").as_str() == "two"

    def test_set_with_list_value(self):
        doc = GValue.map_(MapEntry("data", GValue.list_()))
        patch = parse_patch("@patch\n= .data [1 2 3]\n@end")
        result = apply_patch(doc, patch)
        items = result.get("data").as_list()
        assert len(items) == 3

    def test_nested_map_in_list_value(self):
        v = _parse_value("[{a=1} {b=2}]")
        assert v.type == GType.LIST
        items = v.as_list()
        assert len(items) == 2
        assert items[0].get("a").as_int() == 1
        assert items[1].get("b").as_int() == 2
