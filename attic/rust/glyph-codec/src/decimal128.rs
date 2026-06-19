//! Decimal128 - High-precision decimal type for GLYPH
//!
//! A 128-bit decimal for financial, scientific, and precise mathematical calculations.
//! Value = coefficient * 10^(-scale) where scale is -127 to 127.
//!
//! Unlike f64, Decimal128:
//! - Preserves exact decimal representation
//! - No precision loss for large numbers (>2^53)
//! - Safe for financial calculations
//! - Compatible with blockchain/crypto systems

use std::cmp::Ordering;
use std::fmt;
use std::ops::{Add, Sub, Mul, Div, Neg};
use std::str::FromStr;

const MAX_I128_POW10_EXP: u32 = 38;

/// Decimal128 represents a 128-bit decimal number.
/// Value = coefficient * 10^(-scale)
#[derive(Clone, Copy, Eq)]
pub struct Decimal128 {
    /// Exponent: -127 to 127
    pub scale: i8,
    /// 128-bit coefficient (two's complement, big-endian)
    pub coef: [u8; 16],
}

impl Decimal128 {
    /// Create a new Decimal128 from scale and coefficient bytes.
    pub fn new(scale: i8, coef: [u8; 16]) -> Self {
        Self { scale, coef }
    }

    /// Create a Decimal128 from an i64.
    pub fn from_i64(value: i64) -> Self {
        let mut coef = [0u8; 16];
        let bytes = value.to_be_bytes();

        // Sign extend for negative numbers
        let fill = if value < 0 { 0xFF } else { 0x00 };
        for i in 0..8 {
            coef[i] = fill;
        }
        coef[8..16].copy_from_slice(&bytes);

        Self { scale: 0, coef }
    }

    /// Create a Decimal128 from a string representation.
    pub fn from_string(s: &str) -> Result<Self, DecimalError> {
        let s = s.trim();

        // Remove 'm' suffix if present
        let s = s.strip_suffix('m').unwrap_or(s);

        // Check for negative
        let (negative, s) = if s.starts_with('-') {
            (true, &s[1..])
        } else {
            (false, s)
        };

        // Split by decimal point
        let parts: Vec<&str> = s.split('.').collect();
        if parts.len() > 2 {
            return Err(DecimalError::InvalidFormat);
        }

        let (int_part, frac_part, scale_len) = if parts.len() == 2 {
            (parts[0], parts[1], parts[1].len())
        } else {
            (parts[0], "", 0usize)
        };

        if scale_len > 127 {
            return Err(DecimalError::ScaleOverflow);
        }
        let scale = scale_len as i8;

        // Parse coefficient
        let coef_str = format!("{}{}", int_part, frac_part);
        let mut coef_value = i128::from_str(&coef_str)
            .map_err(|_| DecimalError::InvalidFormat)?;

        if negative {
            coef_value = -coef_value;
        }

        Ok(Self {
            scale,
            coef: int_to_coef(coef_value),
        })
    }

    /// Create a Decimal128 from an f64 (with potential precision loss).
    pub fn from_f64(f: f64) -> Result<Self, DecimalError> {
        Self::from_string(&format!("{}", f))
    }

    /// Convert to i64 (truncates fractional part).
    pub fn to_i64(&self) -> i64 {
        let coef = coef_to_int(&self.coef);
        let value = if self.scale >= 0 {
            match checked_pow10(self.scale as u32) {
                Some(divisor) => coef / divisor,
                None => 0,
            }
        } else {
            match checked_scale_coef(coef, self.scale.unsigned_abs() as u32) {
                Ok(value) => value,
                Err(_) => {
                    return if coef.is_negative() {
                        i64::MIN
                    } else {
                        i64::MAX
                    };
                }
            }
        };

        saturating_i128_to_i64(value)
    }

    /// Convert to f64 (with potential precision loss).
    pub fn to_f64(&self) -> f64 {
        let coef = coef_to_int(&self.coef);
        let divisor = 10f64.powi(self.scale as i32);
        (coef as f64) / divisor
    }

    /// Check if value is zero.
    pub fn is_zero(&self) -> bool {
        coef_to_int(&self.coef) == 0
    }

    /// Check if value is negative.
    pub fn is_negative(&self) -> bool {
        coef_to_int(&self.coef) < 0
    }

    /// Check if value is positive.
    pub fn is_positive(&self) -> bool {
        coef_to_int(&self.coef) > 0
    }

    /// Return the absolute value.
    pub fn abs(&self) -> Self {
        let coef = coef_to_int(&self.coef);
        Self {
            scale: self.scale,
            coef: int_to_coef(coef.wrapping_abs()),
        }
    }

    /// Negate the value.
    pub fn negate(&self) -> Self {
        let coef = coef_to_int(&self.coef);
        Self {
            scale: self.scale,
            coef: int_to_coef(coef.wrapping_neg()),
        }
    }
}

impl fmt::Display for Decimal128 {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let coef = coef_to_int(&self.coef);
        let mut digits = coef.to_string();
        let negative = digits.starts_with('-');
        if negative {
            digits.remove(0);
        }

        let rendered = if self.scale > 0 {
            let mut digits = digits;
            while digits.len() <= self.scale as usize {
                digits.insert(0, '0');
            }
            let insert_pos = digits.len() - self.scale as usize;
            digits.insert(insert_pos, '.');
            digits
        } else if self.scale < 0 {
            let zeros = "0".repeat(self.scale.unsigned_abs() as usize);
            format!("{}{}", digits, zeros)
        } else {
            digits
        };

        if negative {
            write!(f, "-{}", rendered)
        } else {
            write!(f, "{}", rendered)
        }
    }
}

impl fmt::Debug for Decimal128 {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Decimal128(scale={}, value={})", self.scale, self)
    }
}

impl PartialEq for Decimal128 {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other) == Ordering::Equal
    }
}

impl PartialOrd for Decimal128 {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Decimal128 {
    fn cmp(&self, other: &Self) -> Ordering {
        let c1 = coef_to_int(&self.coef);
        let c2 = coef_to_int(&other.coef);

        if c1 == c2 && self.scale == other.scale {
            return Ordering::Equal;
        }

        if c1.is_negative() != c2.is_negative() {
            return c1.cmp(&c2);
        }

        let ordering = compare_abs_decimal(c1, self.scale, c2, other.scale);
        if c1.is_negative() {
            ordering.reverse()
        } else {
            ordering
        }
    }
}

impl Add for Decimal128 {
    type Output = Result<Self, DecimalError>;

    fn add(self, other: Self) -> Self::Output {
        let target_scale = self.scale.max(other.scale);
        let c1 = align_coef_to_scale(coef_to_int(&self.coef), self.scale, target_scale)?;
        let c2 = align_coef_to_scale(coef_to_int(&other.coef), other.scale, target_scale)?;
        let result = c1.checked_add(c2).ok_or(DecimalError::Overflow)?;

        Ok(Self {
            scale: target_scale,
            coef: int_to_coef(result),
        })
    }
}

impl Sub for Decimal128 {
    type Output = Result<Self, DecimalError>;

    fn sub(self, other: Self) -> Self::Output {
        let target_scale = self.scale.max(other.scale);
        let c1 = align_coef_to_scale(coef_to_int(&self.coef), self.scale, target_scale)?;
        let c2 = align_coef_to_scale(coef_to_int(&other.coef), other.scale, target_scale)?;
        let result = c1.checked_sub(c2).ok_or(DecimalError::Overflow)?;

        Ok(Self {
            scale: target_scale,
            coef: int_to_coef(result),
        })
    }
}

impl Mul for Decimal128 {
    type Output = Result<Self, DecimalError>;

    fn mul(self, other: Self) -> Self::Output {
        let c1 = coef_to_int(&self.coef);
        let c2 = coef_to_int(&other.coef);
        let result = c1.checked_mul(c2).ok_or(DecimalError::Overflow)?;

        let new_scale = self.scale as i16 + other.scale as i16;
        if new_scale > 127 || new_scale < -127 {
            return Err(DecimalError::ScaleOverflow);
        }

        Ok(Self {
            scale: new_scale as i8,
            coef: int_to_coef(result),
        })
    }
}

impl Div for Decimal128 {
    type Output = Result<Self, DecimalError>;

    fn div(self, other: Self) -> Self::Output {
        let c2 = coef_to_int(&other.coef);
        if c2 == 0 {
            return Err(DecimalError::DivisionByZero);
        }

        let c1 = coef_to_int(&self.coef);
        let result = c1.checked_div(c2).ok_or(DecimalError::Overflow)?;

        let new_scale = self.scale as i16 - other.scale as i16;
        if new_scale > 127 || new_scale < -127 {
            return Err(DecimalError::ScaleOverflow);
        }

        Ok(Self {
            scale: new_scale as i8,
            coef: int_to_coef(result),
        })
    }
}

impl Neg for Decimal128 {
    type Output = Self;

    fn neg(self) -> Self::Output {
        self.negate()
    }
}

impl FromStr for Decimal128 {
    type Err = DecimalError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Self::from_string(s)
    }
}

// ============================================================
// Error Type
// ============================================================

/// Decimal128 error types.
#[derive(Debug, Clone, PartialEq)]
pub enum DecimalError {
    InvalidFormat,
    Overflow,
    ScaleOverflow,
    DivisionByZero,
}

impl fmt::Display for DecimalError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DecimalError::InvalidFormat => write!(f, "invalid decimal format"),
            DecimalError::Overflow => write!(f, "decimal overflow"),
            DecimalError::ScaleOverflow => write!(f, "scale overflow"),
            DecimalError::DivisionByZero => write!(f, "division by zero"),
        }
    }
}

impl std::error::Error for DecimalError {}

// ============================================================
// Helper Functions
// ============================================================

/// Convert i128 to 16-byte two's complement representation.
fn int_to_coef(value: i128) -> [u8; 16] {
    value.to_be_bytes()
}

/// Convert 16-byte two's complement to i128.
fn coef_to_int(coef: &[u8; 16]) -> i128 {
    i128::from_be_bytes(*coef)
}

fn checked_pow10(exp: u32) -> Option<i128> {
    if exp > MAX_I128_POW10_EXP {
        return None;
    }

    let mut value = 1i128;
    for _ in 0..exp {
        value = value.checked_mul(10)?;
    }
    Some(value)
}

fn checked_scale_coef(coef: i128, exp: u32) -> Result<i128, DecimalError> {
    if exp == 0 || coef == 0 {
        return Ok(coef);
    }

    let factor = checked_pow10(exp).ok_or(DecimalError::Overflow)?;
    coef.checked_mul(factor).ok_or(DecimalError::Overflow)
}

fn align_coef_to_scale(coef: i128, from_scale: i8, to_scale: i8) -> Result<i128, DecimalError> {
    let diff = i16::from(to_scale) - i16::from(from_scale);
    if diff < 0 {
        return Err(DecimalError::ScaleOverflow);
    }

    checked_scale_coef(coef, diff as u32)
}

fn normalize_decimal_parts(coef: i128, scale: i8) -> (String, i32) {
    if coef == 0 {
        return ("0".to_string(), 0);
    }

    let mut digits = coef.to_string();
    if digits.starts_with('-') {
        digits.remove(0);
    }
    let mut scale = i32::from(scale);

    while digits.len() > 1 && digits.ends_with('0') {
        digits.pop();
        scale -= 1;
    }

    (digits, scale)
}

fn compare_abs_decimal(left_coef: i128, left_scale: i8, right_coef: i128, right_scale: i8) -> Ordering {
    let (mut left_digits, left_scale) = normalize_decimal_parts(left_coef, left_scale);
    let (mut right_digits, right_scale) = normalize_decimal_parts(right_coef, right_scale);

    let target_scale = left_scale.max(right_scale);
    if target_scale > left_scale {
        left_digits.push_str(&"0".repeat((target_scale - left_scale) as usize));
    }
    if target_scale > right_scale {
        right_digits.push_str(&"0".repeat((target_scale - right_scale) as usize));
    }

    left_digits
        .len()
        .cmp(&right_digits.len())
        .then_with(|| left_digits.cmp(&right_digits))
}

fn saturating_i128_to_i64(value: i128) -> i64 {
    if value > i64::MAX as i128 {
        i64::MAX
    } else if value < i64::MIN as i128 {
        i64::MIN
    } else {
        value as i64
    }
}

/// Check if a string is a decimal literal (ends with 'm').
pub fn is_decimal_literal(s: &str) -> bool {
    let s = s.trim();
    if !s.ends_with('m') {
        return false;
    }
    let num_part = &s[..s.len()-1];
    Decimal128::from_string(num_part).is_ok()
}

/// Parse a decimal literal (with 'm' suffix).
pub fn parse_decimal_literal(s: &str) -> Result<Decimal128, DecimalError> {
    let s = s.trim();
    if !s.ends_with('m') {
        return Err(DecimalError::InvalidFormat);
    }
    Decimal128::from_string(&s[..s.len()-1])
}

// ============================================================
// Tests
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_from_i64() {
        let d = Decimal128::from_i64(123);
        assert_eq!(d.to_string(), "123");
        assert_eq!(d.to_i64(), 123);

        let d = Decimal128::from_i64(-456);
        assert_eq!(d.to_string(), "-456");
        assert_eq!(d.to_i64(), -456);
    }

    #[test]
    fn test_from_string() {
        let d = Decimal128::from_string("123.45").unwrap();
        assert_eq!(d.to_string(), "123.45");
        assert_eq!(d.scale, 2);

        let d = Decimal128::from_string("-99.99").unwrap();
        assert_eq!(d.to_string(), "-99.99");

        let d = Decimal128::from_string("0.0001").unwrap();
        assert_eq!(d.to_string(), "0.0001");
    }

    #[test]
    fn test_negative_scale_display_and_conversion() {
        let d = Decimal128::new(-2, int_to_coef(123));
        assert_eq!(d.to_string(), "12300");
        assert_eq!(d.to_i64(), 12300);

        let neg = Decimal128::new(-3, int_to_coef(-45));
        assert_eq!(neg.to_string(), "-45000");
        assert_eq!(neg.to_i64(), -45000);
    }

    #[test]
    fn test_arithmetic() {
        let d1 = Decimal128::from_string("100.50").unwrap();
        let d2 = Decimal128::from_string("50.25").unwrap();

        let sum = (d1 + d2).unwrap();
        assert_eq!(sum.to_string(), "150.75");

        let diff = (d1 - d2).unwrap();
        assert_eq!(diff.to_string(), "50.25");
    }

    #[test]
    fn test_comparison() {
        let d1 = Decimal128::from_string("100.50").unwrap();
        let d2 = Decimal128::from_string("100.50").unwrap();
        let d3 = Decimal128::from_string("50.25").unwrap();

        assert_eq!(d1, d2);
        assert!(d1 > d3);
        assert!(d3 < d1);
    }

    #[test]
    fn test_predicates() {
        let zero = Decimal128::from_i64(0);
        assert!(zero.is_zero());

        let neg = Decimal128::from_string("-10.5").unwrap();
        assert!(neg.is_negative());

        let pos = Decimal128::from_string("10.5").unwrap();
        assert!(pos.is_positive());
    }

    #[test]
    fn test_decimal_literal() {
        assert!(is_decimal_literal("99.99m"));
        assert!(is_decimal_literal("100m"));
        assert!(!is_decimal_literal("99.99"));

        let d = parse_decimal_literal("99.99m").unwrap();
        assert_eq!(d.to_string(), "99.99");
    }

    #[test]
    fn test_add_overflow_returns_error() {
        let max = Decimal128::new(0, int_to_coef(i128::MAX));
        let one = Decimal128::from_i64(1);

        assert_eq!(max + one, Err(DecimalError::Overflow));
    }

    #[test]
    fn test_mul_overflow_returns_error() {
        let huge = Decimal128::new(0, int_to_coef(i128::MAX));
        let two = Decimal128::from_i64(2);

        assert_eq!(huge * two, Err(DecimalError::Overflow));
    }

    #[test]
    fn test_compare_negative_scale() {
        let lhs = Decimal128::new(-2, int_to_coef(123));
        let rhs = Decimal128::from_i64(12299);

        assert!(lhs > rhs);
    }
}
