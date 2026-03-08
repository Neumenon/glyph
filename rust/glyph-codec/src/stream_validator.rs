//! GLYPH Streaming Validator
//!
//! Validates GLYPH tool calls incrementally as tokens arrive from an LLM.
//!
//! This enables:
//! - Early tool detection: Know the tool name before full response
//! - Early rejection: Stop on unknown tools mid-stream
//! - Incremental validation: Check constraints as tokens arrive
//! - Latency savings: Reject bad payloads without waiting for completion

use std::collections::HashMap;
use std::time::{Duration, Instant};
use regex::Regex;

// ============================================================
// Tool Registry
// ============================================================

/// Constraints for a tool argument.
#[derive(Debug, Clone)]
pub struct ArgSchema {
    pub arg_type: String,
    pub required: bool,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub min_len: Option<usize>,
    pub max_len: Option<usize>,
    pub pattern: Option<Regex>,
    pub enum_values: Option<Vec<String>>,
}

impl ArgSchema {
    pub fn new(arg_type: &str) -> Self {
        Self {
            arg_type: arg_type.to_string(),
            required: false,
            min: None,
            max: None,
            min_len: None,
            max_len: None,
            pattern: None,
            enum_values: None,
        }
    }

    pub fn required(mut self) -> Self {
        self.required = true;
        self
    }

    pub fn min(mut self, v: f64) -> Self {
        self.min = Some(v);
        self
    }

    pub fn max(mut self, v: f64) -> Self {
        self.max = Some(v);
        self
    }

    pub fn min_len(mut self, v: usize) -> Self {
        self.min_len = Some(v);
        self
    }

    pub fn max_len(mut self, v: usize) -> Self {
        self.max_len = Some(v);
        self
    }

    pub fn pattern(mut self, re: Regex) -> Self {
        self.pattern = Some(re);
        self
    }

    pub fn enum_values(mut self, values: Vec<String>) -> Self {
        self.enum_values = Some(values);
        self
    }
}

/// Schema for a tool.
#[derive(Debug, Clone)]
pub struct ToolSchema {
    pub name: String,
    pub description: String,
    pub args: HashMap<String, ArgSchema>,
}

impl ToolSchema {
    pub fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            description: String::new(),
            args: HashMap::new(),
        }
    }

    pub fn description(mut self, desc: &str) -> Self {
        self.description = desc.to_string();
        self
    }

    pub fn arg(mut self, name: &str, schema: ArgSchema) -> Self {
        self.args.insert(name.to_string(), schema);
        self
    }
}

/// Registry of allowed tools.
#[derive(Debug, Clone, Default)]
pub struct ToolRegistry {
    tools: HashMap<String, ToolSchema>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, tool: ToolSchema) {
        self.tools.insert(tool.name.clone(), tool);
    }

    pub fn is_allowed(&self, name: &str) -> bool {
        self.tools.contains_key(name)
    }

    pub fn get(&self, name: &str) -> Option<&ToolSchema> {
        self.tools.get(name)
    }
}

// ============================================================
// Validation Errors
// ============================================================

/// Validation error codes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCode {
    UnknownTool,
    MissingRequired,
    MissingTool,
    ConstraintMin,
    ConstraintMax,
    ConstraintLen,
    ConstraintPattern,
    ConstraintEnum,
    InvalidType,
    LimitExceeded,
    InvalidStructure,
}

pub const DEFAULT_MAX_BUFFER: usize = 1 << 20; // 1 MB
pub const DEFAULT_MAX_FIELDS: usize = 1000;
pub const DEFAULT_MAX_ERRORS: usize = 100;

/// Validation error.
#[derive(Debug, Clone)]
pub struct ValidationError {
    pub code: ErrorCode,
    pub message: String,
    pub field: Option<String>,
}

impl ValidationError {
    pub fn new(code: ErrorCode, message: &str) -> Self {
        Self {
            code,
            message: message.to_string(),
            field: None,
        }
    }

    pub fn with_field(mut self, field: &str) -> Self {
        self.field = Some(field.to_string());
        self
    }
}

// ============================================================
// Validator State
// ============================================================

/// Parser state machine states.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValidatorState {
    Waiting,
    InObject,
    Complete,
    Error,
}

/// Timeline event during validation.
#[derive(Debug, Clone)]
pub struct TimelineEvent {
    pub event: String,
    pub token: usize,
    pub char_pos: usize,
    pub elapsed: Duration,
    pub detail: String,
}

// ============================================================
// Streaming Validator
// ============================================================

/// Validates GLYPH tool calls incrementally.
pub struct StreamingValidator {
    registry: ToolRegistry,

    // Parser state
    buffer: String,
    state: ValidatorState,
    depth: i32,
    in_string: bool,
    escape_next: bool,
    current_key: String,
    current_val: String,
    has_key: bool,

    // Parsed data
    tool_name: Option<String>,
    fields: HashMap<String, FieldValue>,
    errors: Vec<ValidationError>,

    // Timing
    token_count: usize,
    char_count: usize,
    start_time: Option<Instant>,
    tool_detected_at_token: usize,
    tool_detected_at_time: Duration,
    first_error_at_token: usize,
    first_error_at_time: Duration,
    complete_at_token: usize,
    complete_at_time: Duration,

    // Timeline
    timeline: Vec<TimelineEvent>,

    // Hard limits
    max_buffer_size: usize,
    max_field_count: usize,
    max_error_count: usize,
}

/// Field value during parsing.
#[derive(Debug, Clone, PartialEq)]
pub enum FieldValue {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Str(String),
}

impl StreamingValidator {
    /// Create a new validator with the given registry.
    pub fn new(registry: ToolRegistry) -> Self {
        Self {
            registry,
            buffer: String::new(),
            state: ValidatorState::Waiting,
            depth: 0,
            in_string: false,
            escape_next: false,
            current_key: String::new(),
            current_val: String::new(),
            has_key: false,
            tool_name: None,
            fields: HashMap::new(),
            errors: Vec::new(),
            token_count: 0,
            char_count: 0,
            start_time: None,
            tool_detected_at_token: 0,
            tool_detected_at_time: Duration::ZERO,
            first_error_at_token: 0,
            first_error_at_time: Duration::ZERO,
            complete_at_token: 0,
            complete_at_time: Duration::ZERO,
            timeline: Vec::new(),
            max_buffer_size: DEFAULT_MAX_BUFFER,
            max_field_count: DEFAULT_MAX_FIELDS,
            max_error_count: DEFAULT_MAX_ERRORS,
        }
    }

    pub fn with_limits(
        mut self,
        max_buffer_size: usize,
        max_field_count: usize,
        max_error_count: usize,
    ) -> Self {
        if max_buffer_size > 0 {
            self.max_buffer_size = max_buffer_size;
        }
        if max_field_count > 0 {
            self.max_field_count = max_field_count;
        }
        if max_error_count > 0 {
            self.max_error_count = max_error_count;
        }
        self
    }

    fn add_error(&mut self, error: ValidationError) {
        if self.errors.len() >= self.max_error_count {
            return;
        }
        self.errors.push(error);
    }

    /// Reset the validator for reuse.
    pub fn reset(&mut self) {
        self.buffer.clear();
        self.state = ValidatorState::Waiting;
        self.depth = 0;
        self.in_string = false;
        self.escape_next = false;
        self.current_key.clear();
        self.current_val.clear();
        self.has_key = false;
        self.tool_name = None;
        self.fields.clear();
        self.errors.clear();
        self.token_count = 0;
        self.char_count = 0;
        self.start_time = None;
        self.tool_detected_at_token = 0;
        self.tool_detected_at_time = Duration::ZERO;
        self.first_error_at_token = 0;
        self.first_error_at_time = Duration::ZERO;
        self.complete_at_token = 0;
        self.complete_at_time = Duration::ZERO;
        self.timeline.clear();
    }

    /// Start timing.
    pub fn start(&mut self) {
        self.start_time = Some(Instant::now());
    }

    /// Process a token from the LLM.
    pub fn push_token(&mut self, token: &str) -> ValidationResult {
        if self.start_time.is_none() {
            self.start();
        }

        self.token_count += 1;

        for c in token.chars() {
            self.char_count += 1;
            self.process_char(c);
            if self.state == ValidatorState::Error {
                break;
            }
        }

        let elapsed = self.start_time.map(|t| t.elapsed()).unwrap_or(Duration::ZERO);

        // Record tool detection
        if self.tool_name.is_some() && self.tool_detected_at_token == 0 {
            self.tool_detected_at_token = self.token_count;
            self.tool_detected_at_time = elapsed;

            let tool_name = self.tool_name.as_ref().unwrap();
            let allowed = self.registry.is_allowed(tool_name);
            self.timeline.push(TimelineEvent {
                event: "TOOL_DETECTED".to_string(),
                token: self.token_count,
                char_pos: self.char_count,
                elapsed,
                detail: format!("tool={} allowed={}", tool_name, allowed),
            });
        }

        // Record first error
        if !self.errors.is_empty() && self.first_error_at_token == 0 {
            self.first_error_at_token = self.token_count;
            self.first_error_at_time = elapsed;

            self.timeline.push(TimelineEvent {
                event: "ERROR".to_string(),
                token: self.token_count,
                char_pos: self.char_count,
                elapsed,
                detail: self.errors[0].message.clone(),
            });
        }

        // Record completion
        if self.state == ValidatorState::Complete && self.complete_at_token == 0 {
            self.complete_at_token = self.token_count;
            self.complete_at_time = elapsed;

            self.timeline.push(TimelineEvent {
                event: "COMPLETE".to_string(),
                token: self.token_count,
                char_pos: self.char_count,
                elapsed,
                detail: format!("valid={}", self.errors.is_empty()),
            });
        }

        self.get_result()
    }

    fn process_char(&mut self, c: char) {
        if matches!(self.state, ValidatorState::Complete | ValidatorState::Error) {
            return;
        }

        if self.buffer.len() >= self.max_buffer_size {
            self.state = ValidatorState::Error;
            self.add_error(ValidationError::new(
                ErrorCode::LimitExceeded,
                "Buffer size limit exceeded",
            ));
            return;
        }

        self.buffer.push(c);

        // Handle escape sequences
        if self.escape_next {
            self.escape_next = false;
            self.current_val.push(c);
            return;
        }

        if c == '\\' && self.in_string {
            self.escape_next = true;
            self.current_val.push(c);
            return;
        }

        // Handle quotes
        if c == '"' {
            if self.in_string {
                self.in_string = false;
            } else {
                self.in_string = true;
                self.current_val.clear();
            }
            return;
        }

        // Inside string - accumulate
        if self.in_string {
            self.current_val.push(c);
            return;
        }

        // Handle structural characters
        match c {
            '{' => {
                if self.state == ValidatorState::Waiting {
                    self.state = ValidatorState::InObject;
                } else if self.depth >= 1 {
                    self.current_val.push(c);
                }
                self.depth += 1;
            }
            '}' => {
                if self.depth == 0 {
                    self.state = ValidatorState::Error;
                    self.add_error(ValidationError::new(
                        ErrorCode::InvalidStructure,
                        "Unexpected closing brace",
                    ));
                    return;
                }
                if self.depth > 1 {
                    self.current_val.push(c);
                }
                self.depth -= 1;
                if self.depth == 0 {
                    self.finish_field();
                    if self.state != ValidatorState::Error {
                        self.state = ValidatorState::Complete;
                        self.validate_complete();
                    }
                }
            }
            '[' => {
                self.depth += 1;
                self.current_val.push(c);
            }
            ']' => {
                if self.depth == 0 {
                    self.state = ValidatorState::Error;
                    self.add_error(ValidationError::new(
                        ErrorCode::InvalidStructure,
                        "Unexpected closing bracket",
                    ));
                    return;
                }
                self.depth -= 1;
                self.current_val.push(c);
            }
            '=' => {
                if self.depth == 1 && !self.has_key {
                    self.current_key = self.current_val.trim().to_string();
                    self.current_val.clear();
                    self.has_key = true;
                } else {
                    self.current_val.push(c);
                }
            }
            ' ' | '\n' | '\t' | '\r' => {
                if self.depth == 1 && self.has_key && !self.current_val.is_empty() {
                    self.finish_field();
                }
            }
            _ => {
                self.current_val.push(c);
            }
        }
    }

    fn finish_field(&mut self) {
        if !self.has_key {
            return;
        }

        let key = std::mem::take(&mut self.current_key);
        let val_str = self.current_val.trim().to_string();
        self.current_val.clear();
        self.has_key = false;

        if !self.fields.contains_key(&key) && self.fields.len() >= self.max_field_count {
            self.state = ValidatorState::Error;
            self.add_error(ValidationError::new(
                ErrorCode::LimitExceeded,
                "Field count limit exceeded",
            ));
            return;
        }

        let value = self.parse_value(&val_str);

        // Check for tool/action field
        if key == "action" || key == "tool" {
            if let FieldValue::Str(ref s) = value {
                let discovered_now = self.tool_name.is_none();
                self.tool_name = Some(s.clone());

                // Validate against allow list
                if !self.registry.is_allowed(s) {
                    self.add_error(
                        ValidationError::new(ErrorCode::UnknownTool, &format!("Unknown tool: {}", s))
                            .with_field(&key)
                    );
                }

                if discovered_now {
                    self.validate_existing_fields(s);
                }
            }
        }

        // Validate field constraints
        if let Some(tool_name) = self.tool_name.clone() {
            self.validate_field(&key, &value, &tool_name);
        }

        self.fields.insert(key, value);
    }

    fn parse_value(&self, s: &str) -> FieldValue {
        // Boolean
        if s == "t" || s == "true" {
            return FieldValue::Bool(true);
        }
        if s == "f" || s == "false" {
            return FieldValue::Bool(false);
        }

        // Null
        if s == "_" || s == "null" || s.is_empty() {
            return FieldValue::Null;
        }

        // Integer
        if let Ok(i) = s.parse::<i64>() {
            return FieldValue::Int(i);
        }

        // Float
        if let Ok(f) = s.parse::<f64>() {
            return FieldValue::Float(f);
        }

        // String
        FieldValue::Str(s.to_string())
    }

    fn validate_field(&mut self, key: &str, value: &FieldValue, tool_name: &str) {
        if key == "action" || key == "tool" {
            return;
        }

        let schema = match self.registry.get(tool_name) {
            Some(s) => s,
            None => return,
        };

        let arg_schema = match schema.args.get(key).cloned() {
            Some(s) => s,
            None => {
                self.add_error(
                    ValidationError::new(ErrorCode::UnknownTool, &format!("Unknown argument: {}", key))
                        .with_field(key),
                );
                return;
            }
        };

        if !Self::type_matches(&arg_schema, value) {
            self.add_error(
                ValidationError::new(
                    ErrorCode::InvalidType,
                    &format!(
                        "{} expected {} but got {}",
                        key,
                        arg_schema.arg_type,
                        Self::field_type_name(value),
                    ),
                )
                .with_field(key),
            );
            return;
        }

        // Numeric constraints
        if let Some(num) = match value {
            FieldValue::Int(i) => Some(*i as f64),
            FieldValue::Float(f) => Some(*f),
            _ => None,
        } {
            if let Some(min) = arg_schema.min {
                if num < min {
                    self.add_error(
                        ValidationError::new(ErrorCode::ConstraintMin, &format!("{} < {}", key, min))
                            .with_field(key)
                    );
                }
            }
            if let Some(max) = arg_schema.max {
                if num > max {
                    self.add_error(
                        ValidationError::new(ErrorCode::ConstraintMax, &format!("{} > {}", key, max))
                            .with_field(key)
                    );
                }
            }
        }

        // String constraints
        if let FieldValue::Str(s) = value {
            if let Some(min_len) = arg_schema.min_len {
                if s.len() < min_len {
                    self.add_error(
                        ValidationError::new(ErrorCode::ConstraintLen, &format!("{} length < {}", key, min_len))
                            .with_field(key)
                    );
                }
            }
            if let Some(max_len) = arg_schema.max_len {
                if s.len() > max_len {
                    self.add_error(
                        ValidationError::new(ErrorCode::ConstraintLen, &format!("{} length > {}", key, max_len))
                            .with_field(key)
                    );
                }
            }
            if let Some(ref pattern) = arg_schema.pattern {
                if !pattern.is_match(s) {
                    self.add_error(
                        ValidationError::new(ErrorCode::ConstraintPattern, &format!("{} pattern mismatch", key))
                            .with_field(key)
                    );
                }
            }
            if let Some(ref enum_values) = arg_schema.enum_values {
                if !enum_values.contains(s) {
                    self.add_error(
                        ValidationError::new(ErrorCode::ConstraintEnum, &format!("{} not in allowed values", key))
                            .with_field(key)
                    );
                }
            }
        }
    }

    fn validate_existing_fields(&mut self, tool_name: &str) {
        let fields: Vec<(String, FieldValue)> = self
            .fields
            .iter()
            .map(|(key, value)| (key.clone(), value.clone()))
            .collect();

        for (key, value) in fields {
            self.validate_field(&key, &value, tool_name);
        }
    }

    fn type_matches(arg_schema: &ArgSchema, value: &FieldValue) -> bool {
        let expected = arg_schema.arg_type.to_ascii_lowercase();

        match value {
            FieldValue::Null => !arg_schema.required,
            FieldValue::Bool(_) => matches!(expected.as_str(), "bool" | "boolean"),
            FieldValue::Int(_) => matches!(expected.as_str(), "int" | "integer" | "float" | "number"),
            FieldValue::Float(_) => matches!(expected.as_str(), "float" | "number"),
            FieldValue::Str(_) => matches!(expected.as_str(), "string" | "str"),
        }
    }

    fn field_type_name(value: &FieldValue) -> &'static str {
        match value {
            FieldValue::Null => "null",
            FieldValue::Bool(_) => "bool",
            FieldValue::Int(_) => "int",
            FieldValue::Float(_) => "float",
            FieldValue::Str(_) => "string",
        }
    }

    fn validate_complete(&mut self) {
        if self.tool_name.is_none() {
            self.add_error(ValidationError::new(ErrorCode::MissingTool, "No action field found"));
            return;
        }

        let tool_name = self.tool_name.clone().unwrap();
        let schema = match self.registry.get(&tool_name) {
            Some(s) => s,
            None => return,
        };

        // Check required fields
        let missing_required: Vec<String> = schema
            .args
            .iter()
            .filter_map(|(arg_name, arg_schema)| {
                if arg_schema.required && !self.fields.contains_key(arg_name) {
                    Some(arg_name.clone())
                } else {
                    None
                }
            })
            .collect();

        for arg_name in missing_required {
            self.add_error(
                ValidationError::new(ErrorCode::MissingRequired, &format!("Missing required field: {}", arg_name))
                    .with_field(&arg_name)
            );
        }
    }

    /// Get the current validation result.
    pub fn get_result(&self) -> ValidationResult {
        let tool_allowed = self.tool_name.as_ref().map(|t| self.registry.is_allowed(t));

        ValidationResult {
            complete: self.state == ValidatorState::Complete,
            valid: self.state != ValidatorState::Error && self.errors.is_empty(),
            tool_name: self.tool_name.clone(),
            tool_allowed,
            errors: self.errors.clone(),
            fields: self.fields.clone(),
            token_count: self.token_count,
            char_count: self.char_count,
            timeline: self.timeline.clone(),
            tool_detected_at_token: self.tool_detected_at_token,
            tool_detected_at_time: self.tool_detected_at_time,
            first_error_at_token: self.first_error_at_token,
            first_error_at_time: self.first_error_at_time,
            complete_at_token: self.complete_at_token,
            complete_at_time: self.complete_at_time,
        }
    }

    /// Check if the stream should be cancelled.
    pub fn should_stop(&self) -> bool {
        self.state == ValidatorState::Error
            || self.errors.iter().any(|e| {
                matches!(
                    e.code,
                    ErrorCode::UnknownTool | ErrorCode::LimitExceeded | ErrorCode::InvalidStructure
                )
            })
    }
}

/// Validation result.
#[derive(Debug, Clone)]
pub struct ValidationResult {
    pub complete: bool,
    pub valid: bool,
    pub tool_name: Option<String>,
    pub tool_allowed: Option<bool>,
    pub errors: Vec<ValidationError>,
    pub fields: HashMap<String, FieldValue>,
    pub token_count: usize,
    pub char_count: usize,
    pub timeline: Vec<TimelineEvent>,
    pub tool_detected_at_token: usize,
    pub tool_detected_at_time: Duration,
    pub first_error_at_token: usize,
    pub first_error_at_time: Duration,
    pub complete_at_token: usize,
    pub complete_at_time: Duration,
}

// ============================================================
// Default Registry
// ============================================================

/// Create a default tool registry with common tools.
pub fn default_tool_registry() -> ToolRegistry {
    let mut registry = ToolRegistry::new();

    registry.register(
        ToolSchema::new("search")
            .description("Search for information")
            .arg("query", ArgSchema::new("string").required().min_len(1))
            .arg("max_results", ArgSchema::new("int").min(1.0).max(100.0))
    );

    registry.register(
        ToolSchema::new("calculate")
            .description("Evaluate a mathematical expression")
            .arg("expression", ArgSchema::new("string").required())
            .arg("precision", ArgSchema::new("int").min(0.0).max(15.0))
    );

    registry.register(
        ToolSchema::new("browse")
            .description("Fetch a web page")
            .arg("url", ArgSchema::new("string").required().pattern(Regex::new(r"^https?://").unwrap()))
    );

    registry.register(
        ToolSchema::new("execute")
            .description("Execute a shell command")
            .arg("command", ArgSchema::new("string").required())
    );

    registry
}

// ============================================================
// Tests
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_streaming_validator_basic() {
        let mut registry = ToolRegistry::new();
        registry.register(
            ToolSchema::new("search")
                .arg("query", ArgSchema::new("string").required())
        );

        let mut v = StreamingValidator::new(registry);
        v.start();

        let tokens = vec!["{", "action=", "\"search\"", " ", "query=", "\"test\"", "}"];

        let mut result = v.get_result();
        for tok in tokens {
            result = v.push_token(tok);
        }

        assert!(result.complete);
        assert!(result.valid);
        assert_eq!(result.tool_name, Some("search".to_string()));
    }

    #[test]
    fn test_streaming_validator_unknown_tool() {
        let registry = ToolRegistry::new();
        let mut v = StreamingValidator::new(registry);
        v.start();

        v.push_token("{action=\"unknown\" }");

        assert!(v.should_stop());
    }

    #[test]
    fn test_streaming_validator_constraint() {
        let mut registry = ToolRegistry::new();
        registry.register(
            ToolSchema::new("search")
                .arg("max_results", ArgSchema::new("int").max(100.0))
        );

        let mut v = StreamingValidator::new(registry);
        v.start();

        let result = v.push_token("{action=\"search\" max_results=500}");

        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.code == ErrorCode::ConstraintMax));
    }

    #[test]
    fn test_default_registry() {
        let registry = default_tool_registry();

        assert!(registry.is_allowed("search"));
        assert!(registry.is_allowed("calculate"));
        assert!(registry.is_allowed("browse"));
        assert!(!registry.is_allowed("unknown"));
    }

    #[test]
    fn test_streaming_validator_type_enforcement() {
        let mut registry = ToolRegistry::new();
        registry.register(
            ToolSchema::new("search")
                .arg("query", ArgSchema::new("string").required())
                .arg("max_results", ArgSchema::new("int")),
        );

        let mut v = StreamingValidator::new(registry);
        v.start();

        let result = v.push_token("{action=\"search\" query=123 max_results=\"ten\"}");

        assert!(!result.valid);
        assert_eq!(
            result
                .errors
                .iter()
                .filter(|e| e.code == ErrorCode::InvalidType)
                .count(),
            2
        );
    }

    #[test]
    fn test_streaming_validator_type_enforcement_when_action_arrives_last() {
        let mut registry = ToolRegistry::new();
        registry.register(
            ToolSchema::new("search")
                .arg("query", ArgSchema::new("string").required())
                .arg("max_results", ArgSchema::new("int")),
        );

        let mut v = StreamingValidator::new(registry);
        v.start();

        let result = v.push_token("{query=123 max_results=\"ten\" action=\"search\"}");

        assert!(!result.valid);
        assert_eq!(
            result
                .errors
                .iter()
                .filter(|e| e.code == ErrorCode::InvalidType)
                .count(),
            2
        );
    }

    #[test]
    fn test_streaming_validator_buffer_limit() {
        let registry = ToolRegistry::new();
        let mut v =
            StreamingValidator::new(registry).with_limits(16, DEFAULT_MAX_FIELDS, DEFAULT_MAX_ERRORS);
        v.start();

        let result = v.push_token("{action=\"search\" query=\"this is too long\"}");

        assert!(v.should_stop());
        assert!(matches!(v.state, ValidatorState::Error));
        assert!(result.errors.iter().any(|e| e.code == ErrorCode::LimitExceeded));
    }

    #[test]
    fn test_streaming_validator_field_limit() {
        let mut registry = ToolRegistry::new();
        registry.register(ToolSchema::new("test"));

        let mut v =
            StreamingValidator::new(registry).with_limits(DEFAULT_MAX_BUFFER, 2, DEFAULT_MAX_ERRORS);
        v.start();

        let result = v.push_token("{action=\"test\" a=1 b=2 c=3}");

        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.code == ErrorCode::LimitExceeded));
    }

    #[test]
    fn test_streaming_validator_error_limit() {
        let mut registry = ToolRegistry::new();
        registry.register(
            ToolSchema::new("search")
                .arg("a", ArgSchema::new("int").min(10.0))
                .arg("b", ArgSchema::new("int").min(10.0))
                .arg("c", ArgSchema::new("int").min(10.0)),
        );

        let mut v =
            StreamingValidator::new(registry).with_limits(DEFAULT_MAX_BUFFER, DEFAULT_MAX_FIELDS, 2);
        v.start();

        let result = v.push_token("{action=\"search\" a=1 b=2 c=3}");

        assert!(result.errors.len() <= 2);
    }

    #[test]
    fn test_streaming_validator_depth_underflow() {
        let registry = ToolRegistry::new();
        let mut v = StreamingValidator::new(registry);
        v.start();

        let result = v.push_token("}");

        assert!(v.should_stop());
        assert!(!result.complete);
        assert!(result.errors.iter().any(|e| e.code == ErrorCode::InvalidStructure));
    }
}
