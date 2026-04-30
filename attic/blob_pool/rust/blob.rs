//! GLYPH Blob References
//!
//! Content-addressed blob references with canonical
//! `@blob cid=... mime=... bytes=N` wire format.

use sha2::{Sha256, Digest};
use std::collections::HashMap;
use std::sync::RwLock;

use crate::error::GlyphError;
use crate::loose::canon_string;
use crate::types::{BlobRef, GValue};

/// Compute SHA-256 CID for content.
pub fn compute_cid(content: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(content);
    let hash = hasher.finalize();
    format!("sha256:{}", hex_encode(&hash))
}

fn hex_encode(data: &[u8]) -> String {
    data.iter().map(|b| format!("{:02x}", b)).collect()
}

/// Create a Blob GValue from raw content, computing the CID.
pub fn blob_from_content(content: &[u8], mime: &str, name: &str, caption: &str) -> GValue {
    let mut r = BlobRef::new(compute_cid(content), mime, content.len() as u64);
    if !name.is_empty() {
        r.name = name.to_string();
    }
    if !caption.is_empty() {
        r.caption = caption.to_string();
    }
    GValue::Blob(r)
}

/// Emit canonical blob wire format.
pub fn emit_blob(r: &BlobRef) -> String {
    let mut parts = vec![
        "@blob".to_string(),
        format!("cid={}", r.cid),
        format!("mime={}", r.mime),
        format!("bytes={}", r.bytes),
    ];
    if !r.name.is_empty() {
        parts.push(format!("name={}", canon_string(&r.name)));
    }
    if !r.caption.is_empty() {
        parts.push(format!("caption={}", canon_string(&r.caption)));
    }
    if !r.preview.is_empty() {
        parts.push(format!("preview={}", canon_string(&r.preview)));
    }
    parts.join(" ")
}

/// Parse canonical blob format back into a BlobRef.
pub fn parse_blob_ref(input: &str) -> Result<BlobRef, GlyphError> {
    let s = input.trim();
    if !s.starts_with("@blob") {
        return Err(GlyphError::Parse("blob ref must start with @blob".into()));
    }
    let s = s["@blob".len()..].trim_start();

    let mut fields = HashMap::new();
    let bytes = s.as_bytes();
    let n = bytes.len();
    let mut i = 0;

    while i < n {
        while i < n && bytes[i].is_ascii_whitespace() {
            i += 1;
        }
        if i >= n {
            break;
        }

        let eq = match s[i..].find('=') {
            Some(pos) => i + pos,
            None => return Err(GlyphError::Parse(format!("missing = in blob field at pos {}", i))),
        };
        let key = &s[i..eq];
        i = eq + 1;

        if i < n && bytes[i] == b'"' {
            i += 1;
            let mut buf = String::new();
            while i < n && bytes[i] != b'"' {
                if bytes[i] == b'\\' && i + 1 < n {
                    match bytes[i + 1] {
                        b'n' => buf.push('\n'),
                        b'r' => buf.push('\r'),
                        b't' => buf.push('\t'),
                        b'\\' => buf.push('\\'),
                        b'"' => buf.push('"'),
                        other => buf.push(other as char),
                    }
                    i += 2;
                } else {
                    buf.push(bytes[i] as char);
                    i += 1;
                }
            }
            if i >= n {
                return Err(GlyphError::Parse(format!("unterminated quote for field {}", key)));
            }
            i += 1;
            fields.insert(key.to_string(), buf);
        } else {
            let start = i;
            while i < n && !bytes[i].is_ascii_whitespace() {
                i += 1;
            }
            fields.insert(key.to_string(), s[start..i].to_string());
        }
    }

    let cid = fields.get("cid").ok_or_else(|| GlyphError::Parse("blob ref missing required field: cid".into()))?;
    let mime = fields.get("mime").ok_or_else(|| GlyphError::Parse("blob ref missing required field: mime".into()))?;
    let bytes_str = fields.get("bytes").ok_or_else(|| GlyphError::Parse("blob ref missing required field: bytes".into()))?;
    let bytes_val: u64 = bytes_str.parse().map_err(|_| GlyphError::Parse(format!("invalid bytes field: {}", bytes_str)))?;

    let mut r = BlobRef::new(cid.clone(), mime.clone(), bytes_val);
    if let Some(name) = fields.get("name") {
        r.name = name.clone();
    }
    if let Some(caption) = fields.get("caption") {
        r.caption = caption.clone();
    }
    if let Some(preview) = fields.get("preview") {
        r.preview = preview.clone();
    }
    Ok(r)
}

/// Thread-safe in-memory CID -> content map for tests.
pub struct MemoryBlobRegistry {
    store: RwLock<HashMap<String, Vec<u8>>>,
}

impl MemoryBlobRegistry {
    pub fn new() -> Self {
        Self {
            store: RwLock::new(HashMap::new()),
        }
    }

    pub fn put(&self, cid: &str, content: Vec<u8>) {
        self.store.write().unwrap().insert(cid.to_string(), content);
    }

    pub fn get(&self, cid: &str) -> Option<Vec<u8>> {
        self.store.read().unwrap().get(cid).cloned()
    }

    pub fn has(&self, cid: &str) -> bool {
        self.store.read().unwrap().contains_key(cid)
    }
}

impl Default for MemoryBlobRegistry {
    fn default() -> Self {
        Self::new()
    }
}
