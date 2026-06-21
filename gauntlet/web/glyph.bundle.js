"use strict";
var Glyph = (() => {
  var __create = Object.create;
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __getProtoOf = Object.getPrototypeOf;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __require = /* @__PURE__ */ ((x) => typeof require !== "undefined" ? require : typeof Proxy !== "undefined" ? new Proxy(x, {
    get: (a, b) => (typeof require !== "undefined" ? require : a)[b]
  }) : x)(function(x) {
    if (typeof require !== "undefined") return require.apply(this, arguments);
    throw Error('Dynamic require of "' + x + '" is not supported');
  });
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
    // If the importer is in node compatibility mode or this is not an ESM
    // file that has been converted to a CommonJS file using a Babel-
    // compatible transform (i.e. "__esModule" has not been set), then set
    // "default" to the CommonJS "module.exports" for node compatibility.
    isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
    mod
  ));
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // src/index.ts
  var index_exports = {};
  __export(index_exports, {
    DEFAULT_MAX_BUFFER: () => DEFAULT_MAX_BUFFER,
    DEFAULT_MAX_ERRORS: () => DEFAULT_MAX_ERRORS,
    DEFAULT_MAX_FIELDS: () => DEFAULT_MAX_FIELDS,
    Decimal128: () => Decimal128,
    DecimalError: () => DecimalError,
    ErrorCode: () => ErrorCode,
    EvolutionMode: () => EvolutionMode,
    EvolvingField: () => EvolvingField,
    GValue: () => GValue,
    PatchBuilder: () => PatchBuilder,
    Schema: () => Schema,
    SchemaBuilder: () => SchemaBuilder,
    StreamingValidator: () => StreamingValidator,
    ToolRegistry: () => ToolRegistry,
    ValidatorState: () => ValidatorState,
    VersionSchema: () => VersionSchema,
    VersionedSchema: () => VersionedSchema,
    applyPatch: () => applyPatch,
    buildKeyDictFromValue: () => buildKeyDictFromValue,
    canonicalizeLoose: () => canonicalizeLoose,
    canonicalizeLooseNoTabular: () => canonicalizeLooseNoTabular,
    canonicalizeLooseWithOpts: () => canonicalizeLooseWithOpts,
    canonicalizeLooseWithSchema: () => canonicalizeLooseWithSchema,
    compareTokens: () => compareTokens,
    compareVersions: () => compareVersions,
    decimal: () => decimal,
    defaultLooseCanonOpts: () => defaultLooseCanonOpts,
    defaultToolRegistry: () => defaultToolRegistry,
    emit: () => emit,
    emitHeader: () => emitHeader,
    emitPacked: () => emitPacked,
    emitPatch: () => emitPatch,
    emitTabular: () => emitTabular,
    emitV2: () => emitV2,
    equalLoose: () => equalLoose,
    estimateTokens: () => estimateTokens,
    field: () => field,
    fieldSeg: () => fieldSeg,
    fingerprintLoose: () => fingerprintLoose,
    formatVersionHeader: () => formatVersionHeader,
    fromJson: () => fromJson,
    fromJsonLoose: () => fromJsonLoose,
    g: () => g,
    isDecimalLiteral: () => isDecimalLiteral,
    jsonEqual: () => jsonEqual,
    jsonToLyph: () => jsonToLyph,
    jsonToPacked: () => jsonToPacked,
    jsonToTabular: () => jsonToTabular,
    listIdxSeg: () => listIdxSeg,
    llmLooseCanonOpts: () => llmLooseCanonOpts,
    mapKeySeg: () => mapKeySeg,
    noTabularLooseCanonOpts: () => noTabularLooseCanonOpts,
    normalizeJson: () => normalizeJson,
    parseDecimalLiteral: () => parseDecimalLiteral,
    parseHeader: () => parseHeader,
    parseJson: () => parseJson,
    parseJsonLoose: () => parseJsonLoose,
    parseLoose: () => parseLoose,
    parsePacked: () => parsePacked,
    parsePatch: () => parsePatch,
    parsePathToSegs: () => parsePathToSegs,
    parseSchemaHeader: () => parseSchemaHeader,
    parseTabular: () => parseTabular,
    parseTabularLoose: () => parseTabularLoose,
    parseTabularLooseHeaderWithMeta: () => parseTabularLooseHeaderWithMeta,
    parseVersionHeader: () => parseVersionHeader,
    stream: () => stream_exports,
    stringifyJson: () => stringifyJson,
    stringifyJsonLoose: () => stringifyJsonLoose,
    t: () => t,
    toJson: () => toJson,
    toJsonLoose: () => toJsonLoose,
    unescapeTabularCell: () => unescapeTabularCell,
    versionedSchema: () => versionedSchema
  });

  // src/types.ts
  var GValue = class _GValue {
    constructor(type) {
      this.type = type;
    }
    // ============================================================
    // Constructors
    // ============================================================
    static null() {
      return new _GValue("null");
    }
    static bool(v) {
      const gv = new _GValue("bool");
      gv._bool = v;
      return gv;
    }
    static int(v) {
      const gv = new _GValue("int");
      gv._int = Math.floor(v);
      return gv;
    }
    static float(v) {
      const gv = new _GValue("float");
      gv._float = v;
      return gv;
    }
    static str(v) {
      const gv = new _GValue("str");
      gv._str = v;
      return gv;
    }
    static bytes(v) {
      const gv = new _GValue("bytes");
      gv._bytes = v;
      return gv;
    }
    static time(v) {
      const gv = new _GValue("time");
      gv._time = v;
      return gv;
    }
    static id(prefix, value) {
      const gv = new _GValue("id");
      gv._id = { prefix, value };
      return gv;
    }
    static idFromRef(ref) {
      const gv = new _GValue("id");
      gv._id = ref;
      return gv;
    }
    static list(...values) {
      const gv = new _GValue("list");
      gv._list = values;
      return gv;
    }
    static map(...entries) {
      const gv = new _GValue("map");
      gv._map = entries;
      return gv;
    }
    static struct(typeName, ...fields) {
      const gv = new _GValue("struct");
      gv._struct = { typeName, fields };
      return gv;
    }
    static sum(tag, value) {
      const gv = new _GValue("sum");
      gv._sum = { tag, value };
      return gv;
    }
    // ============================================================
    // Accessors
    // ============================================================
    isNull() {
      return this.type === "null";
    }
    asBool() {
      if (this.type !== "bool") throw new Error("not a bool");
      return this._bool;
    }
    asInt() {
      if (this.type !== "int") throw new Error("not an int");
      return this._int;
    }
    asFloat() {
      if (this.type !== "float") throw new Error("not a float");
      return this._float;
    }
    asStr() {
      if (this.type !== "str") throw new Error("not a str");
      return this._str;
    }
    asBytes() {
      if (this.type !== "bytes") throw new Error("not bytes");
      return this._bytes;
    }
    asTime() {
      if (this.type !== "time") throw new Error("not a time");
      return this._time;
    }
    asId() {
      if (this.type !== "id") throw new Error("not an id");
      return this._id;
    }
    asList() {
      if (this.type !== "list") throw new Error("not a list");
      return this._list;
    }
    asMap() {
      if (this.type !== "map") throw new Error("not a map");
      return this._map;
    }
    asStruct() {
      if (this.type !== "struct") throw new Error("not a struct");
      return this._struct;
    }
    asSum() {
      if (this.type !== "sum") throw new Error("not a sum");
      return this._sum;
    }
    /**
     * Get numeric value as number (works for int or float)
     */
    asNumber() {
      if (this.type === "int") return this._int;
      if (this.type === "float") return this._float;
      throw new Error("not a number");
    }
    /**
     * Get field from struct or map by key
     */
    get(key) {
      if (this.type === "struct") {
        for (const f of this._struct.fields) {
          if (f.key === key) return f.value;
        }
        return null;
      }
      if (this.type === "map") {
        for (const e of this._map) {
          if (e.key === key) return e.value;
        }
        return null;
      }
      return null;
    }
    /**
     * Get element from list by index
     */
    index(i) {
      if (this.type !== "list") throw new Error("not a list");
      if (i < 0 || i >= this._list.length) throw new Error("index out of bounds");
      return this._list[i];
    }
    /**
     * Get length of list, map, or struct fields
     */
    len() {
      if (this.type === "list") return this._list.length;
      if (this.type === "map") return this._map.length;
      if (this.type === "struct") return this._struct.fields.length;
      return 0;
    }
    // ============================================================
    // Mutators
    // ============================================================
    /**
     * Set field on struct or map
     */
    set(key, value) {
      if (this.type === "struct") {
        for (let i = 0; i < this._struct.fields.length; i++) {
          if (this._struct.fields[i].key === key) {
            this._struct.fields[i].value = value;
            return;
          }
        }
        this._struct.fields.push({ key, value });
      } else if (this.type === "map") {
        for (let i = 0; i < this._map.length; i++) {
          if (this._map[i].key === key) {
            this._map[i].value = value;
            return;
          }
        }
        this._map.push({ key, value });
      } else {
        throw new Error("cannot set on non-struct/map");
      }
    }
    /**
     * Append to list
     */
    append(value) {
      if (this.type !== "list") throw new Error("cannot append to non-list");
      this._list.push(value);
    }
    // ============================================================
    // Deep Copy
    // ============================================================
    clone() {
      switch (this.type) {
        case "null":
          return _GValue.null();
        case "bool":
          return _GValue.bool(this._bool);
        case "int":
          return _GValue.int(this._int);
        case "float":
          return _GValue.float(this._float);
        case "str":
          return _GValue.str(this._str);
        case "bytes":
          return _GValue.bytes(new Uint8Array(this._bytes));
        case "time":
          return _GValue.time(new Date(this._time));
        case "id":
          return _GValue.id(this._id.prefix, this._id.value);
        case "list":
          return _GValue.list(...this._list.map((v) => v.clone()));
        case "map":
          return _GValue.map(...this._map.map((e) => ({ key: e.key, value: e.value.clone() })));
        case "struct":
          return _GValue.struct(
            this._struct.typeName,
            ...this._struct.fields.map((f) => ({ key: f.key, value: f.value.clone() }))
          );
        case "sum":
          return _GValue.sum(this._sum.tag, this._sum.value?.clone() ?? null);
      }
    }
  };
  function field(key, value) {
    return { key, value };
  }
  var g = {
    null: GValue.null,
    bool: GValue.bool,
    int: GValue.int,
    float: GValue.float,
    str: GValue.str,
    bytes: GValue.bytes,
    time: GValue.time,
    id: GValue.id,
    list: GValue.list,
    map: GValue.map,
    struct: GValue.struct,
    sum: GValue.sum,
    field
  };

  // src/schema.ts
  var import_crypto = __require("crypto");
  var Schema = class {
    constructor() {
      this.types = /* @__PURE__ */ new Map();
      this.hash = "";
    }
    getType(name) {
      return this.types.get(name);
    }
    getField(typeName, fieldName) {
      const td = this.types.get(typeName);
      if (!td || td.kind !== "struct" || !td.fields) return void 0;
      return td.fields.find((f) => f.name === fieldName || f.wireKey === fieldName);
    }
    /**
     * Get fields sorted by FID
     */
    fieldsByFid(typeName) {
      const td = this.types.get(typeName);
      if (!td || !td.fields) return [];
      return [...td.fields].sort((a, b) => a.fid - b.fid);
    }
    /**
     * Get required fields sorted by FID
     */
    requiredFieldsByFid(typeName) {
      return this.fieldsByFid(typeName).filter((f) => !f.optional);
    }
    /**
     * Get optional fields sorted by FID
     */
    optionalFieldsByFid(typeName) {
      return this.fieldsByFid(typeName).filter((f) => f.optional);
    }
    /**
     * Compute schema hash (SHA-256, first 16 bytes = 32 hex chars).
     * Matches Go schema.go:238 (sha256.Sum256[:16] → hex.EncodeToString).
     */
    computeHash() {
      const canonical = this.canonical();
      const digest = (0, import_crypto.createHash)("sha256").update(canonical).digest();
      this.hash = digest.slice(0, 16).toString("hex");
      return this.hash;
    }
    /**
     * Get canonical representation
     */
    canonical() {
      const lines = ["@schema{"];
      const names = [...this.types.keys()].sort();
      for (const name of names) {
        const td = this.types.get(name);
        const openPrefix = td.open ? "@open " : "";
        lines.push(`  ${name}${td.version ? ":" + td.version : ""} ${openPrefix}${td.kind}{`);
        if (td.kind === "struct" && td.fields) {
          for (const f of td.fields) {
            let line = `    ${f.name}: ${typeSpecToString(f.type)}`;
            if (f.wireKey) line += ` @k(${f.wireKey})`;
            if (f.optional) line += " [optional]";
            lines.push(line);
          }
        }
        lines.push("  }");
      }
      lines.push("}");
      return lines.join("\n");
    }
  };
  function typeSpecToString(ts) {
    switch (ts.kind) {
      case "list":
        return `list<${typeSpecToString(ts.elem)}>`;
      case "map":
        return `map<${typeSpecToString(ts.keyType)},${typeSpecToString(ts.valType)}>`;
      case "ref":
        return ts.name;
      default:
        return ts.kind;
    }
  }
  var SchemaBuilder = class {
    constructor() {
      this.schema = new Schema();
    }
    /**
     * Add a struct type
     */
    addStruct(name, version) {
      this.currentType = {
        name,
        version,
        kind: "struct",
        fields: [],
        tabEnabled: true
      };
      this.schema.types.set(name, this.currentType);
      return this;
    }
    /**
     * Add a packed struct type (packed encoding enabled by default)
     */
    addPackedStruct(name, version) {
      this.currentType = {
        name,
        version,
        kind: "struct",
        fields: [],
        packEnabled: true,
        tabEnabled: true
      };
      this.schema.types.set(name, this.currentType);
      return this;
    }
    /**
     * Add an open struct type (accepts unknown fields)
     */
    addOpenStruct(name, version) {
      this.currentType = {
        name,
        version,
        kind: "struct",
        fields: [],
        open: true,
        tabEnabled: true
      };
      this.schema.types.set(name, this.currentType);
      return this;
    }
    /**
     * Add an open packed struct type (accepts unknown fields + packed encoding)
     */
    addOpenPackedStruct(name, version) {
      this.currentType = {
        name,
        version,
        kind: "struct",
        fields: [],
        open: true,
        packEnabled: true,
        tabEnabled: true
      };
      this.schema.types.set(name, this.currentType);
      return this;
    }
    /**
     * Add a field to the current struct
     */
    field(name, type, options) {
      if (!this.currentType || this.currentType.kind !== "struct") {
        throw new Error("No struct type in progress");
      }
      const fid = options?.fid ?? this.currentType.fields.length + 1;
      this.currentType.fields.push({
        name,
        type,
        fid,
        ...options
      });
      return this;
    }
    /**
     * Add a sum type
     */
    addSum(name, version) {
      this.currentType = {
        name,
        version,
        kind: "sum",
        variants: []
      };
      this.schema.types.set(name, this.currentType);
      return this;
    }
    /**
     * Add a variant to the current sum type
     */
    variant(tag, type) {
      if (!this.currentType || this.currentType.kind !== "sum") {
        throw new Error("No sum type in progress");
      }
      this.currentType.variants.push({ tag, type });
      return this;
    }
    /**
     * Enable packed encoding for a type
     */
    withPack(typeName) {
      const td = this.schema.types.get(typeName);
      if (td) td.packEnabled = true;
      return this;
    }
    /**
     * Enable tabular encoding for a type
     */
    withTab(typeName) {
      const td = this.schema.types.get(typeName);
      if (td) td.tabEnabled = true;
      return this;
    }
    /**
     * Mark a type as open (accepts unknown fields)
     */
    withOpen(typeName) {
      const td = this.schema.types.get(typeName);
      if (td) td.open = true;
      return this;
    }
    /**
     * Build and return the schema
     */
    build() {
      this.schema.computeHash();
      return this.schema;
    }
  };
  var t = {
    null: () => ({ kind: "null" }),
    bool: () => ({ kind: "bool" }),
    int: () => ({ kind: "int" }),
    float: () => ({ kind: "float" }),
    str: () => ({ kind: "str" }),
    bytes: () => ({ kind: "bytes" }),
    time: () => ({ kind: "time" }),
    id: () => ({ kind: "id" }),
    list: (elem) => ({ kind: "list", elem }),
    map: (keyType, valType) => ({ kind: "map", keyType, valType }),
    ref: (name) => ({ kind: "ref", name })
  };

  // src/json.ts
  var hasOwnProperty = Object.prototype.hasOwnProperty;
  function hasOwn(obj, key) {
    return hasOwnProperty.call(obj, key);
  }
  function createJsonObject() {
    return /* @__PURE__ */ Object.create(null);
  }
  function fromJson(json, options = {}) {
    const { schema, typeName, parseDates = true, parseRefs = true } = options;
    return convertValue(json, schema, typeName, parseDates, parseRefs);
  }
  function convertValue(v, schema, typeName, parseDates, parseRefs) {
    if (v === null || v === void 0) {
      return GValue.null();
    }
    if (typeof v === "boolean") {
      return GValue.bool(v);
    }
    if (typeof v === "number") {
      if (Number.isInteger(v)) {
        return GValue.int(v);
      }
      return GValue.float(v);
    }
    if (typeof v === "string") {
      if (parseRefs && v.startsWith("^")) {
        const rest = v.slice(1);
        const colonIdx = rest.indexOf(":");
        if (colonIdx > 0) {
          return GValue.id(rest.slice(0, colonIdx), rest.slice(colonIdx + 1));
        }
        return GValue.id("", rest);
      }
      if (parseDates && isIsoDateString(v)) {
        const date = new Date(v);
        if (!isNaN(date.getTime())) {
          return GValue.time(date);
        }
      }
      return GValue.str(v);
    }
    if (Array.isArray(v)) {
      const items = v.map((item) => convertValue(item, schema, void 0, parseDates, parseRefs));
      return GValue.list(...items);
    }
    if (typeof v === "object") {
      const obj = v;
      const typeMarker = hasOwn(obj, "$type") ? obj.$type : void 0;
      const refMarker = hasOwn(obj, "$ref") ? obj.$ref : void 0;
      const timeMarker = hasOwn(obj, "$time") ? obj.$time : void 0;
      const bytesMarker = hasOwn(obj, "$bytes") ? obj.$bytes : void 0;
      const tagMarker = hasOwn(obj, "$tag") ? obj.$tag : void 0;
      if (typeof typeMarker === "string") {
        const structTypeName = typeMarker;
        const td = schema?.getType(structTypeName);
        const fields = [];
        for (const [key, val] of Object.entries(obj)) {
          if (key === "$type") continue;
          const fieldDef = td?.fields?.find((f) => f.name === key || f.wireKey === key);
          const fieldTypeName = fieldDef?.type.kind === "ref" ? fieldDef.type.name : void 0;
          fields.push({
            key,
            value: convertValue(val, schema, fieldTypeName, parseDates, parseRefs)
          });
        }
        return GValue.struct(structTypeName, ...fields);
      }
      if (typeof refMarker === "string") {
        const ref = refMarker;
        const colonIdx = ref.indexOf(":");
        if (colonIdx > 0) {
          return GValue.id(ref.slice(0, colonIdx), ref.slice(colonIdx + 1));
        }
        return GValue.id("", ref);
      }
      if (typeof timeMarker === "string") {
        return GValue.time(new Date(timeMarker));
      }
      if (typeof bytesMarker === "string") {
        return GValue.bytes(base64ToBytes(bytesMarker));
      }
      if (typeof tagMarker === "string") {
        const value = hasOwn(obj, "$value") ? convertValue(obj.$value, schema, void 0, parseDates, parseRefs) : null;
        return GValue.sum(tagMarker, value);
      }
      if (typeName) {
        const td = schema?.getType(typeName);
        const fields = [];
        for (const [key, val] of Object.entries(obj)) {
          const fieldDef = td?.fields?.find((f) => f.name === key || f.wireKey === key);
          const fieldTypeName = fieldDef?.type.kind === "ref" ? fieldDef.type.name : void 0;
          fields.push({
            key,
            value: convertValue(val, schema, fieldTypeName, parseDates, parseRefs)
          });
        }
        return GValue.struct(typeName, ...fields);
      }
      const entries = [];
      for (const [key, val] of Object.entries(obj)) {
        entries.push({
          key,
          value: convertValue(val, schema, void 0, parseDates, parseRefs)
        });
      }
      return GValue.map(...entries);
    }
    throw new Error(`Unsupported JSON value type: ${typeof v}`);
  }
  function isIsoDateString(s) {
    return /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?/.test(s);
  }
  function base64ToBytes(b64) {
    if (typeof atob === "function") {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      return bytes;
    }
    return new Uint8Array(Buffer.from(b64, "base64"));
  }
  function toJson(gv, options = {}) {
    const {
      includeTypeMarkers = false,
      compactRefs = true,
      formatDates = true,
      useWireKeys = false,
      schema
    } = options;
    return convertToJson(gv, includeTypeMarkers, compactRefs, formatDates, useWireKeys, schema);
  }
  function convertToJson(gv, includeTypeMarkers, compactRefs, formatDates, useWireKeys, schema) {
    switch (gv.type) {
      case "null":
        return null;
      case "bool":
        return gv.asBool();
      case "int":
        return gv.asInt();
      case "float":
        return gv.asFloat();
      case "str":
        return gv.asStr();
      case "bytes": {
        const bytes = gv.asBytes();
        const b64 = bytesToBase64(bytes);
        const result = createJsonObject();
        result.$bytes = b64;
        return result;
      }
      case "time": {
        const date = gv.asTime();
        if (formatDates) {
          return date.toISOString();
        }
        const result = createJsonObject();
        result.$time = date.toISOString();
        return result;
      }
      case "id": {
        const ref = gv.asId();
        const refStr = ref.prefix ? `${ref.prefix}:${ref.value}` : ref.value;
        if (compactRefs) {
          return `^${refStr}`;
        }
        const result = createJsonObject();
        result.$ref = refStr;
        return result;
      }
      case "list": {
        return gv.asList().map(
          (item) => convertToJson(item, includeTypeMarkers, compactRefs, formatDates, useWireKeys, schema)
        );
      }
      case "map": {
        const result = createJsonObject();
        for (const entry of gv.asMap()) {
          result[entry.key] = convertToJson(
            entry.value,
            includeTypeMarkers,
            compactRefs,
            formatDates,
            useWireKeys,
            schema
          );
        }
        return result;
      }
      case "struct": {
        const sv = gv.asStruct();
        const result = createJsonObject();
        if (includeTypeMarkers) {
          result.$type = sv.typeName;
        }
        const td = schema?.getType(sv.typeName);
        for (const field2 of sv.fields) {
          let key = field2.key;
          if (useWireKeys && td) {
            const fd = td.fields?.find((f) => f.name === field2.key);
            if (fd?.wireKey) {
              key = fd.wireKey;
            }
          }
          result[key] = convertToJson(
            field2.value,
            includeTypeMarkers,
            compactRefs,
            formatDates,
            useWireKeys,
            schema
          );
        }
        return result;
      }
      case "sum": {
        const sum = gv.asSum();
        const result = createJsonObject();
        result.$tag = sum.tag;
        if (sum.value === null) {
          return result;
        }
        result.$value = convertToJson(
          sum.value,
          includeTypeMarkers,
          compactRefs,
          formatDates,
          useWireKeys,
          schema
        );
        return result;
      }
    }
  }
  function bytesToBase64(bytes) {
    if (typeof btoa === "function") {
      let binary = "";
      for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      return btoa(binary);
    }
    return Buffer.from(bytes).toString("base64");
  }
  function parseJson(jsonStr, options = {}) {
    const json = JSON.parse(jsonStr);
    return fromJson(json, options);
  }
  function stringifyJson(gv, options = {}, indent) {
    const json = toJson(gv, options);
    return JSON.stringify(json, null, indent);
  }
  function normalizeJson(json, fromOptions = {}, toOptions = {}) {
    const gv = fromJson(json, fromOptions);
    return toJson(gv, toOptions);
  }

  // src/codec_primitives.ts
  var NULL_SYMBOL = "\u2205";
  function canonNull() {
    return NULL_SYMBOL;
  }
  function canonBool(v) {
    return v ? "t" : "f";
  }
  function canonInt(n) {
    if (n === 0) return "0";
    return String(Math.floor(n));
  }
  function normalizeExpStr(jsExp) {
    return jsExp.replace(/[eE]([+-]?)(\d+)$/, (_match, sign, digits) => {
      const signChar = sign === "-" ? "-" : "+";
      const paddedDigits = digits.length === 1 ? "0" + digits : digits;
      return "e" + signChar + paddedDigits;
    });
  }
  function decimalToGoExp(absF) {
    let expStr = absF.toExponential();
    expStr = expStr.replace(/\.?0+(e)/, "$1");
    return normalizeExpStr(expStr);
  }
  function canonFloat(f) {
    if (Number.isNaN(f)) return "NaN";
    if (f === Infinity) return "Inf";
    if (f === -Infinity) return "-Inf";
    if (f === 0 || Object.is(f, -0)) return "0.0";
    const absF = Math.abs(f);
    const neg = f < 0;
    const jsStr = String(absF);
    let s;
    if (jsStr.includes("e") || jsStr.includes("E")) {
      s = normalizeExpStr(jsStr);
    } else {
      const E = Math.floor(Math.log10(absF));
      if (E >= 6 || E <= -5) {
        s = decimalToGoExp(absF);
      } else {
        s = jsStr;
        if (!s.includes(".") && !s.includes("e")) {
          s = s + ".0";
        }
      }
    }
    return neg ? "-" + s : s;
  }
  function canonString(s) {
    if (isBareSafe(s)) {
      return s;
    }
    return quoteString(s);
  }
  function isLetter(c) {
    return c >= 65 && c <= 90 || c >= 97 && c <= 122;
  }
  function isDigit(c) {
    return c >= 48 && c <= 57;
  }
  function isBareSafe(s) {
    if (s.length === 0) return false;
    if (["t", "f", "_", "true", "false", "null", "none", "nil", "struct", "sum", "list", "map", "NaN", "Inf"].includes(s)) {
      return false;
    }
    const first = s.charCodeAt(0);
    if (!isLetter(first) && first !== 95) return false;
    for (let i = 1; i < s.length; i++) {
      const c = s.charCodeAt(i);
      if (!isLetter(c) && !isDigit(c) && c !== 95) {
        return false;
      }
    }
    return true;
  }
  function isRefPartChar(c) {
    return isLetter(c) || isDigit(c) || c === 95 || c === 45 || c === 46;
  }
  function isRefSafe(s) {
    if (s.length === 0) return false;
    const colonIdx = s.indexOf(":");
    if (colonIdx < 0) {
      for (let i = 0; i < s.length; i++) {
        if (!isRefPartChar(s.charCodeAt(i))) return false;
      }
      return true;
    }
    const prefix = s.slice(0, colonIdx);
    const value = s.slice(colonIdx + 1);
    for (let i = 0; i < prefix.length; i++) {
      if (!isRefPartChar(prefix.charCodeAt(i))) return false;
    }
    for (let i = 0; i < value.length; i++) {
      const c = value.charCodeAt(i);
      if (c === 58 || !isRefPartChar(c)) return false;
    }
    return true;
  }
  function quoteString(s) {
    let result = '"';
    for (const ch of s) {
      switch (ch) {
        case "\\":
          result += "\\\\";
          break;
        case '"':
          result += '\\"';
          break;
        case "\n":
          result += "\\n";
          break;
        case "\r":
          result += "\\r";
          break;
        case "	":
          result += "\\t";
          break;
        default:
          if (ch.charCodeAt(0) < 32) {
            result += "\\u" + ch.charCodeAt(0).toString(16).padStart(4, "0");
          } else {
            result += ch;
          }
      }
    }
    return result + '"';
  }

  // src/emit.ts
  function canonRef(ref) {
    const full = ref.prefix ? `${ref.prefix}:${ref.value}` : ref.value;
    if (isRefSafe(full)) {
      return `^${full}`;
    }
    return `^${quoteString(full)}`;
  }
  function canonTime(d) {
    const ms = d.getUTCMilliseconds();
    if (ms === 0) {
      return d.toISOString().replace(/\.\d{3}Z$/, "Z");
    }
    const msStr = ms.toString().padStart(3, "0").replace(/0+$/, "");
    return d.toISOString().replace(/\.\d{3}Z$/, "." + msStr + "Z");
  }
  function maskToBinary(mask) {
    let hi = -1;
    for (let i = mask.length - 1; i >= 0; i--) {
      if (mask[i]) {
        hi = i;
        break;
      }
    }
    if (hi === -1) return "0b0";
    let result = "0b";
    for (let i = hi; i >= 0; i--) {
      result += mask[i] ? "1" : "0";
    }
    return result;
  }
  function emit(gv, options = {}) {
    return emitValue(gv, options);
  }
  function emitValue(gv, opts) {
    switch (gv.type) {
      case "null":
        return canonNull();
      case "bool":
        return canonBool(gv.asBool());
      case "int":
        return canonInt(gv.asInt());
      case "float":
        return canonFloat(gv.asFloat());
      case "str":
        return canonString(gv.asStr());
      case "bytes":
        return "b64" + quoteString(bytesToBase642(gv.asBytes()));
      case "time":
        return canonTime(gv.asTime());
      case "id":
        return canonRef(gv.asId());
      case "list":
        return emitList(gv, opts);
      case "map":
        return emitMap(gv, opts);
      case "struct":
        return emitStruct(gv, opts);
      case "sum":
        return emitSum(gv, opts);
    }
  }
  function emitList(gv, opts) {
    const items = gv.asList().map((v) => emitValue(v, opts));
    return "[" + items.join(" ") + "]";
  }
  function emitMap(gv, opts) {
    const parts = [];
    for (const entry of gv.asMap()) {
      parts.push(`${canonString(entry.key)}:${emitValue(entry.value, opts)}`);
    }
    return "{" + parts.join(" ") + "}";
  }
  function emitStruct(gv, opts) {
    const sv = gv.asStruct();
    const parts = [];
    const td = opts.schema?.getType(sv.typeName);
    for (const field2 of sv.fields) {
      let key = field2.key;
      if (opts.keyMode === "wire" && td) {
        const fd = td.fields?.find((f) => f.name === field2.key);
        if (fd?.wireKey) key = fd.wireKey;
      } else if (opts.keyMode === "fid" && td) {
        const fd = td.fields?.find((f) => f.name === field2.key);
        if (fd) key = `#${fd.fid}`;
      }
      parts.push(`${canonString(key)}=${emitValue(field2.value, opts)}`);
    }
    return `${sv.typeName}{${parts.join(" ")}}`;
  }
  function emitSum(gv, opts) {
    const sum = gv.asSum();
    if (sum.value === null) {
      return `${sum.tag}()`;
    }
    if (sum.value.type === "struct") {
      return `${sum.tag}${emitStruct(sum.value, opts).slice(sum.value.asStruct().typeName.length)}`;
    }
    return `${sum.tag}(${emitValue(sum.value, opts)})`;
  }
  function emitPacked(gv, schema, options = {}) {
    if (gv.type !== "struct") {
      throw new Error("packed encoding requires struct value");
    }
    const sv = gv.asStruct();
    const td = schema.getType(sv.typeName);
    if (!td || td.kind !== "struct") {
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
    if (optFields.length === 0) return false;
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
        parts.push(canonNull());
        continue;
      }
      if (!fd.optional && val === null) {
        throw new Error(`missing required field: ${td.name}.${fd.name}`);
      }
      parts.push(emitPackedValue(val, schema, opts));
    }
    return `${td.name}@(${parts.join(" ")})`;
  }
  function emitPackedBitmap(gv, td, schema, opts) {
    const reqFields = schema.requiredFieldsByFid(td.name);
    const optFields = schema.optionalFieldsByFid(td.name);
    const mask = [];
    for (const fd of optFields) {
      const val = getFieldValue(gv, fd);
      mask.push(isFieldPresent(val, fd));
    }
    const parts = [];
    for (const fd of reqFields) {
      const val = getFieldValue(gv, fd);
      if (val === null) {
        throw new Error(`missing required field: ${td.name}.${fd.name}`);
      }
      parts.push(emitPackedValue(val, schema, opts));
    }
    for (let i = 0; i < optFields.length; i++) {
      if (!mask[i]) continue;
      const val = getFieldValue(gv, optFields[i]);
      parts.push(emitPackedValue(val, schema, opts));
    }
    return `${td.name}@{bm=${maskToBinary(mask)}}(${parts.join(" ")})`;
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
    if (val === null) return false;
    if (val.type === "null" && fd.optional && !fd.keepNull) return false;
    return true;
  }
  function emitPackedValue(gv, schema, opts) {
    switch (gv.type) {
      case "null":
        return canonNull();
      case "bool":
        return canonBool(gv.asBool());
      case "int":
        return canonInt(gv.asInt());
      case "float":
        return canonFloat(gv.asFloat());
      case "str":
        return canonString(gv.asStr());
      case "bytes":
        return "b64" + quoteString(bytesToBase642(gv.asBytes()));
      case "time":
        return canonTime(gv.asTime());
      case "id":
        return canonRef(gv.asId());
      case "list": {
        const items = gv.asList().map((v) => emitPackedValue(v, schema, opts));
        return "[" + items.join(" ") + "]";
      }
      case "map": {
        const parts = [];
        for (const entry of gv.asMap()) {
          parts.push(`${canonString(entry.key)}:${emitPackedValue(entry.value, schema, opts)}`);
        }
        return "{" + parts.join(" ") + "}";
      }
      case "struct": {
        const sv = gv.asStruct();
        const td = schema.getType(sv.typeName);
        if (td?.packEnabled) {
          return emitPacked(gv, schema, opts);
        }
        return emitStruct(gv, { ...opts, schema });
      }
      case "sum": {
        const sum = gv.asSum();
        if (sum.value === null) {
          return `${sum.tag}()`;
        }
        return `${sum.tag}(${emitPackedValue(sum.value, schema, opts)})`;
      }
    }
  }
  function emitTabular(gv, schema, options = {}) {
    if (gv.type !== "list") {
      throw new Error("tabular encoding requires list value");
    }
    const list = gv.asList();
    if (list.length === 0) {
      return "[]";
    }
    const first = list[0];
    if (first.type !== "struct") {
      throw new Error("tabular encoding requires list of structs");
    }
    const typeName = first.asStruct().typeName;
    for (let i = 1; i < list.length; i++) {
      if (list[i].type !== "struct" || list[i].asStruct().typeName !== typeName) {
        throw new Error("all elements must be same type struct");
      }
    }
    const td = schema.getType(typeName);
    if (!td) {
      throw new Error(`unknown type: ${typeName}`);
    }
    const fields = schema.fieldsByFid(typeName);
    const keyMode = options.keyMode || "wire";
    const indent = options.indentPrefix || "";
    const cols = fields.map((fd) => {
      if (keyMode === "wire" && fd.wireKey) return fd.wireKey;
      if (keyMode === "fid") return `#${fd.fid}`;
      return fd.name;
    });
    let result = `@tab ${typeName} [${cols.join(" ")}]
`;
    for (const row of list) {
      result += indent;
      const cells = [];
      for (const fd of fields) {
        const val = getFieldValue(row, fd);
        if (!isFieldPresent(val, fd)) {
          cells.push(canonNull());
        } else {
          cells.push(emitPackedValue(val, schema, options));
        }
      }
      result += cells.join(" ") + "\n";
    }
    result += "@end";
    return result;
  }
  function emitHeader(options = {}) {
    const parts = ["@lyph", options.version || "v2"];
    if (options.schemaId) {
      parts.push(`@schema#${options.schemaId}`);
    }
    if (options.mode && options.mode !== "auto") {
      parts.push(`@mode=${options.mode}`);
    }
    if (options.keyMode && options.keyMode !== "wire") {
      parts.push(`@keys=${options.keyMode}`);
    }
    if (options.target) {
      const ref = options.target.prefix ? `${options.target.prefix}:${options.target.value}` : options.target.value;
      parts.push(`@target=${ref}`);
    }
    return parts.join(" ");
  }
  function emitV2(gv, schema, options = {}) {
    const mode = options.mode || "auto";
    const tabThreshold = options.tabThreshold || 3;
    let selectedMode = mode;
    if (mode === "auto") {
      selectedMode = selectMode(gv, schema, tabThreshold);
    }
    let body;
    switch (selectedMode) {
      case "tabular":
        body = emitTabular(gv, schema, options);
        break;
      case "packed":
        body = emitPacked(gv, schema, options);
        break;
      default:
        body = emit(gv, { ...options, schema });
    }
    if (options.includeHeader) {
      const header = emitHeader({
        schemaId: schema.hash,
        mode: selectedMode,
        keyMode: options.keyMode
      });
      return header + "\n" + body;
    }
    return body;
  }
  function selectMode(gv, schema, tabThreshold) {
    if (gv.type === "list") {
      const list = gv.asList();
      if (list.length >= tabThreshold && list[0]?.type === "struct") {
        const typeName = list[0].asStruct().typeName;
        const td = schema.getType(typeName);
        if (td?.tabEnabled) {
          return "tabular";
        }
      }
    }
    if (gv.type === "struct") {
      const td = schema.getType(gv.asStruct().typeName);
      if (td?.packEnabled) {
        return "packed";
      }
    }
    return "struct";
  }
  function bytesToBase642(bytes) {
    if (typeof btoa === "function") {
      let binary = "";
      for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      return btoa(binary);
    }
    return Buffer.from(bytes).toString("base64");
  }

  // src/parse.ts
  function parsePacked(input, schema) {
    const parser = new PackedParser(input, schema);
    return parser.parse();
  }
  var MAX_PARSE_DEPTH = 128;
  var MAX_COLLECTION_LEN = 1e6;
  var MAX_STRING_LEN = 10 * 1024 * 1024;
  var PackedParser = class {
    constructor(input, schema) {
      this.pos = 0;
      this.depth = 0;
      this.input = input;
      this.schema = schema;
    }
    parse() {
      this.skipWhitespace();
      const typeName = this.parseTypeName();
      this.expect("@");
      const td = this.schema.getType(typeName);
      if (!td) {
        throw new Error(`unknown type: ${typeName}`);
      }
      let mask = null;
      if (this.peek() === "{") {
        mask = this.parseBitmapHeader();
      }
      this.expect("(");
      let value;
      if (mask) {
        value = this.parseBitmapValues(typeName, mask);
      } else {
        value = this.parseDenseValues(typeName);
      }
      this.expect(")");
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
        throw new Error("unexpected end of input");
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
      return c >= 65 && c <= 90 || c >= 97 && c <= 122 || c === 95;
    }
    isTypeNameCont(c) {
      return this.isTypeNameStart(c) || c >= 48 && c <= 57;
    }
    parseBitmapHeader() {
      this.expect("{");
      this.skipWhitespace();
      this.expectLiteral("bm=");
      this.expectLiteral("0b");
      const start = this.pos;
      while (this.pos < this.input.length && (this.input[this.pos] === "0" || this.input[this.pos] === "1")) {
        this.pos++;
      }
      const bits = this.input.slice(start, this.pos);
      if (bits.length === 0) {
        throw new Error("empty bitmap");
      }
      const mask = [];
      for (let i = bits.length - 1; i >= 0; i--) {
        mask.push(bits[i] === "1");
      }
      this.skipWhitespace();
      this.expect("}");
      return mask;
    }
    parseDenseValues(typeName) {
      const fields = this.schema.fieldsByFid(typeName);
      const entries = [];
      for (let i = 0; i < fields.length; i++) {
        const fd = fields[i];
        this.skipWhitespace();
        if (this.peek() === ")") {
          for (let j = i; j < fields.length; j++) {
            entries.push({ key: fields[j].name, value: GValue.null() });
          }
          break;
        }
        const val = this.parseValue(fd.type.kind === "ref" ? fd.type.name : void 0);
        entries.push({ key: fd.name, value: val });
      }
      return GValue.struct(typeName, ...entries);
    }
    parseBitmapValues(typeName, mask) {
      const reqFields = this.schema.requiredFieldsByFid(typeName);
      const optFields = this.schema.optionalFieldsByFid(typeName);
      const entries = [];
      for (const fd of reqFields) {
        this.skipWhitespace();
        const val = this.parseValue(fd.type.kind === "ref" ? fd.type.name : void 0);
        entries.push({ key: fd.name, value: val });
      }
      for (let i = 0; i < optFields.length; i++) {
        const fd = optFields[i];
        if (i < mask.length && mask[i]) {
          this.skipWhitespace();
          const val = this.parseValue(fd.type.kind === "ref" ? fd.type.name : void 0);
          entries.push({ key: fd.name, value: val });
        } else {
          entries.push({ key: fd.name, value: GValue.null() });
        }
      }
      return GValue.struct(typeName, ...entries);
    }
    parseValue(typeHint) {
      this.depth++;
      if (this.depth > MAX_PARSE_DEPTH) {
        throw new Error(`maximum nesting depth exceeded (${MAX_PARSE_DEPTH})`);
      }
      try {
        return this.parseValueInner(typeHint);
      } finally {
        this.depth--;
      }
    }
    parseValueInner(typeHint) {
      this.skipWhitespace();
      const c = this.peek();
      if (c === "\u2205") {
        this.pos++;
        return GValue.null();
      }
      if (c === "t") {
        if (this.tryLiteral("true") || this.tryLiteral("t")) {
          return GValue.bool(true);
        }
        return this.parseBareString();
      }
      if (c === "f") {
        if (this.tryLiteral("false") || this.tryLiteral("f")) {
          return GValue.bool(false);
        }
        return this.parseBareString();
      }
      if (c === '"') {
        return this.parseQuotedString();
      }
      if (c === "^") {
        return this.parseRef();
      }
      if (c === "[") {
        return this.parseList();
      }
      if (c === "{") {
        return this.parseMap();
      }
      if (c === "b" && this.input.startsWith('b64"', this.pos)) {
        return this.parseBytes();
      }
      if (c === "-" || c >= "0" && c <= "9") {
        return this.parseNumberOrTime();
      }
      if (this.isTypeNameStart(c.charCodeAt(0))) {
        const saved = this.pos;
        const name = this.parseTypeName();
        if (this.peek() === "@") {
          this.pos = saved;
          return this.parseNestedPacked();
        }
        return GValue.str(name);
      }
      throw new Error(`unexpected character at pos ${this.pos}: ${c}`);
    }
    parseNestedPacked() {
      const typeName = this.parseTypeName();
      this.expect("@");
      const td = this.schema.getType(typeName);
      if (!td) {
        throw new Error(`unknown nested type: ${typeName}`);
      }
      let mask = null;
      if (this.peek() === "{") {
        mask = this.parseBitmapHeader();
      }
      this.expect("(");
      let value;
      if (mask) {
        value = this.parseBitmapValues(typeName, mask);
      } else {
        value = this.parseDenseValues(typeName);
      }
      this.expect(")");
      return value;
    }
    parseNumberOrTime() {
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
      return GValue.time(date);
    }
    parseNumber() {
      const start = this.pos;
      const match = /^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(this.input.slice(this.pos));
      if (!match) {
        throw new Error(`invalid number at pos ${start}`);
      }
      const numStr = match[0];
      const next = this.input[this.pos + numStr.length] ?? "";
      if (next !== "" && !this.isTokenBoundary(next)) {
        throw new Error(`invalid numeric token at pos ${start}`);
      }
      this.pos += numStr.length;
      const num = Number(numStr);
      if (!Number.isFinite(num)) {
        throw new Error(`invalid number at pos ${start}`);
      }
      if (numStr.includes(".") || numStr.includes("e") || numStr.includes("E")) {
        return GValue.float(num);
      }
      const intVal = parseInt(numStr, 10);
      if (!Number.isSafeInteger(intVal)) {
        throw new Error(`integer exceeds safe range at pos ${start}: ${numStr}`);
      }
      return GValue.int(intVal);
    }
    parseQuotedString() {
      this.expect('"');
      let result = "";
      while (this.pos < this.input.length) {
        const c = this.input[this.pos];
        if (c === '"') {
          this.pos++;
          return GValue.str(result);
        }
        if (result.length >= MAX_STRING_LEN) {
          throw new Error(`string exceeds maximum length (${MAX_STRING_LEN})`);
        }
        if (c === "\\" && this.pos + 1 < this.input.length) {
          this.pos++;
          switch (this.input[this.pos]) {
            case "n":
              result += "\n";
              break;
            case "r":
              result += "\r";
              break;
            case "t":
              result += "	";
              break;
            case "\\":
              result += "\\";
              break;
            case '"':
              result += '"';
              break;
            case "u": {
              const hex = this.input.slice(this.pos + 1, this.pos + 5);
              if (hex.length < 4 || !/^[0-9a-fA-F]{4}$/.test(hex)) {
                throw new Error(`invalid \\u escape at pos ${this.pos}`);
              }
              result += String.fromCharCode(parseInt(hex, 16));
              this.pos += 4;
              break;
            }
            default:
              result += this.input[this.pos];
          }
        } else {
          result += c;
        }
        this.pos++;
      }
      throw new Error("unterminated string");
    }
    // parseBytes decodes a b64"..." literal into a bytes value. The cursor is on
    // the leading 'b'. Invalid base64 is a hard error (never coerced to a string).
    parseBytes() {
      this.pos += 3;
      this.expect('"');
      const start = this.pos;
      while (this.pos < this.input.length && this.input[this.pos] !== '"') {
        this.pos++;
      }
      if (this.pos >= this.input.length) {
        throw new Error("unterminated bytes literal");
      }
      const b64 = this.input.slice(start, this.pos);
      this.pos++;
      return GValue.bytes(base64ToBytes2(b64));
    }
    parseBareString() {
      const start = this.pos;
      while (this.pos < this.input.length) {
        const c = this.input[this.pos];
        if (c === " " || c === ")" || c === "]" || c === "}" || c === "\n") {
          break;
        }
        this.pos++;
      }
      return GValue.str(this.input.slice(start, this.pos));
    }
    parseRef() {
      this.expect("^");
      if (this.peek() === '"') {
        const s = this.parseQuotedString().asStr();
        const colonIdx2 = s.indexOf(":");
        if (colonIdx2 > 0) {
          return GValue.id(s.slice(0, colonIdx2), s.slice(colonIdx2 + 1));
        }
        return GValue.id("", s);
      }
      const start = this.pos;
      while (this.pos < this.input.length) {
        const c = this.input[this.pos];
        if (c === " " || c === ")" || c === "]" || c === "}" || c === "\n") {
          break;
        }
        this.pos++;
      }
      const refStr = this.input.slice(start, this.pos);
      const colonIdx = refStr.indexOf(":");
      if (colonIdx > 0) {
        return GValue.id(refStr.slice(0, colonIdx), refStr.slice(colonIdx + 1));
      }
      return GValue.id("", refStr);
    }
    parseList() {
      this.expect("[");
      const items = [];
      while (true) {
        this.skipWhitespace();
        if (this.peek() === "]") {
          this.pos++;
          return GValue.list(...items);
        }
        if (items.length >= MAX_COLLECTION_LEN) {
          throw new Error(`list exceeds maximum length (${MAX_COLLECTION_LEN})`);
        }
        items.push(this.parseValue());
      }
    }
    parseMap() {
      this.expect("{");
      const entries = [];
      while (true) {
        this.skipWhitespace();
        if (this.peek() === "}") {
          this.pos++;
          return GValue.map(...entries);
        }
        if (entries.length >= MAX_COLLECTION_LEN) {
          throw new Error(`map exceeds maximum length (${MAX_COLLECTION_LEN})`);
        }
        const key = this.parseValue().asStr();
        this.skipWhitespace();
        if (this.peek() !== ":" && this.peek() !== "=") {
          throw new Error(`expected ':' or '=' after map key`);
        }
        this.pos++;
        const value = this.parseValue();
        const existing = entries.findIndex((e) => e.key === key);
        if (existing >= 0) {
          entries[existing].value = value;
        } else {
          entries.push({ key, value });
        }
      }
    }
    skipWhitespace() {
      while (this.pos < this.input.length) {
        const c = this.input[this.pos];
        if (c !== " " && c !== "	" && c !== "\n" && c !== "\r") break;
        this.pos++;
      }
    }
    peek() {
      return this.pos < this.input.length ? this.input[this.pos] : "";
    }
    isTokenBoundary(c) {
      return c === "" || c === " " || c === "	" || c === "\n" || c === "\r" || c === ")" || c === "]" || c === "}";
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
        const next = this.input.charCodeAt(this.pos + s.length);
        if (this.isTypeNameCont(next)) {
          return false;
        }
        this.pos += s.length;
        return true;
      }
      return false;
    }
  };
  function parseHeader(input) {
    const trimmed = input.trim();
    if (!trimmed.startsWith("@lyph") && !trimmed.startsWith("@glyph")) {
      return null;
    }
    const header = { version: "v2" };
    const tokens = tokenizeHeader(trimmed);
    for (let i = 0; i < tokens.length; i++) {
      const tok = tokens[i];
      if (tok === "@lyph" || tok === "@glyph") {
        if (i + 1 < tokens.length && !tokens[i + 1].startsWith("@")) {
          header.version = tokens[++i];
        }
        continue;
      }
      if (tok.startsWith("@schema#")) {
        header.schemaId = tok.slice(8);
        continue;
      }
      if (tok.startsWith("@mode=")) {
        header.mode = tok.slice(6);
        continue;
      }
      if (tok.startsWith("@keys=")) {
        header.keyMode = tok.slice(6);
        continue;
      }
      if (tok.startsWith("@target=")) {
        const ref = tok.slice(8);
        const colonIdx = ref.indexOf(":");
        if (colonIdx > 0) {
          header.target = { prefix: ref.slice(0, colonIdx), value: ref.slice(colonIdx + 1) };
        } else {
          header.target = { prefix: "", value: ref };
        }
        continue;
      }
    }
    return header;
  }
  function tokenizeHeader(input) {
    const tokens = [];
    let current = "";
    let inQuote = false;
    for (const c of input) {
      if (c === '"') {
        inQuote = !inQuote;
        current += c;
      } else if (c === " " && !inQuote) {
        if (current) {
          tokens.push(current);
          current = "";
        }
      } else {
        current += c;
      }
    }
    if (current) tokens.push(current);
    return tokens;
  }
  function parseTabular(input, schema) {
    const lines = input.split("\n");
    if (lines.length === 0) {
      throw new Error("empty tabular input");
    }
    const headerLine = lines[0].trim();
    const { typeName, columns } = parseTabularHeader(headerLine);
    const td = schema.getType(typeName);
    if (!td) {
      throw new Error(`unknown type: ${typeName}`);
    }
    if (!td.fields || td.fields.length === 0) {
      throw new Error(`type ${typeName} has no fields`);
    }
    const fieldMap = /* @__PURE__ */ new Map();
    for (const fd of td.fields) {
      fieldMap.set(fd.name, fd);
      if (fd.wireKey) fieldMap.set(fd.wireKey, fd);
      fieldMap.set(`#${fd.fid}`, fd);
    }
    const columnFields = columns.map((col) => {
      const fd = fieldMap.get(col);
      if (!fd) {
        throw new Error(`unknown column: ${col}`);
      }
      return fd;
    });
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line === "" || line.startsWith("#")) continue;
      if (line === "@end") break;
      const row = parseTabularRow(line, typeName, columnFields, schema);
      rows.push(row);
    }
    return { typeName, columns, rows };
  }
  function parseTabularHeader(line) {
    if (!line.startsWith("@tab")) {
      throw new Error("tabular must start with @tab");
    }
    const rest = line.slice(4).trim();
    let pos = 0;
    while (pos < rest.length && rest[pos] !== " " && rest[pos] !== "[") {
      pos++;
    }
    const typeName = rest.slice(0, pos);
    if (!typeName) {
      throw new Error("missing type name after @tab");
    }
    while (pos < rest.length && rest[pos] !== "[") pos++;
    if (pos >= rest.length) {
      throw new Error("missing column list in tabular header");
    }
    pos++;
    const colStart = pos;
    while (pos < rest.length && rest[pos] !== "]") pos++;
    const colStr = rest.slice(colStart, pos);
    const columns = colStr.trim().split(/\s+/).filter((c) => c.length > 0);
    return { typeName, columns };
  }
  function parseTabularRow(line, typeName, columnFields, schema) {
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
      } else {
        value = parseScalarValue(token);
      }
      entries.push({ key: fd.name, value });
    }
    return GValue.struct(typeName, ...entries);
  }
  function tokenizeRow(line) {
    const tokens = [];
    let pos = 0;
    while (pos < line.length) {
      while (pos < line.length && (line[pos] === " " || line[pos] === "	")) pos++;
      if (pos >= line.length) break;
      const start = pos;
      const c = line[pos];
      if (c === '"') {
        pos++;
        while (pos < line.length && line[pos] !== '"') {
          if (line[pos] === "\\") pos++;
          pos++;
        }
        pos++;
      } else if (c === "[") {
        let depth = 1;
        pos++;
        while (pos < line.length && depth > 0) {
          if (line[pos] === "[") depth++;
          else if (line[pos] === "]") depth--;
          pos++;
        }
      } else if (c === "{") {
        let depth = 1;
        pos++;
        while (pos < line.length && depth > 0) {
          if (line[pos] === "{") depth++;
          else if (line[pos] === "}") depth--;
          pos++;
        }
      } else {
        while (pos < line.length) {
          const ch = line[pos];
          if (ch === " " || ch === "	") break;
          if (ch === "(") {
            let depth = 1;
            pos++;
            while (pos < line.length && depth > 0) {
              if (line[pos] === "(") depth++;
              else if (line[pos] === ")") depth--;
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
    const atIdx = s.indexOf("@");
    if (atIdx <= 0) return false;
    if (atIdx + 1 >= s.length) return false;
    const next = s[atIdx + 1];
    return next === "(" || next === "{";
  }
  function parseScalarValue(s) {
    s = s.trim();
    if (s === "\u2205" || s === "null" || s === "nil" || s === "none") {
      return GValue.null();
    }
    if (s === "t" || s === "true") return GValue.bool(true);
    if (s === "f" || s === "false") return GValue.bool(false);
    if (s.startsWith("^")) {
      const ref = s.slice(1);
      if (ref.startsWith('"')) {
        const inner = ref.slice(1, -1);
        const colonIdx2 = inner.indexOf(":");
        if (colonIdx2 > 0) {
          return GValue.id(inner.slice(0, colonIdx2), inner.slice(colonIdx2 + 1));
        }
        return GValue.id("", inner);
      }
      const colonIdx = ref.indexOf(":");
      if (colonIdx > 0) {
        const first = ref.slice(0, colonIdx);
        const second = ref.slice(colonIdx + 1);
        return GValue.id(first, second);
      }
      return GValue.id("", ref);
    }
    if (s.startsWith('b64"') && s.endsWith('"')) {
      return GValue.bytes(base64ToBytes2(s.slice(4, -1)));
    }
    if (s.startsWith('"')) {
      return parseQuotedScalar(s);
    }
    if (/^\d{4}-\d{2}-\d{2}T/.test(s)) {
      return GValue.time(new Date(s));
    }
    if (/^-?\d/.test(s)) {
      if (s.includes(".") || s.includes("e") || s.includes("E")) {
        return GValue.float(parseFloat(s));
      }
      const intVal = parseInt(s, 10);
      if (!Number.isSafeInteger(intVal)) {
        throw new Error(`integer exceeds safe range: ${s}`);
      }
      return GValue.int(intVal);
    }
    if (s.startsWith("[")) {
      return parseListScalar(s);
    }
    if (s.startsWith("{")) {
      return parseMapScalar(s);
    }
    return GValue.str(s);
  }
  function parseQuotedScalar(s) {
    let result = "";
    for (let i = 1; i < s.length - 1; i++) {
      if (s[i] === "\\" && i + 1 < s.length - 1) {
        i++;
        switch (s[i]) {
          case "n":
            result += "\n";
            break;
          case "r":
            result += "\r";
            break;
          case "t":
            result += "	";
            break;
          case "\\":
            result += "\\";
            break;
          case '"':
            result += '"';
            break;
          case "u": {
            const hex = s.slice(i + 1, i + 5);
            if (hex.length < 4 || !/^[0-9a-fA-F]{4}$/.test(hex)) {
              throw new Error("invalid \\u escape");
            }
            result += String.fromCharCode(parseInt(hex, 16));
            i += 4;
            break;
          }
          default:
            result += s[i];
        }
      } else {
        result += s[i];
      }
    }
    return GValue.str(result);
  }
  function base64ToBytes2(b64) {
    if (typeof atob === "function") {
      const binary = atob(b64);
      const out = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
      return out;
    }
    return new Uint8Array(Buffer.from(b64, "base64"));
  }
  function parseListScalar(s) {
    const inner = s.slice(1, -1).trim();
    if (!inner) return GValue.list();
    const tokens = tokenizeRow(inner);
    return GValue.list(...tokens.map((t2) => parseScalarValue(t2)));
  }
  function parseMapScalar(s) {
    const inner = s.slice(1, -1).trim();
    if (!inner) return GValue.map();
    const entries = [];
    const tokens = tokenizeRow(inner);
    for (const token of tokens) {
      const eqIdx = token.indexOf("=");
      const colonIdx = token.indexOf(":");
      const sepIdx = eqIdx > 0 ? eqIdx : colonIdx;
      if (sepIdx > 0) {
        const key = token.slice(0, sepIdx).trim();
        const valStr = token.slice(sepIdx + 1).trim();
        const value = parseScalarValue(valStr);
        const existing = entries.findIndex((e) => e.key === key);
        if (existing >= 0) {
          entries[existing].value = value;
        } else {
          entries.push({ key, value });
        }
      }
    }
    return GValue.map(...entries);
  }

  // src/loose.ts
  var MAX_JSON_DEPTH = 128;
  var MAX_COLLECTION_LEN2 = 1e6;
  var MAX_STRING_LEN2 = 10 * 1024 * 1024;
  var hasOwnProperty2 = Object.prototype.hasOwnProperty;
  function hasOwn2(obj, key) {
    return hasOwnProperty2.call(obj, key);
  }
  function createJsonObject2() {
    return /* @__PURE__ */ Object.create(null);
  }
  function defaultLooseCanonOpts() {
    return {
      autoTabular: true,
      minRows: 3,
      maxCols: 20,
      allowMissing: true,
      nullStyle: "underscore"
    };
  }
  function llmLooseCanonOpts() {
    return {
      autoTabular: true,
      minRows: 3,
      maxCols: 20,
      allowMissing: true,
      nullStyle: "underscore"
    };
  }
  function noTabularLooseCanonOpts() {
    return {
      autoTabular: false,
      minRows: 3,
      maxCols: 20,
      allowMissing: true,
      nullStyle: "symbol"
    };
  }
  var NULL_SYMBOL2 = "\u2205";
  var NULL_UNDERSCORE = "_";
  function canonNullWithStyle(style) {
    if (style === "underscore") {
      return NULL_UNDERSCORE;
    }
    return NULL_SYMBOL2;
  }
  function canonBool2(v) {
    return v ? "t" : "f";
  }
  function canonInt2(n) {
    if (n === 0) return "0";
    return String(Math.floor(n));
  }
  function canonFloat2(f) {
    if (Number.isNaN(f)) throw new Error("NaN not allowed in GLYPH-Loose");
    if (f === Infinity) throw new Error("Infinity not allowed in GLYPH-Loose");
    if (f === -Infinity) throw new Error("-Infinity not allowed in GLYPH-Loose");
    if (Object.is(f, -0)) return "0.0";
    if (f === 0) return "0.0";
    return goFormatFloat(f);
  }
  function goFormatFloat(f) {
    const absF = Math.abs(f);
    const neg = f < 0;
    const jsStr = String(absF);
    let s;
    if (jsStr.includes("e") || jsStr.includes("E")) {
      s = normalizeExpStr2(jsStr);
    } else {
      const E = Math.floor(Math.log10(absF));
      if (E >= 6 || E <= -5) {
        s = decimalToGoExp2(absF);
      } else {
        s = jsStr;
        if (!s.includes(".") && !s.includes("e")) {
          s = s + ".0";
        }
      }
    }
    return neg ? "-" + s : s;
  }
  function normalizeExpStr2(jsExp) {
    return jsExp.replace(/[eE]([+-]?)(\d+)$/, (_match, sign, digits) => {
      const signChar = sign === "-" ? "-" : "+";
      const paddedDigits = digits.length === 1 ? "0" + digits : digits;
      return "e" + signChar + paddedDigits;
    });
  }
  function decimalToGoExp2(absF) {
    let expStr = absF.toExponential();
    expStr = expStr.replace(/\.?0+(e)/, "$1");
    return normalizeExpStr2(expStr);
  }
  function canonString2(s) {
    if (isBareSafe2(s)) {
      return s;
    }
    return quoteString2(s);
  }
  function canonRef2(prefix, value) {
    const full = prefix ? `${prefix}:${value}` : value;
    if (isRefSafe2(full)) {
      return `^${full}`;
    }
    return `^${quoteString2(full)}`;
  }
  function canonTime2(d) {
    const ms = d.getUTCMilliseconds();
    if (ms === 0) {
      return d.toISOString().replace(/\.\d{3}Z$/, "Z");
    }
    const msStr = ms.toString().padStart(3, "0").replace(/0+$/, "");
    return d.toISOString().replace(/\.\d{3}Z$/, "." + msStr + "Z");
  }
  function canonBytes(bytes) {
    if (bytes.length === 0) {
      return 'b64""';
    }
    return "b64" + quoteString2(bytesToBase643(bytes));
  }
  function isBareSafe2(s) {
    if (s.length === 0) return false;
    if (["t", "f", "_", "true", "false", "null", "none", "nil", "struct", "sum", "list", "map", "NaN", "Inf"].includes(s)) {
      return false;
    }
    const first = s.charCodeAt(0);
    if (!(first >= 65 && first <= 90 || first >= 97 && first <= 122 || first === 95)) return false;
    for (let i = 1; i < s.length; i++) {
      const c = s.charCodeAt(i);
      if (!(c >= 65 && c <= 90 || c >= 97 && c <= 122 || c >= 48 && c <= 57 || c === 95)) {
        return false;
      }
    }
    return true;
  }
  function isRefPartChar2(c) {
    return c >= 65 && c <= 90 || c >= 97 && c <= 122 || c >= 48 && c <= 57 || c === 95 || c === 45 || c === 46;
  }
  function isRefSafe2(s) {
    if (s.length === 0) return false;
    const colonIdx = s.indexOf(":");
    if (colonIdx < 0) {
      for (let i = 0; i < s.length; i++) {
        if (!isRefPartChar2(s.charCodeAt(i))) return false;
      }
      return true;
    }
    const prefix = s.slice(0, colonIdx);
    const value = s.slice(colonIdx + 1);
    for (let i = 0; i < prefix.length; i++) {
      if (!isRefPartChar2(prefix.charCodeAt(i))) return false;
    }
    for (let i = 0; i < value.length; i++) {
      const c = value.charCodeAt(i);
      if (c === 58 || !isRefPartChar2(c)) return false;
    }
    return true;
  }
  function quoteString2(s) {
    let result = '"';
    for (const ch of s) {
      switch (ch) {
        case "\\":
          result += "\\\\";
          break;
        case '"':
          result += '\\"';
          break;
        case "\n":
          result += "\\n";
          break;
        case "\r":
          result += "\\r";
          break;
        case "	":
          result += "\\t";
          break;
        default:
          const code = ch.charCodeAt(0);
          if (code < 32) {
            result += "\\u" + code.toString(16).padStart(4, "0").toUpperCase();
          } else {
            result += ch;
          }
      }
    }
    return result + '"';
  }
  function bytesToBase643(bytes) {
    if (typeof btoa === "function") {
      let binary = "";
      for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      return btoa(binary);
    }
    return Buffer.from(bytes).toString("base64");
  }
  function canonicalizeLoose(v) {
    return canonicalizeLooseImpl(v, defaultLooseCanonOpts());
  }
  function canonicalizeLooseNoTabular(v) {
    return canonicalizeLooseWithOpts(v, noTabularLooseCanonOpts());
  }
  function canonicalizeLooseWithOpts(v, opts) {
    return canonicalizeLooseImpl(v, { ...defaultLooseCanonOpts(), ...opts });
  }
  function canonicalizeLooseImpl(v, opts) {
    switch (v.type) {
      case "null":
        return canonNullWithStyle(opts.nullStyle);
      case "bool":
        return canonBool2(v.asBool());
      case "int":
        return canonInt2(v.asInt());
      case "float":
        return canonFloat2(v.asFloat());
      case "str":
        return canonString2(v.asStr());
      case "bytes":
        return canonBytes(v.asBytes());
      case "time":
        return canonTime2(v.asTime());
      case "id": {
        const ref = v.asId();
        return canonRef2(ref.prefix, ref.value);
      }
      case "list":
        return canonListLooseWithOpts(v.asList(), opts);
      case "map":
        return canonMapLooseWithOpts(v.asMap(), opts);
      case "struct":
        return canonMapLooseWithOpts(v.asStruct().fields, opts);
      case "sum": {
        const sum = v.asSum();
        const entry = { key: sum.tag, value: sum.value ?? GValue.null() };
        return canonMapLooseWithOpts([entry], opts);
      }
    }
  }
  function canonListLooseWithOpts(items, opts) {
    if (items.length === 0) {
      return "[]";
    }
    if (opts.autoTabular) {
      const cols = detectTabular(items, opts);
      if (cols !== null) {
        return emitTabularLoose(items, cols, opts);
      }
    }
    const parts = items.map((v) => canonicalizeLooseImpl(v, opts));
    return "[" + parts.join(" ") + "]";
  }
  function detectTabular(items, opts) {
    const minRows = opts.minRows ?? 3;
    const maxCols = opts.maxCols ?? 20;
    const allowMissing = opts.allowMissing ?? true;
    if (items.length < minRows) {
      return null;
    }
    const allKeys = /* @__PURE__ */ new Set();
    const rowKeys = [];
    for (const item of items) {
      const entries = getMapEntries(item);
      if (entries === null) {
        return null;
      }
      const keys = /* @__PURE__ */ new Set();
      for (const e of entries) {
        allKeys.add(e.key);
        keys.add(e.key);
      }
      rowKeys.push(keys);
    }
    if (allKeys.size === 0 || allKeys.size > maxCols) {
      return null;
    }
    if (!allowMissing) {
      for (const keys of rowKeys) {
        if (keys.size !== allKeys.size) {
          return null;
        }
        for (const k of allKeys) {
          if (!keys.has(k)) {
            return null;
          }
        }
      }
    } else {
      let commonKeys = new Set(rowKeys[0]);
      for (let i = 1; i < rowKeys.length; i++) {
        const itemKeys = rowKeys[i];
        for (const k of commonKeys) {
          if (!itemKeys.has(k)) {
            commonKeys.delete(k);
          }
        }
      }
      if (commonKeys.size < allKeys.size / 2) {
        return null;
      }
    }
    const cols = [...allKeys].sort((a, b) => {
      const ca = canonString2(a);
      const cb = canonString2(b);
      return ca < cb ? -1 : ca > cb ? 1 : 0;
    });
    return cols;
  }
  function getMapEntries(v) {
    if (v.type === "map") {
      return v.asMap();
    }
    if (v.type === "struct") {
      return v.asStruct().fields;
    }
    return null;
  }
  function emitTabularLoose(items, cols, opts) {
    const lines = [];
    const headerCols = cols.map((c) => {
      if (opts.useCompactKeys && opts.keyDict) {
        const idx = opts.keyDict.indexOf(c);
        if (idx >= 0) {
          return `#${idx}`;
        }
      }
      return canonString2(c);
    }).join(" ");
    lines.push(`@tab _ rows=${items.length} cols=${cols.length} [${headerCols}]`);
    for (const item of items) {
      const entries = getMapEntries(item);
      const rowMap = /* @__PURE__ */ new Map();
      for (const e of entries) {
        rowMap.set(e.key, e.value);
      }
      const cells = [];
      for (const col of cols) {
        const val = rowMap.get(col);
        if (val === void 0) {
          cells.push(canonNullWithStyle(opts.nullStyle));
        } else {
          cells.push(escapeTabularCell(canonicalizeLooseImpl(val, opts)));
        }
      }
      lines.push("|" + cells.join("|") + "|");
    }
    lines.push("@end");
    return lines.join("\n");
  }
  function escapeTabularCell(s) {
    return s.replace(/\|/g, "\\|");
  }
  function unescapeTabularCell(s) {
    return s.replace(/\\\|/g, "|");
  }
  function parseTabularLoose(input) {
    const lines = input.split("\n").map((l) => l.trim()).filter((l) => l.length > 0);
    if (lines.length < 2) {
      throw new Error("tabular block requires at least header and @end");
    }
    const header = lines[0];
    if (!header.startsWith("@tab _")) {
      throw new Error("expected @tab _ header");
    }
    const cols = parseTabularLooseHeader(header);
    if (cols.length === 0) {
      throw new Error("no columns found in header");
    }
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i];
      if (line === "@end") {
        break;
      }
      const row = parseTabularLooseRow(line, cols);
      rows.push(row);
    }
    return { columns: cols, rows };
  }
  function parseTabularLooseHeader(line) {
    return parseTabularLooseHeaderWithMeta(line).keys;
  }
  function parseTabularLooseHeaderWithMeta(line) {
    let rest = line.slice(line.indexOf("_") + 1).trim();
    const meta = { rows: -1, cols: -1, keys: [] };
    while (!rest.startsWith("[") && rest.length > 0) {
      if (rest.startsWith("rows=")) {
        rest = rest.slice(5);
        const end2 = rest.search(/[\s\[]/);
        if (end2 === -1) {
          throw new Error("invalid rows= value");
        }
        const rowsVal = parseInt(rest.slice(0, end2), 10);
        if (!Number.isFinite(rowsVal) || rowsVal > Number.MAX_SAFE_INTEGER) {
          throw new Error("rows= value overflows safe integer range");
        }
        meta.rows = rowsVal;
        rest = rest.slice(end2).trim();
      } else if (rest.startsWith("cols=")) {
        rest = rest.slice(5);
        const end2 = rest.search(/[\s\[]/);
        if (end2 === -1) {
          throw new Error("invalid cols= value");
        }
        const colsVal = parseInt(rest.slice(0, end2), 10);
        if (!Number.isFinite(colsVal) || colsVal > Number.MAX_SAFE_INTEGER) {
          throw new Error("cols= value overflows safe integer range");
        }
        meta.cols = colsVal;
        rest = rest.slice(end2).trim();
      } else {
        const spaceIdx = rest.indexOf(" ");
        const bracketIdx = rest.indexOf("[");
        if (spaceIdx === -1 && bracketIdx === -1) {
          throw new Error(`expected '[' in header, got: ${rest}`);
        }
        if (spaceIdx >= 0 && (bracketIdx === -1 || spaceIdx < bracketIdx)) {
          rest = rest.slice(spaceIdx).trim();
        } else {
          break;
        }
      }
    }
    const start = rest.indexOf("[");
    const end = rest.lastIndexOf("]");
    if (start === -1 || end === -1 || end <= start) {
      throw new Error("malformed header: missing brackets");
    }
    const content = rest.slice(start + 1, end).trim();
    if (content.length === 0) {
      meta.keys = [];
    } else {
      meta.keys = parseSpaceSeparatedValues(content);
    }
    return meta;
  }
  function parseTabularLooseRow(line, cols) {
    if (!line.startsWith("|") || !line.endsWith("|")) {
      throw new Error("row must start and end with |");
    }
    const cells = splitTabularCells(line.slice(1, -1));
    const row = {};
    for (let i = 0; i < cols.length && i < cells.length; i++) {
      const cell = unescapeTabularCell(cells[i]);
      row[cols[i]] = parseLooseValue(cell);
    }
    return row;
  }
  function splitTabularCells(s) {
    const cells = [];
    let current = "";
    let i = 0;
    while (i < s.length) {
      if (s[i] === "\\" && i + 1 < s.length && s[i + 1] === "|") {
        current += "\\|";
        i += 2;
      } else if (s[i] === "|") {
        cells.push(current);
        current = "";
        i++;
      } else {
        current += s[i];
        i++;
      }
    }
    cells.push(current);
    return cells;
  }
  function parseSpaceSeparatedValues(s) {
    const values = [];
    let i = 0;
    while (i < s.length) {
      while (i < s.length && /\s/.test(s[i])) i++;
      if (i >= s.length) break;
      if (s[i] === '"') {
        const end = findClosingQuote(s, i);
        values.push(unquoteString(s.slice(i, end + 1)));
        i = end + 1;
      } else {
        let end = i;
        while (end < s.length && !/\s/.test(s[end])) end++;
        values.push(s.slice(i, end));
        i = end;
      }
    }
    return values;
  }
  function findClosingQuote(s, start) {
    let i = start + 1;
    while (i < s.length) {
      if (s[i] === "\\" && i + 1 < s.length) {
        i += 2;
      } else if (s[i] === '"') {
        return i;
      } else {
        i++;
      }
    }
    throw new Error("unclosed quote");
  }
  function parseLooseValue(s) {
    s = s.trim();
    if (s === "\u2205" || s === "_" || s === "null") return null;
    if (s === "t") return true;
    if (s === "f") return false;
    if (s === "NaN") return NaN;
    if (s === "Inf") return Infinity;
    if (s === "-Inf") return -Infinity;
    if (s.startsWith('"') && s.endsWith('"')) {
      return unquoteString(s);
    }
    const num = tryParseNumber(s);
    if (num !== null) return num;
    if (s.startsWith("{") && s.endsWith("}")) {
      return parseLooseMap(s);
    }
    if (s.startsWith("[") && s.endsWith("]")) {
      return parseLooseList(s);
    }
    if (s.startsWith("^")) {
      return s;
    }
    return s;
  }
  function tryParseNumber(s) {
    if (!/^-?\d/.test(s) && s !== "-0") return null;
    const n = Number(s);
    if (Number.isNaN(n)) return null;
    return n;
  }
  function unquoteString(s) {
    if (!s.startsWith('"') || !s.endsWith('"')) {
      return s;
    }
    let result = "";
    let i = 1;
    while (i < s.length - 1) {
      if (s[i] === "\\" && i + 1 < s.length - 1) {
        const next = s[i + 1];
        switch (next) {
          case "n":
            result += "\n";
            break;
          case "r":
            result += "\r";
            break;
          case "t":
            result += "	";
            break;
          case '"':
            result += '"';
            break;
          case "\\":
            result += "\\";
            break;
          case "u":
            if (i + 5 < s.length) {
              const hex = s.slice(i + 2, i + 6);
              result += String.fromCharCode(parseInt(hex, 16));
              i += 4;
            }
            break;
          default:
            result += next;
        }
        i += 2;
      } else {
        result += s[i];
        i++;
      }
    }
    return result;
  }
  function parseLooseMap(s) {
    const inner = s.slice(1, -1).trim();
    if (inner.length === 0) return {};
    const result = {};
    let i = 0;
    let entryCount = 0;
    while (i < inner.length) {
      while (i < inner.length && /\s/.test(inner[i])) i++;
      if (i >= inner.length) break;
      if (entryCount >= MAX_COLLECTION_LEN2) {
        throw new Error(`map too large (>${MAX_COLLECTION_LEN2} entries)`);
      }
      let key;
      if (inner[i] === '"') {
        const end = findClosingQuote(inner, i);
        key = unquoteString(inner.slice(i, end + 1));
        i = end + 1;
      } else {
        let end = i;
        while (end < inner.length && inner[end] !== "=" && !/\s/.test(inner[end])) end++;
        key = inner.slice(i, end);
        i = end;
      }
      while (i < inner.length && /\s/.test(inner[i])) i++;
      if (i >= inner.length || inner[i] !== "=") {
        throw new Error("expected = after key");
      }
      i++;
      while (i < inner.length && /\s/.test(inner[i])) i++;
      const valueEnd = findValueEnd(inner, i);
      const valueStr = inner.slice(i, valueEnd);
      result[key] = parseLooseValue(valueStr);
      i = valueEnd;
      entryCount++;
    }
    return result;
  }
  function parseLooseList(s) {
    const inner = s.slice(1, -1).trim();
    if (inner.length === 0) return [];
    const result = [];
    let i = 0;
    while (i < inner.length) {
      while (i < inner.length && /\s/.test(inner[i])) i++;
      if (i >= inner.length) break;
      if (result.length >= MAX_COLLECTION_LEN2) {
        throw new Error(`list too large (>${MAX_COLLECTION_LEN2} elements)`);
      }
      const valueEnd = findValueEnd(inner, i);
      const valueStr = inner.slice(i, valueEnd);
      result.push(parseLooseValue(valueStr));
      i = valueEnd;
    }
    return result;
  }
  function findValueEnd(s, start) {
    let i = start;
    let depth = 0;
    let inQuote = false;
    while (i < s.length) {
      if (inQuote) {
        if (s[i] === "\\" && i + 1 < s.length) {
          i += 2;
        } else if (s[i] === '"') {
          inQuote = false;
          i++;
        } else {
          i++;
        }
      } else {
        if (s[i] === '"') {
          inQuote = true;
          i++;
        } else if (s[i] === "{" || s[i] === "[") {
          depth++;
          i++;
        } else if (s[i] === "}" || s[i] === "]") {
          depth--;
          i++;
        } else if (/\s/.test(s[i]) && depth === 0) {
          break;
        } else {
          i++;
        }
      }
    }
    return i;
  }
  function canonMapLooseWithOpts(entries, opts) {
    if (entries.length === 0) {
      return "{}";
    }
    const sorted = [...entries].sort((a, b) => {
      const ka = canonString2(a.key);
      const kb = canonString2(b.key);
      return ka < kb ? -1 : ka > kb ? 1 : 0;
    });
    const parts = sorted.map((e) => {
      let keyStr;
      if (opts.useCompactKeys && opts.keyDict) {
        const idx = opts.keyDict.indexOf(e.key);
        if (idx >= 0) {
          keyStr = `#${idx}`;
        } else {
          keyStr = canonString2(e.key);
        }
      } else {
        keyStr = canonString2(e.key);
      }
      return `${keyStr}=${canonicalizeLooseImpl(e.value, opts)}`;
    });
    return "{" + parts.join(" ") + "}";
  }
  function fingerprintLoose(v) {
    const canonical = canonicalizeLooseNoTabular(v);
    const { createHash: createHash2 } = __require("crypto");
    return createHash2("sha256").update(canonical, "utf8").digest("hex");
  }
  function equalLoose(a, b) {
    return canonicalizeLooseNoTabular(a) === canonicalizeLooseNoTabular(b);
  }
  function canonicalizeLooseWithSchema(v, opts) {
    const fullOpts = { ...defaultLooseCanonOpts(), ...opts };
    const parts = [];
    if (fullOpts.schemaRef || fullOpts.keyDict && fullOpts.keyDict.length > 0) {
      parts.push(emitSchemaHeader(fullOpts));
    }
    parts.push(canonicalizeLooseImpl(v, fullOpts));
    return parts.join("\n");
  }
  function emitSchemaHeader(opts) {
    const parts = ["@schema"];
    if (opts.schemaRef) {
      parts[0] += `#${opts.schemaRef}`;
    }
    if (opts.keyDict && opts.keyDict.length > 0) {
      const keys = opts.keyDict.map((k) => canonString2(k)).join(" ");
      parts.push(`keys=[${keys}]`);
    }
    return parts.join(" ");
  }
  function buildKeyDictFromValue(v) {
    const keySet = /* @__PURE__ */ new Set();
    collectKeys(v, keySet);
    return [...keySet].sort();
  }
  function collectKeys(v, keySet) {
    if (v.type === "map") {
      for (const e of v.asMap()) {
        keySet.add(e.key);
        collectKeys(e.value, keySet);
      }
    } else if (v.type === "struct") {
      for (const f of v.asStruct().fields) {
        keySet.add(f.key);
        collectKeys(f.value, keySet);
      }
    } else if (v.type === "list") {
      for (const item of v.asList()) {
        collectKeys(item, keySet);
      }
    }
  }
  function parseSchemaHeader(line) {
    line = line.trim();
    if (!line.startsWith("@schema")) {
      throw new Error(`not a schema header: ${line}`);
    }
    let rest = line.slice("@schema".length);
    let schemaRef = "";
    let keyDict = [];
    if (rest.startsWith("#")) {
      rest = rest.slice(1);
      const end = rest.indexOf(" ");
      if (end === -1) {
        schemaRef = rest;
        return { schemaRef, keyDict };
      }
      schemaRef = rest.slice(0, end);
      rest = rest.slice(end).trim();
    }
    if (rest.startsWith("keys=")) {
      rest = rest.slice("keys=".length);
      if (!rest.startsWith("[")) {
        throw new Error(`keys= must be followed by []: ${rest}`);
      }
      const closeIdx = rest.indexOf("]");
      if (closeIdx === -1) {
        throw new Error(`missing ] in keys: ${rest}`);
      }
      const keysStr = rest.slice(1, closeIdx).trim();
      if (keysStr) {
        keyDict = keysStr.split(/\s+/);
      }
    }
    return { schemaRef, keyDict };
  }
  function fromJsonLoose(json, opts = {}, _depth = 0) {
    if (_depth > MAX_JSON_DEPTH) {
      throw new Error(`maximum nesting depth exceeded (${MAX_JSON_DEPTH})`);
    }
    if (json === null || json === void 0) {
      return GValue.null();
    }
    if (typeof json === "boolean") {
      return GValue.bool(json);
    }
    if (typeof json === "number") {
      if (!Number.isFinite(json)) {
        throw new Error("NaN/Infinity not allowed in GLYPH-Loose");
      }
      if (Number.isInteger(json) && Math.abs(json) <= Number.MAX_SAFE_INTEGER) {
        return GValue.int(json);
      }
      return GValue.float(json);
    }
    if (typeof json === "string") {
      if (json.length > MAX_STRING_LEN2) {
        throw new Error(`string too large (${json.length} > ${MAX_STRING_LEN2})`);
      }
      return GValue.str(json);
    }
    if (Array.isArray(json)) {
      if (json.length > MAX_COLLECTION_LEN2) {
        throw new Error(`list too large (${json.length} > ${MAX_COLLECTION_LEN2})`);
      }
      const items = json.map((item) => fromJsonLoose(item, opts, _depth + 1));
      return GValue.list(...items);
    }
    if (typeof json === "object") {
      const obj = json;
      const glyphMarker = hasOwn2(obj, "$glyph") ? obj.$glyph : void 0;
      if (opts.extended && typeof glyphMarker === "string") {
        return fromGlyphMarker(glyphMarker, obj);
      }
      const keys = Object.keys(obj);
      if (keys.length > MAX_COLLECTION_LEN2) {
        throw new Error(`map too large (${keys.length} > ${MAX_COLLECTION_LEN2})`);
      }
      const entries = [];
      for (const [key, val] of Object.entries(obj)) {
        entries.push({ key, value: fromJsonLoose(val, opts, _depth + 1) });
      }
      return GValue.map(...entries);
    }
    throw new Error(`Unsupported JSON value type: ${typeof json}`);
  }
  function fromGlyphMarker(markerType, obj) {
    switch (markerType) {
      case "time": {
        const value = obj.value;
        if (typeof value !== "string") {
          throw new Error("$glyph time marker missing value");
        }
        return GValue.time(new Date(value));
      }
      case "id": {
        const rawValue = obj.value;
        if (typeof rawValue !== "string") {
          throw new Error("$glyph id marker missing value");
        }
        let value = rawValue;
        if (value.startsWith("^")) {
          value = value.slice(1);
        }
        const colonIdx = value.indexOf(":");
        if (colonIdx > 0) {
          return GValue.id(value.slice(0, colonIdx), value.slice(colonIdx + 1));
        }
        return GValue.id("", value);
      }
      case "bytes": {
        const b64 = obj.base64;
        if (typeof b64 !== "string") {
          throw new Error("$glyph bytes marker missing base64");
        }
        return GValue.bytes(base64ToBytes3(b64));
      }
      default:
        throw new Error(`Unknown $glyph marker type: ${markerType}`);
    }
  }
  function base64ToBytes3(b64) {
    if (typeof atob === "function") {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      return bytes;
    }
    return new Uint8Array(Buffer.from(b64, "base64"));
  }
  function toJsonLoose(gv, opts = {}) {
    switch (gv.type) {
      case "null":
        return null;
      case "bool":
        return gv.asBool();
      case "int":
        return gv.asInt();
      case "float": {
        const f = gv.asFloat();
        if (!Number.isFinite(f)) {
          throw new Error("NaN/Infinity not allowed in JSON");
        }
        return f;
      }
      case "str":
        return gv.asStr();
      case "bytes": {
        const b64 = bytesToBase643(gv.asBytes());
        if (opts.extended) {
          const result = createJsonObject2();
          result.$glyph = "bytes";
          result.base64 = b64;
          return result;
        }
        return b64;
      }
      case "time": {
        const d = gv.asTime();
        const iso = canonTime2(d);
        if (opts.extended) {
          const result = createJsonObject2();
          result.$glyph = "time";
          result.value = iso;
          return result;
        }
        return iso;
      }
      case "id": {
        const ref = gv.asId();
        const refStr = `^${ref.prefix ? ref.prefix + ":" : ""}${ref.value}`;
        if (opts.extended) {
          const result = createJsonObject2();
          result.$glyph = "id";
          result.value = refStr;
          return result;
        }
        return refStr;
      }
      case "list":
        return gv.asList().map((v) => toJsonLoose(v, opts));
      case "map": {
        const result = createJsonObject2();
        for (const entry of gv.asMap()) {
          result[entry.key] = toJsonLoose(entry.value, opts);
        }
        return result;
      }
      case "struct": {
        const sv = gv.asStruct();
        const result = createJsonObject2();
        for (const field2 of sv.fields) {
          result[field2.key] = toJsonLoose(field2.value, opts);
        }
        return result;
      }
      case "sum": {
        const sum = gv.asSum();
        const result = createJsonObject2();
        result[sum.tag] = sum.value ? toJsonLoose(sum.value, opts) : null;
        return result;
      }
    }
  }
  function parseJsonLoose(jsonStr, opts = {}) {
    const json = JSON.parse(jsonStr);
    return fromJsonLoose(json, opts);
  }
  function stringifyJsonLoose(gv, opts = {}, indent) {
    const json = toJsonLoose(gv, opts);
    return JSON.stringify(json, null, indent);
  }
  function jsonEqual(a, b) {
    const va = JSON.parse(a);
    const vb = JSON.parse(b);
    return jsonValueEqual(va, vb);
  }
  function jsonValueEqual(a, b) {
    if (a === b) return true;
    if (a === null || b === null) return a === b;
    if (typeof a !== typeof b) return false;
    if (Array.isArray(a)) {
      if (!Array.isArray(b) || a.length !== b.length) return false;
      for (let i = 0; i < a.length; i++) {
        if (!jsonValueEqual(a[i], b[i])) return false;
      }
      return true;
    }
    if (typeof a === "object") {
      const objA = a;
      const objB = b;
      const keysA = Object.keys(objA);
      const keysB = Object.keys(objB);
      if (keysA.length !== keysB.length) return false;
      for (const key of keysA) {
        if (!hasOwn2(objB, key)) return false;
        if (!jsonValueEqual(objA[key], objB[key])) return false;
      }
      return true;
    }
    return false;
  }

  // src/stream/hash.ts
  async function sha256(data) {
    if (typeof crypto !== "undefined" && crypto.subtle) {
      const hash2 = await crypto.subtle.digest("SHA-256", data);
      return new Uint8Array(hash2);
    }
    const { createHash: createHash2 } = await import("crypto");
    const hash = createHash2("sha256").update(data).digest();
    return new Uint8Array(hash);
  }
  function sha256Sync(data) {
    const { createHash: createHash2 } = __require("crypto");
    const hash = createHash2("sha256").update(data).digest();
    return new Uint8Array(hash);
  }
  async function stateHashLoose(value) {
    const canonical = canonicalizeLoose(value);
    const encoder3 = new TextEncoder();
    return sha256(encoder3.encode(canonical));
  }
  function stateHashLooseSync(value) {
    const canonical = canonicalizeLoose(value);
    const encoder3 = new TextEncoder();
    return sha256Sync(encoder3.encode(canonical));
  }
  async function stateHashBytes(data) {
    return sha256(data);
  }
  function verifyBase(current, expected) {
    if (current.length !== expected.length) return false;
    for (let i = 0; i < current.length; i++) {
      if (current[i] !== expected[i]) return false;
    }
    return true;
  }
  function hashToHex(h) {
    const hex = "0123456789abcdef";
    let result = "";
    for (let i = 0; i < h.length; i++) {
      result += hex[h[i] >> 4];
      result += hex[h[i] & 15];
    }
    return result;
  }
  function hexToHash(s) {
    if (s.startsWith("sha256:")) {
      s = s.slice(7);
    }
    if (s.length !== 64) {
      return null;
    }
    const hash = new Uint8Array(32);
    for (let i = 0; i < 32; i++) {
      const hi = hexDigit(s.charCodeAt(i * 2));
      const lo = hexDigit(s.charCodeAt(i * 2 + 1));
      if (hi < 0 || lo < 0) {
        return null;
      }
      hash[i] = hi << 4 | lo;
    }
    return hash;
  }
  function hexDigit(c) {
    if (c >= 48 && c <= 57) return c - 48;
    if (c >= 97 && c <= 102) return c - 97 + 10;
    if (c >= 65 && c <= 70) return c - 65 + 10;
    return -1;
  }

  // src/patch.ts
  function fieldSeg(name, fid) {
    return { kind: "field", field: name, fid };
  }
  function listIdxSeg(idx) {
    return { kind: "listIdx", listIdx: parseNonNegativeSafeInt(String(idx), "list index") };
  }
  function mapKeySeg(key) {
    return { kind: "mapKey", mapKey: key };
  }
  function parseNonNegativeSafeInt(raw, field2) {
    if (!/^\d+$/.test(raw)) {
      throw new Error(`invalid ${field2}: ${raw}`);
    }
    const value = Number(raw);
    if (!Number.isSafeInteger(value)) {
      throw new Error(`${field2} out of range: ${raw}`);
    }
    return value;
  }
  function parseFiniteNumber(raw, field2) {
    if (!/^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(raw)) {
      throw new Error(`invalid ${field2}: ${raw}`);
    }
    const value = Number(raw);
    if (!Number.isFinite(value)) {
      throw new Error(`invalid ${field2}: ${raw}`);
    }
    return value;
  }
  function parseQuotedPathString(path, start) {
    if (path[start] !== '"') {
      throw new Error(`expected quoted string at pos ${start}`);
    }
    let value = "";
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
      if (c === "\\") {
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
  function parsePathToSegs(path) {
    path = path.trim();
    if (!path) return [];
    const segs = [];
    let i = path.startsWith(".") ? 1 : 0;
    if (i >= path.length) {
      throw new Error("path cannot end with dot");
    }
    while (i < path.length) {
      const c = path[i];
      if (c === "[") {
        i++;
        if (i >= path.length) {
          throw new Error(`unterminated path segment at pos ${i - 1}`);
        }
        if (path[i] === '"') {
          const parsed = parseQuotedPathString(path, i);
          i = parsed.next;
          if (path[i] !== "]") {
            throw new Error(`unterminated map key segment at pos ${i}`);
          }
          segs.push(mapKeySeg(parsed.value));
          i++;
        } else {
          const end = path.indexOf("]", i);
          if (end < 0) {
            throw new Error(`unterminated list index at pos ${i - 1}`);
          }
          const inner = path.slice(i, end);
          segs.push(listIdxSeg(parseNonNegativeSafeInt(inner, "list index")));
          i = end + 1;
        }
      } else if (c === "#") {
        const start = i + 1;
        let j = start;
        while (j < path.length && path[j] >= "0" && path[j] <= "9") {
          j++;
        }
        if (j === start) {
          throw new Error(`missing field id at pos ${i}`);
        }
        segs.push({ kind: "field", fid: parseNonNegativeSafeInt(path.slice(start, j), "field id") });
        i = j;
      } else {
        let field2;
        if (c === '"') {
          const parsed = parseQuotedPathString(path, i);
          field2 = parsed.value;
          i = parsed.next;
        } else {
          let j = i;
          while (j < path.length && path[j] !== "." && path[j] !== "[" && path[j] !== "]") {
            j++;
          }
          if (j === i) {
            throw new Error(`empty path segment at pos ${i}`);
          }
          field2 = path.slice(i, j);
          i = j;
        }
        if (!field2) {
          throw new Error(`empty field name at pos ${i}`);
        }
        segs.push(fieldSeg(field2));
      }
      if (i >= path.length) {
        break;
      }
      if (path[i] === ".") {
        i++;
        if (i >= path.length) {
          throw new Error("path cannot end with dot");
        }
        continue;
      }
      if (path[i] === "[") {
        continue;
      }
      throw new Error(`unexpected character '${path[i]}' in path`);
    }
    return segs;
  }
  var PatchBuilder = class {
    constructor(target) {
      this.patch = {
        target,
        ops: []
      };
    }
    withSchema(schema) {
      this.schema = schema;
      this.patch.schemaId = schema.hash;
      return this;
    }
    withSchemaId(id) {
      this.patch.schemaId = id;
      return this;
    }
    withTargetType(typeName) {
      this.patch.targetType = typeName;
      return this;
    }
    /**
     * Set the base state fingerprint for validation.
     * The fingerprint should be the first 16 chars of the SHA-256 hash
     * of the canonical form of the base state.
     */
    withBaseFingerprint(fingerprint) {
      this.patch.baseFingerprint = fingerprint;
      return this;
    }
    /**
     * Compute and set the base fingerprint from a GValue.
     * Uses the SHA-256 hash of the loose canonical form (first 16 hex chars).
     */
    withBaseValue(base) {
      const hash = stateHashLooseSync(base);
      const hex = hashToHex(hash);
      this.patch.baseFingerprint = hex.slice(0, 16);
      return this;
    }
    set(path, value) {
      this.patch.ops.push({
        op: "=",
        path: parsePathToSegs(path),
        value
      });
      return this;
    }
    setWithSegs(path, value) {
      this.patch.ops.push({
        op: "=",
        path,
        value
      });
      return this;
    }
    append(path, value) {
      this.patch.ops.push({
        op: "+",
        path: parsePathToSegs(path),
        value,
        index: -1
      });
      return this;
    }
    delete(path) {
      this.patch.ops.push({
        op: "-",
        path: parsePathToSegs(path)
      });
      return this;
    }
    delta(path, amount) {
      this.patch.ops.push({
        op: "~",
        path: parsePathToSegs(path),
        value: GValue.float(amount)
      });
      return this;
    }
    insertAt(path, index, value) {
      this.patch.ops.push({
        op: "+",
        path: parsePathToSegs(path),
        value,
        index: parseNonNegativeSafeInt(String(index), "patch index")
      });
      return this;
    }
    build() {
      return this.patch;
    }
  };
  function emitPatch(patch, options = {}) {
    const keyMode = options.keyMode || "wire";
    const sortOps = options.sortOps !== false;
    const lines = [];
    let header = "@patch";
    if (patch.schemaId) {
      header += ` @schema#${patch.schemaId}`;
    }
    header += ` @keys=${keyMode}`;
    header += ` @target=${patch.target.prefix}:${patch.target.value}`;
    if (patch.baseFingerprint) {
      header += ` @base=${patch.baseFingerprint}`;
    }
    lines.push(header);
    let ops = patch.ops;
    if (sortOps) {
      ops = [...ops].sort((a, b) => {
        const pa = pathSegsToString(a.path, keyMode);
        const pb = pathSegsToString(b.path, keyMode);
        if (pa !== pb) return pa < pb ? -1 : 1;
        return a.op < b.op ? -1 : a.op > b.op ? 1 : 0;
      });
    }
    const prefix = options.indentPrefix || "";
    for (const op of ops) {
      let line = prefix + op.op + " ";
      line += emitPathSegs(op.path, keyMode);
      if (op.op === "=" || op.op === "+") {
        if (op.value) {
          line += " " + emitValue2(op.value, options.schema);
        }
        if (op.op === "+" && op.index !== void 0 && op.index >= 0) {
          line += ` @idx=${op.index}`;
        }
      } else if (op.op === "~") {
        if (op.value) {
          const num = op.value.type === "float" ? op.value.asFloat() : op.value.asInt();
          line += " " + (num >= 0 ? "+" : "") + canonFloat(num);
        }
      }
      lines.push(line);
    }
    lines.push("@end");
    return lines.join("\n");
  }
  function pathSegsToString(path, keyMode) {
    let result = "";
    for (let i = 0; i < path.length; i++) {
      const seg = path[i];
      if (seg.kind === "field") {
        if (i > 0) result += ".";
        if (keyMode === "fid" && seg.fid) {
          result += "#" + seg.fid;
        } else {
          result += seg.field || "";
        }
      } else if (seg.kind === "listIdx") {
        result += `[${seg.listIdx}]`;
      } else if (seg.kind === "mapKey") {
        result += `["${seg.mapKey}"]`;
      }
    }
    return result;
  }
  function emitPathSegs(path, keyMode) {
    return pathSegsToString(path, keyMode);
  }
  function emitValue2(gv, schema) {
    switch (gv.type) {
      case "null":
        return "\u2205";
      case "bool":
        return gv.asBool() ? "t" : "f";
      case "int":
        return canonInt(gv.asInt());
      case "float":
        return canonFloat(gv.asFloat());
      case "str":
        return canonString(gv.asStr());
      case "id":
        return canonRef3(gv.asId());
      case "time":
        return gv.asTime().toISOString().replace(".000Z", "Z");
      case "list": {
        const items = gv.asList().map((v) => emitValue2(v, schema));
        return "[" + items.join(" ") + "]";
      }
      case "map": {
        const parts = [];
        for (const e of gv.asMap()) {
          parts.push(`${canonString(e.key)}:${emitValue2(e.value, schema)}`);
        }
        return "{" + parts.join(" ") + "}";
      }
      case "struct": {
        const sv = gv.asStruct();
        const parts = [];
        for (const f of sv.fields) {
          parts.push(`${canonString(f.key)}=${emitValue2(f.value, schema)}`);
        }
        return `${sv.typeName}{${parts.join(" ")}}`;
      }
      case "sum": {
        const sum = gv.asSum();
        if (!sum.value) return `${sum.tag}()`;
        return `${sum.tag}(${emitValue2(sum.value, schema)})`;
      }
      default:
        return "\u2205";
    }
  }
  function parsePatch(input, schema) {
    const lines = input.split("\n");
    if (lines.length === 0) {
      throw new Error("empty patch input");
    }
    const headerLine = lines[0].trim();
    const header = parsePatchHeader(headerLine);
    const patch = {
      target: header.target,
      schemaId: header.schemaId,
      baseFingerprint: header.baseFingerprint,
      ops: []
    };
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line || line.startsWith("#")) continue;
      if (line === "@end") break;
      const op = parsePatchOp(line, schema);
      patch.ops.push(op);
    }
    return patch;
  }
  function parsePatchHeader(line) {
    if (!line.startsWith("@patch")) {
      throw new Error("patch must start with @patch");
    }
    const result = {
      target: { prefix: "", value: "" },
      keyMode: "wire"
    };
    const tokens = tokenizeHeader2(line);
    for (const tok of tokens) {
      if (tok.startsWith("@schema#")) {
        result.schemaId = tok.slice(8);
      } else if (tok.startsWith("@keys=")) {
        result.keyMode = tok.slice(6);
      } else if (tok.startsWith("@target=")) {
        const ref = tok.slice(8);
        const colonIdx = ref.indexOf(":");
        if (colonIdx > 0) {
          result.target = { prefix: ref.slice(0, colonIdx), value: ref.slice(colonIdx + 1) };
        } else {
          result.target = { prefix: "", value: ref };
        }
      } else if (tok.startsWith("@base=")) {
        result.baseFingerprint = tok.slice(6);
      }
    }
    return result;
  }
  function tokenizeHeader2(input) {
    const tokens = [];
    let current = "";
    let inQuote = false;
    for (const c of input) {
      if (c === '"') {
        inQuote = !inQuote;
        current += c;
      } else if (c === " " && !inQuote) {
        if (current) {
          tokens.push(current);
          current = "";
        }
      } else {
        current += c;
      }
    }
    if (current) tokens.push(current);
    return tokens;
  }
  function parsePatchOp(line, schema) {
    if (!line) {
      throw new Error("empty operation line");
    }
    const opChar = line[0];
    if (!["=", "+", "-", "~"].includes(opChar)) {
      throw new Error(`unknown operation: ${opChar}`);
    }
    const rest = line.slice(1).trim();
    if (!rest) {
      throw new Error("missing path in operation");
    }
    const pathEnd = findPathEnd(rest);
    const pathStr = rest.slice(0, pathEnd);
    let valueStr = rest.slice(pathEnd).trim();
    const path = parsePathToSegs(pathStr);
    const op = {
      op: opChar,
      path,
      index: -1
    };
    switch (opChar) {
      case "=":
      case "+": {
        if (valueStr) {
          const tokens = tokenizeValues(valueStr);
          const lastToken = tokens[tokens.length - 1];
          if (opChar === "+" && tokens.length > 1 && lastToken?.startsWith("@idx=")) {
            op.index = parseNonNegativeSafeInt(lastToken.slice(5), "patch index");
            tokens.pop();
            valueStr = tokens.join(" ").trim();
          }
          op.value = parseInlineValue(valueStr, schema);
        }
        break;
      }
      case "~": {
        if (!valueStr) {
          throw new Error("delta operation requires a value");
        }
        const num = parseFiniteNumber(valueStr, "delta");
        op.value = GValue.float(num);
        break;
      }
      case "-":
        break;
    }
    return op;
  }
  function findPathEnd(s) {
    let inQuote = false;
    let bracketDepth = 0;
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (c === '"') {
        inQuote = !inQuote;
      } else if (c === "[" && !inQuote) {
        bracketDepth++;
      } else if (c === "]" && !inQuote && bracketDepth > 0) {
        bracketDepth--;
      } else if ((c === " " || c === "	") && !inQuote && bracketDepth === 0) {
        return i;
      }
    }
    return s.length;
  }
  function parseInlineValue(s, schema) {
    s = s.trim();
    if (!s) return GValue.null();
    if (s === "\u2205" || s === "null") return GValue.null();
    if (s === "t" || s === "true") return GValue.bool(true);
    if (s === "f" || s === "false") return GValue.bool(false);
    if (s.startsWith("^")) {
      const ref = s.slice(1);
      const colonIdx = ref.indexOf(":");
      if (colonIdx > 0) {
        return GValue.id(ref.slice(0, colonIdx), ref.slice(colonIdx + 1));
      }
      return GValue.id("", ref);
    }
    if (s.startsWith('"')) {
      return parseQuotedString(s);
    }
    if (/^-?\d/.test(s)) {
      const num = parseFiniteNumber(s, "number");
      if (s.includes(".") || s.includes("e") || s.includes("E")) {
        return GValue.float(num);
      }
      return GValue.int(parseInt(s, 10));
    }
    if (s.startsWith("[")) {
      return parseList(s);
    }
    if (/^[A-Za-z_]\w*\{/.test(s)) {
      return parseStruct(s);
    }
    return GValue.str(s);
  }
  function parseQuotedString(s) {
    if (s.length < 2 || !s.endsWith('"')) {
      throw new Error("unterminated string literal");
    }
    let result = "";
    for (let i = 1; i < s.length - 1; i++) {
      if (s[i] === "\\" && i + 1 < s.length - 1) {
        i++;
        switch (s[i]) {
          case "n":
            result += "\n";
            break;
          case "r":
            result += "\r";
            break;
          case "t":
            result += "	";
            break;
          case "\\":
            result += "\\";
            break;
          case '"':
            result += '"';
            break;
          default:
            result += s[i];
        }
      } else {
        result += s[i];
      }
    }
    return GValue.str(result);
  }
  function parseList(s) {
    const inner = s.slice(1, -1).trim();
    if (!inner) return GValue.list();
    const items = [];
    const tokens = tokenizeValues(inner);
    for (const tok of tokens) {
      items.push(parseInlineValue(tok));
    }
    return GValue.list(...items);
  }
  function parseStruct(s) {
    const braceIdx = s.indexOf("{");
    const typeName = s.slice(0, braceIdx);
    const inner = s.slice(braceIdx + 1, -1).trim();
    if (!inner) return GValue.struct(typeName);
    const entries = [];
    const tokens = tokenizeValues(inner);
    for (const tok of tokens) {
      const eqIdx = tok.indexOf("=");
      if (eqIdx > 0) {
        const key = tok.slice(0, eqIdx).trim();
        const valStr = tok.slice(eqIdx + 1).trim();
        entries.push({ key, value: parseInlineValue(valStr) });
      }
    }
    return GValue.struct(typeName, ...entries);
  }
  function tokenizeValues(s) {
    const tokens = [];
    let current = "";
    let inQuote = false;
    let depth = 0;
    for (const c of s) {
      if (c === '"') {
        inQuote = !inQuote;
        current += c;
      } else if (!inQuote) {
        if (c === "[" || c === "{" || c === "(") {
          depth++;
          current += c;
        } else if (c === "]" || c === "}" || c === ")") {
          depth--;
          current += c;
        } else if (c === " " && depth === 0) {
          if (current) {
            tokens.push(current);
            current = "";
          }
        } else {
          current += c;
        }
      } else {
        current += c;
      }
    }
    if (current) tokens.push(current);
    return tokens;
  }
  function applyPatch(value, patch) {
    let result = value.clone();
    for (const op of patch.ops) {
      result = applyOp(result, op);
    }
    return result;
  }
  function applyOp(value, op) {
    if (op.path.length === 0) {
      if (op.op === "=") {
        return op.value || GValue.null();
      }
      throw new Error(`cannot apply ${op.op} to root`);
    }
    return applyAtPath(value, op.path, op);
  }
  function applyAtPath(value, path, op) {
    if (path.length === 1) {
      return applyToParent(value, path[0], op);
    }
    const seg = path[0];
    const rest = path.slice(1);
    if (seg.kind === "field") {
      const key = seg.field;
      if (value.type !== "struct") {
        throw new Error(`cannot navigate into ${value.type} with field`);
      }
      const sv = value.asStruct();
      for (let i = 0; i < sv.fields.length; i++) {
        if (sv.fields[i].key === key) {
          sv.fields[i].value = applyAtPath(sv.fields[i].value, rest, op);
          return value;
        }
      }
      throw new Error(`field not found: ${key}`);
    }
    if (seg.kind === "listIdx") {
      if (value.type !== "list") {
        throw new Error(`cannot index into ${value.type}`);
      }
      const list = value.asList();
      const idx = seg.listIdx;
      if (idx < 0 || idx >= list.length) {
        throw new Error(`index out of bounds: ${idx}`);
      }
      list[idx] = applyAtPath(list[idx], rest, op);
      return value;
    }
    if (seg.kind === "mapKey") {
      if (value.type !== "map") {
        throw new Error(`cannot access map key in ${value.type}`);
      }
      const entries = value.asMap();
      const key = seg.mapKey;
      for (let i = 0; i < entries.length; i++) {
        if (entries[i].key === key) {
          entries[i].value = applyAtPath(entries[i].value, rest, op);
          return value;
        }
      }
      throw new Error(`key not found: ${key}`);
    }
    throw new Error("unknown path segment kind");
  }
  function applyToParent(value, seg, op) {
    const key = seg.kind === "mapKey" ? seg.mapKey : seg.field;
    switch (op.op) {
      case "=":
        value.set(key, op.value || GValue.null());
        return value;
      case "+": {
        const existing = value.get(key);
        if (!existing || existing.isNull()) {
          value.set(key, GValue.list(op.value || GValue.null()));
        } else if (existing.type === "list") {
          const list = existing.asList();
          if (op.index !== void 0 && op.index >= 0 && op.index <= list.length) {
            list.splice(op.index, 0, op.value || GValue.null());
          } else {
            list.push(op.value || GValue.null());
          }
        } else {
          throw new Error(`cannot append to ${existing.type}`);
        }
        return value;
      }
      case "-": {
        if (value.type === "struct") {
          const sv = value.asStruct();
          sv.fields = sv.fields.filter((f) => f.key !== key);
        } else if (value.type === "map") {
          const entries = value.asMap();
          const idx = entries.findIndex((e) => e.key === key);
          if (idx >= 0) entries.splice(idx, 1);
        } else {
          throw new Error(`cannot delete from ${value.type}`);
        }
        return value;
      }
      case "~": {
        const existing = value.get(key);
        if (!existing) {
          throw new Error(`field not found for delta: ${key}`);
        }
        const delta = op.value?.type === "float" ? op.value.asFloat() : op.value?.asInt() || 0;
        if (existing.type === "int") {
          value.set(key, GValue.int(existing.asInt() + delta));
        } else if (existing.type === "float") {
          value.set(key, GValue.float(existing.asFloat() + delta));
        } else {
          throw new Error(`cannot apply delta to ${existing.type}`);
        }
        return value;
      }
    }
    throw new Error(`unknown operation: ${op.op}`);
  }
  function canonRef3(ref) {
    const full = ref.prefix ? `${ref.prefix}:${ref.value}` : ref.value;
    return `^${full}`;
  }

  // src/parse_loose.ts
  var DEFAULT_MAX_DEPTH = 128;
  var MAX_COLLECTION_LEN3 = 1e6;
  var MAX_STRING_LEN3 = 10 * 1024 * 1024;
  function isAsciiDigit(c) {
    return c >= "0" && c <= "9";
  }
  function isLetter2(c) {
    return /\p{L}/u.test(c);
  }
  function isAlnum(c) {
    return /[\p{L}\p{N}]/u.test(c);
  }
  var IDENT_CONTINUE_EXTRA = "_-./@+";
  var Lexer = class {
    constructor(text) {
      this.text = text;
      this.pos = 0;
      this.length = text.length;
    }
    peekChar() {
      if (this.pos >= this.length) return "";
      return this.text[this.pos];
    }
    nextChar() {
      if (this.pos >= this.length) return "";
      const c = this.text[this.pos];
      this.pos += 1;
      return c;
    }
    skipWhitespace() {
      while (this.pos < this.length && " 	\r".includes(this.text[this.pos])) {
        this.pos += 1;
      }
    }
    skipWhitespaceAndNewlines() {
      while (this.pos < this.length && " 	\r\n".includes(this.text[this.pos])) {
        this.pos += 1;
      }
    }
    nextToken() {
      this.skipWhitespace();
      if (this.pos >= this.length) {
        return { type: "EOF" /* EOF */, value: null, pos: this.pos };
      }
      const start = this.pos;
      const c = this.peekChar();
      switch (c) {
        case "{":
          this.pos += 1;
          return { type: "{" /* LBRACE */, value: c, pos: start };
        case "}":
          this.pos += 1;
          return { type: "}" /* RBRACE */, value: c, pos: start };
        case "[":
          this.pos += 1;
          return { type: "[" /* LBRACKET */, value: c, pos: start };
        case "]":
          this.pos += 1;
          return { type: "]" /* RBRACKET */, value: c, pos: start };
        case "(":
          this.pos += 1;
          return { type: "(" /* LPAREN */, value: c, pos: start };
        case ")":
          this.pos += 1;
          return { type: ")" /* RPAREN */, value: c, pos: start };
        case "=":
          this.pos += 1;
          return { type: "=" /* EQUALS */, value: c, pos: start };
        case ":":
          this.pos += 1;
          return { type: ":" /* COLON */, value: c, pos: start };
        case ",":
          this.pos += 1;
          return { type: "," /* COMMA */, value: c, pos: start };
        case "|":
          this.pos += 1;
          return { type: "|" /* PIPE */, value: c, pos: start };
        case "^":
          this.pos += 1;
          return { type: "^" /* CARET */, value: c, pos: start };
        case "@":
          this.pos += 1;
          return { type: "@" /* AT */, value: c, pos: start };
        case "\n":
          this.pos += 1;
          return { type: "NEWLINE" /* NEWLINE */, value: c, pos: start };
      }
      if (c === "\u2205" || c === "_") {
        this.pos += 1;
        return { type: "NULL" /* NULL */, value: null, pos: start };
      }
      if (c === '"') {
        return this.readString();
      }
      if (c === "b" && this.text.slice(this.pos, this.pos + 4) === 'b64"') {
        return this.readBytes();
      }
      if (c === "-" || isAsciiDigit(c)) {
        return this.readNumberOrIdent();
      }
      if (isLetter2(c) || c === "_") {
        return this.readIdent();
      }
      throw new Error(`unexpected character '${c}' at position ${this.pos}`);
    }
    readString() {
      const start = this.pos;
      this.pos += 1;
      let result = "";
      while (this.pos < this.length) {
        const c = this.text[this.pos];
        if (c === '"') {
          this.pos += 1;
          return { type: "STRING" /* STRING */, value: result, pos: start };
        }
        if (result.length >= MAX_STRING_LEN3) {
          throw new Error(`string too large (>${MAX_STRING_LEN3} characters)`);
        }
        if (c === "\\") {
          this.pos += 1;
          if (this.pos >= this.length) {
            throw new Error("unterminated escape sequence");
          }
          const esc = this.text[this.pos];
          switch (esc) {
            case "n":
              result += "\n";
              break;
            case "r":
              result += "\r";
              break;
            case "t":
              result += "	";
              break;
            case '"':
              result += '"';
              break;
            case "\\":
              result += "\\";
              break;
            case "u": {
              if (this.pos + 5 > this.length) {
                throw new Error("invalid unicode escape");
              }
              const hex = this.text.slice(this.pos + 1, this.pos + 5);
              if (!/^[0-9a-fA-F]{4}$/.test(hex)) {
                throw new Error("invalid unicode escape");
              }
              result += String.fromCharCode(parseInt(hex, 16));
              this.pos += 4;
              break;
            }
            default:
              result += esc;
          }
        } else {
          result += c;
        }
        this.pos += 1;
      }
      throw new Error("unterminated string");
    }
    readBytes() {
      const start = this.pos;
      this.pos += 4;
      let b64 = "";
      while (this.pos < this.length) {
        const c = this.text[this.pos];
        if (c === '"') {
          this.pos += 1;
          return { type: "BYTES" /* BYTES */, value: base64ToBytes4(b64), pos: start };
        }
        b64 += c;
        this.pos += 1;
      }
      throw new Error("unterminated bytes literal");
    }
    parseFloatToken(literal, start) {
      const value = Number(literal);
      if (Number.isNaN(value)) {
        throw new Error(`invalid float literal '${literal}' at position ${start}`);
      }
      if (!Number.isFinite(value)) {
        throw new Error(`non-finite float literal '${literal}' at position ${start}`);
      }
      return { type: "FLOAT" /* FLOAT */, value, pos: start };
    }
    readNumberOrIdent() {
      const start = this.pos;
      let result = "";
      if (this.peekChar() === "-") {
        result += this.nextChar();
        if (this.text.slice(this.pos, this.pos + 3) === "Inf" && (this.pos + 3 >= this.length || !isAlnum(this.text[this.pos + 3]) && this.text[this.pos + 3] !== "_")) {
          throw new Error(`non-finite float literal '-Inf' at position ${start}`);
        }
      }
      let hasDot = false;
      let hasExp = false;
      while (this.pos < this.length) {
        const c = this.peekChar();
        if (isAsciiDigit(c)) {
          result += this.nextChar();
        } else if (c === "." && !hasDot && !hasExp) {
          hasDot = true;
          result += this.nextChar();
        } else if ((c === "e" || c === "E") && !hasExp) {
          hasExp = true;
          result += this.nextChar();
          if (this.peekChar() === "+" || this.peekChar() === "-") {
            result += this.nextChar();
          }
        } else if (isLetter2(c) || c === "_") {
          while (this.pos < this.length && (isAlnum(this.peekChar()) || IDENT_CONTINUE_EXTRA.includes(this.peekChar()))) {
            result += this.nextChar();
          }
          return { type: "IDENT" /* IDENT */, value: result, pos: start };
        } else {
          break;
        }
      }
      if (hasDot || hasExp) {
        return this.parseFloatToken(result, start);
      }
      const intVal = Number(result);
      if (Number.isNaN(intVal)) {
        return { type: "IDENT" /* IDENT */, value: result, pos: start };
      }
      return { type: "INT" /* INT */, value: intVal, pos: start };
    }
    readIdent() {
      const start = this.pos;
      let result = "";
      while (this.pos < this.length) {
        const c = this.peekChar();
        if (isAlnum(c) || IDENT_CONTINUE_EXTRA.includes(c)) {
          result += this.nextChar();
        } else {
          break;
        }
      }
      switch (result) {
        case "t":
        case "true":
          return { type: "BOOL" /* BOOL */, value: true, pos: start };
        case "f":
        case "false":
          return { type: "BOOL" /* BOOL */, value: false, pos: start };
        case "null":
        case "nil":
          return { type: "NULL" /* NULL */, value: null, pos: start };
        case "NaN":
          throw new Error(`non-finite float literal 'NaN' at position ${start}`);
        case "Inf":
          throw new Error(`non-finite float literal 'Inf' at position ${start}`);
      }
      return { type: "IDENT" /* IDENT */, value: result, pos: start };
    }
  };
  function base64ToBytes4(b64) {
    if (typeof atob === "function") {
      const binary = atob(b64);
      const out = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
      return out;
    }
    return new Uint8Array(Buffer.from(b64, "base64"));
  }
  var Parser = class _Parser {
    constructor(text, maxDepth = DEFAULT_MAX_DEPTH, nestingDepth = 0) {
      this.lexer = new Lexer(text);
      this.maxDepth = maxDepth;
      this.depth = nestingDepth;
    }
    enter(kind) {
      if (this.depth >= this.maxDepth) {
        throw new Error(`maximum nesting depth exceeded while parsing ${kind}`);
      }
      this.depth += 1;
    }
    leave() {
      this.depth -= 1;
    }
    advance() {
      this.current = this.lexer.nextToken();
      return this.current;
    }
    // Predicate over the current token type. Routing comparisons through a method
    // (rather than `this.current.type === X` inline) avoids TypeScript's
    // control-flow narrowing persisting across the mutating `advance()` call.
    is(t2) {
      return this.current.type === t2;
    }
    parse() {
      this.lexer.skipWhitespaceAndNewlines();
      this.current = this.lexer.nextToken();
      const v = this.parseValue();
      while (this.is("NEWLINE" /* NEWLINE */)) {
        this.advance();
      }
      if (!this.is("EOF" /* EOF */)) {
        throw new Error(`trailing garbage at position ${this.current.pos}`);
      }
      return v;
    }
    parseValue() {
      const tok = this.current;
      const v = tok.value;
      switch (tok.type) {
        case "NULL" /* NULL */:
          this.advance();
          return GValue.null();
        case "BOOL" /* BOOL */:
          this.advance();
          return GValue.bool(v);
        case "INT" /* INT */:
          this.advance();
          return GValue.int(v);
        case "FLOAT" /* FLOAT */:
          this.advance();
          return GValue.float(v);
        case "STRING" /* STRING */:
          this.advance();
          return GValue.str(v);
        case "BYTES" /* BYTES */:
          this.advance();
          return GValue.bytes(v);
        case "^" /* CARET */:
          return this.parseRef();
        case "[" /* LBRACKET */:
          return this.parseList();
        case "{" /* LBRACE */:
          return this.parseMap();
        case "@" /* AT */:
          return this.parseDirective();
        case "IDENT" /* IDENT */:
          return this.parseIdentValue();
      }
      throw new Error(`unexpected token ${tok.type} at position ${tok.pos}`);
    }
    parseRef() {
      this.advance();
      if (this.is("STRING" /* STRING */)) {
        const s = this.current.value;
        this.advance();
        const idx = s.indexOf(":");
        if (idx >= 0) {
          return GValue.id(s.slice(0, idx), s.slice(idx + 1));
        }
        return GValue.id("", s);
      }
      let first;
      if (this.is("IDENT" /* IDENT */)) {
        first = this.current.value;
        this.advance();
      } else if (this.is("BOOL" /* BOOL */)) {
        first = this.current.value ? "t" : "f";
        this.advance();
      } else if (this.is("INT" /* INT */)) {
        first = String(this.current.value);
        this.advance();
      } else {
        throw new Error(`expected reference value, got ${this.current.type}`);
      }
      if (this.is(":" /* COLON */)) {
        this.advance();
        let second;
        if (this.is("IDENT" /* IDENT */) || this.is("STRING" /* STRING */)) {
          second = this.current.value;
          this.advance();
        } else if (this.is("INT" /* INT */)) {
          second = String(this.current.value);
          this.advance();
        } else if (this.is("BOOL" /* BOOL */)) {
          second = this.current.value ? "t" : "f";
          this.advance();
        } else {
          throw new Error(`expected reference value part, got ${this.current.type}`);
        }
        return GValue.id(first, second);
      }
      return GValue.id("", first);
    }
    parseList() {
      this.enter("list");
      try {
        this.advance();
        const items = [];
        while (!this.is("]" /* RBRACKET */)) {
          if (this.is("EOF" /* EOF */)) {
            throw new Error("unterminated list");
          }
          if (this.is("," /* COMMA */) || this.is("NEWLINE" /* NEWLINE */)) {
            this.advance();
            continue;
          }
          if (items.length >= MAX_COLLECTION_LEN3) {
            throw new Error(`list too large (>${MAX_COLLECTION_LEN3} elements)`);
          }
          items.push(this.parseValue());
        }
        this.advance();
        return GValue.list(...items);
      } finally {
        this.leave();
      }
    }
    parseMap() {
      this.enter("map");
      try {
        this.advance();
        const entries = [];
        while (!this.is("}" /* RBRACE */)) {
          if (this.is("EOF" /* EOF */)) {
            throw new Error("unterminated map");
          }
          if (this.is("," /* COMMA */) || this.is("NEWLINE" /* NEWLINE */)) {
            this.advance();
            continue;
          }
          if (entries.length >= MAX_COLLECTION_LEN3) {
            throw new Error(`map too large (>${MAX_COLLECTION_LEN3} entries)`);
          }
          const key = this.parseKey();
          if (!this.is("=" /* EQUALS */) && !this.is(":" /* COLON */)) {
            throw new Error(`expected '=' or ':' after key '${key}'`);
          }
          this.advance();
          entries.push({ key, value: this.parseValue() });
        }
        this.advance();
        return GValue.map(...entries);
      } finally {
        this.leave();
      }
    }
    parseKey() {
      if (this.is("IDENT" /* IDENT */) || this.is("STRING" /* STRING */)) {
        const key = this.current.value;
        this.advance();
        return key;
      }
      throw new Error(`expected key, got ${this.current.type}`);
    }
    parseIdentValue() {
      const name = this.current.value;
      this.advance();
      if (this.is("{" /* LBRACE */)) {
        this.enter("struct");
        try {
          this.advance();
          const fields = [];
          while (!this.is("}" /* RBRACE */)) {
            if (this.is("EOF" /* EOF */)) {
              throw new Error("unterminated struct");
            }
            if (this.is("," /* COMMA */) || this.is("NEWLINE" /* NEWLINE */)) {
              this.advance();
              continue;
            }
            if (fields.length >= MAX_COLLECTION_LEN3) {
              throw new Error(`struct too large (>${MAX_COLLECTION_LEN3} fields)`);
            }
            const key = this.parseKey();
            if (!this.is("=" /* EQUALS */) && !this.is(":" /* COLON */)) {
              throw new Error(`expected '=' or ':' after field '${key}'`);
            }
            this.advance();
            fields.push({ key, value: this.parseValue() });
          }
          this.advance();
          return GValue.struct(name, ...fields);
        } finally {
          this.leave();
        }
      }
      if (this.is("(" /* LPAREN */)) {
        this.enter("sum");
        try {
          this.advance();
          if (this.is(")" /* RPAREN */)) {
            this.advance();
            return GValue.sum(name, null);
          }
          const value = this.parseValue();
          if (!this.is(")" /* RPAREN */)) {
            throw new Error(`expected ), got ${this.current.type}`);
          }
          this.advance();
          return GValue.sum(name, value);
        } finally {
          this.leave();
        }
      }
      return GValue.str(name);
    }
    parseDirective() {
      this.advance();
      if (!this.is("IDENT" /* IDENT */)) {
        throw new Error(`expected directive name, got ${this.current.type}`);
      }
      const directive = this.current.value;
      this.advance();
      if (directive === "tab") {
        return this.parseTabular();
      }
      throw new Error(`unknown directive: ${directive}`);
    }
    parseTabular() {
      this.enter("tabular directive");
      try {
        if (this.is("NULL" /* NULL */) || this.is("IDENT" /* IDENT */) && this.current.value === "_") {
          this.advance();
        }
        while (!this.is("[" /* LBRACKET */)) {
          if (this.is("EOF" /* EOF */)) {
            throw new Error("expected [ for column headers");
          }
          this.advance();
        }
        this.advance();
        const cols = [];
        while (!this.is("]" /* RBRACKET */)) {
          if (this.is("IDENT" /* IDENT */) || this.is("STRING" /* STRING */)) {
            cols.push(this.current.value);
            this.advance();
          } else if (this.is("," /* COMMA */) || this.is("NEWLINE" /* NEWLINE */)) {
            this.advance();
          } else if (this.is("EOF" /* EOF */)) {
            throw new Error("unterminated column header");
          } else {
            throw new Error(`expected column name, got ${this.current.type}`);
          }
        }
        this.advance();
        const rows = [];
        for (; ; ) {
          while (this.is("NEWLINE" /* NEWLINE */)) {
            this.advance();
          }
          if (this.is("@" /* AT */)) {
            this.advance();
            if (this.is("IDENT" /* IDENT */) && this.current.value === "end") {
              this.advance();
              break;
            }
            throw new Error("expected @end");
          }
          if (this.is("|" /* PIPE */)) {
            rows.push(this.parseTabularRow(cols));
          } else if (this.is("EOF" /* EOF */)) {
            break;
          } else {
            throw new Error(`expected row or @end, got ${this.current.type}`);
          }
        }
        return GValue.list(...rows);
      } finally {
        this.leave();
      }
    }
    parseTabularRow(cols) {
      const entries = [];
      for (const col of cols) {
        let cell = "";
        while (this.lexer.pos < this.lexer.length) {
          const c = this.lexer.text[this.lexer.pos];
          if (c === "|") break;
          if (c === "\\" && this.lexer.pos + 1 < this.lexer.length) {
            const nextC = this.lexer.text[this.lexer.pos + 1];
            if (nextC === "|") {
              cell += "|";
              this.lexer.pos += 2;
              continue;
            }
            if (nextC === "n") {
              cell += "\n";
              this.lexer.pos += 2;
              continue;
            }
            if (nextC === "\\") {
              cell += "\\";
              this.lexer.pos += 2;
              continue;
            }
          }
          cell += c;
          this.lexer.pos += 1;
        }
        if (this.lexer.pos >= this.lexer.length || this.lexer.text[this.lexer.pos] !== "|") {
          throw new Error("expected | after cell");
        }
        this.lexer.pos += 1;
        const cellText = cell.trim();
        let value;
        if (cellText === "" || cellText === "\u2205" || cellText === "_") {
          value = GValue.null();
        } else {
          const sub = new _Parser(cellText, this.maxDepth, this.depth);
          value = sub.parse();
        }
        entries.push({ key: col, value });
      }
      this.current = this.lexer.nextToken();
      return GValue.map(...entries);
    }
  };
  function parseLoose(text, maxDepth = DEFAULT_MAX_DEPTH) {
    return new Parser(text, maxDepth).parse();
  }

  // src/stream/index.ts
  var stream_exports = {};
  __export(stream_exports, {
    BaseMismatchError: () => BaseMismatchError,
    CRCMismatchError: () => CRCMismatchError,
    FLAGS: () => FLAGS,
    FrameHandler: () => FrameHandler,
    KIND_VALUES: () => KIND_VALUES,
    MAX_PAYLOAD_SIZE: () => MAX_PAYLOAD_SIZE,
    ParseError: () => ParseError,
    Reader: () => Reader,
    StreamCursor: () => StreamCursor,
    VALUE_KINDS: () => VALUE_KINDS,
    VERSION: () => VERSION,
    ackFrame: () => ackFrame,
    artifact: () => artifact,
    computeCRC: () => computeCRC,
    counter: () => counter,
    crcToHex: () => crcToHex,
    decodeFrame: () => decodeFrame,
    decodeFrames: () => decodeFrames,
    docFrame: () => docFrame,
    emitArtifact: () => emitArtifact,
    emitError: () => emitError,
    emitLog: () => emitLog,
    emitMetric: () => emitMetric,
    emitProgress: () => emitProgress,
    emitResyncRequest: () => emitResyncRequest,
    emitUI: () => emitUI,
    encodeFrame: () => encodeFrame,
    encodeFrames: () => encodeFrames,
    errFrame: () => errFrame,
    error: () => error,
    hashToHex: () => hashToHex,
    hexToHash: () => hexToHash,
    kindToString: () => kindToString,
    log: () => log,
    logDebug: () => logDebug,
    logError: () => logError,
    logInfo: () => logInfo,
    logWarn: () => logWarn,
    metric: () => metric,
    parseCRC: () => parseCRC,
    parseKind: () => parseKind,
    parseUIEvent: () => parseUIEvent,
    patchFrame: () => patchFrame,
    pingFrame: () => pingFrame,
    pongFrame: () => pongFrame,
    progress: () => progress,
    resyncRequest: () => resyncRequest,
    rowFrame: () => rowFrame,
    sha256: () => sha256,
    sha256Sync: () => sha256Sync,
    stateHashBytes: () => stateHashBytes,
    stateHashLoose: () => stateHashLoose,
    stateHashLooseSync: () => stateHashLooseSync,
    uiFrame: () => uiFrame,
    verifyBase: () => verifyBase,
    verifyCRC: () => verifyCRC
  });

  // src/stream/types.ts
  var VERSION = 1;
  var KIND_VALUES = {
    doc: 0,
    patch: 1,
    row: 2,
    ui: 3,
    ack: 4,
    err: 5,
    ping: 6,
    pong: 7
  };
  var VALUE_KINDS = {
    0: "doc",
    1: "patch",
    2: "row",
    3: "ui",
    4: "ack",
    5: "err",
    6: "ping",
    7: "pong"
  };
  function parseKind(s) {
    if (s in KIND_VALUES) {
      return s;
    }
    const n = parseInt(s, 10);
    if (!isNaN(n) && n >= 0 && n <= 255) {
      return VALUE_KINDS[n] ?? n;
    }
    throw new Error(`Invalid kind: ${s}`);
  }
  function kindToString(kind) {
    if (typeof kind === "string") {
      return kind;
    }
    return VALUE_KINDS[kind] ?? `unknown(${kind})`;
  }
  var FLAGS = {
    HAS_CRC: 1,
    HAS_BASE: 2,
    FINAL: 4,
    COMPRESSED: 8
    // Reserved for GS1.1
  };
  var MAX_PAYLOAD_SIZE = 64 * 1024 * 1024;
  var ParseError = class extends Error {
    constructor(reason, offset = -1) {
      super(offset >= 0 ? `gs1: ${reason} at offset ${offset}` : `gs1: ${reason}`);
      this.reason = reason;
      this.offset = offset;
      this.name = "ParseError";
    }
  };
  var CRCMismatchError = class extends Error {
    constructor(expected, got) {
      super(`gs1: CRC mismatch: expected ${expected.toString(16).padStart(8, "0")}, got ${got.toString(16).padStart(8, "0")}`);
      this.expected = expected;
      this.got = got;
      this.name = "CRCMismatchError";
    }
  };
  var BaseMismatchError = class extends Error {
    constructor() {
      super("gs1: base hash mismatch");
      this.name = "BaseMismatchError";
    }
  };

  // src/stream/crc.ts
  var CRC_TABLE = new Uint32Array(256);
  (function initCRCTable() {
    const polynomial = 3988292384;
    for (let i = 0; i < 256; i++) {
      let crc = i;
      for (let j = 0; j < 8; j++) {
        if (crc & 1) {
          crc = crc >>> 1 ^ polynomial;
        } else {
          crc = crc >>> 1;
        }
      }
      CRC_TABLE[i] = crc >>> 0;
    }
  })();
  function computeCRC(data) {
    let crc = 4294967295;
    for (let i = 0; i < data.length; i++) {
      crc = CRC_TABLE[(crc ^ data[i]) & 255] ^ crc >>> 8;
    }
    return (crc ^ 4294967295) >>> 0;
  }
  function verifyCRC(data, expected) {
    return computeCRC(data) === expected;
  }
  function crcToHex(crc) {
    return crc.toString(16).padStart(8, "0");
  }
  function parseCRC(s) {
    if (s.startsWith("crc32:")) {
      s = s.slice(6);
    }
    if (s.length !== 8) {
      return null;
    }
    const n = parseInt(s, 16);
    if (isNaN(n)) {
      return null;
    }
    return n >>> 0;
  }

  // src/stream/gs1t.ts
  var encoder = new TextEncoder();
  var decoder = new TextDecoder();
  var DEFAULT_MAX_HEADER_BYTES = 8 * 1024;
  function encodeFrame(frame, options = {}) {
    const parts = [];
    parts.push(`v=${frame.version || VERSION}`);
    parts.push(`sid=${frame.sid}`);
    parts.push(`seq=${frame.seq}`);
    parts.push(`kind=${kindToString(frame.kind)}`);
    parts.push(`len=${frame.payload.length}`);
    let crc = frame.crc;
    if (crc === void 0 && options.withCRC && frame.payload.length > 0) {
      crc = computeCRC(frame.payload);
    }
    if (crc !== void 0) {
      parts.push(`crc=${crcToHex(crc)}`);
    }
    if (frame.base) {
      parts.push(`base=sha256:${hashToHex(frame.base)}`);
    }
    if (frame.final) {
      parts.push("final=true");
    }
    const header = `@frame{${parts.join(" ")}}
`;
    const headerBytes = encoder.encode(header);
    const result = new Uint8Array(headerBytes.length + frame.payload.length + 1);
    result.set(headerBytes, 0);
    result.set(frame.payload, headerBytes.length);
    result[result.length - 1] = 10;
    return result;
  }
  function encodeFrames(frames, options = {}) {
    const encoded = frames.map((f) => encodeFrame(f, options));
    const totalLength = encoded.reduce((sum, arr) => sum + arr.length, 0);
    const result = new Uint8Array(totalLength);
    let offset = 0;
    for (const arr of encoded) {
      result.set(arr, offset);
      offset += arr.length;
    }
    return result;
  }
  var Reader = class {
    constructor(options = {}) {
      this.buffer = new Uint8Array(0);
      this.offset = 0;
      this.maxPayload = options.maxPayload ?? MAX_PAYLOAD_SIZE;
      this.maxHeaderBytes = options.maxHeaderBytes ?? DEFAULT_MAX_HEADER_BYTES;
      this.verifyCRC = options.verifyCRC ?? true;
    }
    /**
     * Add data to the internal buffer.
     */
    push(data) {
      if (this.offset > 0) {
        this.buffer = this.buffer.slice(this.offset);
        this.offset = 0;
      }
      const newBuffer = new Uint8Array(this.buffer.length + data.length);
      newBuffer.set(this.buffer, 0);
      newBuffer.set(data, this.buffer.length);
      this.buffer = newBuffer;
    }
    /**
     * Try to read the next frame.
     * Returns null if not enough data is available.
     * Throws ParseError or CRCMismatchError on errors.
     */
    next() {
      const headerEnd = this.findNewline(this.offset);
      if (headerEnd < 0) {
        if (this.buffer.length - this.offset > this.maxHeaderBytes) {
          throw new ParseError(`header too large: > ${this.maxHeaderBytes}`);
        }
        return null;
      }
      if (headerEnd - this.offset > this.maxHeaderBytes) {
        throw new ParseError(`header too large: > ${this.maxHeaderBytes}`);
      }
      const headerLine = decoder.decode(this.buffer.slice(this.offset, headerEnd));
      const header = this.parseHeader(headerLine);
      if (header.version !== 1) {
        throw new ParseError(`unsupported version: ${header.version} (only v=1 is supported)`);
      }
      if (header.payloadLen > this.maxPayload) {
        throw new ParseError(`payload too large: ${header.payloadLen} > ${this.maxPayload}`);
      }
      const payloadStart = headerEnd + 1;
      if (this.buffer.length < payloadStart + header.payloadLen) {
        return null;
      }
      const payload = this.buffer.slice(payloadStart, payloadStart + header.payloadLen);
      if (this.buffer.length > payloadStart + header.payloadLen && this.buffer[payloadStart + header.payloadLen] === 10) {
        this.offset = payloadStart + header.payloadLen + 1;
      } else {
        this.offset = payloadStart + header.payloadLen;
      }
      if (this.verifyCRC && header.crc !== void 0) {
        const computed = computeCRC(payload);
        if (computed !== header.crc) {
          throw new CRCMismatchError(header.crc, computed);
        }
      }
      return {
        version: header.version,
        sid: header.sid,
        seq: header.seq,
        kind: header.kind,
        payload,
        crc: header.crc,
        base: header.base,
        flags: header.flags,
        final: header.final
      };
    }
    /**
     * Read all available frames.
     */
    readAll() {
      const frames = [];
      let frame;
      while ((frame = this.next()) !== null) {
        frames.push(frame);
      }
      return frames;
    }
    findNewline(start) {
      for (let i = start; i < this.buffer.length; i++) {
        if (this.buffer[i] === 10) {
          return i;
        }
      }
      return -1;
    }
    parseHeader(line) {
      line = line.trim();
      if (!line.startsWith("@frame{")) {
        throw new ParseError("expected @frame{", 0);
      }
      const endIdx = line.lastIndexOf("}");
      if (endIdx < 0) {
        throw new ParseError("missing closing }");
      }
      if (endIdx !== line.length - 1) {
        throw new ParseError("trailing data after header");
      }
      const content = line.slice(7, endIdx);
      const pairs = this.tokenize(content);
      const header = {
        version: 1,
        sid: 0n,
        seq: 0n,
        kind: "doc",
        payloadLen: 0
      };
      for (const pair of pairs) {
        const eqIdx = pair.indexOf("=");
        if (eqIdx < 0) continue;
        const key = pair.slice(0, eqIdx);
        const val = pair.slice(eqIdx + 1);
        switch (key) {
          case "v":
            header.version = this.parseUnsignedInt(val, "v");
            break;
          case "sid":
            header.sid = this.parseUnsignedBigInt(val, "sid");
            break;
          case "seq":
            header.seq = this.parseUnsignedBigInt(val, "seq");
            break;
          case "kind":
            header.kind = parseKind(val);
            break;
          case "len":
            header.payloadLen = this.parseUnsignedInt(val, "len");
            break;
          case "crc":
            header.crc = parseCRC(val) ?? void 0;
            break;
          case "base":
            header.base = hexToHash(val) ?? void 0;
            break;
          case "final":
            header.final = val === "true" || val === "1";
            break;
          case "flags":
            header.flags = this.parseHexInt(val, "flags");
            break;
        }
      }
      return header;
    }
    tokenize(s) {
      const tokens = [];
      let current = "";
      let inQuote = false;
      for (let i = 0; i < s.length; i++) {
        const c = s[i];
        if (c === '"') {
          inQuote = !inQuote;
          current += c;
        } else if ((c === " " || c === "," || c === "	") && !inQuote) {
          if (current.length > 0) {
            tokens.push(current);
            current = "";
          }
        } else {
          current += c;
        }
      }
      if (current.length > 0) {
        tokens.push(current);
      }
      return tokens;
    }
    parseUnsignedInt(raw, field2) {
      if (!/^\d+$/.test(raw)) {
        throw new ParseError(`invalid ${field2}`);
      }
      const value = Number(raw);
      if (!Number.isSafeInteger(value)) {
        throw new ParseError(`${field2} out of range`);
      }
      return value;
    }
    parseUnsignedBigInt(raw, field2) {
      if (!/^\d+$/.test(raw)) {
        throw new ParseError(`invalid ${field2}`);
      }
      return BigInt(raw);
    }
    parseHexInt(raw, field2) {
      const normalized = raw.replace(/^0x/i, "");
      if (!/^[0-9a-fA-F]+$/.test(normalized)) {
        throw new ParseError(`invalid ${field2}`);
      }
      const value = parseInt(normalized, 16);
      if (!Number.isSafeInteger(value)) {
        throw new ParseError(`${field2} out of range`);
      }
      return value;
    }
  };
  function decodeFrames(data, options) {
    const reader = new Reader(options);
    reader.push(data);
    return reader.readAll();
  }
  function decodeFrame(data, options) {
    const reader = new Reader(options);
    reader.push(data);
    return reader.next();
  }
  function docFrame(sid, seq, payload) {
    return {
      version: VERSION,
      sid,
      seq,
      kind: "doc",
      payload: typeof payload === "string" ? encoder.encode(payload) : payload
    };
  }
  function patchFrame(sid, seq, payload, base) {
    return {
      version: VERSION,
      sid,
      seq,
      kind: "patch",
      payload: typeof payload === "string" ? encoder.encode(payload) : payload,
      base
    };
  }
  function rowFrame(sid, seq, payload) {
    return {
      version: VERSION,
      sid,
      seq,
      kind: "row",
      payload: typeof payload === "string" ? encoder.encode(payload) : payload
    };
  }
  function uiFrame(sid, seq, payload) {
    return {
      version: VERSION,
      sid,
      seq,
      kind: "ui",
      payload: typeof payload === "string" ? encoder.encode(payload) : payload
    };
  }
  function ackFrame(sid, seq) {
    return {
      version: VERSION,
      sid,
      seq,
      kind: "ack",
      payload: new Uint8Array(0)
    };
  }
  function errFrame(sid, seq, payload) {
    return {
      version: VERSION,
      sid,
      seq,
      kind: "err",
      payload: typeof payload === "string" ? encoder.encode(payload) : payload
    };
  }
  function pingFrame(sid, seq) {
    return {
      version: VERSION,
      sid,
      seq,
      kind: "ping",
      payload: new Uint8Array(0)
    };
  }
  function pongFrame(sid, seq) {
    return {
      version: VERSION,
      sid,
      seq,
      kind: "pong",
      payload: new Uint8Array(0)
    };
  }

  // src/stream/cursor.ts
  var StreamCursor = class {
    constructor() {
      this.cursors = /* @__PURE__ */ new Map();
    }
    /**
     * Get state for a SID, creating it if needed.
     */
    get(sid) {
      let state = this.cursors.get(sid);
      if (!state) {
        state = {
          sid,
          lastSeq: 0n,
          lastAcked: 0n,
          stateHash: null,
          state: null,
          final: false
        };
        this.cursors.set(sid, state);
      }
      return state;
    }
    /**
     * Get state for a SID without creating it.
     */
    getReadOnly(sid) {
      return this.cursors.get(sid);
    }
    /**
     * Delete state for a SID.
     */
    delete(sid) {
      this.cursors.delete(sid);
    }
    /**
     * Get all tracked SIDs.
     */
    allSIDs() {
      return Array.from(this.cursors.keys());
    }
    /**
     * Process a frame and update cursor state.
     * Throws on sequence gaps, duplicates, or base mismatches.
     */
    processFrame(frame) {
      const state = this.get(frame.sid);
      if (frame.seq !== 0n && frame.seq <= state.lastSeq) {
        throw new Error(`sequence not monotonic: got ${frame.seq}, last was ${state.lastSeq}`);
      }
      if (state.lastSeq > 0n && frame.seq !== state.lastSeq + 1n) {
        throw new Error(`sequence gap: expected ${state.lastSeq + 1n}, got ${frame.seq}`);
      }
      if (frame.kind === "patch" && frame.base && state.stateHash) {
        if (!verifyBase(state.stateHash, frame.base)) {
          throw new BaseMismatchError();
        }
      }
      state.lastSeq = frame.seq;
      if (frame.final) {
        state.final = true;
      }
    }
    /**
     * Set the current state and compute its hash.
     */
    setState(sid, value) {
      const state = this.get(sid);
      state.state = value;
      state.stateHash = stateHashLooseSync(value);
    }
    /**
     * Set the state hash directly.
     */
    setStateHash(sid, hash) {
      const state = this.get(sid);
      state.stateHash = hash;
    }
    /**
     * Mark a sequence as acknowledged.
     */
    ack(sid, seq) {
      const state = this.get(sid);
      if (seq > state.lastAcked) {
        state.lastAcked = seq;
      }
    }
    /**
     * Get sequences that have been seen but not acked.
     */
    pendingAcks(sid) {
      const state = this.getReadOnly(sid);
      if (!state || state.lastSeq <= state.lastAcked) {
        return [];
      }
      const pending = [];
      for (let seq = state.lastAcked + 1n; seq <= state.lastSeq; seq++) {
        pending.push(seq);
      }
      return pending;
    }
    /**
     * Check if resync is needed (no state hash).
     */
    needsResync(sid) {
      const state = this.getReadOnly(sid);
      return !state || !state.stateHash;
    }
  };
  var FrameHandler = class {
    constructor(callbacks = {}) {
      this.cursor = new StreamCursor();
      this.callbacks = callbacks;
    }
    /**
     * Handle a frame and call the appropriate callback.
     */
    handle(frame) {
      const state = this.cursor.get(frame.sid);
      if (frame.seq !== 0n && state.lastSeq > 0n) {
        if (frame.seq <= state.lastSeq) {
          return;
        }
        if (frame.seq !== state.lastSeq + 1n) {
          if (this.callbacks.onSeqGap) {
            const allow = this.callbacks.onSeqGap(frame.sid, state.lastSeq + 1n, frame.seq);
            if (!allow) return;
          }
        }
      }
      if (frame.kind === "patch" && frame.base && state.stateHash) {
        if (!verifyBase(state.stateHash, frame.base)) {
          if (this.callbacks.onBaseMismatch) {
            const allow = this.callbacks.onBaseMismatch(frame.sid, frame);
            if (!allow) return;
          } else {
            throw new BaseMismatchError();
          }
        }
      }
      state.lastSeq = frame.seq;
      switch (frame.kind) {
        case "doc":
          this.callbacks.onDoc?.(frame.sid, frame.seq, frame.payload, state);
          break;
        case "patch":
          this.callbacks.onPatch?.(frame.sid, frame.seq, frame.payload, state);
          break;
        case "row":
          this.callbacks.onRow?.(frame.sid, frame.seq, frame.payload, state);
          break;
        case "ui":
          this.callbacks.onUI?.(frame.sid, frame.seq, frame.payload, state);
          break;
        case "ack":
          this.callbacks.onAck?.(frame.sid, frame.seq, state);
          break;
        case "err":
          this.callbacks.onErr?.(frame.sid, frame.seq, frame.payload, state);
          break;
      }
      if (frame.final) {
        state.final = true;
        this.callbacks.onFinal?.(frame.sid, state);
      }
    }
  };

  // src/stream/ui_events.ts
  var encoder2 = new TextEncoder();
  function progress(pct, msg) {
    return g.struct(
      "Progress",
      field("pct", g.float(pct)),
      field("msg", g.str(msg))
    );
  }
  function log(level, msg) {
    return g.struct(
      "Log",
      field("level", g.str(level)),
      field("msg", g.str(msg)),
      field("ts", g.time(/* @__PURE__ */ new Date()))
    );
  }
  function logInfo(msg) {
    return log("info", msg);
  }
  function logWarn(msg) {
    return log("warn", msg);
  }
  function logError(msg) {
    return log("error", msg);
  }
  function logDebug(msg) {
    return log("debug", msg);
  }
  function metric(name, value, unit) {
    const fields = [
      field("name", g.str(name)),
      field("value", g.float(value))
    ];
    if (unit) {
      fields.push(field("unit", g.str(unit)));
    }
    return g.struct("Metric", ...fields);
  }
  function counter(name, count) {
    return g.struct(
      "Metric",
      field("name", g.str(name)),
      field("value", g.int(count)),
      field("unit", g.str("count"))
    );
  }
  function artifact(mime, ref, name) {
    return g.struct(
      "Artifact",
      field("mime", g.str(mime)),
      field("ref", g.str(ref)),
      field("name", g.str(name))
    );
  }
  function resyncRequest(sid, seq, want, reason) {
    return g.struct(
      "ResyncRequest",
      field("sid", g.int(Number(sid))),
      field("seq", g.int(Number(seq))),
      field("want", g.str(want)),
      field("reason", g.str(reason))
    );
  }
  function error(code, msg, sid, seq) {
    return g.struct(
      "Error",
      field("code", g.str(code)),
      field("msg", g.str(msg)),
      field("sid", g.int(Number(sid))),
      field("seq", g.int(Number(seq)))
    );
  }
  function emitUI(v) {
    return encoder2.encode(emit(v));
  }
  function emitProgress(pct, msg) {
    return emitUI(progress(pct, msg));
  }
  function emitLog(level, msg) {
    return emitUI(log(level, msg));
  }
  function emitMetric(name, value, unit) {
    return emitUI(metric(name, value, unit));
  }
  function emitArtifact(mime, ref, name) {
    return emitUI(artifact(mime, ref, name));
  }
  function emitError(code, msg, sid, seq) {
    return emitUI(error(code, msg, sid, seq));
  }
  function emitResyncRequest(sid, seq, want, reason) {
    return emitUI(resyncRequest(sid, seq, want, reason));
  }
  function parseUIEvent(payload) {
    const decoder2 = new TextDecoder();
    const text = decoder2.decode(payload);
    const match = text.match(/^(\w+)[@{]\((.*)\)$/s) || text.match(/^(\w+)\{(.*)\}$/s);
    if (!match) {
      throw new Error(`Invalid UI event format: ${text}`);
    }
    const type = match[1];
    const content = match[2];
    const fields = {};
    const pairs = content.match(/(\w+)=("[^"]*"|\S+)/g);
    if (pairs) {
      for (const pair of pairs) {
        const [key, ...rest] = pair.split("=");
        let value = rest.join("=");
        if (typeof value === "string") {
          if (value.startsWith('"') && value.endsWith('"')) {
            value = value.slice(1, -1);
          } else if (value === "t" || value === "true") {
            value = true;
          } else if (value === "f" || value === "false") {
            value = false;
          } else if (/^-?\d+$/.test(value)) {
            value = parseInt(value, 10);
          } else if (/^-?\d*\.\d+$/.test(value)) {
            value = parseFloat(value);
          }
        }
        fields[key] = value;
      }
    }
    return { type, fields };
  }

  // src/decimal128.ts
  var DecimalError = class extends Error {
    constructor(message) {
      super(message);
      this.name = "DecimalError";
    }
  };
  var Decimal128 = class _Decimal128 {
    constructor(scale, coef) {
      if (scale < -127 || scale > 127) {
        throw new DecimalError(`scale must be -127 to 127, got ${scale}`);
      }
      this.scale = scale;
      this.coef = coef;
    }
    /**
     * Create a Decimal128 from an integer.
     */
    static fromInt(value) {
      return new _Decimal128(0, BigInt(value));
    }
    /**
     * Create a Decimal128 from a string.
     * Examples: "123.45", "99.99", "-0.001"
     */
    static fromString(s) {
      s = s.trim();
      if (s.endsWith("m")) {
        s = s.slice(0, -1);
      }
      const negative = s.startsWith("-");
      if (negative) {
        s = s.slice(1);
      }
      const parts = s.split(".");
      if (parts.length > 2) {
        throw new DecimalError(`invalid decimal format: ${s}`);
      }
      let scale = 0;
      let coefStr;
      if (parts.length === 2) {
        const intPart = parts[0] || "0";
        const fracPart = parts[1];
        scale = fracPart.length;
        coefStr = intPart + fracPart;
      } else {
        coefStr = parts[0];
      }
      if (scale > 127) {
        throw new DecimalError(`scale too large: ${scale}`);
      }
      let coef = BigInt(coefStr);
      if (negative) {
        coef = -coef;
      }
      return new _Decimal128(scale, coef);
    }
    /**
     * Create a Decimal128 from a number (with potential precision loss).
     */
    static fromNumber(n) {
      return _Decimal128.fromString(n.toString());
    }
    /**
     * Convert to integer (truncates fractional part).
     */
    toInt() {
      const divisor = 10n ** BigInt(this.scale);
      return this.coef / divisor;
    }
    /**
     * Convert to number (with potential precision loss).
     */
    toNumber() {
      const divisor = 10 ** this.scale;
      return Number(this.coef) / divisor;
    }
    /**
     * Convert to string.
     */
    toString() {
      if (this.scale === 0) {
        return this.coef.toString();
      }
      const negative = this.coef < 0n;
      let coefStr = (negative ? -this.coef : this.coef).toString();
      while (coefStr.length <= this.scale) {
        coefStr = "0" + coefStr;
      }
      const insertPos = coefStr.length - this.scale;
      const result = coefStr.slice(0, insertPos) + "." + coefStr.slice(insertPos);
      return negative ? "-" + result : result;
    }
    /**
     * Check if value is zero.
     */
    isZero() {
      return this.coef === 0n;
    }
    /**
     * Check if value is negative.
     */
    isNegative() {
      return this.coef < 0n;
    }
    /**
     * Check if value is positive.
     */
    isPositive() {
      return this.coef > 0n;
    }
    /**
     * Return the absolute value.
     */
    abs() {
      return new _Decimal128(this.scale, this.coef < 0n ? -this.coef : this.coef);
    }
    /**
     * Negate the value.
     */
    negate() {
      return new _Decimal128(this.scale, -this.coef);
    }
    /**
     * Add two decimals.
     */
    add(other) {
      let c1 = this.coef;
      let c2 = other.coef;
      let targetScale;
      if (this.scale < other.scale) {
        const diff = other.scale - this.scale;
        c1 = c1 * 10n ** BigInt(diff);
        targetScale = other.scale;
      } else {
        const diff = this.scale - other.scale;
        c2 = c2 * 10n ** BigInt(diff);
        targetScale = this.scale;
      }
      return new _Decimal128(targetScale, c1 + c2);
    }
    /**
     * Subtract two decimals.
     */
    sub(other) {
      return this.add(other.negate());
    }
    /**
     * Multiply two decimals.
     */
    mul(other) {
      const result = this.coef * other.coef;
      const newScale = this.scale + other.scale;
      if (newScale > 127 || newScale < -127) {
        throw new DecimalError("scale overflow");
      }
      return new _Decimal128(newScale, result);
    }
    /**
     * Divide two decimals.
     */
    div(other) {
      if (other.coef === 0n) {
        throw new DecimalError("division by zero");
      }
      const result = this.coef / other.coef;
      const newScale = this.scale - other.scale;
      if (newScale > 127 || newScale < -127) {
        throw new DecimalError("scale overflow");
      }
      return new _Decimal128(newScale, result);
    }
    /**
     * Compare two decimals.
     * Returns -1 if this < other, 0 if equal, 1 if this > other.
     */
    cmp(other) {
      let c1 = this.coef;
      let c2 = other.coef;
      if (this.scale < other.scale) {
        const diff = other.scale - this.scale;
        c1 = c1 * 10n ** BigInt(diff);
      } else if (this.scale > other.scale) {
        const diff = this.scale - other.scale;
        c2 = c2 * 10n ** BigInt(diff);
      }
      if (c1 < c2) return -1;
      if (c1 > c2) return 1;
      return 0;
    }
    /**
     * Check equality.
     */
    equals(other) {
      return this.cmp(other) === 0;
    }
    /**
     * Less than comparison.
     */
    lt(other) {
      return this.cmp(other) < 0;
    }
    /**
     * Greater than comparison.
     */
    gt(other) {
      return this.cmp(other) > 0;
    }
    /**
     * Less than or equal comparison.
     */
    lte(other) {
      return this.cmp(other) <= 0;
    }
    /**
     * Greater than or equal comparison.
     */
    gte(other) {
      return this.cmp(other) >= 0;
    }
  };
  function isDecimalLiteral(s) {
    s = s.trim();
    if (!s.endsWith("m")) {
      return false;
    }
    try {
      Decimal128.fromString(s.slice(0, -1));
      return true;
    } catch {
      return false;
    }
  }
  function parseDecimalLiteral(s) {
    s = s.trim();
    if (!s.endsWith("m")) {
      throw new DecimalError("not a decimal literal");
    }
    return Decimal128.fromString(s.slice(0, -1));
  }
  function decimal(value) {
    if (typeof value === "string") {
      return Decimal128.fromString(value);
    }
    if (typeof value === "bigint") {
      return Decimal128.fromInt(value);
    }
    return Decimal128.fromNumber(value);
  }

  // src/schema_evolution.ts
  var EvolutionMode = /* @__PURE__ */ ((EvolutionMode2) => {
    EvolutionMode2["Strict"] = "strict";
    EvolutionMode2["Tolerant"] = "tolerant";
    EvolutionMode2["Migrate"] = "migrate";
    return EvolutionMode2;
  })(EvolutionMode || {});
  var EvolvingField = class {
    constructor(name, config) {
      this.name = name;
      this.type = config.type;
      this.required = config.required ?? false;
      this.default = config.default;
      this.addedIn = config.addedIn ?? "1.0";
      this.deprecatedIn = config.deprecatedIn;
      this.renamedFrom = config.renamedFrom;
      this.validation = config.validation ? typeof config.validation === "string" ? new RegExp(config.validation) : config.validation : void 0;
    }
    /**
     * Check if field is available in a given version.
     */
    isAvailableIn(version) {
      if (compareVersions(version, this.addedIn) < 0) {
        return false;
      }
      if (this.deprecatedIn && compareVersions(version, this.deprecatedIn) >= 0) {
        return false;
      }
      return true;
    }
    /**
     * Check if field is deprecated in a given version.
     */
    isDeprecatedIn(version) {
      if (!this.deprecatedIn) {
        return false;
      }
      return compareVersions(version, this.deprecatedIn) >= 0;
    }
    /**
     * Validate a value against this field.
     */
    validate(value) {
      if (value === null || value === void 0) {
        if (this.required) {
          return `field ${this.name} is required`;
        }
        return null;
      }
      switch (this.type) {
        case "str":
          if (typeof value !== "string") {
            return `field ${this.name} must be string`;
          }
          if (this.validation && !this.validation.test(value)) {
            return `field ${this.name} does not match pattern`;
          }
          break;
        case "int":
          if (typeof value !== "number" || !Number.isInteger(value)) {
            return `field ${this.name} must be int`;
          }
          break;
        case "float":
          if (typeof value !== "number") {
            return `field ${this.name} must be float`;
          }
          break;
        case "bool":
          if (typeof value !== "boolean") {
            return `field ${this.name} must be bool`;
          }
          break;
        case "list":
          if (!Array.isArray(value)) {
            return `field ${this.name} must be list`;
          }
          break;
      }
      return null;
    }
  };
  var VersionSchema = class {
    constructor(name, version) {
      this.name = name;
      this.version = version;
      this.fields = /* @__PURE__ */ new Map();
      this.description = "";
    }
    /**
     * Add a field.
     */
    addField(field2) {
      this.fields.set(field2.name, field2);
    }
    /**
     * Get a field by name.
     */
    getField(name) {
      return this.fields.get(name);
    }
    /**
     * Validate data against this schema.
     */
    validate(data) {
      for (const [name, field2] of this.fields) {
        if (field2.required && !(name in data)) {
          return `missing required field: ${name}`;
        }
      }
      for (const [name, value] of Object.entries(data)) {
        const field2 = this.fields.get(name);
        if (field2) {
          const error2 = field2.validate(value);
          if (error2) {
            return error2;
          }
        }
      }
      return null;
    }
  };
  var VersionedSchema = class {
    constructor(name) {
      this.name = name;
      this.versions = /* @__PURE__ */ new Map();
      this.latestVersion = "1.0";
      this.mode = "tolerant" /* Tolerant */;
    }
    /**
     * Set evolution mode.
     */
    withMode(mode) {
      this.mode = mode;
      return this;
    }
    /**
     * Add a version with fields.
     */
    addVersion(version, fields) {
      const schema = new VersionSchema(this.name, version);
      for (const [name, config] of Object.entries(fields)) {
        const fieldConfig = { ...config };
        if (!fieldConfig.addedIn) {
          fieldConfig.addedIn = version;
        }
        schema.addField(new EvolvingField(name, fieldConfig));
      }
      this.versions.set(version, schema);
      this.latestVersion = this.getLatestVersion();
    }
    /**
     * Get schema for a specific version.
     */
    getVersion(version) {
      return this.versions.get(version);
    }
    /**
     * Parse data from a specific version.
     */
    parse(data, fromVersion) {
      const schema = this.getVersion(fromVersion);
      if (!schema) {
        return { error: `unknown version: ${fromVersion}` };
      }
      if (this.mode === "strict" /* Strict */) {
        const error2 = schema.validate(data);
        if (error2) {
          return { error: error2 };
        }
      }
      let result = { ...data };
      if (fromVersion !== this.latestVersion) {
        const migrated = this.migrate(data, fromVersion, this.latestVersion);
        if (migrated.error) {
          return migrated;
        }
        result = migrated.data;
      }
      if (this.mode === "tolerant" /* Tolerant */) {
        const targetSchema = this.getVersion(this.latestVersion);
        if (targetSchema) {
          const filtered = {};
          for (const [k, v] of Object.entries(result)) {
            if (targetSchema.fields.has(k)) {
              filtered[k] = v;
            }
          }
          result = filtered;
        }
      }
      return { data: result };
    }
    /**
     * Emit version header for data.
     */
    emit(data, version) {
      const targetVersion = version ?? this.latestVersion;
      const schema = this.getVersion(targetVersion);
      if (!schema) {
        return { error: `unknown version: ${targetVersion}` };
      }
      const error2 = schema.validate(data);
      if (error2) {
        return { error: error2 };
      }
      return { header: `@version ${targetVersion}` };
    }
    /**
     * Migrate data between versions.
     */
    migrate(data, fromVersion, toVersion) {
      const path = this.getMigrationPath(fromVersion, toVersion);
      if (!path) {
        return { error: `cannot migrate from ${fromVersion} to ${toVersion}` };
      }
      let currentData = { ...data };
      let currentVersion = fromVersion;
      for (const nextVersion of path) {
        const result = this.migrateStep(currentData, currentVersion, nextVersion);
        if (result.error) {
          return result;
        }
        currentData = result.data;
        currentVersion = nextVersion;
      }
      return { data: currentData };
    }
    /**
     * Migrate one step.
     */
    migrateStep(data, _fromVersion, toVersion) {
      const toSchema = this.getVersion(toVersion);
      if (!toSchema) {
        return { error: "invalid version" };
      }
      const result = { ...data };
      for (const [name, field2] of toSchema.fields) {
        if (field2.renamedFrom && field2.renamedFrom in result && !(name in result)) {
          result[name] = result[field2.renamedFrom];
          delete result[field2.renamedFrom];
        }
      }
      for (const [name, field2] of toSchema.fields) {
        if (!(name in result)) {
          if (field2.default !== void 0) {
            result[name] = field2.default;
          } else if (!field2.required) {
            result[name] = null;
          }
        }
      }
      if (this.mode === "tolerant" /* Tolerant */) {
        for (const key of Object.keys(result)) {
          if (!toSchema.fields.has(key)) {
            delete result[key];
          }
        }
      }
      return { data: result };
    }
    /**
     * Get migration path between versions.
     */
    getMigrationPath(fromVersion, toVersion) {
      const versions = Array.from(this.versions.keys()).sort(
        (a, b) => compareVersions(a, b)
      );
      const fromIdx = versions.indexOf(fromVersion);
      const toIdx = versions.indexOf(toVersion);
      if (fromIdx === -1 || toIdx === -1) {
        return null;
      }
      if (fromIdx < toIdx) {
        return versions.slice(fromIdx + 1, toIdx + 1);
      } else if (fromIdx > toIdx) {
        return null;
      }
      return [];
    }
    /**
     * Get the latest version string.
     */
    getLatestVersion() {
      const versions = Array.from(this.versions.keys()).sort(
        (a, b) => compareVersions(a, b)
      );
      return versions[versions.length - 1] ?? "1.0";
    }
    /**
     * Get changelog of schema evolution.
     */
    getChangelog() {
      const versions = Array.from(this.versions.keys()).sort(
        (a, b) => compareVersions(a, b)
      );
      return versions.map((version) => {
        const schema = this.versions.get(version);
        const addedFields = [];
        const deprecatedFields = [];
        const renamedFields = [];
        for (const [name, field2] of schema.fields) {
          if (field2.addedIn === version) {
            addedFields.push(name);
          }
          if (field2.deprecatedIn === version) {
            deprecatedFields.push(name);
          }
          if (field2.renamedFrom) {
            renamedFields.push([field2.renamedFrom, name]);
          }
        }
        return {
          version,
          description: schema.description,
          addedFields,
          deprecatedFields,
          renamedFields
        };
      });
    }
  };
  function compareVersions(v1, v2) {
    const parts1 = v1.split(".").map((s) => parseInt(s, 10) || 0);
    const parts2 = v2.split(".").map((s) => parseInt(s, 10) || 0);
    const maxLen = Math.max(parts1.length, parts2.length);
    for (let i = 0; i < maxLen; i++) {
      const p1 = parts1[i] ?? 0;
      const p2 = parts2[i] ?? 0;
      if (p1 < p2) return -1;
      if (p1 > p2) return 1;
    }
    return 0;
  }
  function parseVersionHeader(text) {
    text = text.trim();
    if (!text.startsWith("@version ")) {
      return null;
    }
    const version = text.slice(9).trim();
    if (!version) {
      return null;
    }
    return version;
  }
  function formatVersionHeader(version) {
    return `@version ${version}`;
  }
  function versionedSchema(name) {
    return new VersionedSchema(name);
  }

  // src/stream_validator.ts
  var hasOwnProperty3 = Object.prototype.hasOwnProperty;
  function hasOwn3(obj, key) {
    return hasOwnProperty3.call(obj, key);
  }
  function createArgRecord() {
    return /* @__PURE__ */ Object.create(null);
  }
  function createFieldRecord() {
    return /* @__PURE__ */ Object.create(null);
  }
  function cloneFieldRecord(fields) {
    return Object.assign(createFieldRecord(), fields);
  }
  var ToolRegistry = class {
    constructor() {
      this.tools = /* @__PURE__ */ new Map();
    }
    /**
     * Register a tool.
     */
    register(tool) {
      const args = createArgRecord();
      for (const [name, schema] of Object.entries(tool.args)) {
        args[name] = schema;
      }
      this.tools.set(tool.name, { ...tool, args });
    }
    /**
     * Check if a tool is allowed.
     */
    isAllowed(name) {
      return this.tools.has(name);
    }
    /**
     * Get a tool schema.
     */
    get(name) {
      return this.tools.get(name);
    }
  };
  var ErrorCode = /* @__PURE__ */ ((ErrorCode2) => {
    ErrorCode2["UnknownTool"] = "UNKNOWN_TOOL";
    ErrorCode2["MissingRequired"] = "MISSING_REQUIRED";
    ErrorCode2["MissingTool"] = "MISSING_TOOL";
    ErrorCode2["ConstraintMin"] = "CONSTRAINT_MIN";
    ErrorCode2["ConstraintMax"] = "CONSTRAINT_MAX";
    ErrorCode2["ConstraintLen"] = "CONSTRAINT_LEN";
    ErrorCode2["ConstraintPattern"] = "CONSTRAINT_PATTERN";
    ErrorCode2["ConstraintEnum"] = "CONSTRAINT_ENUM";
    ErrorCode2["InvalidType"] = "INVALID_TYPE";
    ErrorCode2["LimitExceeded"] = "LIMIT_EXCEEDED";
    return ErrorCode2;
  })(ErrorCode || {});
  var DEFAULT_MAX_BUFFER = 1 << 20;
  var DEFAULT_MAX_FIELDS = 1e3;
  var DEFAULT_MAX_ERRORS = 100;
  var ValidatorState = /* @__PURE__ */ ((ValidatorState2) => {
    ValidatorState2["Waiting"] = "waiting";
    ValidatorState2["InObject"] = "in_object";
    ValidatorState2["Complete"] = "complete";
    ValidatorState2["Error"] = "error";
    return ValidatorState2;
  })(ValidatorState || {});
  var StreamingValidator = class {
    constructor(registry, limits) {
      // Parser state
      this.buffer = "";
      this.state = "waiting" /* Waiting */;
      this.depth = 0;
      this.inString = false;
      this.escapeNext = false;
      this.currentKey = "";
      this.currentVal = "";
      this.hasKey = false;
      // Parsed data
      this.toolName = null;
      this.fields = createFieldRecord();
      this.fieldCount = 0;
      this.errors = [];
      // Timing
      this.tokenCount = 0;
      this.charCount = 0;
      this.startTime = 0;
      this.toolDetectedAtToken = 0;
      this.toolDetectedAtChar = 0;
      this.toolDetectedAtTime = 0;
      this.firstErrorAtToken = 0;
      this.firstErrorAtTime = 0;
      this.completeAtToken = 0;
      this.completeAtTime = 0;
      // Timeline
      this.timeline = [];
      // Hard limits to prevent OOM/DoS
      this.maxBufferSize = DEFAULT_MAX_BUFFER;
      this.maxFieldCount = DEFAULT_MAX_FIELDS;
      this.maxErrorCount = DEFAULT_MAX_ERRORS;
      this.registry = registry;
      if (limits) {
        this.withLimits(limits);
      }
    }
    /**
     * Set custom limits. Returns self for chaining.
     */
    withLimits(limits) {
      if (limits.maxBufferSize !== void 0 && limits.maxBufferSize > 0) {
        this.maxBufferSize = limits.maxBufferSize;
      }
      if (limits.maxFieldCount !== void 0 && limits.maxFieldCount > 0) {
        this.maxFieldCount = limits.maxFieldCount;
      }
      if (limits.maxErrorCount !== void 0 && limits.maxErrorCount > 0) {
        this.maxErrorCount = limits.maxErrorCount;
      }
      return this;
    }
    /**
     * Add an error, respecting maxErrorCount limit.
     */
    addError(code, message, field2) {
      if (this.errors.length >= this.maxErrorCount) {
        return;
      }
      this.errors.push({ code, message, field: field2 });
    }
    /**
     * Reset the validator for reuse.
     */
    reset() {
      this.buffer = "";
      this.state = "waiting" /* Waiting */;
      this.depth = 0;
      this.inString = false;
      this.escapeNext = false;
      this.currentKey = "";
      this.currentVal = "";
      this.hasKey = false;
      this.toolName = null;
      this.fields = createFieldRecord();
      this.fieldCount = 0;
      this.errors = [];
      this.tokenCount = 0;
      this.charCount = 0;
      this.startTime = 0;
      this.toolDetectedAtToken = 0;
      this.toolDetectedAtChar = 0;
      this.toolDetectedAtTime = 0;
      this.firstErrorAtToken = 0;
      this.firstErrorAtTime = 0;
      this.completeAtToken = 0;
      this.completeAtTime = 0;
      this.timeline = [];
    }
    /**
     * Start timing.
     */
    start() {
      this.startTime = Date.now();
    }
    /**
     * Process a token from the LLM.
     */
    pushToken(token) {
      if (this.startTime === 0) {
        this.start();
      }
      this.tokenCount++;
      for (const c of token) {
        this.charCount++;
        this.processChar(c);
      }
      const elapsed = Date.now() - this.startTime;
      if (this.toolName && this.toolDetectedAtToken === 0) {
        this.toolDetectedAtToken = this.tokenCount;
        this.toolDetectedAtChar = this.charCount;
        this.toolDetectedAtTime = elapsed;
        const allowed = this.registry.isAllowed(this.toolName);
        this.timeline.push({
          event: "TOOL_DETECTED",
          token: this.tokenCount,
          charPos: this.charCount,
          elapsed,
          detail: `tool=${this.toolName} allowed=${allowed}`
        });
      }
      if (this.errors.length > 0 && this.firstErrorAtToken === 0) {
        this.firstErrorAtToken = this.tokenCount;
        this.firstErrorAtTime = elapsed;
        this.timeline.push({
          event: "ERROR",
          token: this.tokenCount,
          charPos: this.charCount,
          elapsed,
          detail: this.errors[0].message
        });
      }
      if (this.state === "complete" /* Complete */ && this.completeAtToken === 0) {
        this.completeAtToken = this.tokenCount;
        this.completeAtTime = elapsed;
        this.timeline.push({
          event: "COMPLETE",
          token: this.tokenCount,
          charPos: this.charCount,
          elapsed,
          detail: `valid=${this.errors.length === 0}`
        });
      }
      return this.getResult();
    }
    processChar(c) {
      if (this.state === "error" /* Error */) {
        return;
      }
      if (this.buffer.length >= this.maxBufferSize) {
        this.state = "error" /* Error */;
        this.addError("LIMIT_EXCEEDED" /* LimitExceeded */, "Buffer size limit exceeded");
        return;
      }
      this.buffer += c;
      if (this.escapeNext) {
        this.escapeNext = false;
        this.currentVal += c;
        return;
      }
      if (c === "\\" && this.inString) {
        this.escapeNext = true;
        this.currentVal += c;
        return;
      }
      if (c === '"') {
        if (this.inString) {
          this.inString = false;
        } else {
          this.inString = true;
          this.currentVal = "";
        }
        return;
      }
      if (this.inString) {
        this.currentVal += c;
        return;
      }
      switch (c) {
        case "{":
          if (this.state === "waiting" /* Waiting */) {
            const preBraceText = this.currentVal.trim();
            if (preBraceText) {
              this.toolName = preBraceText;
              this.currentVal = "";
              if (!this.registry.isAllowed(preBraceText)) {
                this.addError("UNKNOWN_TOOL" /* UnknownTool */, `Unknown tool: ${preBraceText}`);
              }
            }
            this.state = "in_object" /* InObject */;
          }
          this.depth++;
          break;
        case "}":
          this.depth--;
          if (this.depth === 0) {
            this.finishField();
            this.state = "complete" /* Complete */;
            this.validateComplete();
          }
          break;
        case "[":
          this.depth++;
          this.currentVal += c;
          break;
        case "]":
          this.depth--;
          this.currentVal += c;
          break;
        case "=":
          if (this.depth === 1 && !this.hasKey) {
            this.currentKey = this.currentVal.trim();
            this.currentVal = "";
            this.hasKey = true;
          } else {
            this.currentVal += c;
          }
          break;
        case " ":
        case "\n":
        case "	":
        case "\r":
          if (this.depth === 1 && this.hasKey && this.currentVal.length > 0) {
            this.finishField();
          }
          break;
        default:
          if (this.state === "waiting" /* Waiting */ && this.depth === 0) {
            this.currentVal += c;
          } else if (this.depth >= 1) {
            this.currentVal += c;
          }
      }
    }
    finishField() {
      if (!this.hasKey) {
        return;
      }
      const key = this.currentKey;
      const valStr = this.currentVal.trim();
      this.currentKey = "";
      this.currentVal = "";
      this.hasKey = false;
      const value = this.parseValue(valStr);
      if (key === "action" || key === "tool") {
        if (typeof value === "string") {
          this.toolName = value;
          if (!this.registry.isAllowed(value)) {
            this.addError("UNKNOWN_TOOL" /* UnknownTool */, `Unknown tool: ${value}`, key);
          }
        }
      }
      if (this.toolName) {
        this.validateField(key, value);
      }
      if (!hasOwn3(this.fields, key)) {
        if (this.fieldCount >= this.maxFieldCount) {
          this.state = "error" /* Error */;
          this.addError("LIMIT_EXCEEDED" /* LimitExceeded */, "Field count limit exceeded");
          return;
        }
        this.fieldCount++;
      }
      this.fields[key] = value;
    }
    parseValue(s) {
      if (s === "t" || s === "true") {
        return true;
      }
      if (s === "f" || s === "false") {
        return false;
      }
      if (s === "_" || s === "null" || s === "" || s === "\u2205") {
        return null;
      }
      if (/^-?\d+$/.test(s)) {
        return parseInt(s, 10);
      }
      if (/^-?\d+\.?\d*(?:[eE][+-]?\d+)?$/.test(s) || /^-?\d*\.?\d+(?:[eE][+-]?\d+)?$/.test(s)) {
        const f = parseFloat(s);
        if (!isNaN(f)) {
          return f;
        }
      }
      return s;
    }
    validateField(key, value) {
      if (key === "action" || key === "tool") {
        return;
      }
      const schema = this.registry.get(this.toolName);
      if (!schema) {
        return;
      }
      const argSchema = hasOwn3(schema.args, key) ? schema.args[key] : void 0;
      if (!argSchema) {
        this.addError("UNKNOWN_TOOL" /* UnknownTool */, `Unknown argument: ${key}`, key);
        return;
      }
      if (!this.isValidType(argSchema.type, value)) {
        this.addError("INVALID_TYPE" /* InvalidType */, `${key} expected ${argSchema.type}`, key);
        return;
      }
      if (typeof value === "number") {
        if (argSchema.min !== void 0 && value < argSchema.min) {
          this.addError("CONSTRAINT_MIN" /* ConstraintMin */, `${key} < ${argSchema.min}`, key);
        }
        if (argSchema.max !== void 0 && value > argSchema.max) {
          this.addError("CONSTRAINT_MAX" /* ConstraintMax */, `${key} > ${argSchema.max}`, key);
        }
      }
      if (typeof value === "string") {
        if (argSchema.minLen !== void 0 && value.length < argSchema.minLen) {
          this.addError("CONSTRAINT_LEN" /* ConstraintLen */, `${key} length < ${argSchema.minLen}`, key);
        }
        if (argSchema.maxLen !== void 0 && value.length > argSchema.maxLen) {
          this.addError("CONSTRAINT_LEN" /* ConstraintLen */, `${key} length > ${argSchema.maxLen}`, key);
        }
        if (argSchema.pattern && !argSchema.pattern.test(value)) {
          this.addError("CONSTRAINT_PATTERN" /* ConstraintPattern */, `${key} pattern mismatch`, key);
        }
        if (argSchema.enumValues && !argSchema.enumValues.includes(value)) {
          this.addError("CONSTRAINT_ENUM" /* ConstraintEnum */, `${key} not in allowed values`, key);
        }
      }
    }
    isValidType(type, value) {
      if (value === null) {
        return true;
      }
      switch (type) {
        case "string":
          return typeof value === "string";
        case "int":
          return typeof value === "number" && Number.isFinite(value) && Number.isInteger(value);
        case "float":
        case "number":
          return typeof value === "number" && Number.isFinite(value);
        case "bool":
        case "boolean":
          return typeof value === "boolean";
        case "null":
          return value === null;
        case "any":
          return true;
      }
    }
    validateComplete() {
      if (!this.toolName) {
        this.addError("MISSING_TOOL" /* MissingTool */, "No action field found");
        return;
      }
      const schema = this.registry.get(this.toolName);
      if (!schema) {
        return;
      }
      for (const [argName, argSchema] of Object.entries(schema.args)) {
        if (argSchema.required && !hasOwn3(this.fields, argName)) {
          this.addError("MISSING_REQUIRED" /* MissingRequired */, `Missing required field: ${argName}`, argName);
        }
      }
    }
    /**
     * Get the current validation result.
     */
    getResult() {
      const toolAllowed = this.toolName ? this.registry.isAllowed(this.toolName) : null;
      return {
        complete: this.state === "complete" /* Complete */,
        valid: this.errors.length === 0,
        state: this.state,
        toolName: this.toolName,
        toolAllowed,
        errors: [...this.errors],
        fields: cloneFieldRecord(this.fields),
        tokenCount: this.tokenCount,
        charCount: this.charCount,
        timeline: [...this.timeline],
        toolDetectedAtToken: this.toolDetectedAtToken,
        toolDetectedAtChar: this.toolDetectedAtChar,
        toolDetectedAtTime: this.toolDetectedAtTime,
        firstErrorAtToken: this.firstErrorAtToken,
        firstErrorAtTime: this.firstErrorAtTime,
        completeAtToken: this.completeAtToken,
        completeAtTime: this.completeAtTime
      };
    }
    /**
     * Check if the stream should be cancelled.
     */
    shouldStop() {
      return this.errors.some((e) => e.code === "UNKNOWN_TOOL" /* UnknownTool */ || e.code === "LIMIT_EXCEEDED" /* LimitExceeded */);
    }
    /**
     * Check if the detected tool is allowed.
     * Returns false if no tool detected or registry not configured.
     */
    isToolAllowed() {
      if (!this.toolName) {
        return false;
      }
      return this.registry.isAllowed(this.toolName);
    }
    /**
     * Get the parsed fields if validation is complete and valid.
     * Returns null if not complete or if there are errors.
     */
    getParsed() {
      if (this.state === "complete" /* Complete */ && this.errors.length === 0) {
        return cloneFieldRecord(this.fields);
      }
      return null;
    }
  };
  function defaultToolRegistry() {
    const registry = new ToolRegistry();
    registry.register({
      name: "search",
      description: "Search for information",
      args: {
        query: { type: "string", required: true, minLen: 1 },
        max_results: { type: "int", min: 1, max: 100 }
      }
    });
    registry.register({
      name: "calculate",
      description: "Evaluate a mathematical expression",
      args: {
        expression: { type: "string", required: true },
        precision: { type: "int", min: 0, max: 15 }
      }
    });
    registry.register({
      name: "browse",
      description: "Fetch a web page",
      args: {
        url: { type: "string", required: true, pattern: /^https?:\/\// }
      }
    });
    registry.register({
      name: "execute",
      description: "Execute a shell command",
      args: {
        command: { type: "string", required: true }
      }
    });
    registry.register({
      name: "read_file",
      description: "Read a file from disk",
      args: {
        path: { type: "string", required: true },
        limit: { type: "int", min: 1 }
      }
    });
    registry.register({
      name: "write_file",
      description: "Write content to a file",
      args: {
        path: { type: "string", required: true },
        content: { type: "string", required: true }
      }
    });
    return registry;
  }

  // src/index.ts
  function jsonToPacked(json, schema, options = {}) {
    const gv = fromJson(json, { ...options, schema });
    return emitPacked(gv, schema);
  }
  function jsonToTabular(json, schema, options = {}) {
    const gv = fromJson(json, { ...options, schema });
    return emitTabular(gv, schema);
  }
  function jsonToLyph(json, schema, options = {}) {
    const gv = fromJson(json, { ...options, schema });
    return emitV2(gv, schema, options);
  }
  function estimateTokens(s) {
    return s.split(/\s+/).filter(Boolean).length;
  }
  function compareTokens(json, schema, options = {}) {
    const jsonStr = JSON.stringify(json);
    const lyphStr = jsonToLyph(json, schema, options);
    const jsonTokens = estimateTokens(jsonStr);
    const lyphTokens = estimateTokens(lyphStr);
    const savings = jsonTokens - lyphTokens;
    const savingsPercent = jsonTokens > 0 ? savings / jsonTokens * 100 : 0;
    return { json: jsonTokens, lyph: lyphTokens, savings, savingsPercent };
  }
  return __toCommonJS(index_exports);
})();
