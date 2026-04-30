"""Tests for Blob and Pool reference support (GLYPH MVP parity port)."""

from __future__ import annotations

import pytest

from glyph import (
    BlobRef,
    PoolRef,
    GValue,
    GType,
    Pool,
    PoolKind,
    PoolRegistry,
    blob_from_content,
    canonicalize_loose,
    compute_cid,
    emit_blob,
    emit_pool,
    g,
    is_pool_ref_id,
    parse,
    parse_blob_ref,
    parse_document,
    parse_pool,
    parse_pool_ref,
    resolve_pool_refs,
    ParseBlobError,
    ParsePoolError,
    field,
)


class TestCid:
    def test_sha256_hex(self):
        assert compute_cid(b"hello") == (
            "sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )

    def test_empty(self):
        assert compute_cid(b"") == (
            "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )


class TestBlobRef:
    def test_round_trip_minimum(self):
        ref = BlobRef(cid="sha256:abc", mime="image/png", bytes=1024)
        text = emit_blob(ref)
        assert text == "@blob cid=sha256:abc mime=image/png bytes=1024"
        parsed = parse_blob_ref(text)
        assert parsed == ref

    def test_round_trip_optional_fields(self):
        ref = BlobRef(
            cid="sha256:abc",
            mime="image/png",
            bytes=1024,
            name="cat.png",
            caption="A very fluffy cat",
        )
        text = emit_blob(ref)
        assert "name=cat.png" in text
        assert 'caption="A very fluffy cat"' in text
        parsed = parse_blob_ref(text)
        assert parsed == ref

    def test_escape_sequences(self):
        ref = BlobRef(cid="sha256:a", mime="text/plain", bytes=1, caption='quote "x" here')
        text = emit_blob(ref)
        parsed = parse_blob_ref(text)
        assert parsed.caption == 'quote "x" here'

    def test_missing_cid_raises(self):
        with pytest.raises(ParseBlobError):
            parse_blob_ref("@blob mime=x bytes=1")

    def test_missing_mime_raises(self):
        with pytest.raises(ParseBlobError):
            parse_blob_ref("@blob cid=x bytes=1")

    def test_missing_bytes_raises(self):
        with pytest.raises(ParseBlobError):
            parse_blob_ref("@blob cid=x mime=y")

    def test_bad_prefix(self):
        with pytest.raises(ParseBlobError):
            parse_blob_ref("cid=x mime=y bytes=1")

    def test_algorithm_and_hash(self):
        ref = BlobRef(cid="sha256:deadbeef", mime="x", bytes=0)
        assert ref.algorithm() == "sha256"
        assert ref.hash() == "deadbeef"

    def test_blob_from_content(self):
        gv = blob_from_content(b"hello", mime="text/plain", name="h.txt")
        assert gv.type == GType.BLOB
        ref = gv.as_blob()
        assert ref.bytes == 5
        assert ref.cid.startswith("sha256:")
        assert ref.name == "h.txt"

    def test_canonicalize_as_gvalue(self):
        gv = GValue.blob(BlobRef(cid="sha256:x", mime="image/png", bytes=42))
        assert canonicalize_loose(gv) == "@blob cid=sha256:x mime=image/png bytes=42"


class TestPoolRefIdValidation:
    @pytest.mark.parametrize("s", ["S1", "O1", "P42", "AA9", "S100"])
    def test_valid(self, s):
        assert is_pool_ref_id(s)

    @pytest.mark.parametrize("s", ["", "S", "s1", "1S", "SS", "S-1", "^S1"])
    def test_invalid(self, s):
        assert not is_pool_ref_id(s)


class TestPoolRef:
    def test_parse(self):
        ref = parse_pool_ref("^S1:0")
        assert ref.pool_id == "S1"
        assert ref.index == 0

    def test_emit_gvalue(self):
        gv = GValue.pool_ref("O3", 12)
        assert canonicalize_loose(gv) == "^O3:12"

    def test_missing_caret(self):
        with pytest.raises(ParsePoolError):
            parse_pool_ref("S1:0")

    def test_missing_colon(self):
        with pytest.raises(ParsePoolError):
            parse_pool_ref("^S1")

    def test_parser_recognizes_pool_ref(self):
        gv = parse("^S1:5")
        assert gv.type == GType.POOL_REF
        assert gv.as_pool_ref() == PoolRef("S1", 5)

    def test_parser_still_recognizes_plain_id(self):
        gv = parse("^hello:world")
        assert gv.type == GType.ID


class TestPool:
    def test_string_pool_add_get(self):
        pool = Pool("S1", PoolKind.STRING)
        idx = pool.add(g.str("hello"))
        assert idx == 0
        assert pool.get(0).as_str() == "hello"

    def test_object_pool_mixed_types(self):
        pool = Pool("O1", PoolKind.OBJECT)
        pool.add(g.map(field("a", g.int(1))))
        pool.add(g.int(42))
        assert len(pool) == 2

    def test_string_pool_rejects_non_string(self):
        pool = Pool("S1", PoolKind.STRING)
        with pytest.raises(ParsePoolError):
            pool.add(g.int(7))

    def test_registry_resolve(self):
        pool = Pool("S1", PoolKind.STRING)
        pool.add(g.str("a"))
        reg = PoolRegistry()
        reg.register(pool)
        resolved = reg.resolve(PoolRef("S1", 0))
        assert resolved.as_str() == "a"

    def test_registry_unknown_pool(self):
        with pytest.raises(ParsePoolError):
            PoolRegistry().resolve(PoolRef("X1", 0))


class TestPoolSerialization:
    def test_emit_string_pool(self):
        pool = Pool("S1", PoolKind.STRING)
        pool.add(g.str("hello"))
        pool.add(g.str("world"))
        assert emit_pool(pool) == "@pool.str id=S1 [hello world]"

    def test_parse_string_pool(self):
        pool = parse_pool("@pool.str id=S1 [hello world]")
        assert pool.id == "S1"
        assert pool.kind == PoolKind.STRING
        assert len(pool) == 2
        assert pool.get(0).as_str() == "hello"

    def test_round_trip_object_pool(self):
        pool = Pool("O1", PoolKind.OBJECT)
        pool.add(g.map(field("code", g.int(400)), field("msg", g.str("bad"))))
        text = emit_pool(pool)
        pool2 = parse_pool(text)
        assert pool2.kind == PoolKind.OBJECT
        assert len(pool2) == 1


class TestDocument:
    def test_parse_document_with_pool(self):
        text = "@pool.str id=S1 [alpha beta]\n\n[^S1:0 ^S1:1]"
        registry, value = parse_document(text)
        assert registry.get("S1") is not None
        assert value.type == GType.LIST
        resolved = resolve_pool_refs(value, registry)
        items = resolved.as_list()
        assert items[0].as_str() == "alpha"
        assert items[1].as_str() == "beta"

    def test_resolve_nested(self):
        pool = Pool("S1", PoolKind.STRING)
        pool.add(g.str("shared"))
        reg = PoolRegistry()
        reg.register(pool)
        value = g.map(field("a", GValue.pool_ref("S1", 0)))
        resolved = resolve_pool_refs(value, reg)
        assert resolved.get("a").as_str() == "shared"
