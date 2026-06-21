/**
 * GLYPH-Loose text parser.
 *
 * Inverts `canonicalizeLoose`: parses schema-free GLYPH-Loose text back into a
 * GValue. This is the JS counterpart to Go's `ParseDocument` and Python's
 * `parse` / `parse_loose`, and is a faithful port of `py/glyph/parse.py` so the
 * three surfaces stay round-trip compatible (see tests/all_impl_parity_test.py).
 *
 * Loose mode is JSON-domain: structs collapse to maps and `time` is not a
 * JSON-domain type, so — exactly as in the Python reference — there is no `time`
 * token here. Values that only arise from explicit typed construction
 * (g.time, packed structs) are intentionally out of loose scope.
 */

import { GValue, MapEntry } from './types';

// ============================================================
// Limits (aligned with Go, Python, C, Rust)
// ============================================================

export const DEFAULT_MAX_DEPTH = 128;
const MAX_COLLECTION_LEN = 1_000_000; // 1M elements
const MAX_STRING_LEN = 10 * 1024 * 1024; // 10MB

// ============================================================
// Lexer
// ============================================================

enum TokenType {
  EOF = 'EOF',
  LBRACE = '{',
  RBRACE = '}',
  LBRACKET = '[',
  RBRACKET = ']',
  LPAREN = '(',
  RPAREN = ')',
  EQUALS = '=',
  COLON = ':',
  COMMA = ',',
  PIPE = '|',
  CARET = '^',
  AT = '@',
  NULL = 'NULL',
  BOOL = 'BOOL',
  INT = 'INT',
  FLOAT = 'FLOAT',
  STRING = 'STRING',
  BYTES = 'BYTES',
  IDENT = 'IDENT',
  NEWLINE = 'NEWLINE',
}

interface Token {
  type: TokenType;
  value: unknown;
  pos: number;
}

function isAsciiDigit(c: string): boolean {
  return c >= '0' && c <= '9';
}

// Unicode-aware letter / alphanumeric tests, mirroring Python's str.isalpha /
// str.isalnum so hand-written (non-emitter) input with Unicode bare identifiers
// lexes the same way it does in the Python reference. The canonical emitter only
// ever emits ASCII bare identifiers (isBareSafe is conservative), so this only
// matters for tolerant parsing of external input.
function isLetter(c: string): boolean {
  return /\p{L}/u.test(c);
}
function isAlnum(c: string): boolean {
  return /[\p{L}\p{N}]/u.test(c);
}

const IDENT_CONTINUE_EXTRA = '_-./@+';

class Lexer {
  text: string;
  pos: number;
  length: number;

  constructor(text: string) {
    this.text = text;
    this.pos = 0;
    this.length = text.length;
  }

  private peekChar(): string {
    if (this.pos >= this.length) return '';
    return this.text[this.pos];
  }

  private nextChar(): string {
    if (this.pos >= this.length) return '';
    const c = this.text[this.pos];
    this.pos += 1;
    return c;
  }

  private skipWhitespace(): void {
    while (this.pos < this.length && ' \t\r'.includes(this.text[this.pos])) {
      this.pos += 1;
    }
  }

  skipWhitespaceAndNewlines(): void {
    while (this.pos < this.length && ' \t\r\n'.includes(this.text[this.pos])) {
      this.pos += 1;
    }
  }

  nextToken(): Token {
    this.skipWhitespace();

    if (this.pos >= this.length) {
      return { type: TokenType.EOF, value: null, pos: this.pos };
    }

    const start = this.pos;
    const c = this.peekChar();

    switch (c) {
      case '{': this.pos += 1; return { type: TokenType.LBRACE, value: c, pos: start };
      case '}': this.pos += 1; return { type: TokenType.RBRACE, value: c, pos: start };
      case '[': this.pos += 1; return { type: TokenType.LBRACKET, value: c, pos: start };
      case ']': this.pos += 1; return { type: TokenType.RBRACKET, value: c, pos: start };
      case '(': this.pos += 1; return { type: TokenType.LPAREN, value: c, pos: start };
      case ')': this.pos += 1; return { type: TokenType.RPAREN, value: c, pos: start };
      case '=': this.pos += 1; return { type: TokenType.EQUALS, value: c, pos: start };
      case ':': this.pos += 1; return { type: TokenType.COLON, value: c, pos: start };
      case ',': this.pos += 1; return { type: TokenType.COMMA, value: c, pos: start };
      case '|': this.pos += 1; return { type: TokenType.PIPE, value: c, pos: start };
      case '^': this.pos += 1; return { type: TokenType.CARET, value: c, pos: start };
      case '@': this.pos += 1; return { type: TokenType.AT, value: c, pos: start };
      case '\n': this.pos += 1; return { type: TokenType.NEWLINE, value: c, pos: start };
    }

    // Null symbol
    if (c === '∅' || c === '_') {
      this.pos += 1;
      return { type: TokenType.NULL, value: null, pos: start };
    }

    // Quoted string
    if (c === '"') {
      return this.readString();
    }

    // Bytes literal: b64"..."
    if (c === 'b' && this.text.slice(this.pos, this.pos + 4) === 'b64"') {
      return this.readBytes();
    }

    // Number or identifier
    if (c === '-' || isAsciiDigit(c)) {
      return this.readNumberOrIdent();
    }

    // Identifier or keyword
    if (isLetter(c) || c === '_') {
      return this.readIdent();
    }

    throw new Error(`unexpected character '${c}' at position ${this.pos}`);
  }

  private readString(): Token {
    const start = this.pos;
    this.pos += 1; // skip opening quote
    let result = '';

    while (this.pos < this.length) {
      const c = this.text[this.pos];
      if (c === '"') {
        this.pos += 1;
        return { type: TokenType.STRING, value: result, pos: start };
      }
      if (result.length >= MAX_STRING_LEN) {
        throw new Error(`string too large (>${MAX_STRING_LEN} characters)`);
      }
      if (c === '\\') {
        this.pos += 1;
        if (this.pos >= this.length) {
          throw new Error('unterminated escape sequence');
        }
        const esc = this.text[this.pos];
        switch (esc) {
          case 'n': result += '\n'; break;
          case 'r': result += '\r'; break;
          case 't': result += '\t'; break;
          case '"': result += '"'; break;
          case '\\': result += '\\'; break;
          case 'u': {
            if (this.pos + 5 > this.length) {
              throw new Error('invalid unicode escape');
            }
            const hex = this.text.slice(this.pos + 1, this.pos + 5);
            if (!/^[0-9a-fA-F]{4}$/.test(hex)) {
              throw new Error('invalid unicode escape');
            }
            result += String.fromCharCode(parseInt(hex, 16));
            this.pos += 4;
            break;
          }
          default: result += esc;
        }
      } else {
        result += c;
      }
      this.pos += 1;
    }

    throw new Error('unterminated string');
  }

  private readBytes(): Token {
    const start = this.pos;
    this.pos += 4; // skip b64"
    let b64 = '';

    while (this.pos < this.length) {
      const c = this.text[this.pos];
      if (c === '"') {
        this.pos += 1;
        return { type: TokenType.BYTES, value: base64ToBytes(b64), pos: start };
      }
      b64 += c;
      this.pos += 1;
    }

    throw new Error('unterminated bytes literal');
  }

  private parseFloatToken(literal: string, start: number): Token {
    const value = Number(literal);
    if (Number.isNaN(value)) {
      throw new Error(`invalid float literal '${literal}' at position ${start}`);
    }
    if (!Number.isFinite(value)) {
      throw new Error(`non-finite float literal '${literal}' at position ${start}`);
    }
    return { type: TokenType.FLOAT, value, pos: start };
  }

  private readNumberOrIdent(): Token {
    const start = this.pos;
    let result = '';

    if (this.peekChar() === '-') {
      result += this.nextChar();
      // Reject -Inf (with word boundary)
      if (
        this.text.slice(this.pos, this.pos + 3) === 'Inf' &&
        (this.pos + 3 >= this.length ||
          (!isAlnum(this.text[this.pos + 3]) && this.text[this.pos + 3] !== '_'))
      ) {
        throw new Error(`non-finite float literal '-Inf' at position ${start}`);
      }
    }

    let hasDot = false;
    let hasExp = false;

    while (this.pos < this.length) {
      const c = this.peekChar();
      if (isAsciiDigit(c)) {
        result += this.nextChar();
      } else if (c === '.' && !hasDot && !hasExp) {
        hasDot = true;
        result += this.nextChar();
      } else if ((c === 'e' || c === 'E') && !hasExp) {
        hasExp = true;
        result += this.nextChar();
        if (this.peekChar() === '+' || this.peekChar() === '-') {
          result += this.nextChar();
        }
      } else if (isLetter(c) || c === '_') {
        // It's an identifier
        while (
          this.pos < this.length &&
          (isAlnum(this.peekChar()) || IDENT_CONTINUE_EXTRA.includes(this.peekChar()))
        ) {
          result += this.nextChar();
        }
        return { type: TokenType.IDENT, value: result, pos: start };
      } else {
        break;
      }
    }

    if (hasDot || hasExp) {
      return this.parseFloatToken(result, start);
    }

    // Integer. JS numbers can only represent integers exactly up to 2^53-1;
    // the canonical emitter already lifts larger ints to float exponent form,
    // so an INT token beyond the safe range only occurs for hand-written input.
    const intVal = Number(result);
    if (Number.isNaN(intVal)) {
      return { type: TokenType.IDENT, value: result, pos: start };
    }
    return { type: TokenType.INT, value: intVal, pos: start };
  }

  private readIdent(): Token {
    const start = this.pos;
    let result = '';

    while (this.pos < this.length) {
      const c = this.peekChar();
      if (isAlnum(c) || IDENT_CONTINUE_EXTRA.includes(c)) {
        result += this.nextChar();
      } else {
        break;
      }
    }

    switch (result) {
      case 't':
      case 'true':
        return { type: TokenType.BOOL, value: true, pos: start };
      case 'f':
      case 'false':
        return { type: TokenType.BOOL, value: false, pos: start };
      case 'null':
      case 'nil':
        return { type: TokenType.NULL, value: null, pos: start };
      case 'NaN':
        throw new Error(`non-finite float literal 'NaN' at position ${start}`);
      case 'Inf':
        throw new Error(`non-finite float literal 'Inf' at position ${start}`);
    }

    return { type: TokenType.IDENT, value: result, pos: start };
  }
}

// base64ToBytes decodes standard base64. Mirrors the file-local helper used
// elsewhere in this codebase (atob in the browser, Buffer in Node).
function base64ToBytes(b64: string): Uint8Array {
  if (typeof atob === 'function') {
    const binary = atob(b64);
    const out = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
    return out;
  }
  return new Uint8Array(Buffer.from(b64, 'base64'));
}

// ============================================================
// Parser
// ============================================================

class Parser {
  private lexer: Lexer;
  private current!: Token;
  private maxDepth: number;
  private depth: number;

  constructor(text: string, maxDepth = DEFAULT_MAX_DEPTH, nestingDepth = 0) {
    this.lexer = new Lexer(text);
    this.maxDepth = maxDepth;
    this.depth = nestingDepth;
  }

  private enter(kind: string): void {
    if (this.depth >= this.maxDepth) {
      throw new Error(`maximum nesting depth exceeded while parsing ${kind}`);
    }
    this.depth += 1;
  }

  private leave(): void {
    this.depth -= 1;
  }

  private advance(): Token {
    this.current = this.lexer.nextToken();
    return this.current;
  }

  // Predicate over the current token type. Routing comparisons through a method
  // (rather than `this.current.type === X` inline) avoids TypeScript's
  // control-flow narrowing persisting across the mutating `advance()` call.
  private is(t: TokenType): boolean {
    return this.current.type === t;
  }

  parse(): GValue {
    this.lexer.skipWhitespaceAndNewlines();
    this.current = this.lexer.nextToken();
    const v = this.parseValue();
    while (this.is(TokenType.NEWLINE)) {
      this.advance();
    }
    if (!this.is(TokenType.EOF)) {
      throw new Error(`trailing garbage at position ${this.current.pos}`);
    }
    return v;
  }

  private parseValue(): GValue {
    const tok = this.current;
    const v = tok.value;

    switch (tok.type) {
      case TokenType.NULL:
        this.advance();
        return GValue.null();
      case TokenType.BOOL:
        this.advance();
        return GValue.bool(v as boolean);
      case TokenType.INT:
        this.advance();
        return GValue.int(v as number);
      case TokenType.FLOAT:
        this.advance();
        return GValue.float(v as number);
      case TokenType.STRING:
        this.advance();
        return GValue.str(v as string);
      case TokenType.BYTES:
        this.advance();
        return GValue.bytes(v as Uint8Array);
      case TokenType.CARET:
        return this.parseRef();
      case TokenType.LBRACKET:
        return this.parseList();
      case TokenType.LBRACE:
        return this.parseMap();
      case TokenType.AT:
        return this.parseDirective();
      case TokenType.IDENT:
        return this.parseIdentValue();
    }

    throw new Error(`unexpected token ${tok.type} at position ${tok.pos}`);
  }

  private parseRef(): GValue {
    // current is CARET
    this.advance();

    if (this.is(TokenType.STRING)) {
      const s = this.current.value as string;
      this.advance();
      const idx = s.indexOf(':');
      if (idx >= 0) {
        return GValue.id(s.slice(0, idx), s.slice(idx + 1));
      }
      return GValue.id('', s);
    }

    let first: string;
    if (this.is(TokenType.IDENT)) {
      first = this.current.value as string;
      this.advance();
    } else if (this.is(TokenType.BOOL)) {
      first = this.current.value ? 't' : 'f';
      this.advance();
    } else if (this.is(TokenType.INT)) {
      first = String(this.current.value);
      this.advance();
    } else {
      throw new Error(`expected reference value, got ${this.current.type}`);
    }

    if (this.is(TokenType.COLON)) {
      this.advance();
      let second: string;
      if (this.is(TokenType.IDENT) || this.is(TokenType.STRING)) {
        second = this.current.value as string;
        this.advance();
      } else if (this.is(TokenType.INT)) {
        second = String(this.current.value);
        this.advance();
      } else if (this.is(TokenType.BOOL)) {
        second = this.current.value ? 't' : 'f';
        this.advance();
      } else {
        throw new Error(`expected reference value part, got ${this.current.type}`);
      }
      return GValue.id(first, second);
    }

    return GValue.id('', first);
  }

  private parseList(): GValue {
    this.enter('list');
    try {
      // current is LBRACKET
      this.advance();
      const items: GValue[] = [];

      while (!this.is(TokenType.RBRACKET)) {
        if (this.is(TokenType.EOF)) {
          throw new Error('unterminated list');
        }
        if (this.is(TokenType.COMMA) || this.is(TokenType.NEWLINE)) {
          this.advance();
          continue;
        }
        if (items.length >= MAX_COLLECTION_LEN) {
          throw new Error(`list too large (>${MAX_COLLECTION_LEN} elements)`);
        }
        items.push(this.parseValue());
      }

      this.advance(); // consume RBRACKET
      return GValue.list(...items);
    } finally {
      this.leave();
    }
  }

  private parseMap(): GValue {
    this.enter('map');
    try {
      // current is LBRACE
      this.advance();
      const entries: MapEntry[] = [];

      while (!this.is(TokenType.RBRACE)) {
        if (this.is(TokenType.EOF)) {
          throw new Error('unterminated map');
        }
        if (this.is(TokenType.COMMA) || this.is(TokenType.NEWLINE)) {
          this.advance();
          continue;
        }
        if (entries.length >= MAX_COLLECTION_LEN) {
          throw new Error(`map too large (>${MAX_COLLECTION_LEN} entries)`);
        }

        const key = this.parseKey();

        if (!this.is(TokenType.EQUALS) && !this.is(TokenType.COLON)) {
          throw new Error(`expected '=' or ':' after key '${key}'`);
        }
        this.advance();

        entries.push({ key, value: this.parseValue() });
      }

      this.advance(); // consume RBRACE
      return GValue.map(...entries);
    } finally {
      this.leave();
    }
  }

  private parseKey(): string {
    if (this.is(TokenType.IDENT) || this.is(TokenType.STRING)) {
      const key = this.current.value as string;
      this.advance();
      return key;
    }
    throw new Error(`expected key, got ${this.current.type}`);
  }

  private parseIdentValue(): GValue {
    const name = this.current.value as string;
    this.advance();

    // Struct: Name{...}
    if (this.is(TokenType.LBRACE)) {
      this.enter('struct');
      try {
        this.advance();
        const fields: MapEntry[] = [];

        while (!this.is(TokenType.RBRACE)) {
          if (this.is(TokenType.EOF)) {
            throw new Error('unterminated struct');
          }
          if (this.is(TokenType.COMMA) || this.is(TokenType.NEWLINE)) {
            this.advance();
            continue;
          }
          if (fields.length >= MAX_COLLECTION_LEN) {
            throw new Error(`struct too large (>${MAX_COLLECTION_LEN} fields)`);
          }

          const key = this.parseKey();

          if (!this.is(TokenType.EQUALS) && !this.is(TokenType.COLON)) {
            throw new Error(`expected '=' or ':' after field '${key}'`);
          }
          this.advance();

          fields.push({ key, value: this.parseValue() });
        }

        this.advance(); // consume RBRACE
        return GValue.struct(name, ...fields);
      } finally {
        this.leave();
      }
    }

    // Sum: Tag(value) or Tag()
    if (this.is(TokenType.LPAREN)) {
      this.enter('sum');
      try {
        this.advance();
        if (this.is(TokenType.RPAREN)) {
          this.advance();
          return GValue.sum(name, null);
        }
        const value = this.parseValue();
        if (!this.is(TokenType.RPAREN)) {
          throw new Error(`expected ), got ${this.current.type}`);
        }
        this.advance();
        return GValue.sum(name, value);
      } finally {
        this.leave();
      }
    }

    // Bare string
    return GValue.str(name);
  }

  private parseDirective(): GValue {
    // current is AT
    this.advance();

    if (!this.is(TokenType.IDENT)) {
      throw new Error(`expected directive name, got ${this.current.type}`);
    }

    const directive = this.current.value as string;
    this.advance();

    if (directive === 'tab') {
      return this.parseTabular();
    }

    throw new Error(`unknown directive: ${directive}`);
  }

  private parseTabular(): GValue {
    this.enter('tabular directive');
    try {
      // Skip the _ placeholder (lexed as NULL)
      if (this.is(TokenType.NULL) || (this.is(TokenType.IDENT) && this.current.value === '_')) {
        this.advance();
      }

      // Column headers: [col1 col2 ...]. The v2.4.0 JS emitter writes
      // `rows=N cols=M` metadata between the placeholder and the bracket (the
      // Python emitter does not); skip any such attributes until the bracket.
      while (!this.is(TokenType.LBRACKET)) {
        if (this.is(TokenType.EOF)) {
          throw new Error('expected [ for column headers');
        }
        this.advance();
      }

      this.advance(); // consume LBRACKET
      const cols: string[] = [];
      while (!this.is(TokenType.RBRACKET)) {
        if (this.is(TokenType.IDENT) || this.is(TokenType.STRING)) {
          cols.push(this.current.value as string);
          this.advance();
        } else if (this.is(TokenType.COMMA) || this.is(TokenType.NEWLINE)) {
          this.advance();
        } else if (this.is(TokenType.EOF)) {
          throw new Error('unterminated column header');
        } else {
          throw new Error(`expected column name, got ${this.current.type}`);
        }
      }
      this.advance(); // consume RBRACKET

      // Rows
      const rows: GValue[] = [];
      for (;;) {
        while (this.is(TokenType.NEWLINE)) {
          this.advance();
        }

        if (this.is(TokenType.AT)) {
          this.advance();
          if (this.is(TokenType.IDENT) && this.current.value === 'end') {
            this.advance();
            break;
          }
          throw new Error('expected @end');
        }

        if (this.is(TokenType.PIPE)) {
          rows.push(this.parseTabularRow(cols));
        } else if (this.is(TokenType.EOF)) {
          break;
        } else {
          throw new Error(`expected row or @end, got ${this.current.type}`);
        }
      }

      return GValue.list(...rows);
    } finally {
      this.leave();
    }
  }

  private parseTabularRow(cols: string[]): GValue {
    // current is PIPE; lexer.pos is right after the opening pipe, so cell
    // content is read as raw characters (not tokenized) until the next pipe.
    const entries: MapEntry[] = [];

    for (const col of cols) {
      let cell = '';

      while (this.lexer.pos < this.lexer.length) {
        const c = this.lexer.text[this.lexer.pos];
        if (c === '|') break;
        if (c === '\\' && this.lexer.pos + 1 < this.lexer.length) {
          const nextC = this.lexer.text[this.lexer.pos + 1];
          if (nextC === '|') { cell += '|'; this.lexer.pos += 2; continue; }
          if (nextC === 'n') { cell += '\n'; this.lexer.pos += 2; continue; }
          if (nextC === '\\') { cell += '\\'; this.lexer.pos += 2; continue; }
        }
        cell += c;
        this.lexer.pos += 1;
      }

      if (this.lexer.pos >= this.lexer.length || this.lexer.text[this.lexer.pos] !== '|') {
        throw new Error('expected | after cell');
      }
      this.lexer.pos += 1; // skip the closing pipe

      const cellText = cell.trim();
      let value: GValue;
      if (cellText === '' || cellText === '∅' || cellText === '_') {
        value = GValue.null();
      } else {
        const sub = new Parser(cellText, this.maxDepth, this.depth);
        value = sub.parse();
      }
      entries.push({ key: col, value });
    }

    // Resynchronize the token stream after the raw cell read.
    this.current = this.lexer.nextToken();

    return GValue.map(...entries);
  }
}

// ============================================================
// Public API
// ============================================================

/**
 * Parse GLYPH-Loose text into a GValue. Inverse of `canonicalizeLoose`.
 *
 * Closes the JS loose round-trip gap: `parseLoose(canonicalizeLoose(v))` is
 * deep-equal to `v` for JSON-domain values, matching Go's `ParseDocument` and
 * Python's `parse`.
 */
export function parseLoose(text: string, maxDepth = DEFAULT_MAX_DEPTH): GValue {
  return new Parser(text, maxDepth).parse();
}
