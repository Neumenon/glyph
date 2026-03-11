"use strict";
/**
 * LYPH v2 JSON Conversion
 *
 * Converts between JSON and GValue representations.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.fromJson = fromJson;
exports.toJson = toJson;
exports.parseJson = parseJson;
exports.stringifyJson = stringifyJson;
exports.normalizeJson = normalizeJson;
const types_1 = require("./types");
const hasOwnProperty = Object.prototype.hasOwnProperty;
function hasOwn(obj, key) {
    return hasOwnProperty.call(obj, key);
}
function createJsonObject() {
    return Object.create(null);
}
/**
 * Convert JSON value to GValue
 */
function fromJson(json, options = {}) {
    const { schema, typeName, parseDates = true, parseRefs = true } = options;
    return convertValue(json, schema, typeName, parseDates, parseRefs);
}
function convertValue(v, schema, typeName, parseDates, parseRefs) {
    // Null
    if (v === null || v === undefined) {
        return types_1.GValue.null();
    }
    // Boolean
    if (typeof v === 'boolean') {
        return types_1.GValue.bool(v);
    }
    // Number
    if (typeof v === 'number') {
        if (Number.isInteger(v)) {
            return types_1.GValue.int(v);
        }
        return types_1.GValue.float(v);
    }
    // String
    if (typeof v === 'string') {
        // Check for ref pattern: ^prefix:value
        if (parseRefs && v.startsWith('^')) {
            const rest = v.slice(1);
            const colonIdx = rest.indexOf(':');
            if (colonIdx > 0) {
                return types_1.GValue.id(rest.slice(0, colonIdx), rest.slice(colonIdx + 1));
            }
            return types_1.GValue.id('', rest);
        }
        // Check for ISO date pattern
        if (parseDates && isIsoDateString(v)) {
            const date = new Date(v);
            if (!isNaN(date.getTime())) {
                return types_1.GValue.time(date);
            }
        }
        return types_1.GValue.str(v);
    }
    // Array
    if (Array.isArray(v)) {
        const items = v.map(item => convertValue(item, schema, undefined, parseDates, parseRefs));
        return types_1.GValue.list(...items);
    }
    // Object
    if (typeof v === 'object') {
        const obj = v;
        const typeMarker = hasOwn(obj, '$type') ? obj.$type : undefined;
        const refMarker = hasOwn(obj, '$ref') ? obj.$ref : undefined;
        const timeMarker = hasOwn(obj, '$time') ? obj.$time : undefined;
        const bytesMarker = hasOwn(obj, '$bytes') ? obj.$bytes : undefined;
        const tagMarker = hasOwn(obj, '$tag') ? obj.$tag : undefined;
        // Check for special type markers
        if (typeof typeMarker === 'string') {
            // Typed struct: { $type: "TypeName", field1: ..., field2: ... }
            const structTypeName = typeMarker;
            const td = schema?.getType(structTypeName);
            const fields = [];
            for (const [key, val] of Object.entries(obj)) {
                if (key === '$type')
                    continue;
                // Get field type hint from schema
                const fieldDef = td?.fields?.find(f => f.name === key || f.wireKey === key);
                const fieldTypeName = fieldDef?.type.kind === 'ref' ? fieldDef.type.name : undefined;
                fields.push({
                    key,
                    value: convertValue(val, schema, fieldTypeName, parseDates, parseRefs),
                });
            }
            return types_1.GValue.struct(structTypeName, ...fields);
        }
        // Check for ref marker
        if (typeof refMarker === 'string') {
            const ref = refMarker;
            const colonIdx = ref.indexOf(':');
            if (colonIdx > 0) {
                return types_1.GValue.id(ref.slice(0, colonIdx), ref.slice(colonIdx + 1));
            }
            return types_1.GValue.id('', ref);
        }
        // Check for time marker
        if (typeof timeMarker === 'string') {
            return types_1.GValue.time(new Date(timeMarker));
        }
        // Check for bytes marker
        if (typeof bytesMarker === 'string') {
            return types_1.GValue.bytes(base64ToBytes(bytesMarker));
        }
        // Check for sum type marker
        if (typeof tagMarker === 'string') {
            const value = hasOwn(obj, '$value')
                ? convertValue(obj.$value, schema, undefined, parseDates, parseRefs)
                : null;
            return types_1.GValue.sum(tagMarker, value);
        }
        // Regular object -> struct with typeName or map
        if (typeName) {
            const td = schema?.getType(typeName);
            const fields = [];
            for (const [key, val] of Object.entries(obj)) {
                const fieldDef = td?.fields?.find(f => f.name === key || f.wireKey === key);
                const fieldTypeName = fieldDef?.type.kind === 'ref' ? fieldDef.type.name : undefined;
                fields.push({
                    key,
                    value: convertValue(val, schema, fieldTypeName, parseDates, parseRefs),
                });
            }
            return types_1.GValue.struct(typeName, ...fields);
        }
        // Map
        const entries = [];
        for (const [key, val] of Object.entries(obj)) {
            entries.push({
                key,
                value: convertValue(val, schema, undefined, parseDates, parseRefs),
            });
        }
        return types_1.GValue.map(...entries);
    }
    throw new Error(`Unsupported JSON value type: ${typeof v}`);
}
function isIsoDateString(s) {
    // Simple ISO-8601 detection: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
    return /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?/.test(s);
}
function base64ToBytes(b64) {
    if (typeof atob === 'function') {
        const binary = atob(b64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return bytes;
    }
    // Node.js fallback
    return new Uint8Array(Buffer.from(b64, 'base64'));
}
/**
 * Convert GValue to JSON-compatible value
 */
function toJson(gv, options = {}) {
    const { includeTypeMarkers = false, compactRefs = true, formatDates = true, useWireKeys = false, schema, } = options;
    return convertToJson(gv, includeTypeMarkers, compactRefs, formatDates, useWireKeys, schema);
}
function convertToJson(gv, includeTypeMarkers, compactRefs, formatDates, useWireKeys, schema) {
    switch (gv.type) {
        case 'null':
            return null;
        case 'bool':
            return gv.asBool();
        case 'int':
            return gv.asInt();
        case 'float':
            return gv.asFloat();
        case 'str':
            return gv.asStr();
        case 'bytes': {
            const bytes = gv.asBytes();
            const b64 = bytesToBase64(bytes);
            const result = createJsonObject();
            result.$bytes = b64;
            return result;
        }
        case 'time': {
            const date = gv.asTime();
            if (formatDates) {
                return date.toISOString();
            }
            const result = createJsonObject();
            result.$time = date.toISOString();
            return result;
        }
        case 'id': {
            const ref = gv.asId();
            const refStr = ref.prefix ? `${ref.prefix}:${ref.value}` : ref.value;
            if (compactRefs) {
                return `^${refStr}`;
            }
            const result = createJsonObject();
            result.$ref = refStr;
            return result;
        }
        case 'list': {
            return gv.asList().map(item => convertToJson(item, includeTypeMarkers, compactRefs, formatDates, useWireKeys, schema));
        }
        case 'map': {
            const result = createJsonObject();
            for (const entry of gv.asMap()) {
                result[entry.key] = convertToJson(entry.value, includeTypeMarkers, compactRefs, formatDates, useWireKeys, schema);
            }
            return result;
        }
        case 'struct': {
            const sv = gv.asStruct();
            const result = createJsonObject();
            if (includeTypeMarkers) {
                result.$type = sv.typeName;
            }
            const td = schema?.getType(sv.typeName);
            for (const field of sv.fields) {
                let key = field.key;
                if (useWireKeys && td) {
                    const fd = td.fields?.find(f => f.name === field.key);
                    if (fd?.wireKey) {
                        key = fd.wireKey;
                    }
                }
                result[key] = convertToJson(field.value, includeTypeMarkers, compactRefs, formatDates, useWireKeys, schema);
            }
            return result;
        }
        case 'sum': {
            const sum = gv.asSum();
            const result = createJsonObject();
            result.$tag = sum.tag;
            if (sum.value === null) {
                return result;
            }
            result.$value = convertToJson(sum.value, includeTypeMarkers, compactRefs, formatDates, useWireKeys, schema);
            return result;
        }
    }
}
function bytesToBase64(bytes) {
    if (typeof btoa === 'function') {
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }
    // Node.js fallback
    return Buffer.from(bytes).toString('base64');
}
// ============================================================
// Convenience Functions
// ============================================================
/**
 * Parse JSON string to GValue
 */
function parseJson(jsonStr, options = {}) {
    const json = JSON.parse(jsonStr);
    return fromJson(json, options);
}
/**
 * Stringify GValue to JSON string
 */
function stringifyJson(gv, options = {}, indent) {
    const json = toJson(gv, options);
    return JSON.stringify(json, null, indent);
}
/**
 * Round-trip convert: JSON -> GValue -> JSON
 * Useful for normalizing JSON to LYPH conventions
 */
function normalizeJson(json, fromOptions = {}, toOptions = {}) {
    const gv = fromJson(json, fromOptions);
    return toJson(gv, toOptions);
}
//# sourceMappingURL=json.js.map