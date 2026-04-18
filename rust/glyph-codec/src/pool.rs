//! GLYPH Pool References
//!
//! Pool-based deduplication for strings and objects.
//! Pool refs use `^<PoolID>:<Index>` wire format; pool definitions
//! use `@pool.str id=S1 [...]` and `@pool.obj id=O1 [...]`.

use std::collections::HashMap;

use crate::error::GlyphError;
use crate::types::{GValue, MapEntry, PoolRef};

/// Pool kind: string or object.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PoolKind {
    String,
    Object,
}

impl PoolKind {
    pub fn wire_tag(&self) -> &'static str {
        match self {
            PoolKind::String => "str",
            PoolKind::Object => "obj",
        }
    }
}

/// Check if a string is a valid pool ID (uppercase letters + at least one digit).
pub fn is_pool_ref_id(s: &str) -> bool {
    if s.len() < 2 {
        return false;
    }
    let bytes = s.as_bytes();
    if !bytes[0].is_ascii_uppercase() {
        return false;
    }
    let mut saw_digit = false;
    for &b in &bytes[1..] {
        if b.is_ascii_digit() {
            saw_digit = true;
        } else if !b.is_ascii_uppercase() {
            return false;
        }
    }
    saw_digit
}

/// Parse a pool reference from `^S1:0` format.
pub fn parse_pool_ref(input: &str) -> Result<PoolRef, GlyphError> {
    if !input.starts_with('^') {
        return Err(GlyphError::Parse("pool ref must start with ^".into()));
    }
    let body = &input[1..];
    let colon = body.find(':').ok_or_else(|| GlyphError::Parse("pool ref must contain colon".into()))?;
    let pool_id = &body[..colon];
    if !is_pool_ref_id(pool_id) {
        return Err(GlyphError::Parse(format!("invalid pool ID: {}", pool_id)));
    }
    let idx_str = &body[colon + 1..];
    let index: usize = idx_str.parse().map_err(|_| GlyphError::Parse(format!("invalid pool index: {}", idx_str)))?;
    Ok(PoolRef::new(pool_id, index))
}

/// A single named pool of values.
pub struct Pool {
    pub id: String,
    pub kind: PoolKind,
    pub entries: Vec<GValue>,
}

impl Pool {
    pub fn new(id: impl Into<String>, kind: PoolKind) -> Self {
        Self {
            id: id.into(),
            kind,
            entries: Vec::new(),
        }
    }

    pub fn add(&mut self, value: GValue) -> Result<usize, GlyphError> {
        if self.kind == PoolKind::String && !value.is_str() {
            return Err(GlyphError::Parse(format!(
                "pool {} is a string pool but got non-string",
                self.id
            )));
        }
        let idx = self.entries.len();
        self.entries.push(value);
        Ok(idx)
    }

    pub fn get(&self, index: usize) -> Option<&GValue> {
        self.entries.get(index)
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

/// Registry of pools keyed by pool ID.
pub struct PoolRegistry {
    pools: HashMap<String, Pool>,
}

impl PoolRegistry {
    pub fn new() -> Self {
        Self {
            pools: HashMap::new(),
        }
    }

    pub fn register(&mut self, pool: Pool) {
        self.pools.insert(pool.id.clone(), pool);
    }

    pub fn get(&self, pool_id: &str) -> Option<&Pool> {
        self.pools.get(pool_id)
    }

    pub fn resolve(&self, r: &PoolRef) -> Result<&GValue, GlyphError> {
        let pool = self.pools.get(&r.pool_id).ok_or_else(|| {
            GlyphError::Parse(format!("pool not found: {}", r.pool_id))
        })?;
        pool.get(r.index).ok_or_else(|| {
            GlyphError::Parse(format!(
                "pool {}[{}] out of bounds (len={})",
                r.pool_id, r.index, pool.len()
            ))
        })
    }

    pub fn ids(&self) -> Vec<String> {
        let mut ids: Vec<_> = self.pools.keys().cloned().collect();
        ids.sort();
        ids
    }
}

impl Default for PoolRegistry {
    fn default() -> Self {
        Self::new()
    }
}

/// Emit canonical pool-definition wire format.
pub fn emit_pool(pool: &Pool) -> Result<String, GlyphError> {
    use crate::loose::canonicalize_loose;

    let header = format!("@pool.{} id={}", pool.kind.wire_tag(), pool.id);
    let mut body_parts = Vec::with_capacity(pool.entries.len());
    for v in &pool.entries {
        body_parts.push(canonicalize_loose(v)?);
    }
    Ok(format!("{} [{}]", header, body_parts.join(" ")))
}

/// Recursively replace PoolRef values with their resolved pool entries.
pub fn resolve_pool_refs(value: &GValue, registry: &PoolRegistry) -> Result<GValue, GlyphError> {
    match value {
        GValue::PoolRef(r) => {
            let resolved = registry.resolve(r)?;
            Ok(resolved.clone())
        }
        GValue::List(items) => {
            let mut resolved = Vec::with_capacity(items.len());
            for v in items {
                resolved.push(resolve_pool_refs(v, registry)?);
            }
            Ok(GValue::List(resolved))
        }
        GValue::Map(entries) => {
            let mut resolved = Vec::with_capacity(entries.len());
            for e in entries {
                resolved.push(MapEntry::new(
                    e.key.clone(),
                    resolve_pool_refs(&e.value, registry)?,
                ));
            }
            Ok(GValue::Map(resolved))
        }
        GValue::Struct(s) => {
            let mut resolved = Vec::with_capacity(s.fields.len());
            for f in &s.fields {
                resolved.push(MapEntry::new(
                    f.key.clone(),
                    resolve_pool_refs(&f.value, registry)?,
                ));
            }
            Ok(GValue::struct_val(s.type_name.clone(), resolved))
        }
        GValue::Sum(s) => {
            let inner = match &s.value {
                Some(v) => Some(resolve_pool_refs(v, registry)?),
                None => None,
            };
            Ok(GValue::sum(s.tag.clone(), inner))
        }
        other => Ok(other.clone()),
    }
}
