/**
 * GLYPH Pool References
 *
 * Pool-based deduplication for strings and objects. Mirrors Go's
 * `glyph.Pool` / `glyph.PoolRegistry`. Pool refs use the
 * `^<PoolID>:<Index>` wire format; pool definitions use
 * `@pool.str id=S1 [...]` and `@pool.obj id=O1 [...]`.
 */

import { GValue, PoolRef } from './types';
import { canonicalizeLoose } from './loose';

export enum PoolKind {
  STRING = 'str',
  OBJECT = 'obj',
}

export class ParsePoolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ParsePoolError';
  }
}

export function isPoolRefId(ref: string): boolean {
  if (ref.length < 2) return false;
  const first = ref.charCodeAt(0);
  if (first < 65 || first > 90) return false; // A-Z
  let sawDigit = false;
  for (let i = 1; i < ref.length; i++) {
    const c = ref.charCodeAt(i);
    if (c >= 48 && c <= 57) {
      sawDigit = true;
    } else if (c < 65 || c > 90) {
      return false;
    }
  }
  return sawDigit;
}

export function parsePoolRef(input: string): PoolRef {
  if (!input.startsWith('^')) {
    throw new ParsePoolError('pool ref must start with ^');
  }
  const body = input.slice(1);
  const colon = body.indexOf(':');
  if (colon < 0) {
    throw new ParsePoolError('pool ref must contain colon');
  }
  const poolId = body.slice(0, colon);
  if (!isPoolRefId(poolId)) {
    throw new ParsePoolError(`invalid pool ID: ${poolId}`);
  }
  const idxStr = body.slice(colon + 1);
  const index = Number(idxStr);
  if (!Number.isFinite(index) || !Number.isInteger(index) || index < 0) {
    throw new ParsePoolError(`invalid pool index: ${idxStr}`);
  }
  return { poolId, index };
}

export class Pool {
  readonly id: string;
  readonly kind: PoolKind;
  readonly entries: GValue[] = [];

  constructor(id: string, kind: PoolKind) {
    this.id = id;
    this.kind = kind;
  }

  add(value: GValue): number {
    if (this.kind === PoolKind.STRING && value.type !== 'str') {
      throw new ParsePoolError(`pool ${this.id} is a string pool but got ${value.type}`);
    }
    this.entries.push(value);
    return this.entries.length - 1;
  }

  get(index: number): GValue {
    if (index < 0 || index >= this.entries.length) {
      throw new RangeError(`pool ${this.id}[${index}] out of bounds (len=${this.entries.length})`);
    }
    return this.entries[index];
  }

  get length(): number {
    return this.entries.length;
  }
}

export class PoolRegistry {
  private pools = new Map<string, Pool>();

  register(pool: Pool): void {
    this.pools.set(pool.id, pool);
  }

  get(poolId: string): Pool | undefined {
    return this.pools.get(poolId);
  }

  resolve(ref: PoolRef): GValue {
    const pool = this.pools.get(ref.poolId);
    if (pool === undefined) {
      throw new ParsePoolError(`pool not found: ${ref.poolId}`);
    }
    return pool.get(ref.index);
  }

  ids(): string[] {
    return [...this.pools.keys()].sort();
  }
}

export function emitPool(pool: Pool): string {
  const header = `@pool.${pool.kind} id=${pool.id}`;
  const body = pool.entries.map(v => canonicalizeLoose(v)).join(' ');
  return `${header} [${body}]`;
}

/**
 * Split a pool body like `hello world` or `{a=1} {b=2}` into top-level tokens,
 * respecting quotes and bracket/brace nesting.
 */
function tokenizePoolBody(inner: string): string[] {
  const tokens: string[] = [];
  const n = inner.length;
  let i = 0;
  while (i < n) {
    while (i < n && /\s/.test(inner[i])) i++;
    if (i >= n) break;

    const start = i;
    let depth = 0;
    let inStr = false;
    let esc = false;
    while (i < n) {
      const c = inner[i];
      if (esc) {
        esc = false;
      } else if (inStr) {
        if (c === '\\') esc = true;
        else if (c === '"') inStr = false;
      } else {
        if (c === '"') inStr = true;
        else if (c === '[' || c === '{' || c === '(') depth++;
        else if (c === ']' || c === '}' || c === ')') depth--;
        else if (depth === 0 && /\s/.test(c)) break;
      }
      i++;
    }
    tokens.push(inner.slice(start, i));
  }
  return tokens;
}

function parsePoolEntry(token: string): GValue {
  // Lazy import to break circular dependency with parse.ts
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { parseScalarValue } = require('./parse') as typeof import('./parse');
  return parseScalarValue(token);
}

export function parsePool(input: string): Pool {
  const s = input.trim();
  let rest: string;
  let kind: PoolKind;
  if (s.startsWith('@pool.str')) {
    kind = PoolKind.STRING;
    rest = s.slice('@pool.str'.length).replace(/^\s+/, '');
  } else if (s.startsWith('@pool.obj')) {
    kind = PoolKind.OBJECT;
    rest = s.slice('@pool.obj'.length).replace(/^\s+/, '');
  } else {
    throw new ParsePoolError('pool must start with @pool.str or @pool.obj');
  }

  if (!rest.startsWith('id=')) {
    throw new ParsePoolError('pool missing id= field');
  }
  rest = rest.slice('id='.length);

  let i = 0;
  while (i < rest.length && !/\s/.test(rest[i]) && rest[i] !== '[') i++;
  const poolId = rest.slice(0, i);
  if (!isPoolRefId(poolId)) {
    throw new ParsePoolError(`invalid pool ID: ${poolId}`);
  }

  const body = rest.slice(i).replace(/^\s+/, '');
  if (!body.startsWith('[') || !body.endsWith(']')) {
    throw new ParsePoolError('pool body must be bracketed list');
  }

  const inner = body.slice(1, -1).trim();
  const pool = new Pool(poolId, kind);
  if (!inner) return pool;

  for (const token of tokenizePoolBody(inner)) {
    const entry = parsePoolEntry(token);
    if (kind === PoolKind.STRING && entry.type !== 'str') {
      throw new ParsePoolError(`@pool.str ${poolId} entry is not a string: ${entry.type}`);
    }
    pool.entries.push(entry);
  }
  return pool;
}

/**
 * Split a document into leading @pool.* definitions and the remaining value.
 */
export function splitDocument(input: string): { pools: string[]; value: string } {
  let text = input.replace(/^\s+/, '');
  const pools: string[] = [];
  while (text.startsWith('@pool.')) {
    let depth = 0;
    let inStr = false;
    let esc = false;
    let i = 0;
    const n = text.length;
    while (i < n) {
      const c = text[i];
      if (esc) {
        esc = false;
      } else if (inStr) {
        if (c === '\\') esc = true;
        else if (c === '"') inStr = false;
      } else {
        if (c === '"') inStr = true;
        else if (c === '[') depth++;
        else if (c === ']') {
          depth--;
          if (depth === 0) {
            i++;
            break;
          }
        }
      }
      i++;
    }
    if (depth !== 0) {
      throw new ParsePoolError('unbalanced brackets in pool definition');
    }
    pools.push(text.slice(0, i));
    text = text.slice(i).replace(/^\s+/, '');
  }
  return { pools, value: text };
}

export interface ParsedDocument {
  registry: PoolRegistry;
  value: GValue;
}

export function parseDocument(input: string): ParsedDocument {
  const { pools, value } = splitDocument(input);
  const registry = new PoolRegistry();
  for (const block of pools) {
    registry.register(parsePool(block));
  }
  if (!value) {
    throw new ParsePoolError('document has no value');
  }
  const parsed = parsePoolEntry(value);
  return { registry, value: parsed };
}

export function resolvePoolRefs(value: GValue, registry: PoolRegistry): GValue {
  switch (value.type) {
    case 'poolRef':
      return registry.resolve(value.asPoolRef()).clone();
    case 'list':
      return GValue.list(...value.asList().map(v => resolvePoolRefs(v, registry)));
    case 'map':
      return GValue.map(
        ...value.asMap().map(e => ({ key: e.key, value: resolvePoolRefs(e.value, registry) }))
      );
    case 'struct': {
      const sv = value.asStruct();
      return GValue.struct(
        sv.typeName,
        ...sv.fields.map(f => ({ key: f.key, value: resolvePoolRefs(f.value, registry) }))
      );
    }
    case 'sum': {
      const sm = value.asSum();
      const inner = sm.value ? resolvePoolRefs(sm.value, registry) : null;
      return GValue.sum(sm.tag, inner);
    }
    default:
      return value.clone();
  }
}
