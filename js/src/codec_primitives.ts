/**
 * Shared canonical scalar encoding primitives for the ASCII-only
 * codec paths (emit + patch). The loose codec has its own
 * Unicode-aware / Go-strconv-compatible variants — do not merge.
 */

const NULL_SYMBOL = '∅';

export function canonNull(): string {
  return NULL_SYMBOL;
}

export function canonBool(v: boolean): string {
  return v ? 't' : 'f';
}

export function canonInt(n: number): string {
  if (n === 0) return '0';
  return String(Math.floor(n));
}

export function canonFloat(f: number): string {
  // D4: -0 and 0 → '0.0'
  if (f === 0 || Object.is(f, -0)) return '0.0';

  const absF = Math.abs(f);
  const neg = f < 0;
  const jsStr = String(absF);

  let s: string;
  if (jsStr.includes('e') || jsStr.includes('E')) {
    // Normalize existing exponential form: ensure e+XX or e-XX with 2-digit exp
    s = jsStr.replace(/[eE]([+-]?)(\d+)$/, (_match: string, sign: string, digits: string) => {
      const signChar = sign === '-' ? '-' : '+';
      const paddedDigits = digits.length === 1 ? '0' + digits : digits;
      return 'e' + signChar + paddedDigits;
    });
  } else if (absF < 1e-4) {
    // Small number: Go uses exponential; convert via toExponential
    let expStr = absF.toExponential().replace(/\.?0+(e)/, '$1');
    s = expStr.replace(/e([+-]?)(\d+)$/, (_match: string, sign: string, digits: string) => {
      const signChar = sign === '-' ? '-' : '+';
      const paddedDigits = digits.length === 1 ? '0' + digits : digits;
      return 'e' + signChar + paddedDigits;
    });
  } else if (absF >= 1e6 && !jsStr.includes('.')) {
    // Large integer-valued float: Go uses exponential
    let expStr = absF.toExponential().replace(/\.?0+(e)/, '$1');
    s = expStr.replace(/e([+-]?)(\d+)$/, (_match: string, sign: string, digits: string) => {
      const signChar = sign === '-' ? '-' : '+';
      const paddedDigits = digits.length === 1 ? '0' + digits : digits;
      return 'e' + signChar + paddedDigits;
    });
  } else {
    s = jsStr;
    // D4: ensure decimal point for whole-number floats
    if (!s.includes('.') && !s.includes('e')) {
      s = s + '.0';
    }
  }

  return neg ? '-' + s : s;
}

export function canonString(s: string): string {
  if (isBareSafe(s)) {
    return s;
  }
  return quoteString(s);
}

export function isLetter(c: number): boolean {
  return (c >= 65 && c <= 90) || (c >= 97 && c <= 122);
}

export function isDigit(c: number): boolean {
  return c >= 48 && c <= 57;
}

export function isBareSafe(s: string): boolean {
  if (s.length === 0) return false;

  // D8: extended reserved word list
  if (['t', 'f', '_', 'true', 'false', 'null', 'none', 'nil', 'struct', 'sum', 'list', 'map', 'NaN', 'Inf'].includes(s)) {
    return false;
  }

  const first = s.charCodeAt(0);
  // First char: ASCII letter or underscore
  if (!isLetter(first) && first !== 95) return false;

  // D8: continuation chars: ASCII letter, digit, underscore only (no -./  )
  for (let i = 1; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (!isLetter(c) && !isDigit(c) && c !== 95) {
      return false;
    }
  }

  return true;
}

export function isRefSafe(s: string): boolean {
  if (s.length === 0) return false;
  // D7: '/' (47) is NOT safe; ASCII letters/digits/underscore/dash/dot/colon only
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (!isLetter(c) && !isDigit(c) && c !== 95 && c !== 45 && c !== 46 && c !== 58) {
      return false;
    }
  }
  return true;
}

export function quoteString(s: string): string {
  let result = '"';
  for (const ch of s) {
    switch (ch) {
      case '\\': result += '\\\\'; break;
      case '"': result += '\\"'; break;
      case '\n': result += '\\n'; break;
      case '\r': result += '\\r'; break;
      case '\t': result += '\\t'; break;
      default:
        if (ch.charCodeAt(0) < 0x20) {
          result += '\\u' + ch.charCodeAt(0).toString(16).padStart(4, '0');
        } else {
          result += ch;
        }
    }
  }
  return result + '"';
}
