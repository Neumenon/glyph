"use strict";
/**
 * GLYPH v2 Encoders
 *
 * Emits GLYPH format from GValue.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.emit = emit;
exports.emitPacked = emitPacked;
exports.emitTabular = emitTabular;
exports.emitHeader = emitHeader;
exports.emitV2 = emitV2;
const codec_primitives_1 = require("./codec_primitives");
// ============================================================
// Canonical Scalar Encoding
// ============================================================
function canonRef(ref) {
    const full = ref.prefix ? `${ref.prefix}:${ref.value}` : ref.value;
    if ((0, codec_primitives_1.isRefSafe)(full)) {
        return `^${full}`;
    }
    return `^${(0, codec_primitives_1.quoteString)(full)}`;
}
function canonTime(d) {
    return d.toISOString().replace('.000Z', 'Z');
}
// ============================================================
// Bitmap Encoding
// ============================================================
function maskToBinary(mask) {
    // Find highest set bit
    let hi = -1;
    for (let i = mask.length - 1; i >= 0; i--) {
        if (mask[i]) {
            hi = i;
            break;
        }
    }
    if (hi === -1)
        return '0b0';
    let result = '0b';
    for (let i = hi; i >= 0; i--) {
        result += mask[i] ? '1' : '0';
    }
    return result;
}
// ============================================================
// Struct Mode Emitter (v1 compatible)
// ============================================================
function emit(gv, options = {}) {
    return emitValue(gv, options);
}
function emitValue(gv, opts) {
    switch (gv.type) {
        case 'null':
            return (0, codec_primitives_1.canonNull)();
        case 'bool':
            return (0, codec_primitives_1.canonBool)(gv.asBool());
        case 'int':
            return (0, codec_primitives_1.canonInt)(gv.asInt());
        case 'float':
            return (0, codec_primitives_1.canonFloat)(gv.asFloat());
        case 'str':
            return (0, codec_primitives_1.canonString)(gv.asStr());
        case 'bytes':
            return 'b64' + (0, codec_primitives_1.quoteString)(bytesToBase64(gv.asBytes()));
        case 'time':
            return canonTime(gv.asTime());
        case 'id':
            return canonRef(gv.asId());
        case 'list':
            return emitList(gv, opts);
        case 'map':
            return emitMap(gv, opts);
        case 'struct':
            return emitStruct(gv, opts);
        case 'sum':
            return emitSum(gv, opts);
        case 'blob': {
            // eslint-disable-next-line @typescript-eslint/no-require-imports
            const { emitBlob } = require('./blob');
            return emitBlob(gv.asBlob());
        }
        case 'poolRef': {
            const pr = gv.asPoolRef();
            return `^${pr.poolId}:${pr.index}`;
        }
    }
}
function emitList(gv, opts) {
    const items = gv.asList().map(v => emitValue(v, opts));
    return '[' + items.join(' ') + ']';
}
function emitMap(gv, opts) {
    const parts = [];
    for (const entry of gv.asMap()) {
        parts.push(`${(0, codec_primitives_1.canonString)(entry.key)}:${emitValue(entry.value, opts)}`);
    }
    return '{' + parts.join(' ') + '}';
}
function emitStruct(gv, opts) {
    const sv = gv.asStruct();
    const parts = [];
    const td = opts.schema?.getType(sv.typeName);
    for (const field of sv.fields) {
        let key = field.key;
        if (opts.keyMode === 'wire' && td) {
            const fd = td.fields?.find(f => f.name === field.key);
            if (fd?.wireKey)
                key = fd.wireKey;
        }
        else if (opts.keyMode === 'fid' && td) {
            const fd = td.fields?.find(f => f.name === field.key);
            if (fd)
                key = `#${fd.fid}`;
        }
        parts.push(`${(0, codec_primitives_1.canonString)(key)}=${emitValue(field.value, opts)}`);
    }
    return `${sv.typeName}{${parts.join(' ')}}`;
}
function emitSum(gv, opts) {
    const sum = gv.asSum();
    if (sum.value === null) {
        return `${sum.tag}()`;
    }
    if (sum.value.type === 'struct') {
        return `${sum.tag}${emitStruct(sum.value, opts).slice(sum.value.asStruct().typeName.length)}`;
    }
    return `${sum.tag}(${emitValue(sum.value, opts)})`;
}
function emitPacked(gv, schema, options = {}) {
    if (gv.type !== 'struct') {
        throw new Error('packed encoding requires struct value');
    }
    const sv = gv.asStruct();
    const td = schema.getType(sv.typeName);
    if (!td || td.kind !== 'struct') {
        throw new Error(`unknown struct type: ${sv.typeName}`);
    }
    const useBitmap = options.useBitmap !== false && shouldUseBitmap(gv, td, schema);
    if (useBitmap) {
        return emitPackedBitmap(gv, td, schema, options);
    }
    return emitPackedDense(gv, td, schema, options);
}
function shouldUseBitmap(gv, td, schema) {
    const optFields = schema.optionalFieldsByFid(td.name);
    if (optFields.length === 0)
        return false;
    // Check if any optional is missing
    for (const fd of optFields) {
        const val = getFieldValue(gv, fd);
        if (!isFieldPresent(val, fd)) {
            return true;
        }
    }
    return false;
}
function emitPackedDense(gv, td, schema, opts) {
    const fields = schema.fieldsByFid(td.name);
    const parts = [];
    for (const fd of fields) {
        const val = getFieldValue(gv, fd);
        if (fd.optional && !isFieldPresent(val, fd)) {
            parts.push((0, codec_primitives_1.canonNull)());
            continue;
        }
        if (!fd.optional && val === null) {
            throw new Error(`missing required field: ${td.name}.${fd.name}`);
        }
        parts.push(emitPackedValue(val, schema, opts));
    }
    return `${td.name}@(${parts.join(' ')})`;
}
function emitPackedBitmap(gv, td, schema, opts) {
    const reqFields = schema.requiredFieldsByFid(td.name);
    const optFields = schema.optionalFieldsByFid(td.name);
    // Compute bitmap
    const mask = [];
    for (const fd of optFields) {
        const val = getFieldValue(gv, fd);
        mask.push(isFieldPresent(val, fd));
    }
    const parts = [];
    // Required fields first
    for (const fd of reqFields) {
        const val = getFieldValue(gv, fd);
        if (val === null) {
            throw new Error(`missing required field: ${td.name}.${fd.name}`);
        }
        parts.push(emitPackedValue(val, schema, opts));
    }
    // Present optional fields
    for (let i = 0; i < optFields.length; i++) {
        if (!mask[i])
            continue;
        const val = getFieldValue(gv, optFields[i]);
        parts.push(emitPackedValue(val, schema, opts));
    }
    return `${td.name}@{bm=${maskToBinary(mask)}}(${parts.join(' ')})`;
}
function getFieldValue(gv, fd) {
    const sv = gv.asStruct();
    for (const f of sv.fields) {
        if (f.key === fd.name || f.key === fd.wireKey) {
            return f.value;
        }
    }
    return null;
}
function isFieldPresent(val, fd) {
    if (val === null)
        return false;
    if (val.type === 'null' && fd.optional && !fd.keepNull)
        return false;
    return true;
}
function emitPackedValue(gv, schema, opts) {
    switch (gv.type) {
        case 'null':
            return (0, codec_primitives_1.canonNull)();
        case 'bool':
            return (0, codec_primitives_1.canonBool)(gv.asBool());
        case 'int':
            return (0, codec_primitives_1.canonInt)(gv.asInt());
        case 'float':
            return (0, codec_primitives_1.canonFloat)(gv.asFloat());
        case 'str':
            return (0, codec_primitives_1.canonString)(gv.asStr());
        case 'bytes':
            return 'b64' + (0, codec_primitives_1.quoteString)(bytesToBase64(gv.asBytes()));
        case 'time':
            return canonTime(gv.asTime());
        case 'id':
            return canonRef(gv.asId());
        case 'list': {
            const items = gv.asList().map(v => emitPackedValue(v, schema, opts));
            return '[' + items.join(' ') + ']';
        }
        case 'map': {
            const parts = [];
            for (const entry of gv.asMap()) {
                parts.push(`${(0, codec_primitives_1.canonString)(entry.key)}:${emitPackedValue(entry.value, schema, opts)}`);
            }
            return '{' + parts.join(' ') + '}';
        }
        case 'struct': {
            const sv = gv.asStruct();
            const td = schema.getType(sv.typeName);
            if (td?.packEnabled) {
                return emitPacked(gv, schema, opts);
            }
            return emitStruct(gv, { ...opts, schema });
        }
        case 'sum': {
            const sum = gv.asSum();
            if (sum.value === null) {
                return `${sum.tag}()`;
            }
            return `${sum.tag}(${emitPackedValue(sum.value, schema, opts)})`;
        }
        case 'blob': {
            // eslint-disable-next-line @typescript-eslint/no-require-imports
            const { emitBlob } = require('./blob');
            return emitBlob(gv.asBlob());
        }
        case 'poolRef': {
            const pr = gv.asPoolRef();
            return `^${pr.poolId}:${pr.index}`;
        }
    }
}
function emitTabular(gv, schema, options = {}) {
    if (gv.type !== 'list') {
        throw new Error('tabular encoding requires list value');
    }
    const list = gv.asList();
    if (list.length === 0) {
        return '[]';
    }
    // Verify all elements are same type structs
    const first = list[0];
    if (first.type !== 'struct') {
        throw new Error('tabular encoding requires list of structs');
    }
    const typeName = first.asStruct().typeName;
    for (let i = 1; i < list.length; i++) {
        if (list[i].type !== 'struct' || list[i].asStruct().typeName !== typeName) {
            throw new Error('all elements must be same type struct');
        }
    }
    const td = schema.getType(typeName);
    if (!td) {
        throw new Error(`unknown type: ${typeName}`);
    }
    const fields = schema.fieldsByFid(typeName);
    const keyMode = options.keyMode || 'wire';
    const indent = options.indentPrefix || '';
    // Header
    const cols = fields.map(fd => {
        if (keyMode === 'wire' && fd.wireKey)
            return fd.wireKey;
        if (keyMode === 'fid')
            return `#${fd.fid}`;
        return fd.name;
    });
    let result = `@tab ${typeName} [${cols.join(' ')}]\n`;
    // Rows
    for (const row of list) {
        result += indent;
        const cells = [];
        for (const fd of fields) {
            const val = getFieldValue(row, fd);
            if (!isFieldPresent(val, fd)) {
                cells.push((0, codec_primitives_1.canonNull)());
            }
            else {
                cells.push(emitPackedValue(val, schema, options));
            }
        }
        result += cells.join(' ') + '\n';
    }
    result += '@end';
    return result;
}
function emitHeader(options = {}) {
    const parts = ['@lyph', options.version || 'v2'];
    if (options.schemaId) {
        parts.push(`@schema#${options.schemaId}`);
    }
    if (options.mode && options.mode !== 'auto') {
        parts.push(`@mode=${options.mode}`);
    }
    if (options.keyMode && options.keyMode !== 'wire') {
        parts.push(`@keys=${options.keyMode}`);
    }
    if (options.target) {
        const ref = options.target.prefix
            ? `${options.target.prefix}:${options.target.value}`
            : options.target.value;
        parts.push(`@target=${ref}`);
    }
    return parts.join(' ');
}
function emitV2(gv, schema, options = {}) {
    const mode = options.mode || 'auto';
    const tabThreshold = options.tabThreshold || 3;
    let selectedMode = mode;
    if (mode === 'auto') {
        selectedMode = selectMode(gv, schema, tabThreshold);
    }
    let body;
    switch (selectedMode) {
        case 'tabular':
            body = emitTabular(gv, schema, options);
            break;
        case 'packed':
            body = emitPacked(gv, schema, options);
            break;
        default:
            body = emit(gv, { ...options, schema });
    }
    if (options.includeHeader) {
        const header = emitHeader({
            schemaId: schema.hash,
            mode: selectedMode,
            keyMode: options.keyMode,
        });
        return header + '\n' + body;
    }
    return body;
}
function selectMode(gv, schema, tabThreshold) {
    // Tabular for list<struct> with enough elements
    if (gv.type === 'list') {
        const list = gv.asList();
        if (list.length >= tabThreshold && list[0]?.type === 'struct') {
            const typeName = list[0].asStruct().typeName;
            const td = schema.getType(typeName);
            if (td?.tabEnabled) {
                return 'tabular';
            }
        }
    }
    // Packed for structs with packEnabled
    if (gv.type === 'struct') {
        const td = schema.getType(gv.asStruct().typeName);
        if (td?.packEnabled) {
            return 'packed';
        }
    }
    return 'struct';
}
// ============================================================
// Helpers
// ============================================================
function bytesToBase64(bytes) {
    if (typeof btoa === 'function') {
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }
    return Buffer.from(bytes).toString('base64');
}
//# sourceMappingURL=emit.js.map