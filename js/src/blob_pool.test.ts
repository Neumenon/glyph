/**
 * Tests for Blob and Pool reference support (GLYPH MVP parity port).
 */

import {
  BlobRef,
  GValue,
  Pool,
  PoolKind,
  PoolRegistry,
  blobFromContent,
  blobAlgorithm,
  blobHash,
  canonicalizeLoose,
  computeCid,
  emitBlob,
  emitPool,
  g,
  isPoolRefId,
  parseBlobRef,
  parsePool,
  parsePoolRef,
  parseDocument,
  resolvePoolRefs,
  ParseBlobError,
  ParsePoolError,
  field,
} from './index';
import { parseScalarValue } from './parse';

describe('computeCid', () => {
  test('sha256 hex of "hello"', () => {
    expect(computeCid('hello')).toBe(
      'sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    );
  });

  test('sha256 hex of empty', () => {
    expect(computeCid('')).toBe(
      'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    );
  });
});

describe('BlobRef round-trip', () => {
  test('minimum fields', () => {
    const ref: BlobRef = { cid: 'sha256:abc', mime: 'image/png', bytes: 1024 };
    const text = emitBlob(ref);
    expect(text).toBe('@blob cid=sha256:abc mime=image/png bytes=1024');
    const parsed = parseBlobRef(text);
    expect(parsed).toEqual(ref);
  });

  test('optional fields', () => {
    const ref: BlobRef = {
      cid: 'sha256:abc',
      mime: 'image/png',
      bytes: 1024,
      name: 'cat.png',
      caption: 'A very fluffy cat',
    };
    const text = emitBlob(ref);
    expect(text).toContain('name=cat.png');
    expect(text).toContain('caption="A very fluffy cat"');
    const parsed = parseBlobRef(text);
    expect(parsed).toEqual(ref);
  });

  test('escape sequences in caption', () => {
    const ref: BlobRef = {
      cid: 'sha256:a',
      mime: 'text/plain',
      bytes: 1,
      caption: 'quote "x" here',
    };
    const text = emitBlob(ref);
    const parsed = parseBlobRef(text);
    expect(parsed.caption).toBe('quote "x" here');
  });

  test('missing cid throws', () => {
    expect(() => parseBlobRef('@blob mime=x bytes=1')).toThrow(ParseBlobError);
  });

  test('missing mime throws', () => {
    expect(() => parseBlobRef('@blob cid=x bytes=1')).toThrow(ParseBlobError);
  });

  test('missing bytes throws', () => {
    expect(() => parseBlobRef('@blob cid=x mime=y')).toThrow(ParseBlobError);
  });

  test('bad prefix throws', () => {
    expect(() => parseBlobRef('cid=x mime=y bytes=1')).toThrow(ParseBlobError);
  });

  test('algorithm and hash helpers', () => {
    const ref: BlobRef = { cid: 'sha256:deadbeef', mime: 'x', bytes: 0 };
    expect(blobAlgorithm(ref)).toBe('sha256');
    expect(blobHash(ref)).toBe('deadbeef');
  });

  test('blobFromContent computes cid and bytes', () => {
    const gv = blobFromContent('hello', 'text/plain', 'h.txt');
    expect(gv.type).toBe('blob');
    const ref = gv.asBlob();
    expect(ref.bytes).toBe(5);
    expect(ref.cid.startsWith('sha256:')).toBe(true);
    expect(ref.name).toBe('h.txt');
  });

  test('canonicalizeLoose emits blob wire format', () => {
    const gv = GValue.blob({ cid: 'sha256:x', mime: 'image/png', bytes: 42 });
    expect(canonicalizeLoose(gv)).toBe('@blob cid=sha256:x mime=image/png bytes=42');
  });
});

describe('isPoolRefId', () => {
  test.each(['S1', 'O1', 'P42', 'AA9', 'S100'])('valid: %s', (s) => {
    expect(isPoolRefId(s)).toBe(true);
  });

  test.each(['', 'S', 's1', '1S', 'SS', 'S-1', '^S1'])('invalid: %s', (s) => {
    expect(isPoolRefId(s)).toBe(false);
  });
});

describe('PoolRef', () => {
  test('parse ^S1:0', () => {
    const ref = parsePoolRef('^S1:0');
    expect(ref.poolId).toBe('S1');
    expect(ref.index).toBe(0);
  });

  test('GValue.poolRef canonicalizes to ^O3:12', () => {
    const gv = GValue.poolRef('O3', 12);
    expect(canonicalizeLoose(gv)).toBe('^O3:12');
  });

  test('missing caret throws', () => {
    expect(() => parsePoolRef('S1:0')).toThrow(ParsePoolError);
  });

  test('missing colon throws', () => {
    expect(() => parsePoolRef('^S1')).toThrow(ParsePoolError);
  });

  test('parser recognizes pool ref', () => {
    const gv = parseScalarValue('^S1:5');
    expect(gv.type).toBe('poolRef');
    expect(gv.asPoolRef()).toEqual({ poolId: 'S1', index: 5 });
  });

  test('parser still recognizes plain id', () => {
    const gv = parseScalarValue('^hello:world');
    expect(gv.type).toBe('id');
  });
});

describe('Pool', () => {
  test('string pool add/get', () => {
    const pool = new Pool('S1', PoolKind.STRING);
    const idx = pool.add(g.str('hello'));
    expect(idx).toBe(0);
    expect(pool.get(0).asStr()).toBe('hello');
  });

  test('object pool accepts mixed types', () => {
    const pool = new Pool('O1', PoolKind.OBJECT);
    pool.add(g.map(field('a', g.int(1))));
    pool.add(g.int(42));
    expect(pool.length).toBe(2);
  });

  test('string pool rejects non-string', () => {
    const pool = new Pool('S1', PoolKind.STRING);
    expect(() => pool.add(g.int(7))).toThrow(ParsePoolError);
  });

  test('registry resolve', () => {
    const pool = new Pool('S1', PoolKind.STRING);
    pool.add(g.str('a'));
    const reg = new PoolRegistry();
    reg.register(pool);
    const resolved = reg.resolve({ poolId: 'S1', index: 0 });
    expect(resolved.asStr()).toBe('a');
  });

  test('registry unknown pool throws', () => {
    expect(() => new PoolRegistry().resolve({ poolId: 'X1', index: 0 })).toThrow(
      ParsePoolError
    );
  });
});

describe('Pool serialization', () => {
  test('emit string pool', () => {
    const pool = new Pool('S1', PoolKind.STRING);
    pool.add(g.str('hello'));
    pool.add(g.str('world'));
    expect(emitPool(pool)).toBe('@pool.str id=S1 [hello world]');
  });

  test('parse string pool', () => {
    const pool = parsePool('@pool.str id=S1 [hello world]');
    expect(pool.id).toBe('S1');
    expect(pool.kind).toBe(PoolKind.STRING);
    expect(pool.length).toBe(2);
    expect(pool.get(0).asStr()).toBe('hello');
  });

  test('round-trip object pool', () => {
    const pool = new Pool('O1', PoolKind.OBJECT);
    pool.add(g.map(field('code', g.int(400)), field('msg', g.str('bad'))));
    const text = emitPool(pool);
    const pool2 = parsePool(text);
    expect(pool2.kind).toBe(PoolKind.OBJECT);
    expect(pool2.length).toBe(1);
  });
});

describe('Document parsing', () => {
  test('parse document with pool', () => {
    const text = '@pool.str id=S1 [alpha beta]\n\n[^S1:0 ^S1:1]';
    const { registry, value } = parseDocument(text);
    expect(registry.get('S1')).toBeDefined();
    expect(value.type).toBe('list');
    const resolved = resolvePoolRefs(value, registry);
    const items = resolved.asList();
    expect(items[0].asStr()).toBe('alpha');
    expect(items[1].asStr()).toBe('beta');
  });

  test('resolve nested pool refs', () => {
    const pool = new Pool('S1', PoolKind.STRING);
    pool.add(g.str('shared'));
    const reg = new PoolRegistry();
    reg.register(pool);
    const value = g.map(field('a', GValue.poolRef('S1', 0)));
    const resolved = resolvePoolRefs(value, reg);
    expect(resolved.get('a')!.asStr()).toBe('shared');
  });
});
