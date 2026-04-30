"use strict";
/**
 * GLYPH v2 Parser
 *
 * Parses GLYPH format back to GValue.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.parsePacked = parsePacked;
exports.parseHeader = parseHeader;
exports.parseTabular = parseTabular;
exports.parseScalarValue = parseScalarValue;
const types_1 = require("./types");
const pool_1 = require("./pool");
function parsePacked(input, schema) {
    const parser = new PackedParser(input, schema);
    return parser.parse();
}
const MAX_PARSE_DEPTH = 128; // aligned with loose.ts, C, Python
const MAX_COLLECTION_LEN = 1000000; // 1M elements (aligned across all impls)
const MAX_STRING_LEN = 10 * 1024 * 1024; // 10MB (aligned across all impls)
class PackedParser {
    constructor(input, schema) {
        this.pos = 0;
        this.depth = 0;
        this.input = input;
        this.schema = schema;
    }
    parse() {
        this.skipWhitespace();
        // Expect Type@(...) or Type@{bm=...}(...)
        const typeName = this.parseTypeName();
        this.expect('@');
        const td = this.schema.getType(typeName);
        if (!td) {
            throw new Error(`unknown type: ${typeName}`);
        }
        // Check for bitmap header
        let mask = null;
        if (this.peek() === '{') {
            mask = this.parseBitmapHeader();
        }
        this.expect('(');
        let value;
        if (mask) {
            value = this.parseBitmapValues(typeName, mask);
        }
        else {
            value = this.parseDenseValues(typeName);
        }
        this.expect(')');
        this.skipWhitespace();
        if (this.pos !== this.input.length) {
            throw new Error(`trailing garbage at pos ${this.pos}`);
        }
        return value;
    }
    parseTypeName() {
        this.skipWhitespace();
        const start = this.pos;
        if (this.pos >= this.input.length) {
            throw new Error('unexpected end of input');
        }
        if (!this.isTypeNameStart(this.input.charCodeAt(this.pos))) {
            throw new Error(`expected type name at pos ${this.pos}`);
        }
        while (this.pos < this.input.length && this.isTypeNameCont(this.input.charCodeAt(this.pos))) {
            this.pos++;
        }
        return this.input.slice(start, this.pos);
    }
    isTypeNameStart(c) {
        return (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c === 95;
    }
    isTypeNameCont(c) {
        return this.isTypeNameStart(c) || (c >= 48 && c <= 57);
    }
    parseBitmapHeader() {
        this.expect('{');
        this.skipWhitespace();
        this.expectLiteral('bm=');
        this.expectLiteral('0b');
        const start = this.pos;
        while (this.pos < this.input.length && (this.input[this.pos] === '0' || this.input[this.pos] === '1')) {
            this.pos++;
        }
        const bits = this.input.slice(start, this.pos);
        if (bits.length === 0) {
            throw new Error('empty bitmap');
        }
        // Convert bits to mask (LSB first)
        const mask = [];
        for (let i = bits.length - 1; i >= 0; i--) {
            mask.push(bits[i] === '1');
        }
        this.skipWhitespace();
        this.expect('}');
        return mask;
    }
    parseDenseValues(typeName) {
        const fields = this.schema.fieldsByFid(typeName);
        const entries = [];
        for (let i = 0; i < fields.length; i++) {
            const fd = fields[i];
            this.skipWhitespace();
            if (this.peek() === ')') {
                // Remaining fields are null
                for (let j = i; j < fields.length; j++) {
                    entries.push({ key: fields[j].name, value: types_1.GValue.null() });
                }
                break;
            }
            const val = this.parseValue(fd.type.kind === 'ref' ? fd.type.name : undefined);
            entries.push({ key: fd.name, value: val });
        }
        return types_1.GValue.struct(typeName, ...entries);
    }
    parseBitmapValues(typeName, mask) {
        const reqFields = this.schema.requiredFieldsByFid(typeName);
        const optFields = this.schema.optionalFieldsByFid(typeName);
        const entries = [];
        // Parse required fields
        for (const fd of reqFields) {
            this.skipWhitespace();
            const val = this.parseValue(fd.type.kind === 'ref' ? fd.type.name : undefined);
            entries.push({ key: fd.name, value: val });
        }
        // Parse optional fields based on mask
        for (let i = 0; i < optFields.length; i++) {
            const fd = optFields[i];
            if (i < mask.length && mask[i]) {
                this.skipWhitespace();
                const val = this.parseValue(fd.type.kind === 'ref' ? fd.type.name : undefined);
                entries.push({ key: fd.name, value: val });
            }
            else {
                entries.push({ key: fd.name, value: types_1.GValue.null() });
            }
        }
        return types_1.GValue.struct(typeName, ...entries);
    }
    parseValue(typeHint) {
        this.depth++;
        if (this.depth > MAX_PARSE_DEPTH) {
            throw new Error(`maximum nesting depth exceeded (${MAX_PARSE_DEPTH})`);
        }
        try {
            return this.parseValueInner(typeHint);
        }
        finally {
            this.depth--;
        }
    }
    parseValueInner(typeHint) {
        this.skipWhitespace();
        const c = this.peek();
        // Null
        if (c === '∅') {
            this.pos++;
            return types_1.GValue.null();
        }
        // Boolean
        if (c === 't') {
            if (this.tryLiteral('true') || this.tryLiteral('t')) {
                return types_1.GValue.bool(true);
            }
            return this.parseBareString();
        }
        if (c === 'f') {
            if (this.tryLiteral('false') || this.tryLiteral('f')) {
                return types_1.GValue.bool(false);
            }
            return this.parseBareString();
        }
        // String
        if (c === '"') {
            return this.parseQuotedString();
        }
        // Ref
        if (c === '^') {
            return this.parseRef();
        }
        // List
        if (c === '[') {
            return this.parseList();
        }
        // Map
        if (c === '{') {
            return this.parseMap();
        }
        // Number or time
        if (c === '-' || (c >= '0' && c <= '9')) {
            return this.parseNumberOrTime();
        }
        // Nested packed struct or bare string
        if (this.isTypeNameStart(c.charCodeAt(0))) {
            const saved = this.pos;
            const name = this.parseTypeName();
            if (this.peek() === '@') {
                // Nested packed struct
                this.pos = saved;
                return this.parseNestedPacked();
            }
            // Bare string
            return types_1.GValue.str(name);
        }
        throw new Error(`unexpected character at pos ${this.pos}: ${c}`);
    }
    parseNestedPacked() {
        const typeName = this.parseTypeName();
        this.expect('@');
        const td = this.schema.getType(typeName);
        if (!td) {
            throw new Error(`unknown nested type: ${typeName}`);
        }
        let mask = null;
        if (this.peek() === '{') {
            mask = this.parseBitmapHeader();
        }
        this.expect('(');
        let value;
        if (mask) {
            value = this.parseBitmapValues(typeName, mask);
        }
        else {
            value = this.parseDenseValues(typeName);
        }
        this.expect(')');
        return value;
    }
    parseNumberOrTime() {
        // Check for ISO time pattern
        if (this.pos + 10 < this.input.length) {
            const ahead = this.input.slice(this.pos, this.pos + 11);
            if (/^\d{4}-\d{2}-\d{2}T/.test(ahead)) {
                return this.parseTime();
            }
        }
        return this.parseNumber();
    }
    parseTime() {
        const start = this.pos;
        while (this.pos < this.input.length) {
            const c = this.input[this.pos];
            if (this.isTokenBoundary(c)) {
                break;
            }
            this.pos++;
        }
        const timeStr = this.input.slice(start, this.pos);
        const date = new Date(timeStr);
        if (Number.isNaN(date.getTime())) {
            throw new Error(`invalid time at pos ${start}`);
        }
        return types_1.GValue.time(date);
    }
    parseNumber() {
        const start = this.pos;
        const match = /^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(this.input.slice(this.pos));
        if (!match) {
            throw new Error(`invalid number at pos ${start}`);
        }
        const numStr = match[0];
        const next = this.input[this.pos + numStr.length] ?? '';
        if (next !== '' && !this.isTokenBoundary(next)) {
            throw new Error(`invalid numeric token at pos ${start}`);
        }
        this.pos += numStr.length;
        const num = Number(numStr);
        if (!Number.isFinite(num)) {
            throw new Error(`invalid number at pos ${start}`);
        }
        if (numStr.includes('.') || numStr.includes('e') || numStr.includes('E')) {
            return types_1.GValue.float(num);
        }
        const intVal = parseInt(numStr, 10);
        if (!Number.isSafeInteger(intVal)) {
            throw new Error(`integer exceeds safe range at pos ${start}: ${numStr}`);
        }
        return types_1.GValue.int(intVal);
    }
    parseQuotedString() {
        this.expect('"');
        let result = '';
        while (this.pos < this.input.length) {
            const c = this.input[this.pos];
            if (c === '"') {
                this.pos++;
                return types_1.GValue.str(result);
            }
            if (result.length >= MAX_STRING_LEN) {
                throw new Error(`string exceeds maximum length (${MAX_STRING_LEN})`);
            }
            if (c === '\\' && this.pos + 1 < this.input.length) {
                this.pos++;
                switch (this.input[this.pos]) {
                    case 'n':
                        result += '\n';
                        break;
                    case 'r':
                        result += '\r';
                        break;
                    case 't':
                        result += '\t';
                        break;
                    case '\\':
                        result += '\\';
                        break;
                    case '"':
                        result += '"';
                        break;
                    default: result += this.input[this.pos];
                }
            }
            else {
                result += c;
            }
            this.pos++;
        }
        throw new Error('unterminated string');
    }
    parseBareString() {
        const start = this.pos;
        while (this.pos < this.input.length) {
            const c = this.input[this.pos];
            if (c === ' ' || c === ')' || c === ']' || c === '}' || c === '\n') {
                break;
            }
            this.pos++;
        }
        return types_1.GValue.str(this.input.slice(start, this.pos));
    }
    parseRef() {
        this.expect('^');
        // Quoted ref
        if (this.peek() === '"') {
            const s = this.parseQuotedString().asStr();
            const colonIdx = s.indexOf(':');
            if (colonIdx > 0) {
                return types_1.GValue.id(s.slice(0, colonIdx), s.slice(colonIdx + 1));
            }
            return types_1.GValue.id('', s);
        }
        // Bare ref
        const start = this.pos;
        while (this.pos < this.input.length) {
            const c = this.input[this.pos];
            if (c === ' ' || c === ')' || c === ']' || c === '}' || c === '\n') {
                break;
            }
            this.pos++;
        }
        const refStr = this.input.slice(start, this.pos);
        const colonIdx = refStr.indexOf(':');
        if (colonIdx > 0) {
            return types_1.GValue.id(refStr.slice(0, colonIdx), refStr.slice(colonIdx + 1));
        }
        return types_1.GValue.id('', refStr);
    }
    parseList() {
        this.expect('[');
        const items = [];
        while (true) {
            this.skipWhitespace();
            if (this.peek() === ']') {
                this.pos++;
                return types_1.GValue.list(...items);
            }
            if (items.length >= MAX_COLLECTION_LEN) {
                throw new Error(`list exceeds maximum length (${MAX_COLLECTION_LEN})`);
            }
            items.push(this.parseValue());
        }
    }
    parseMap() {
        this.expect('{');
        const entries = [];
        while (true) {
            this.skipWhitespace();
            if (this.peek() === '}') {
                this.pos++;
                return types_1.GValue.map(...entries);
            }
            if (entries.length >= MAX_COLLECTION_LEN) {
                throw new Error(`map exceeds maximum length (${MAX_COLLECTION_LEN})`);
            }
            // Parse key
            const key = this.parseValue().asStr();
            this.skipWhitespace();
            if (this.peek() !== ':' && this.peek() !== '=') {
                throw new Error(`expected ':' or '=' after map key`);
            }
            this.pos++;
            // Parse value
            const value = this.parseValue();
            entries.push({ key, value });
        }
    }
    skipWhitespace() {
        while (this.pos < this.input.length) {
            const c = this.input[this.pos];
            if (c !== ' ' && c !== '\t' && c !== '\n' && c !== '\r')
                break;
            this.pos++;
        }
    }
    peek() {
        return this.pos < this.input.length ? this.input[this.pos] : '';
    }
    isTokenBoundary(c) {
        return c === '' || c === ' ' || c === '\t' || c === '\n' || c === '\r' || c === ')' || c === ']' || c === '}';
    }
    expect(c) {
        this.skipWhitespace();
        if (this.pos >= this.input.length || this.input[this.pos] !== c) {
            throw new Error(`expected '${c}' at pos ${this.pos}`);
        }
        this.pos++;
    }
    expectLiteral(s) {
        if (this.input.slice(this.pos, this.pos + s.length) !== s) {
            throw new Error(`expected '${s}' at pos ${this.pos}`);
        }
        this.pos += s.length;
    }
    tryLiteral(s) {
        if (this.input.slice(this.pos, this.pos + s.length) === s) {
            // Check not followed by identifier char
            const next = this.input.charCodeAt(this.pos + s.length);
            if (this.isTypeNameCont(next)) {
                return false;
            }
            this.pos += s.length;
            return true;
        }
        return false;
    }
}
function parseHeader(input) {
    const trimmed = input.trim();
    if (!trimmed.startsWith('@lyph') && !trimmed.startsWith('@glyph')) {
        return null;
    }
    const header = { version: 'v2' };
    const tokens = tokenizeHeader(trimmed);
    for (let i = 0; i < tokens.length; i++) {
        const tok = tokens[i];
        if (tok === '@lyph' || tok === '@glyph') {
            if (i + 1 < tokens.length && !tokens[i + 1].startsWith('@')) {
                header.version = tokens[++i];
            }
            continue;
        }
        if (tok.startsWith('@schema#')) {
            header.schemaId = tok.slice(8);
            continue;
        }
        if (tok.startsWith('@mode=')) {
            header.mode = tok.slice(6);
            continue;
        }
        if (tok.startsWith('@keys=')) {
            header.keyMode = tok.slice(6);
            continue;
        }
        if (tok.startsWith('@target=')) {
            const ref = tok.slice(8);
            const colonIdx = ref.indexOf(':');
            if (colonIdx > 0) {
                header.target = { prefix: ref.slice(0, colonIdx), value: ref.slice(colonIdx + 1) };
            }
            else {
                header.target = { prefix: '', value: ref };
            }
            continue;
        }
    }
    return header;
}
function tokenizeHeader(input) {
    const tokens = [];
    let current = '';
    let inQuote = false;
    for (const c of input) {
        if (c === '"') {
            inQuote = !inQuote;
            current += c;
        }
        else if (c === ' ' && !inQuote) {
            if (current) {
                tokens.push(current);
                current = '';
            }
        }
        else {
            current += c;
        }
    }
    if (current)
        tokens.push(current);
    return tokens;
}
/**
 * Parse a tabular format block.
 *
 * Format:
 *   @tab Type [col1 col2 col3]
 *   value1 value2 value3
 *   value4 value5 value6
 *   @end
 */
function parseTabular(input, schema) {
    const lines = input.split('\n');
    if (lines.length === 0) {
        throw new Error('empty tabular input');
    }
    // Parse header: @tab Type [cols]
    const headerLine = lines[0].trim();
    const { typeName, columns } = parseTabularHeader(headerLine);
    const td = schema.getType(typeName);
    if (!td) {
        throw new Error(`unknown type: ${typeName}`);
    }
    if (!td.fields || td.fields.length === 0) {
        throw new Error(`type ${typeName} has no fields`);
    }
    const fieldMap = new Map();
    for (const fd of td.fields) {
        fieldMap.set(fd.name, fd);
        if (fd.wireKey)
            fieldMap.set(fd.wireKey, fd);
        fieldMap.set(`#${fd.fid}`, fd);
    }
    const columnFields = columns.map(col => {
        const fd = fieldMap.get(col);
        if (!fd) {
            throw new Error(`unknown column: ${col}`);
        }
        return fd;
    });
    // Parse rows
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        // Skip empty lines and comments
        if (line === '' || line.startsWith('#'))
            continue;
        // Stop at @end
        if (line === '@end')
            break;
        // Parse row
        const row = parseTabularRow(line, typeName, columnFields, schema);
        rows.push(row);
    }
    return { typeName, columns, rows };
}
function parseTabularHeader(line) {
    // @tab Type [col1 col2 col3]
    if (!line.startsWith('@tab')) {
        throw new Error('tabular must start with @tab');
    }
    const rest = line.slice(4).trim();
    // Parse type name
    let pos = 0;
    while (pos < rest.length && rest[pos] !== ' ' && rest[pos] !== '[') {
        pos++;
    }
    const typeName = rest.slice(0, pos);
    if (!typeName) {
        throw new Error('missing type name after @tab');
    }
    // Skip to [
    while (pos < rest.length && rest[pos] !== '[')
        pos++;
    if (pos >= rest.length) {
        throw new Error('missing column list in tabular header');
    }
    // Parse columns
    pos++; // skip [
    const colStart = pos;
    while (pos < rest.length && rest[pos] !== ']')
        pos++;
    const colStr = rest.slice(colStart, pos);
    const columns = colStr.trim().split(/\s+/).filter(c => c.length > 0);
    return { typeName, columns };
}
function parseTabularRow(line, typeName, columnFields, schema) {
    // Tokenize the row (respecting quoted strings, brackets, packed structs)
    const tokens = tokenizeRow(line);
    if (tokens.length !== columnFields.length) {
        throw new Error(`row has ${tokens.length} values, expected ${columnFields.length}`);
    }
    const entries = [];
    for (let i = 0; i < tokens.length; i++) {
        const fd = columnFields[i];
        const token = tokens[i];
        let value;
        if (isPackedFormat(token)) {
            value = parsePacked(token, schema);
        }
        else {
            value = parseScalarValue(token);
        }
        entries.push({ key: fd.name, value });
    }
    return types_1.GValue.struct(typeName, ...entries);
}
function tokenizeRow(line) {
    const tokens = [];
    let pos = 0;
    while (pos < line.length) {
        // Skip whitespace
        while (pos < line.length && (line[pos] === ' ' || line[pos] === '\t'))
            pos++;
        if (pos >= line.length)
            break;
        const start = pos;
        const c = line[pos];
        if (c === '"') {
            // Quoted string
            pos++;
            while (pos < line.length && line[pos] !== '"') {
                if (line[pos] === '\\')
                    pos++;
                pos++;
            }
            pos++; // closing quote
        }
        else if (c === '[') {
            // List
            let depth = 1;
            pos++;
            while (pos < line.length && depth > 0) {
                if (line[pos] === '[')
                    depth++;
                else if (line[pos] === ']')
                    depth--;
                pos++;
            }
        }
        else if (c === '{') {
            // Map or bitmap header
            let depth = 1;
            pos++;
            while (pos < line.length && depth > 0) {
                if (line[pos] === '{')
                    depth++;
                else if (line[pos] === '}')
                    depth--;
                pos++;
            }
        }
        else {
            // Bare token - handle packed structs Type@(...)
            while (pos < line.length) {
                const ch = line[pos];
                if (ch === ' ' || ch === '\t')
                    break;
                if (ch === '(') {
                    // Start of packed values - consume until matching )
                    let depth = 1;
                    pos++;
                    while (pos < line.length && depth > 0) {
                        if (line[pos] === '(')
                            depth++;
                        else if (line[pos] === ')')
                            depth--;
                        pos++;
                    }
                    break;
                }
                pos++;
            }
        }
        tokens.push(line.slice(start, pos));
    }
    return tokens;
}
function isPackedFormat(s) {
    const atIdx = s.indexOf('@');
    if (atIdx <= 0)
        return false;
    if (atIdx + 1 >= s.length)
        return false;
    const next = s[atIdx + 1];
    return next === '(' || next === '{';
}
function parseScalarValue(s) {
    s = s.trim();
    // Null
    if (s === '∅' || s === 'null' || s === 'nil' || s === 'none') {
        return types_1.GValue.null();
    }
    // Boolean
    if (s === 't' || s === 'true')
        return types_1.GValue.bool(true);
    if (s === 'f' || s === 'false')
        return types_1.GValue.bool(false);
    // Ref
    if (s.startsWith('^')) {
        const ref = s.slice(1);
        // Handle quoted ref
        if (ref.startsWith('"')) {
            const inner = ref.slice(1, -1);
            const colonIdx = inner.indexOf(':');
            if (colonIdx > 0) {
                return types_1.GValue.id(inner.slice(0, colonIdx), inner.slice(colonIdx + 1));
            }
            return types_1.GValue.id('', inner);
        }
        const colonIdx = ref.indexOf(':');
        if (colonIdx > 0) {
            const first = ref.slice(0, colonIdx);
            const second = ref.slice(colonIdx + 1);
            if ((0, pool_1.isPoolRefId)(first) && /^\d+$/.test(second)) {
                return types_1.GValue.poolRef(first, parseInt(second, 10));
            }
            return types_1.GValue.id(first, second);
        }
        return types_1.GValue.id('', ref);
    }
    // Quoted string
    if (s.startsWith('"')) {
        return parseQuotedScalar(s);
    }
    // Time (ISO format)
    if (/^\d{4}-\d{2}-\d{2}T/.test(s)) {
        return types_1.GValue.time(new Date(s));
    }
    // Number
    if (/^-?\d/.test(s)) {
        if (s.includes('.') || s.includes('e') || s.includes('E')) {
            return types_1.GValue.float(parseFloat(s));
        }
        const intVal = parseInt(s, 10);
        if (!Number.isSafeInteger(intVal)) {
            throw new Error(`integer exceeds safe range: ${s}`);
        }
        return types_1.GValue.int(intVal);
    }
    // List
    if (s.startsWith('[')) {
        return parseListScalar(s);
    }
    // Map
    if (s.startsWith('{')) {
        return parseMapScalar(s);
    }
    // Bare string
    return types_1.GValue.str(s);
}
function parseQuotedScalar(s) {
    let result = '';
    for (let i = 1; i < s.length - 1; i++) {
        if (s[i] === '\\' && i + 1 < s.length - 1) {
            i++;
            switch (s[i]) {
                case 'n':
                    result += '\n';
                    break;
                case 'r':
                    result += '\r';
                    break;
                case 't':
                    result += '\t';
                    break;
                case '\\':
                    result += '\\';
                    break;
                case '"':
                    result += '"';
                    break;
                default: result += s[i];
            }
        }
        else {
            result += s[i];
        }
    }
    return types_1.GValue.str(result);
}
function parseListScalar(s) {
    // Simple list parsing - tokenize content
    const inner = s.slice(1, -1).trim();
    if (!inner)
        return types_1.GValue.list();
    const tokens = tokenizeRow(inner);
    return types_1.GValue.list(...tokens.map(t => parseScalarValue(t)));
}
function parseMapScalar(s) {
    // Simple map parsing
    const inner = s.slice(1, -1).trim();
    if (!inner)
        return types_1.GValue.map();
    const entries = [];
    const tokens = tokenizeRow(inner);
    for (const token of tokens) {
        const eqIdx = token.indexOf('=');
        const colonIdx = token.indexOf(':');
        const sepIdx = eqIdx > 0 ? eqIdx : colonIdx;
        if (sepIdx > 0) {
            const key = token.slice(0, sepIdx).trim();
            const valStr = token.slice(sepIdx + 1).trim();
            entries.push({ key, value: parseScalarValue(valStr) });
        }
    }
    return types_1.GValue.map(...entries);
}
//# sourceMappingURL=parse.js.map