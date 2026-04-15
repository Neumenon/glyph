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
  if (f === 0) return '0';
  return String(f).replace('E', 'e');
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

  if (['t', 'f', 'true', 'false', 'null', 'none', 'nil'].includes(s)) {
    return false;
  }

  const first = s.charCodeAt(0);
  if (!isLetter(first) && first !== 95) return false;

  for (let i = 1; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (!isLetter(c) && !isDigit(c) && c !== 95 && c !== 45 && c !== 46 && c !== 47) {
      return false;
    }
  }

  return true;
}

export function isRefSafe(s: string): boolean {
  if (s.length === 0) return false;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (!isLetter(c) && !isDigit(c) && c !== 95 && c !== 45 && c !== 46 && c !== 47 && c !== 58) {
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
