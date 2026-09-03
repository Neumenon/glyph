/**
 * GLYPH v2 Patch System
 * 
 * Implements patch emit, parse, and apply for cross-implementation parity with Go.
 */

import { GValue, RefID, MapEntry } from './types';
import { Schema } from './schema';
import { canonJson, fingerprint, compareCodePoints } from './canon';
import { fromJsonLoose } from './loose';

// ============================================================
// Patch Types (Match Go's emit_patch.go)
// ============================================================

export type PatchOpKind = '=' | '+' | '-' | '~';

export type PathSegKind = 'field' | 'listIdx' | 'mapKey';

export interface PathSeg {
  kind: PathSegKind;
  field?: string;   // For field: canonical field name
  fid?: number;     // For field: resolved FID
  listIdx?: number; // For listIdx: index
  mapKey?: string;  // For mapKey: key
}

export interface PatchOp {
  op: PatchOpKind;
  path: PathSeg[];
  value?: GValue;    // For =, +, ~
  index?: number;    // For +: insert at index (-1 = append)
}

export interface Patch {
  target: RefID;
  schemaId?: string;
  targetType?: string;
  baseFingerprint?: string;  // v2.4.0: Base state fingerprint for validation
  ops: PatchOp[];
}

// ============================================================
// Path Segment Constructors
// ============================================================

export function fieldSeg(name: string, fid?: number): PathSeg {
  return { kind: 'field', field: name, fid };
}

export function listIdxSeg(idx: number): PathSeg {
  return { kind: 'listIdx', listIdx: parseNonNegativeSafeInt(String(idx), 'list index') };
}

export function mapKeySeg(key: string): PathSeg {
  return { kind: 'mapKey', mapKey: key };
}

function parseNonNegativeSafeInt(raw: string, field: string): number {
  if (!/^\d+$/.test(raw)) {
    throw new Error(`invalid ${field}: ${raw}`);
  }
  const value = Number(raw);
  if (!Number.isSafeInteger(value)) {
    throw new Error(`${field} out of range: ${raw}`);
  }
  return value;
}

function parseQuotedPathString(path: string, start: number): { value: string; next: number } {
  if (path[start] !== '"') {
    throw new Error(`expected quoted string at pos ${start}`);
  }

  let value = '';
  let escaped = false;
  let i = start + 1;

  while (i < path.length) {
    const c = path[i];
    if (escaped) {
      value += c;
      escaped = false;
      i++;
      continue;
    }
    if (c === '\\') {
      escaped = true;
      i++;
      continue;
    }
    if (c === '"') {
      return { value, next: i + 1 };
    }
    value += c;
    i++;
  }

  throw new Error(`unterminated quoted path segment at pos ${start}`);
}

// ============================================================
// Path Parsing
// ============================================================

/**
 * Parse a path string into segments.
 * Supports: .fieldName, .#fid, [N], ["key"]
 */
export function parsePathToSegs(path: string): PathSeg[] {
  path = path.trim();
  if (!path) return [];

  const segs: PathSeg[] = [];
  let i = path.startsWith('.') ? 1 : 0;
  if (i >= path.length) {
    throw new Error('path cannot end with dot');
  }

  while (i < path.length) {
    const c = path[i];

    if (c === '[') {
      i++;
      if (i >= path.length) {
        throw new Error(`unterminated path segment at pos ${i - 1}`);
      }

      if (path[i] === '"') {
        const parsed = parseQuotedPathString(path, i);
        i = parsed.next;
        if (path[i] !== ']') {
          throw new Error(`unterminated map key segment at pos ${i}`);
        }
        segs.push(mapKeySeg(parsed.value));
        i++;
      } else {
        const end = path.indexOf(']', i);
        if (end < 0) {
          throw new Error(`unterminated list index at pos ${i - 1}`);
        }
        const inner = path.slice(i, end);
        segs.push(listIdxSeg(parseNonNegativeSafeInt(inner, 'list index')));
        i = end + 1;
      }
    } else if (c === '#') {
      const start = i + 1;
      let j = start;
      while (j < path.length && path[j] >= '0' && path[j] <= '9') {
        j++;
      }
      if (j === start) {
        throw new Error(`missing field id at pos ${i}`);
      }
      segs.push({ kind: 'field', fid: parseNonNegativeSafeInt(path.slice(start, j), 'field id') });
      i = j;
    } else {
      let field: string;
      if (c === '"') {
        const parsed = parseQuotedPathString(path, i);
        field = parsed.value;
        i = parsed.next;
      } else {
        let j = i;
        while (j < path.length && path[j] !== '.' && path[j] !== '[' && path[j] !== ']') {
          j++;
        }
        if (j === i) {
          throw new Error(`empty path segment at pos ${i}`);
        }
        field = path.slice(i, j);
        i = j;
      }
      if (!field) {
        throw new Error(`empty field name at pos ${i}`);
      }
      segs.push(fieldSeg(field));
    }

    if (i >= path.length) {
      break;
    }
    if (path[i] === '.') {
      i++;
      if (i >= path.length) {
        throw new Error('path cannot end with dot');
      }
      continue;
    }
    if (path[i] === '[') {
      continue;
    }
    throw new Error(`unexpected character '${path[i]}' in path`);
  }

  return segs;
}

// ============================================================
// Patch Builder
// ============================================================

export class PatchBuilder {
  private patch: Patch;
  private schema?: Schema;

  constructor(target: RefID) {
    this.patch = {
      target,
      ops: [],
    };
  }

  withSchema(schema: Schema): this {
    this.schema = schema;
    this.patch.schemaId = schema.hash;
    return this;
  }

  withSchemaId(id: string): this {
    this.patch.schemaId = id;
    return this;
  }

  withTargetType(typeName: string): this {
    this.patch.targetType = typeName;
    return this;
  }

  /**
   * Set the base state fingerprint for validation: fingerprint(base),
   * 64 hex of sha256(canonJson(base)) (SPEC-CANON.md §5).
   */
  withBaseFingerprint(fingerprint: string): this {
    this.patch.baseFingerprint = fingerprint;
    return this;
  }

  /** Set the base fingerprint to fingerprint(base) (SPEC-CANON.md §5). */
  withBaseValue(base: GValue): this {
    this.patch.baseFingerprint = computeBaseFingerprint(base);
    return this;
  }

  set(path: string, value: GValue): this {
    this.patch.ops.push({
      op: '=',
      path: parsePathToSegs(path),
      value,
    });
    return this;
  }

  setWithSegs(path: PathSeg[], value: GValue): this {
    this.patch.ops.push({
      op: '=',
      path,
      value,
    });
    return this;
  }

  append(path: string, value: GValue): this {
    this.patch.ops.push({
      op: '+',
      path: parsePathToSegs(path),
      value,
      index: -1,
    });
    return this;
  }

  delete(path: string): this {
    this.patch.ops.push({
      op: '-',
      path: parsePathToSegs(path),
    });
    return this;
  }

  delta(path: string, amount: number): this {
    this.patch.ops.push({
      op: '~',
      path: parsePathToSegs(path),
      value: GValue.float(amount),
    });
    return this;
  }

  insertAt(path: string, index: number, value: GValue): this {
    this.patch.ops.push({
      op: '+',
      path: parsePathToSegs(path),
      value,
      index: parseNonNegativeSafeInt(String(index), 'patch index'),
    });
    return this;
  }

  build(): Patch {
    return this.patch;
  }
}

// ============================================================
// Wire form (SPEC-CANON.md §7)
//
// {"glyph_patch":1,"ops":[op,…],"base"?,"schema"?,"target"?,"type"?}
// op := {"op":"="|"+"|"-"|"~","path":[seg,…],"value"?,"index"?}
// seg := string (struct field or map key) | non-negative int (list index)
// ============================================================

export const PATCH_WIRE_VERSION = 1;

const HEADER_KEYS = new Set(['glyph_patch', 'ops', 'base', 'schema', 'target', 'type']);
const OP_KEYS = new Set(['op', 'path', 'value', 'index']);
const OP_KINDS: PatchOpKind[] = ['=', '+', '-', '~'];

function pathGv(path: PathSeg[]): GValue {
  return GValue.list(...path.map(s => {
    if (s.kind === 'listIdx') return GValue.int(s.listIdx!);
    const key = s.kind === 'field' ? s.field : s.mapKey;
    if (key === undefined) throw new Error(`${s.kind} segment has no name`);
    return GValue.str(key);
  }));
}

function opGv(op: PatchOp): GValue {
  const entries: MapEntry[] = [
    { key: 'op', value: GValue.str(op.op) },
    { key: 'path', value: pathGv(op.path) },
  ];
  if (op.op === '~') {
    entries.push({ key: 'value', value: GValue.float(op.value ? op.value.asNumber() : 0) });
  } else if (op.op !== '-') {
    entries.push({ key: 'value', value: op.value ?? GValue.null() });
  }
  if (op.op === '+' && op.index !== undefined && op.index >= 0) {
    entries.push({ key: 'index', value: GValue.int(op.index) });
  }
  return GValue.map(...entries);
}

/**
 * Canonical JSON wire form — the inverse of parsePatch. Ops are sorted by
 * (canonJson(path), op) so a patch diffed in any language emits the same
 * bytes; empty header fields are omitted.
 */
export function emitPatch(patch: Patch): string {
  const ops = patch.ops
    .map(op => ({ op, key: canonJson(pathGv(op.path)) }))
    .sort((a, b) => compareCodePoints(a.key, b.key) || compareCodePoints(a.op.op, b.op.op))
    .map(x => opGv(x.op));
  const entries: MapEntry[] = [
    { key: 'glyph_patch', value: GValue.int(PATCH_WIRE_VERSION) },
    { key: 'ops', value: GValue.list(...ops) },
  ];
  const t = patch.target;
  const header: [string, string | undefined][] = [
    ['base', patch.baseFingerprint],
    ['schema', patch.schemaId],
    ['target', t.prefix ? `${t.prefix}:${t.value}` : t.value],
    ['type', patch.targetType],
  ];
  for (const [key, v] of header) {
    if (v) entries.push({ key, value: GValue.str(v) });
  }
  return canonJson(GValue.map(...entries));
}

function isInt(v: unknown): v is number {
  return typeof v === 'number' && Number.isInteger(v);
}

/**
 * Parse the JSON wire form. Accepts any JSON spelling (whitespace, key
 * order); canonical bytes are the GS1 cursor's job (SPEC-CANON.md §5).
 * Unknown keys at either level are errors.
 */
export function parsePatch(input: string | Uint8Array): Patch {
  const text = typeof input === 'string' ? input : new TextDecoder('utf-8', { fatal: true }).decode(input);
  let doc: unknown;
  try {
    doc = JSON.parse(text);
  } catch (e) {
    throw new Error(`patch is not JSON: ${(e as Error).message}`);
  }
  if (typeof doc !== 'object' || doc === null || Array.isArray(doc)) {
    throw new Error('patch must be a JSON object');
  }
  const d = doc as Record<string, unknown>;
  const unknown = Object.keys(d).filter(k => !HEADER_KEYS.has(k));
  if (unknown.length) throw new Error(`unknown patch key(s): ${unknown.join(', ')}`);
  if (d.glyph_patch !== PATCH_WIRE_VERSION) {
    throw new Error(`patch must carry glyph_patch: ${PATCH_WIRE_VERSION}`);
  }
  if (!Array.isArray(d.ops)) throw new Error('patch ops must be a list');
  for (const key of ['base', 'schema', 'target', 'type']) {
    if (key in d && typeof d[key] !== 'string') throw new Error(`patch ${key} must be a string`);
  }

  const target = (d.target as string | undefined) ?? '';
  const colon = target.indexOf(':');
  const patch: Patch = {
    target: colon < 0 ? { prefix: '', value: target } : { prefix: target.slice(0, colon), value: target.slice(colon + 1) },
    ops: d.ops.map(parseOp),
  };
  if (typeof d.schema === 'string') patch.schemaId = d.schema;
  if (typeof d.base === 'string') patch.baseFingerprint = d.base;
  if (typeof d.type === 'string') patch.targetType = d.type;
  return patch;
}

function parseOp(raw: unknown, i: number): PatchOp {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    throw new Error(`op ${i}: must be an object`);
  }
  const r = raw as Record<string, unknown>;
  const unknown = Object.keys(r).filter(k => !OP_KEYS.has(k));
  if (unknown.length) throw new Error(`op ${i}: unknown key(s): ${unknown.join(', ')}`);
  const kind = r.op as PatchOpKind;
  if (!OP_KINDS.includes(kind)) throw new Error(`op ${i}: unknown operation: ${JSON.stringify(r.op)}`);
  if (!Array.isArray(r.path)) throw new Error(`op ${i}: path must be a list`);
  const op: PatchOp = { op: kind, path: r.path.map(seg => parseSeg(seg, i)) };

  if (kind === '-') {
    if ('value' in r) throw new Error(`op ${i}: '-' takes no value`);
  } else if (!('value' in r)) {
    throw new Error(`op ${i}: '${kind}' requires a value`);
  } else if (kind === '~') {
    if (typeof r.value !== 'number') throw new Error(`op ${i}: invalid delta: ${JSON.stringify(r.value)}`);
    op.value = GValue.float(r.value);
  } else {
    op.value = fromJsonLoose(r.value);
  }

  if ('index' in r) {
    if (kind !== '+') throw new Error(`op ${i}: index is only allowed on '+'`);
    if (!isInt(r.index) || r.index < 0) throw new Error(`op ${i}: index must be a non-negative integer`);
    op.index = r.index;
  } else if (kind === '+') {
    op.index = -1;
  }
  return op;
}

function parseSeg(seg: unknown, i: number): PathSeg {
  if (typeof seg === 'string') return fieldSeg(seg);
  if (isInt(seg) && seg >= 0) return listIdxSeg(seg);
  throw new Error(`op ${i}: path segment must be a string or non-negative integer: ${JSON.stringify(seg)}`);
}
// ============================================================
// Base-fingerprint verification
//

/**
 * Raised (thrown) when a patch's recorded base fingerprint does not match
 * the base state presented to verifyPatchBase / applyPatch. Mirrors Go's
 * FingerprintMismatch / PatchBaseMismatch and Python's PatchBaseMismatch.
 */
export class PatchBaseMismatch extends Error {
  got: string;
  want: string;

  constructor(got: string, want: string) {
    super(`patch base fingerprint mismatch: got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
    this.name = 'PatchBaseMismatch';
    this.got = got;
    this.want = want;
  }
}

/** Patch base fingerprint: fingerprint(base), the one digest (SPEC-CANON.md §5). */
export function computeBaseFingerprint(v: GValue): string {
  return fingerprint(v);
}

/**
 * Verify a patch's recorded base fingerprint against the base state.
 *
 * No-op when the patch records no base (patch.baseFingerprint falsy) —
 * mirrors Go VerifyPatchBase / Python verify_patch_base. Throws
 * PatchBaseMismatch when the recomputed fingerprint differs.
 *
 * applyPatch calls this automatically (unless { verifyBase: false } is
 * passed) before applying any operation. This function remains exported for
 * callers who want to verify ahead of time, or who use
 * applyPatch(..., { verifyBase: false }) and want the check back.
 */
export function verifyPatchBase(base: GValue, patch: Patch): void {
  if (!patch.baseFingerprint) return;
  const got = computeBaseFingerprint(base);
  if (got !== patch.baseFingerprint) {
    throw new PatchBaseMismatch(got, patch.baseFingerprint);
  }
}

// ============================================================
// Patch Apply
// ============================================================

export interface ApplyPatchOptions {
  /**
   * Verify the patch's recorded base fingerprint (if any) against value
   * before applying any operation. Defaults to true. Pass false to skip the
   * check entirely — e.g. a caller that has already verified the base
   * out-of-band, or that intentionally wants to force-apply a stale patch.
   */
  verifyBase?: boolean;
}

/**
 * Apply a patch to a GValue and return the modified copy.
 *
 * Base enforcement: when patch carries a base fingerprint
 * (patch.baseFingerprint is truthy) and options.verifyBase is not false (the
 * default), this verifies it against value via verifyPatchBase BEFORE
 * applying any operation, throwing PatchBaseMismatch on a stale base. A
 * patch with no recorded fingerprint is applied unconditionally either way.
 */
export function applyPatch(value: GValue, patch: Patch, options: ApplyPatchOptions = {}): GValue {
  if (options.verifyBase !== false) {
    verifyPatchBase(value, patch);
  }

  let result = value.clone();

  for (const op of patch.ops) {
    result = applyOp(result, op);
  }

  return result;
}

function applyOp(value: GValue, op: PatchOp): GValue {
  if (op.path.length === 0) {
    // Root-level operation
    if (op.op === '=') {
      return op.value || GValue.null();
    }
    throw new Error(`cannot apply ${op.op} to root`);
  }
  
  return applyAtPath(value, op.path, op);
}

function applyAtPath(value: GValue, path: PathSeg[], op: PatchOp): GValue {
  if (path.length === 1) {
    return applyToParent(value, path[0], op);
  }
  
  const seg = path[0];
  const rest = path.slice(1);
  
  if (seg.kind === 'field' || seg.kind === 'mapKey') {
    // Wire paths carry one string kind, so a field seg must walk maps too.
    const key = seg.kind === 'field' ? seg.field! : seg.mapKey!;
    const entries = value.type === 'struct' ? value.asStruct().fields
      : value.type === 'map' ? value.asMap() : null;
    if (!entries) {
      throw new Error(`cannot navigate into ${value.type} with ${seg.kind}`);
    }
    for (const e of entries) {
      if (e.key === key) {
        e.value = applyAtPath(e.value, rest, op);
        return value;
      }
    }
    throw new Error(`key not found: ${key}`);
  }
  
  if (seg.kind === 'listIdx') {
    if (value.type !== 'list') {
      throw new Error(`cannot index into ${value.type}`);
    }
    const list = value.asList();
    const idx = seg.listIdx!;
    if (idx < 0 || idx >= list.length) {
      throw new Error(`index out of bounds: ${idx}`);
    }
    list[idx] = applyAtPath(list[idx], rest, op);
    return value;
  }
  
  throw new Error('unknown path segment kind');
}

function applyToParent(value: GValue, seg: PathSeg, op: PatchOp): GValue {
  const key = seg.kind === 'mapKey' ? seg.mapKey! : seg.field!;
  
  switch (op.op) {
    case '=':
      value.set(key, op.value || GValue.null());
      return value;
    
    case '+': {
      const existing = value.get(key);
      if (!existing || existing.isNull()) {
        value.set(key, GValue.list(op.value || GValue.null()));
      } else if (existing.type === 'list') {
        const list = existing.asList();
        if (op.index !== undefined && op.index >= 0 && op.index <= list.length) {
          list.splice(op.index, 0, op.value || GValue.null());
        } else {
          list.push(op.value || GValue.null());
        }
      } else {
        throw new Error(`cannot append to ${existing.type}`);
      }
      return value;
    }
    
    case '-': {
      if (value.type === 'struct') {
        const sv = value.asStruct();
        sv.fields = sv.fields.filter(f => f.key !== key);
      } else if (value.type === 'map') {
        const entries = value.asMap();
        const idx = entries.findIndex(e => e.key === key);
        if (idx >= 0) entries.splice(idx, 1);
      } else {
        throw new Error(`cannot delete from ${value.type}`);
      }
      return value;
    }
    
    case '~': {
      const existing = value.get(key);
      if (!existing) {
        throw new Error(`field not found for delta: ${key}`);
      }
      
      const delta = op.value?.type === 'float' ? op.value.asFloat() : op.value?.asInt() || 0;
      
      if (existing.type === 'int') {
        value.set(key, GValue.int(existing.asInt() + delta));
      } else if (existing.type === 'float') {
        value.set(key, GValue.float(existing.asFloat() + delta));
      } else {
        throw new Error(`cannot apply delta to ${existing.type}`);
      }
      return value;
    }
  }
  
  throw new Error(`unknown operation: ${op.op}`);
}

// ============================================================
// Diff Generation
//
// Port of Go's Diff (emit_patch.go): same semantics, including whole-list
// replace on any list change (no per-index diffing) and the narrow
// valuesEqual type coverage below (map/bytes/time/sum values are never
// considered equal, so a list containing them is always replaced wholesale
// on any diff — this mirrors Go's behavior exactly, not an improvement).
// ============================================================

/**
 * Compute the patch set needed to transform `from` into `to`. Mirrors Go's
 * Diff(from, to, typeName): the returned patch has a zero-value target and
 * empty schema id (Diff does not scope to a target document); set
 * patch.target before emitting/sending if needed. It carries the base
 * fingerprint of `from` (same computation as computeBaseFingerprint), so
 * applyPatch rejects it against any other state.
 */
export function diff(from: GValue | undefined | null, to: GValue | undefined | null, typeName?: string): Patch {
  const p: Patch = {
    target: { prefix: '', value: '' },
    ops: [],
  };
  if (typeName) {
    p.targetType = typeName;
  }
  if (from != null) {
    p.baseFingerprint = computeBaseFingerprint(from);
  }
  diffValues(from ?? undefined, to ?? undefined, [], p);
  return p;
}

function copyPath(path: PathSeg[]): PathSeg[] {
  return path.slice();
}

function diffValues(from: GValue | undefined, to: GValue | undefined, path: PathSeg[], p: Patch): void {
  if (from === undefined && to === undefined) {
    return;
  }
  if (from === undefined) {
    p.ops.push({ op: '=', path: copyPath(path), value: to });
    return;
  }
  if (to === undefined) {
    if (path.length > 0) {
      p.ops.push({ op: '-', path: copyPath(path) });
    }
    return;
  }
  if (from.type !== to.type) {
    p.ops.push({ op: '=', path: copyPath(path), value: to });
    return;
  }

  switch (from.type) {
    case 'null':
      // Both null, no change.
      break;

    case 'bool':
      if (from.asBool() !== to.asBool()) {
        p.ops.push({ op: '=', path: copyPath(path), value: to });
      }
      break;

    case 'int':
      if (from.asInt() !== to.asInt()) {
        p.ops.push({ op: '=', path: copyPath(path), value: to });
      }
      break;

    case 'float':
      if (from.asFloat() !== to.asFloat()) {
        p.ops.push({ op: '=', path: copyPath(path), value: to });
      }
      break;

    case 'str':
      if (from.asStr() !== to.asStr()) {
        p.ops.push({ op: '=', path: copyPath(path), value: to });
      }
      break;

    case 'id': {
      const a = from.asId();
      const b = to.asId();
      if (a.prefix !== b.prefix || a.value !== b.value) {
        p.ops.push({ op: '=', path: copyPath(path), value: to });
      }
      break;
    }

    case 'struct':
      diffStructValues(from, to, path, p);
      break;

    case 'map':
      diffMapValues(from, to, path, p);
      break;

    case 'list':
      // For now, just replace if different (whole-list replace, matches Go).
      if (!listsEqual(from.asList(), to.asList())) {
        p.ops.push({ op: '=', path: copyPath(path), value: to });
      }
      break;

    default:
      // Other types: replace if not equal.
      p.ops.push({ op: '=', path: copyPath(path), value: to });
      break;
  }
}

function diffStructValues(from: GValue, to: GValue, path: PathSeg[], p: Patch): void {
  const fromFields = new Map<string, GValue>();
  for (const f of from.asStruct().fields) {
    fromFields.set(f.key, f.value);
  }
  const toFields = new Map<string, GValue>();
  for (const f of to.asStruct().fields) {
    toFields.set(f.key, f.value);
  }

  for (const [key, toVal] of toFields) {
    const fromVal = fromFields.get(key);
    diffValues(fromVal, toVal, [...copyPath(path), fieldSeg(key)], p);
  }

  for (const key of fromFields.keys()) {
    if (!toFields.has(key)) {
      p.ops.push({ op: '-', path: [...copyPath(path), fieldSeg(key)] });
    }
  }
}

function diffMapValues(from: GValue, to: GValue, path: PathSeg[], p: Patch): void {
  const fromMap = new Map<string, GValue>();
  for (const e of from.asMap()) {
    fromMap.set(e.key, e.value);
  }
  const toMap = new Map<string, GValue>();
  for (const e of to.asMap()) {
    toMap.set(e.key, e.value);
  }

  for (const [key, toVal] of toMap) {
    const fromVal = fromMap.get(key);
    diffValues(fromVal, toVal, [...copyPath(path), mapKeySeg(key)], p);
  }

  for (const key of fromMap.keys()) {
    if (!toMap.has(key)) {
      p.ops.push({ op: '-', path: [...copyPath(path), mapKeySeg(key)] });
    }
  }
}

function listsEqual(a: GValue[], b: GValue[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (!valuesEqual(a[i], b[i])) return false;
  }
  return true;
}

function valuesEqual(a: GValue | undefined | null, b: GValue | undefined | null): boolean {
  if (a == null && b == null) return true;
  if (a == null || b == null) return false;
  if (a.type !== b.type) return false;

  switch (a.type) {
    case 'null':
      return true;
    case 'bool':
      return a.asBool() === (b as GValue).asBool();
    case 'int':
      return a.asInt() === (b as GValue).asInt();
    case 'float':
      return a.asFloat() === (b as GValue).asFloat();
    case 'str':
      return a.asStr() === (b as GValue).asStr();
    case 'id': {
      const ai = a.asId();
      const bi = (b as GValue).asId();
      return ai.prefix === bi.prefix && ai.value === bi.value;
    }
    case 'list':
      return listsEqual(a.asList(), (b as GValue).asList());
    case 'struct': {
      const as = a.asStruct();
      const bs = (b as GValue).asStruct();
      if (as.typeName !== bs.typeName) return false;
      if (as.fields.length !== bs.fields.length) return false;
      const aFields = new Map<string, GValue>();
      for (const f of as.fields) aFields.set(f.key, f.value);
      for (const f of bs.fields) {
        if (!valuesEqual(aFields.get(f.key), f.value)) return false;
      }
      return true;
    }
    // map/bytes/time/sum: not covered, mirrors Go's valuesEqual default case
    // (always unequal) — see the module doc comment above.
    default:
      return false;
  }
}
