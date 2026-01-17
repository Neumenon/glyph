//! GLYPH Codec - Token-efficient serialization for AI agents
//!
//! GLYPH is a serialization format designed for LLM tool calls that provides
//! 30-50% token savings over JSON while remaining human-readable.
//!
//! # Example
//!
//! ```rust
//! use glyph_codec::{from_json, canonicalize_loose, GValue};
//! use serde_json::json;
//!
//! let data = json!({"action": "search", "query": "weather"});
//! let gvalue = from_json(&data);
//! let glyph = canonicalize_loose(&gvalue);
//! assert_eq!(glyph, "{action=search query=weather}");
//! ```

mod types;
mod loose;
mod json_bridge;
mod error;

pub use types::*;
pub use loose::*;
pub use json_bridge::*;
pub use error::*;

#[cfg(test)]
mod tests;
