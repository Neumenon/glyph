/**
 * Canonical JSON profile glyph-canon-json-1.1.0 (see SPEC-CANON.md).
 *
 * The only byte form GLYPH hashes. fingerprint, the patch base and the GS1
 * state hash are all sha256(canonJson(v)). GLYPH text is a renderer and is
 * never hashed.
 */

import { GValue, MapEntry } from './types';
import {
  canonFloat,
  canonTime,
  bytesToBase64,
  fromJsonLoose,
  TENSOR_DTYPE_BITS,
  tensorRefValue,
  checkTensorPadding,
} from './loose';

export const CANON_MAX_DEPTH = 1000;

/**
 * Value cannot be canonicalized: int outside ±(2^53-1), non-finite float,
 * duplicate object key, or nesting deeper than CANON_MAX_DEPTH.
 */
export class CanonError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CanonError';
  }
}

/** Canonical JSON text of v (SPEC-CANON.md §1-§3). */
export function canonJson(v: GValue): string {
  return canon(v, 0);
}

/**
 * The one digest: 64 lowercase hex of sha256(canonJson(v)) (SPEC-CANON.md §5).
 * Node-only (uses the crypto module); in a browser hash canonJson(v) with
 * crypto.subtle.
 */
export function fingerprint(v: GValue): string {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { createHash } = require('crypto');
  return createHash('sha256').update(canonJson(v), 'utf8').digest('hex');
}

/**
 * {"$tensor":{dtype,shape,sha256}} for raw element bytes (SPEC-CANON.md §4).
 * Only sha256(data) enters the value. Throws for an unknown dtype, a negative
 * dim, data that is not the packed size dtype and shape imply
 * (little-endian, row-major, sub-byte dtypes LSB-first), or non-zero padding
 * bits in the unused high bits of the last byte. Node-only (crypto).
 */
export function tensorRef(dtype: string, shape: number[], data: Uint8Array): GValue {
  if (!Object.prototype.hasOwnProperty.call(TENSOR_DTYPE_BITS, dtype)) {
    throw new CanonError(`unknown tensor dtype ${JSON.stringify(dtype)}`);
  }
  if (!shape.every((d) => Number.isInteger(d) && d >= 0)) {
    throw new CanonError(`tensor shape must be non-negative ints: ${JSON.stringify(shape)}`);
  }
  const n = shape.reduce((a, d) => a * d, 1);
  const want = Math.ceil((n * TENSOR_DTYPE_BITS[dtype]) / 8);
  if (data.length !== want) {
    throw new CanonError(`tensor data is ${data.length} bytes; dtype ${dtype} shape [${shape}] packs to ${want}`);
  }
  checkTensorPadding(dtype, shape, data);
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { createHash } = require('crypto');
  return tensorRefValue(dtype, shape, createHash('sha256').update(data).digest('hex'));
}

/**
 * True iff b is exactly the canonical JSON of the value it encodes.
 * Receivers at trust boundaries (patch ingest, GS1 state frames) reject bytes
 * that fail this: "exactly one valid encoding" with a stdlib parser.
 */
export function isCanonical(b: Uint8Array | string): boolean {
  try {
    const text = typeof b === 'string' ? b : new TextDecoder('utf-8', { fatal: true }).decode(b);
    return canonJson(fromJsonLoose(JSON.parse(text))) === text;
  } catch {
    return false;
  }
}

function quote(s: string): string {
  // RFC 8785 §3.2.2.2 escaping == JSON.stringify.
  return JSON.stringify(s);
}

function canon(v: GValue, depth: number): string {
  switch (v.type) {
    case 'null':
      return 'null';
    case 'bool':
      return v.asBool() ? 'true' : 'false';
    case 'int': {
      const n = v.asInt();
      if (!Number.isSafeInteger(n)) throw new CanonError(`integer outside ±(2^53-1): ${n}`);
      return String(n);
    }
    case 'float': {
      const f = v.asFloat();
      if (!Number.isFinite(f)) throw new CanonError('non-finite float');
      if (Number.isSafeInteger(f)) return String(f); // 1.0 -> "1", -0 -> "0"
      return canonFloat(f);
    }
    case 'str':
      return quote(v.asStr());
    case 'bytes':
      return `{"$bytes":${quote(bytesToBase64(v.asBytes()))}}`;
    case 'time':
      return `{"$time":"${canonTime(v.asTime())}"}`;
    case 'id': {
      const r = v.asId();
      return `{"$id":[${quote(r.prefix)},${quote(r.value)}]}`;
    }
    case 'list':
      checkDepth(depth);
      return '[' + v.asList().map((x) => canon(x, depth + 1)).join(',') + ']';
    case 'map':
      return object(v.asMap(), depth);
    case 'struct':
      return object(v.asStruct().fields, depth);
    case 'sum': {
      checkDepth(depth);
      const s = v.asSum();
      return `{${quote(s.tag)}:${s.value === null ? 'null' : canon(s.value, depth + 1)}}`;
    }
  }
  throw new CanonError(`unsupported type ${(v as GValue).type}`);
}

function object(entries: MapEntry[], depth: number): string {
  checkDepth(depth);
  const sorted = entries.slice().sort((a, b) => compareCodePoints(a.key, b.key));
  const parts: string[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i].key === sorted[i - 1].key) {
      throw new CanonError(`duplicate key ${quote(sorted[i].key)}`);
    }
    parts.push(quote(sorted[i].key) + ':' + canon(sorted[i].value, depth + 1));
  }
  return '{' + parts.join(',') + '}';
}

/**
 * Code point order (== UTF-8 byte order, what Go and Python sort by). Plain
 * string comparison would sort by UTF-16 unit, putting non-BMP keys
 * (surrogates D800-DFFF) below E000-FFFF.
 */
export function compareCodePoints(a: string, b: string): number {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    let x = a.charCodeAt(i);
    let y = b.charCodeAt(i);
    if (x !== y) {
      if (x >= 0xd800 && x <= 0xdfff) x += 0x2800;
      if (y >= 0xd800 && y <= 0xdfff) y += 0x2800;
      return x - y;
    }
  }
  return a.length - b.length;
}

function checkDepth(depth: number): void {
  if (depth >= CANON_MAX_DEPTH) throw new CanonError(`nesting depth exceeds ${CANON_MAX_DEPTH}`);
}
