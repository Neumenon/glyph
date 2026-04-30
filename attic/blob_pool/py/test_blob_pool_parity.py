"""Cross-implementation parity tests for Blob + PoolRef.

Validates Python output against shared fixture vectors in
tests/fixtures/blob_pool_vectors.json.
"""

from __future__ import annotations

import json
import os

import pytest

from glyph import (
    BlobRef,
    GValue,
    Pool,
    PoolKind,
    canonicalize_loose,
    compute_cid,
    emit_blob,
    emit_pool,
    g,
    is_pool_ref_id,
)

FIXTURES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "fixtures", "blob_pool_vectors.json"
)


@pytest.fixture(scope="module")
def vectors():
    with open(FIXTURES_PATH) as f:
        return json.load(f)


class TestCidParity:
    def test_cid_vectors(self, vectors):
        for case in vectors["cid"]:
            assert compute_cid(case["input_utf8"].encode()) == case["expected"], case["desc"]


class TestEmitBlobParity:
    def test_emit_blob_vectors(self, vectors):
        for case in vectors["emit_blob"]:
            ref = BlobRef(
                cid=case["cid"],
                mime=case["mime"],
                bytes=case["bytes"],
                name=case.get("name", ""),
                caption=case.get("caption", ""),
            )
            assert emit_blob(ref) == case["expected"], case["desc"]


class TestPoolRefIdParity:
    def test_valid(self, vectors):
        for s in vectors["pool_ref_id_valid"]:
            assert is_pool_ref_id(s), f"expected valid: {s}"

    def test_invalid(self, vectors):
        for s in vectors["pool_ref_id_invalid"]:
            assert not is_pool_ref_id(s), f"expected invalid: {s}"


class TestCanonicalizePoolRefParity:
    def test_pool_ref_vectors(self, vectors):
        for case in vectors["canonicalize_pool_ref"]:
            gv = GValue.pool_ref(case["pool_id"], case["index"])
            assert canonicalize_loose(gv) == case["expected"], case["desc"]


class TestCanonicalizeBlobParity:
    def test_blob_vectors(self, vectors):
        for case in vectors["canonicalize_blob"]:
            gv = GValue.blob(BlobRef(
                cid=case["cid"],
                mime=case["mime"],
                bytes=case["bytes"],
            ))
            assert canonicalize_loose(gv) == case["expected"], case["desc"]


class TestEmitPoolParity:
    def test_emit_pool_vectors(self, vectors):
        for case in vectors["emit_pool"]:
            kind = PoolKind.STRING if case["kind"] == "str" else PoolKind.OBJECT
            pool = Pool(case["id"], kind)
            for entry in case["entries"]:
                pool.add(g.str(entry))
            assert emit_pool(pool) == case["expected"], case["desc"]
