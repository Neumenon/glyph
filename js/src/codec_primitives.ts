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

/** Normalize a JS exponential string to Go's format: always e+XX or e-XX, 2-digit exp. */
function normalizeExpStr(jsExp: string): string {
  return jsExp.replace(/[eE]([+-]?)(\d+)$/, (_match: string, sign: string, digits: string) => {
    const signChar = sign === '-' ? '-' : '+';
    const paddedDigits = digits.length === 1 ? '0' + digits : digits;
    return 'e' + signChar + paddedDigits;
  });
}

/** Convert a non-zero absolute float to Go exponential form using JS toExponential(). */
function decimalToGoExp(absF: number): string {
  let expStr = absF.toExponential();
  expStr = expStr.replace(/\.?0+(e)/, '$1');
  return normalizeExpStr(expStr);
}

export function canonFloat(f: number): string {
  // Finding 4: guard NaN/Inf — typed path returns bare tokens, never "NaN.0"
  if (Number.isNaN(f)) return 'NaN';
  if (f === Infinity) return 'Inf';
  if (f === -Infinity) return '-Inf';
  // D4: -0 and 0 → '0.0'
  if (f === 0 || Object.is(f, -0)) return '0.0';

  const absF = Math.abs(f);
  const neg = f < 0;
  const jsStr = String(absF);

  let s: string;
  if (jsStr.includes('e') || jsStr.includes('E')) {
    // Normalize existing exponential form to Go format.
    s = normalizeExpStr(jsStr);
  } else {
    // JS gave decimal form. Apply Go's threshold: E = floor(log10(absF)).
    const E = Math.floor(Math.log10(absF));
    if (E >= 6 || E <= -5) {
      // Go uses exponential; JS used decimal — convert.
      s = decimalToGoExp(absF);
    } else {
      // Go uses decimal — JS form is correct.
      s = jsStr;
      // D4: ensure decimal point so token is unambiguously float.
      if (!s.includes('.') && !s.includes('e')) {
        s = s + '.0';
      }
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

/** isRefPartChar: ASCII [A-Za-z0-9_.-] — excludes ':' and '/' per D7. */
export function isRefPartChar(c: number): boolean {
  return isLetter(c) || isDigit(c) || c === 95 /* _ */ || c === 45 /* - */ || c === 46 /* . */;
}

/**
 * isRefSafe mirrors Go canon.go isRefSafe:
 * - All chars in prefix must pass isRefPartChar (excludes ':' and '/')
 * - All chars in value must pass isRefPartChar AND value must not contain ':'
 * - '/' anywhere forces quoting (typed lexer rejects it)
 */
export function isRefSafe(s: string): boolean {
  if (s.length === 0) return false;
  const colonIdx = s.indexOf(':');
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
    if (c === 58 /* : */ || !isRefPartChar(c)) return false;
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
