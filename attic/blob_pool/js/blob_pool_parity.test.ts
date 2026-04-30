/**
 * Cross-implementation parity tests for Blob + PoolRef.
 *
 * Validates JS/TS output against shared fixture vectors in
 * tests/fixtures/blob_pool_vectors.json.
 */

import * as fs from 'fs';
import * as path from 'path';
import {
  BlobRef,
  GValue,
  Pool,
  PoolKind,
  canonicalizeLoose,
  computeCid,
  emitBlob,
  emitPool,
  g,
  isPoolRefId,
} from './index';

const FIXTURES_PATH = path.join(__dirname, '..', '..', 'tests', 'fixtures', 'blob_pool_vectors.json');
const vectors = JSON.parse(fs.readFileSync(FIXTURES_PATH, 'utf8'));

describe('CID parity', () => {
  for (const c of vectors.cid) {
    test(c.desc, () => {
      expect(computeCid(c.input_utf8)).toBe(c.expected);
    });
  }
});

describe('emitBlob parity', () => {
  for (const c of vectors.emit_blob) {
    test(c.desc, () => {
      const ref: BlobRef = {
        cid: c.cid,
        mime: c.mime,
        bytes: c.bytes,
      };
      if (c.name) ref.name = c.name;
      if (c.caption) ref.caption = c.caption;
      expect(emitBlob(ref)).toBe(c.expected);
    });
  }
});

describe('isPoolRefId parity', () => {
  test('valid IDs', () => {
    for (const s of vectors.pool_ref_id_valid) {
      expect(isPoolRefId(s)).toBe(true);
    }
  });

  test('invalid IDs', () => {
    for (const s of vectors.pool_ref_id_invalid) {
      expect(isPoolRefId(s)).toBe(false);
    }
  });
});

describe('canonicalize poolRef parity', () => {
  for (const c of vectors.canonicalize_pool_ref) {
    test(c.desc, () => {
      const gv = GValue.poolRef(c.pool_id, c.index);
      expect(canonicalizeLoose(gv)).toBe(c.expected);
    });
  }
});

describe('canonicalize blob parity', () => {
  for (const c of vectors.canonicalize_blob) {
    test(c.desc, () => {
      const gv = GValue.blob({ cid: c.cid, mime: c.mime, bytes: c.bytes });
      expect(canonicalizeLoose(gv)).toBe(c.expected);
    });
  }
});

describe('emitPool parity', () => {
  for (const c of vectors.emit_pool) {
    test(c.desc, () => {
      const kind = c.kind === 'str' ? PoolKind.STRING : PoolKind.OBJECT;
      const pool = new Pool(c.id, kind);
      for (const entry of c.entries) {
        pool.add(g.str(entry));
      }
      expect(emitPool(pool)).toBe(c.expected);
    });
  }
});
