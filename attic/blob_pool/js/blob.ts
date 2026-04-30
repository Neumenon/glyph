/**
 * GLYPH Blob References
 *
 * Content-addressed blob references with canonical
 * `@blob cid=... mime=... bytes=N` wire format. Mirrors the Go
 * `glyph.BlobRef` and Python `glyph.blob` semantics.
 */

import { createHash } from 'crypto';

import { BlobRef, GValue } from './types';
import { canonString } from './codec_primitives';

export class ParseBlobError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ParseBlobError';
  }
}

export function computeCid(content: Uint8Array | string): string {
  const buf = typeof content === 'string' ? Buffer.from(content, 'utf8') : Buffer.from(content);
  return 'sha256:' + createHash('sha256').update(buf).digest('hex');
}

export function blobFromContent(
  content: Uint8Array | string,
  mime: string,
  name = '',
  caption = ''
): GValue {
  const bytes = typeof content === 'string' ? Buffer.byteLength(content, 'utf8') : content.length;
  const ref: BlobRef = {
    cid: computeCid(content),
    mime,
    bytes,
  };
  if (name) ref.name = name;
  if (caption) ref.caption = caption;
  return GValue.blob(ref);
}

export function blobAlgorithm(ref: BlobRef): string {
  const colon = ref.cid.indexOf(':');
  return colon < 0 ? '' : ref.cid.slice(0, colon);
}

export function blobHash(ref: BlobRef): string {
  const colon = ref.cid.indexOf(':');
  return colon < 0 ? ref.cid : ref.cid.slice(colon + 1);
}

export function emitBlob(ref: BlobRef): string {
  const parts = [
    '@blob',
    `cid=${ref.cid}`,
    `mime=${ref.mime}`,
    `bytes=${ref.bytes}`,
  ];
  if (ref.name) parts.push(`name=${canonString(ref.name)}`);
  if (ref.caption) parts.push(`caption=${canonString(ref.caption)}`);
  if (ref.preview) parts.push(`preview=${canonString(ref.preview)}`);
  return parts.join(' ');
}

export function parseBlobRef(input: string): BlobRef {
  let s = input.trim();
  if (!s.startsWith('@blob')) {
    throw new ParseBlobError('blob ref must start with @blob');
  }
  s = s.slice('@blob'.length).replace(/^\s+/, '');

  const fields: Record<string, string> = {};
  let i = 0;
  const n = s.length;
  while (i < n) {
    while (i < n && /\s/.test(s[i])) i++;
    if (i >= n) break;

    const eq = s.indexOf('=', i);
    if (eq < 0) {
      throw new ParseBlobError(`missing = in blob field at pos ${i}`);
    }
    const key = s.slice(i, eq);
    i = eq + 1;

    if (i < n && s[i] === '"') {
      i++;
      let buf = '';
      while (i < n && s[i] !== '"') {
        if (s[i] === '\\' && i + 1 < n) {
          const nxt = s[i + 1];
          if (nxt === 'n') buf += '\n';
          else if (nxt === 'r') buf += '\r';
          else if (nxt === 't') buf += '\t';
          else if (nxt === '\\') buf += '\\';
          else if (nxt === '"') buf += '"';
          else buf += nxt;
          i += 2;
        } else {
          buf += s[i];
          i++;
        }
      }
      if (i >= n) {
        throw new ParseBlobError(`unterminated quote for field ${key}`);
      }
      i++;
      fields[key] = buf;
    } else {
      const start = i;
      while (i < n && !/\s/.test(s[i])) i++;
      fields[key] = s.slice(start, i);
    }
  }

  if (!('cid' in fields)) throw new ParseBlobError('blob ref missing required field: cid');
  if (!('mime' in fields)) throw new ParseBlobError('blob ref missing required field: mime');
  if (!('bytes' in fields)) throw new ParseBlobError('blob ref missing required field: bytes');

  const bytesVal = Number(fields.bytes);
  if (!Number.isFinite(bytesVal) || !Number.isInteger(bytesVal)) {
    throw new ParseBlobError(`invalid bytes field: ${fields.bytes}`);
  }

  const ref: BlobRef = {
    cid: fields.cid,
    mime: fields.mime,
    bytes: bytesVal,
  };
  if (fields.name) ref.name = fields.name;
  if (fields.caption) ref.caption = fields.caption;
  if (fields.preview) ref.preview = fields.preview;
  return ref;
}

export class MemoryBlobRegistry {
  private store = new Map<string, Uint8Array>();

  put(cid: string, content: Uint8Array): void {
    this.store.set(cid, content);
  }

  get(cid: string): Uint8Array | undefined {
    return this.store.get(cid);
  }

  has(cid: string): boolean {
    return this.store.has(cid);
  }
}
