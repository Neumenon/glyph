"use strict";
/**
 * GLYPH Streaming Validator
 *
 * Validates GLYPH tool calls incrementally as tokens arrive from an LLM.
 *
 * This enables:
 * - Early tool detection: Know the tool name before full response
 * - Early rejection: Stop on unknown tools mid-stream
 * - Incremental validation: Check constraints as tokens arrive
 * - Latency savings: Reject bad payloads without waiting for completion
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.StreamingValidator = exports.ValidatorState = exports.DEFAULT_MAX_ERRORS = exports.DEFAULT_MAX_FIELDS = exports.DEFAULT_MAX_BUFFER = exports.ErrorCode = exports.ToolRegistry = void 0;
exports.defaultToolRegistry = defaultToolRegistry;
class ToolRegistry {
    constructor() {
        this.tools = new Map();
    }
    /**
     * Register a tool.
     */
    register(tool) {
        this.tools.set(tool.name, tool);
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
}
exports.ToolRegistry = ToolRegistry;
// ============================================================
// Validation Errors
// ============================================================
var ErrorCode;
(function (ErrorCode) {
    ErrorCode["UnknownTool"] = "UNKNOWN_TOOL";
    ErrorCode["MissingRequired"] = "MISSING_REQUIRED";
    ErrorCode["MissingTool"] = "MISSING_TOOL";
    ErrorCode["ConstraintMin"] = "CONSTRAINT_MIN";
    ErrorCode["ConstraintMax"] = "CONSTRAINT_MAX";
    ErrorCode["ConstraintLen"] = "CONSTRAINT_LEN";
    ErrorCode["ConstraintPattern"] = "CONSTRAINT_PATTERN";
    ErrorCode["ConstraintEnum"] = "CONSTRAINT_ENUM";
    ErrorCode["InvalidType"] = "INVALID_TYPE";
    ErrorCode["LimitExceeded"] = "LIMIT_EXCEEDED";
})(ErrorCode || (exports.ErrorCode = ErrorCode = {}));
// Default limits to prevent DoS
exports.DEFAULT_MAX_BUFFER = 1 << 20; // 1MB
exports.DEFAULT_MAX_FIELDS = 1000;
exports.DEFAULT_MAX_ERRORS = 100;
// ============================================================
// Validator State
// ============================================================
var ValidatorState;
(function (ValidatorState) {
    ValidatorState["Waiting"] = "waiting";
    ValidatorState["InObject"] = "in_object";
    ValidatorState["Complete"] = "complete";
    ValidatorState["Error"] = "error";
})(ValidatorState || (exports.ValidatorState = ValidatorState = {}));
class StreamingValidator {
    constructor(registry, limits) {
        // Parser state
        this.buffer = '';
        this.state = ValidatorState.Waiting;
        this.depth = 0;
        this.inString = false;
        this.escapeNext = false;
        this.currentKey = '';
        this.currentVal = '';
        this.hasKey = false;
        // Parsed data
        this.toolName = null;
        this.fields = {};
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
        this.maxBufferSize = exports.DEFAULT_MAX_BUFFER;
        this.maxFieldCount = exports.DEFAULT_MAX_FIELDS;
        this.maxErrorCount = exports.DEFAULT_MAX_ERRORS;
        this.registry = registry;
        if (limits) {
            this.withLimits(limits);
        }
    }
    /**
     * Set custom limits. Returns self for chaining.
     */
    withLimits(limits) {
        if (limits.maxBufferSize !== undefined && limits.maxBufferSize > 0) {
            this.maxBufferSize = limits.maxBufferSize;
        }
        if (limits.maxFieldCount !== undefined && limits.maxFieldCount > 0) {
            this.maxFieldCount = limits.maxFieldCount;
        }
        if (limits.maxErrorCount !== undefined && limits.maxErrorCount > 0) {
            this.maxErrorCount = limits.maxErrorCount;
        }
        return this;
    }
    /**
     * Add an error, respecting maxErrorCount limit.
     */
    addError(code, message, field) {
        if (this.errors.length >= this.maxErrorCount) {
            return;
        }
        this.errors.push({ code, message, field });
    }
    /**
     * Reset the validator for reuse.
     */
    reset() {
        this.buffer = '';
        this.state = ValidatorState.Waiting;
        this.depth = 0;
        this.inString = false;
        this.escapeNext = false;
        this.currentKey = '';
        this.currentVal = '';
        this.hasKey = false;
        this.toolName = null;
        this.fields = {};
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
        // Record tool detection
        if (this.toolName && this.toolDetectedAtToken === 0) {
            this.toolDetectedAtToken = this.tokenCount;
            this.toolDetectedAtChar = this.charCount;
            this.toolDetectedAtTime = elapsed;
            const allowed = this.registry.isAllowed(this.toolName);
            this.timeline.push({
                event: 'TOOL_DETECTED',
                token: this.tokenCount,
                charPos: this.charCount,
                elapsed,
                detail: `tool=${this.toolName} allowed=${allowed}`,
            });
        }
        // Record first error
        if (this.errors.length > 0 && this.firstErrorAtToken === 0) {
            this.firstErrorAtToken = this.tokenCount;
            this.firstErrorAtTime = elapsed;
            this.timeline.push({
                event: 'ERROR',
                token: this.tokenCount,
                charPos: this.charCount,
                elapsed,
                detail: this.errors[0].message,
            });
        }
        // Record completion
        if (this.state === ValidatorState.Complete && this.completeAtToken === 0) {
            this.completeAtToken = this.tokenCount;
            this.completeAtTime = elapsed;
            this.timeline.push({
                event: 'COMPLETE',
                token: this.tokenCount,
                charPos: this.charCount,
                elapsed,
                detail: `valid=${this.errors.length === 0}`,
            });
        }
        return this.getResult();
    }
    processChar(c) {
        // Check hard limits before processing
        if (this.buffer.length >= this.maxBufferSize) {
            if (this.state !== ValidatorState.Error) {
                this.state = ValidatorState.Error;
                this.addError(ErrorCode.LimitExceeded, 'Buffer size limit exceeded');
            }
            return;
        }
        if (Object.keys(this.fields).length >= this.maxFieldCount) {
            if (this.state !== ValidatorState.Error) {
                this.state = ValidatorState.Error;
                this.addError(ErrorCode.LimitExceeded, 'Field count limit exceeded');
            }
            return;
        }
        this.buffer += c;
        // Handle escape sequences
        if (this.escapeNext) {
            this.escapeNext = false;
            this.currentVal += c;
            return;
        }
        if (c === '\\' && this.inString) {
            this.escapeNext = true;
            this.currentVal += c;
            return;
        }
        // Handle quotes
        if (c === '"') {
            if (this.inString) {
                this.inString = false;
            }
            else {
                this.inString = true;
                this.currentVal = '';
            }
            return;
        }
        // Inside string - accumulate
        if (this.inString) {
            this.currentVal += c;
            return;
        }
        // Handle structural characters
        switch (c) {
            case '{':
                if (this.state === ValidatorState.Waiting) {
                    // Check for tool name before brace (e.g., "search{query=test}")
                    const preBraceText = this.currentVal.trim();
                    if (preBraceText) {
                        this.toolName = preBraceText;
                        this.currentVal = '';
                        // Validate against allow list
                        if (!this.registry.isAllowed(preBraceText)) {
                            this.addError(ErrorCode.UnknownTool, `Unknown tool: ${preBraceText}`);
                        }
                    }
                    this.state = ValidatorState.InObject;
                }
                this.depth++;
                break;
            case '}':
                this.depth--;
                if (this.depth === 0) {
                    this.finishField();
                    this.state = ValidatorState.Complete;
                    this.validateComplete();
                }
                break;
            case '[':
                this.depth++;
                this.currentVal += c;
                break;
            case ']':
                this.depth--;
                this.currentVal += c;
                break;
            case '=':
                if (this.depth === 1 && !this.hasKey) {
                    this.currentKey = this.currentVal.trim();
                    this.currentVal = '';
                    this.hasKey = true;
                }
                else {
                    this.currentVal += c;
                }
                break;
            case ' ':
            case '\n':
            case '\t':
            case '\r':
                if (this.depth === 1 && this.hasKey && this.currentVal.length > 0) {
                    this.finishField();
                }
                break;
            default:
                // Accumulate tool name before brace when waiting, or field value when in object
                if (this.state === ValidatorState.Waiting && this.depth === 0) {
                    this.currentVal += c;
                }
                else if (this.depth >= 1) {
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
        this.currentKey = '';
        this.currentVal = '';
        this.hasKey = false;
        const value = this.parseValue(valStr);
        // Check for tool/action field
        if (key === 'action' || key === 'tool') {
            if (typeof value === 'string') {
                this.toolName = value;
                // Validate against allow list
                if (!this.registry.isAllowed(value)) {
                    this.addError(ErrorCode.UnknownTool, `Unknown tool: ${value}`, key);
                }
            }
        }
        // Validate field constraints
        if (this.toolName) {
            this.validateField(key, value);
        }
        this.fields[key] = value;
    }
    parseValue(s) {
        // Boolean
        if (s === 't' || s === 'true') {
            return true;
        }
        if (s === 'f' || s === 'false') {
            return false;
        }
        // Null (including Unicode ∅)
        if (s === '_' || s === 'null' || s === '' || s === '∅') {
            return null;
        }
        // Integer (no decimal point or exponent)
        if (/^-?\d+$/.test(s)) {
            return parseInt(s, 10);
        }
        // Float (including scientific notation like 1e5, 1.5e-3)
        if (/^-?\d+\.?\d*(?:[eE][+-]?\d+)?$/.test(s) || /^-?\d*\.?\d+(?:[eE][+-]?\d+)?$/.test(s)) {
            const f = parseFloat(s);
            if (!isNaN(f)) {
                return f;
            }
        }
        // String
        return s;
    }
    validateField(key, value) {
        if (key === 'action' || key === 'tool') {
            return;
        }
        const schema = this.registry.get(this.toolName);
        if (!schema) {
            return;
        }
        const argSchema = schema.args[key];
        if (!argSchema) {
            return;
        }
        // Numeric constraints
        if (typeof value === 'number') {
            if (argSchema.min !== undefined && value < argSchema.min) {
                this.addError(ErrorCode.ConstraintMin, `${key} < ${argSchema.min}`, key);
            }
            if (argSchema.max !== undefined && value > argSchema.max) {
                this.addError(ErrorCode.ConstraintMax, `${key} > ${argSchema.max}`, key);
            }
        }
        // String constraints
        if (typeof value === 'string') {
            if (argSchema.minLen !== undefined && value.length < argSchema.minLen) {
                this.addError(ErrorCode.ConstraintLen, `${key} length < ${argSchema.minLen}`, key);
            }
            if (argSchema.maxLen !== undefined && value.length > argSchema.maxLen) {
                this.addError(ErrorCode.ConstraintLen, `${key} length > ${argSchema.maxLen}`, key);
            }
            if (argSchema.pattern && !argSchema.pattern.test(value)) {
                this.addError(ErrorCode.ConstraintPattern, `${key} pattern mismatch`, key);
            }
            if (argSchema.enumValues && !argSchema.enumValues.includes(value)) {
                this.addError(ErrorCode.ConstraintEnum, `${key} not in allowed values`, key);
            }
        }
    }
    validateComplete() {
        if (!this.toolName) {
            this.addError(ErrorCode.MissingTool, 'No action field found');
            return;
        }
        const schema = this.registry.get(this.toolName);
        if (!schema) {
            return;
        }
        // Check required fields
        for (const [argName, argSchema] of Object.entries(schema.args)) {
            if (argSchema.required && !(argName in this.fields)) {
                this.addError(ErrorCode.MissingRequired, `Missing required field: ${argName}`, argName);
            }
        }
    }
    /**
     * Get the current validation result.
     */
    getResult() {
        const toolAllowed = this.toolName ? this.registry.isAllowed(this.toolName) : null;
        return {
            complete: this.state === ValidatorState.Complete,
            valid: this.errors.length === 0,
            state: this.state,
            toolName: this.toolName,
            toolAllowed,
            errors: [...this.errors],
            fields: { ...this.fields },
            tokenCount: this.tokenCount,
            charCount: this.charCount,
            timeline: [...this.timeline],
            toolDetectedAtToken: this.toolDetectedAtToken,
            toolDetectedAtChar: this.toolDetectedAtChar,
            toolDetectedAtTime: this.toolDetectedAtTime,
            firstErrorAtToken: this.firstErrorAtToken,
            firstErrorAtTime: this.firstErrorAtTime,
            completeAtToken: this.completeAtToken,
            completeAtTime: this.completeAtTime,
        };
    }
    /**
     * Check if the stream should be cancelled.
     */
    shouldStop() {
        return this.errors.some(e => e.code === ErrorCode.UnknownTool || e.code === ErrorCode.LimitExceeded);
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
        if (this.state === ValidatorState.Complete && this.errors.length === 0) {
            return { ...this.fields };
        }
        return null;
    }
}
exports.StreamingValidator = StreamingValidator;
// ============================================================
// Default Registry
// ============================================================
/**
 * Create a default tool registry with common tools.
 */
function defaultToolRegistry() {
    const registry = new ToolRegistry();
    registry.register({
        name: 'search',
        description: 'Search for information',
        args: {
            query: { type: 'string', required: true, minLen: 1 },
            max_results: { type: 'int', min: 1, max: 100 },
        },
    });
    registry.register({
        name: 'calculate',
        description: 'Evaluate a mathematical expression',
        args: {
            expression: { type: 'string', required: true },
            precision: { type: 'int', min: 0, max: 15 },
        },
    });
    registry.register({
        name: 'browse',
        description: 'Fetch a web page',
        args: {
            url: { type: 'string', required: true, pattern: /^https?:\/\// },
        },
    });
    registry.register({
        name: 'execute',
        description: 'Execute a shell command',
        args: {
            command: { type: 'string', required: true },
        },
    });
    registry.register({
        name: 'read_file',
        description: 'Read a file from disk',
        args: {
            path: { type: 'string', required: true },
            limit: { type: 'int', min: 1 },
        },
    });
    registry.register({
        name: 'write_file',
        description: 'Write content to a file',
        args: {
            path: { type: 'string', required: true },
            content: { type: 'string', required: true },
        },
    });
    return registry;
}
//# sourceMappingURL=stream_validator.js.map