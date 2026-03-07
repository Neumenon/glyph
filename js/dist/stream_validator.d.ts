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
export interface ArgSchema {
    type: string;
    required?: boolean;
    min?: number;
    max?: number;
    minLen?: number;
    maxLen?: number;
    pattern?: RegExp;
    enumValues?: string[];
}
export interface ToolSchema {
    name: string;
    description?: string;
    args: Record<string, ArgSchema>;
}
export declare class ToolRegistry {
    private tools;
    /**
     * Register a tool.
     */
    register(tool: ToolSchema): void;
    /**
     * Check if a tool is allowed.
     */
    isAllowed(name: string): boolean;
    /**
     * Get a tool schema.
     */
    get(name: string): ToolSchema | undefined;
}
export declare enum ErrorCode {
    UnknownTool = "UNKNOWN_TOOL",
    MissingRequired = "MISSING_REQUIRED",
    MissingTool = "MISSING_TOOL",
    ConstraintMin = "CONSTRAINT_MIN",
    ConstraintMax = "CONSTRAINT_MAX",
    ConstraintLen = "CONSTRAINT_LEN",
    ConstraintPattern = "CONSTRAINT_PATTERN",
    ConstraintEnum = "CONSTRAINT_ENUM",
    InvalidType = "INVALID_TYPE",
    LimitExceeded = "LIMIT_EXCEEDED"
}
export declare const DEFAULT_MAX_BUFFER: number;
export declare const DEFAULT_MAX_FIELDS = 1000;
export declare const DEFAULT_MAX_ERRORS = 100;
export interface ValidatorLimits {
    maxBufferSize?: number;
    maxFieldCount?: number;
    maxErrorCount?: number;
}
export interface ValidationError {
    code: ErrorCode;
    message: string;
    field?: string;
}
export declare enum ValidatorState {
    Waiting = "waiting",
    InObject = "in_object",
    Complete = "complete",
    Error = "error"
}
export interface TimelineEvent {
    event: string;
    token: number;
    charPos: number;
    elapsed: number;
    detail: string;
}
export type FieldValue = null | boolean | number | string;
export interface ValidationResult {
    complete: boolean;
    valid: boolean;
    state: ValidatorState;
    toolName: string | null;
    toolAllowed: boolean | null;
    errors: ValidationError[];
    fields: Record<string, FieldValue>;
    tokenCount: number;
    charCount: number;
    timeline: TimelineEvent[];
    toolDetectedAtToken: number;
    toolDetectedAtChar: number;
    toolDetectedAtTime: number;
    firstErrorAtToken: number;
    firstErrorAtTime: number;
    completeAtToken: number;
    completeAtTime: number;
}
export declare class StreamingValidator {
    private registry;
    private buffer;
    private state;
    private depth;
    private inString;
    private escapeNext;
    private currentKey;
    private currentVal;
    private hasKey;
    private toolName;
    private fields;
    private errors;
    private tokenCount;
    private charCount;
    private startTime;
    private toolDetectedAtToken;
    private toolDetectedAtChar;
    private toolDetectedAtTime;
    private firstErrorAtToken;
    private firstErrorAtTime;
    private completeAtToken;
    private completeAtTime;
    private timeline;
    private maxBufferSize;
    private maxFieldCount;
    private maxErrorCount;
    constructor(registry: ToolRegistry, limits?: ValidatorLimits);
    /**
     * Set custom limits. Returns self for chaining.
     */
    withLimits(limits: ValidatorLimits): this;
    /**
     * Add an error, respecting maxErrorCount limit.
     */
    private addError;
    /**
     * Reset the validator for reuse.
     */
    reset(): void;
    /**
     * Start timing.
     */
    start(): void;
    /**
     * Process a token from the LLM.
     */
    pushToken(token: string): ValidationResult;
    private processChar;
    private finishField;
    private parseValue;
    private validateField;
    private validateComplete;
    /**
     * Get the current validation result.
     */
    getResult(): ValidationResult;
    /**
     * Check if the stream should be cancelled.
     */
    shouldStop(): boolean;
    /**
     * Check if the detected tool is allowed.
     * Returns false if no tool detected or registry not configured.
     */
    isToolAllowed(): boolean;
    /**
     * Get the parsed fields if validation is complete and valid.
     * Returns null if not complete or if there are errors.
     */
    getParsed(): Record<string, FieldValue> | null;
}
/**
 * Create a default tool registry with common tools.
 */
export declare function defaultToolRegistry(): ToolRegistry;
//# sourceMappingURL=stream_validator.d.ts.map