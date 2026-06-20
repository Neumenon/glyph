// Package glyph - Streaming Incremental Parser for real-time GLYPH processing.
//
// This module provides an incremental parser that emits events as tokens arrive,
// enabling processing of streaming LLM output before the complete response is
// available. This reduces perceived latency for UI applications.
//
// Key features:
//   - Event-based parsing with callbacks
//   - Partial value extraction for early processing
//   - Automatic buffering and state management
//   - Support for resumption after network interruption
package glyph

import (
	"errors"
	"fmt"
	"math"
	"strconv"
	"sync"
)

// ParseEventType identifies the type of parse event.
type ParseEventType uint8

const (
	EventNone        ParseEventType = iota
	EventStartObject                // Beginning of { or Type{
	EventEndObject                  // End of }
	EventStartList                  // Beginning of [
	EventEndList                    // End of ]
	EventKey                        // Field key parsed
	EventValue                      // Scalar value parsed
	EventStartSum                   // Beginning of Tag( or Tag{
	EventEndSum                     // End of ) or }
	EventError                      // Parse error
	EventNeedMore                   // Need more input
)

// String returns the event type name.
func (e ParseEventType) String() string {
	switch e {
	case EventNone:
		return "NONE"
	case EventStartObject:
		return "START_OBJECT"
	case EventEndObject:
		return "END_OBJECT"
	case EventStartList:
		return "START_LIST"
	case EventEndList:
		return "END_LIST"
	case EventKey:
		return "KEY"
	case EventValue:
		return "VALUE"
	case EventStartSum:
		return "START_SUM"
	case EventEndSum:
		return "END_SUM"
	case EventError:
		return "ERROR"
	case EventNeedMore:
		return "NEED_MORE"
	default:
		return "UNKNOWN"
	}
}

// ParseEvent represents a single parsing event.
type ParseEvent struct {
	Type     ParseEventType
	Path     []PathElement // Path to current location
	Key      string        // For EventKey
	Value    *GValue       // For EventValue
	TypeName string        // For EventStartObject (struct type)
	Tag      string        // For EventStartSum
	Error    error         // For EventError
	Pos      Position      // Source position
}

// PathElement represents one level in the parse path.
type PathElement struct {
	IsIndex bool   // true if array index, false if key
	Index   int    // Array index (if IsIndex)
	Key     string // Object key (if !IsIndex)
}

// ParseHandler is called for each parse event.
type ParseHandler func(event ParseEvent) error

// IncrementalParser provides streaming parse functionality.
type IncrementalParser struct {
	mu      sync.Mutex
	handler ParseHandler
	buffer  []byte
	pos     int
	path    []PathElement
	state   parseState
	stack   []parseStackFrame
	err     error

	// Configuration
	maxDepth    int
	maxKeyLen   int
	maxValueLen int

	handlingErrorEvent bool

	// atEnd is set by End() so the final, otherwise-extensible token (a number,
	// identifier or reference that reaches the buffer end) can be flushed
	// instead of waiting for input that will never arrive.
	atEnd bool
}

type parseState int

const (
	stateStart parseState = iota
	stateInObject
	stateInList
	stateExpectKey
	stateExpectValue
	stateExpectColon
	stateAfterValue
	stateDone
	stateError
)

type parseStackFrame struct {
	state    parseState
	typeName string // For structs
	tag      string // For sums
	count    int    // Number of items parsed
	pathLen  int    // len(path) when this container was entered (for clean unwinding)
}

// IncrementalParserOptions configures the parser.
type IncrementalParserOptions struct {
	// MaxDepth limits nesting depth (default: 128)
	MaxDepth int

	// MaxKeyLen limits key string length (default: 4096)
	MaxKeyLen int

	// MaxValueLen limits value string length (default: 1MB)
	MaxValueLen int
}

// DefaultIncrementalParserOptions returns sensible defaults.
func DefaultIncrementalParserOptions() IncrementalParserOptions {
	return IncrementalParserOptions{
		MaxDepth:    128,
		MaxKeyLen:   4096,
		MaxValueLen: 1 << 20, // 1MB
	}
}

// NewIncrementalParser creates a new incremental parser.
func NewIncrementalParser(handler ParseHandler, opts IncrementalParserOptions) *IncrementalParser {
	if opts.MaxDepth == 0 {
		opts.MaxDepth = 128
	}
	if opts.MaxKeyLen == 0 {
		opts.MaxKeyLen = 4096
	}
	if opts.MaxValueLen == 0 {
		opts.MaxValueLen = 1 << 20
	}

	return &IncrementalParser{
		handler:     handler,
		buffer:      make([]byte, 0, 4096),
		path:        make([]PathElement, 0, 16),
		state:       stateStart,
		stack:       make([]parseStackFrame, 0, 16),
		maxDepth:    opts.MaxDepth,
		maxKeyLen:   opts.MaxKeyLen,
		maxValueLen: opts.MaxValueLen,
	}
}

// Feed adds more input data to the parser.
// Returns number of bytes consumed and any error.
func (p *IncrementalParser) Feed(data []byte) (int, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.state == stateError {
		return 0, p.err
	}

	// Append to buffer
	p.buffer = append(p.buffer, data...)

	p.process()

	// Compact buffer
	if p.pos > 0 {
		copy(p.buffer, p.buffer[p.pos:])
		p.buffer = p.buffer[:len(p.buffer)-p.pos]
		consumed := p.pos
		p.pos = 0
		return consumed, p.err
	}

	return 0, p.err
}

// process consumes as much of the buffer as possible. A state, stack or path
// change counts as progress even when zero bytes are consumed, so zero-width
// transitions (closing a container, an implicit item separator) never stall the
// loop. Genuine lack of progress means the current token needs more input.
func (p *IncrementalParser) process() {
	for p.pos < len(p.buffer) && p.state != stateError && p.state != stateDone {
		beforePos, beforeState := p.pos, p.state
		beforeStack, beforePath := len(p.stack), len(p.path)

		consumed := p.processNext()

		if consumed == 0 && p.pos == beforePos && p.state == beforeState &&
			len(p.stack) == beforeStack && len(p.path) == beforePath {
			if !p.atEnd {
				p.emitEvent(ParseEvent{Type: EventNeedMore})
			}
			break
		}
	}
}

// End signals end of input.
func (p *IncrementalParser) End() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.state == stateError {
		return p.err
	}

	// No more input is coming: flush any pending extensible token (e.g. a
	// trailing number/identifier/reference that was waiting for a terminator).
	p.atEnd = true
	p.process()

	if p.state == stateError {
		return p.err
	}

	// Check for incomplete parse (unclosed container, or a dangling key/colon).
	if len(p.stack) > 0 || p.state == stateExpectKey || p.state == stateExpectColon ||
		p.state == stateExpectValue {
		p.setError(errors.New("unexpected end of input"))
		return p.err
	}

	p.state = stateDone
	return nil
}

// Reset clears the parser state for reuse.
func (p *IncrementalParser) Reset() {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.buffer = p.buffer[:0]
	p.pos = 0
	p.path = p.path[:0]
	p.state = stateStart
	p.stack = p.stack[:0]
	p.err = nil
	p.handlingErrorEvent = false
	p.atEnd = false
}

// Path returns the current parse path.
func (p *IncrementalParser) Path() []PathElement {
	p.mu.Lock()
	defer p.mu.Unlock()

	result := make([]PathElement, len(p.path))
	copy(result, p.path)
	return result
}

func (p *IncrementalParser) processNext() int {
	// Skip whitespace
	for p.pos < len(p.buffer) && isWhitespace(p.buffer[p.pos]) {
		p.pos++
	}

	if p.pos >= len(p.buffer) {
		return 0
	}

	ch := p.buffer[p.pos]

	switch p.state {
	case stateStart, stateExpectValue:
		return p.parseValue()

	case stateInObject, stateExpectKey:
		if ch == '}' {
			return p.closeContainer('}')
		}
		return p.parseKey()

	case stateExpectColon:
		if ch == ':' || ch == '=' {
			p.pos++
			p.state = stateExpectValue
			return 1
		}
		p.setError(errors.New("expected ':' or '='"))
		return 0

	case stateInList:
		if ch == ']' {
			return p.closeContainer(']')
		}
		// Set the path index for this element before parsing it. Done before the
		// value parse (and idempotently on a need-more re-entry) so that the
		// count is only advanced once the element actually completes.
		if len(p.stack) > 0 {
			p.updatePathIndex(&p.stack[len(p.stack)-1])
		}
		n := p.parseValue()
		if n > 0 && len(p.stack) > 0 {
			p.stack[len(p.stack)-1].count++
		}
		return n

	case stateAfterValue:
		// After a value: a separator (',' or whitespace), or a closing token.
		if ch == '}' || ch == ']' || ch == ')' {
			return p.closeContainer(ch)
		}
		var frame *parseStackFrame
		if len(p.stack) > 0 {
			frame = &p.stack[len(p.stack)-1]
		}
		if ch == ',' {
			p.pos++
			p.advanceToNextItem(frame)
			return 1
		}
		// Implicit (whitespace-only) separator between items.
		if frame == nil {
			// Trailing content after a complete top-level value.
			return 0
		}
		p.advanceToNextItem(frame)
		return 0

	default:
		return 0
	}
}

// closeContainer consumes a closing token, unwinds the path to the container's
// entry depth, pops the frame and emits the matching End event.
func (p *IncrementalParser) closeContainer(ch byte) int {
	if len(p.stack) == 0 {
		p.setError(fmt.Errorf("unexpected '%c'", ch))
		return 0
	}
	frame := p.stack[len(p.stack)-1]

	var evt ParseEventType
	var match bool
	switch frame.state {
	case stateInObject:
		match, evt = ch == '}', EventEndObject
	case stateInList:
		match, evt = ch == ']', EventEndList
	case stateExpectValue: // sum frame
		match, evt = ch == ')', EventEndSum
	}
	if !match {
		p.setError(fmt.Errorf("mismatched '%c'", ch))
		return 0
	}

	p.pos++
	if len(p.path) > frame.pathLen {
		p.path = p.path[:frame.pathLen]
	}
	p.stack = p.stack[:len(p.stack)-1]
	if len(p.stack) > 0 {
		p.state = stateAfterValue
	} else {
		p.state = stateDone
	}
	p.emitEvent(ParseEvent{Type: evt, Path: p.copyPath()})
	return 1
}

// advanceToNextItem transitions from stateAfterValue to the state that reads the
// next item of the enclosing container, unwinding any per-item path element.
func (p *IncrementalParser) advanceToNextItem(frame *parseStackFrame) {
	if frame == nil {
		return
	}
	switch frame.state {
	case stateInList:
		p.state = stateInList
	case stateExpectValue:
		// A sum holds a single value; only its closing ')' is valid next.
	default: // object
		if len(p.path) > frame.pathLen {
			p.path = p.path[:frame.pathLen] // pop the completed field's key
		}
		p.state = stateExpectKey
	}
}

func (p *IncrementalParser) parseValue() int {
	if p.pos >= len(p.buffer) {
		return 0
	}

	ch := p.buffer[p.pos]

	// Empty sum: Tag() — a closing token where a value was expected.
	if ch == ')' || ch == '}' || ch == ']' {
		return p.closeContainer(ch)
	}

	// Null symbol ∅ (3-byte UTF-8). Wait for the full sequence if it is split.
	if ch == 0xE2 {
		if p.pos+3 <= len(p.buffer) {
			if string(p.buffer[p.pos:p.pos+3]) == "∅" {
				p.pos += 3
				p.emitEvent(ParseEvent{Type: EventValue, Value: Null(), Path: p.copyPath()})
				p.state = stateAfterValue
				return 3
			}
		} else if !p.atEnd {
			return 0 // need the rest of the symbol
		}
		p.setError(errors.New("unexpected character"))
		return 0
	}

	// Number
	if ch == '-' || (ch >= '0' && ch <= '9') {
		return p.parseNumber()
	}

	// String
	if ch == '"' {
		return p.parseString()
	}

	// List
	if ch == '[' {
		p.pos++
		if !p.pushStack(stateInList, "", "") {
			return 0
		}
		p.emitEvent(ParseEvent{Type: EventStartList, Path: p.copyPath()})
		p.state = stateInList
		return 1
	}

	// Object or struct
	if ch == '{' {
		p.pos++
		if !p.pushStack(stateInObject, "", "") {
			return 0
		}
		p.emitEvent(ParseEvent{Type: EventStartObject, Path: p.copyPath()})
		p.state = stateExpectKey
		return 1
	}

	// Reference (^prefix:value)
	if ch == '^' {
		return p.parseRef()
	}

	// Identifier: keyword (true/t/false/f/null/none/nil), struct type, sum tag,
	// or bare string. Resolved in parseIdentifier once the full token is known.
	if isIdentStart(ch) {
		return p.parseIdentifier()
	}

	p.setError(errors.New("unexpected character"))
	return 0
}

func (p *IncrementalParser) parseKey() int {
	if p.pos >= len(p.buffer) {
		return 0
	}

	ch := p.buffer[p.pos]

	// Quoted key
	if ch == '"' {
		start := p.pos
		key, consumed := p.scanString()
		if consumed == 0 {
			return 0 // Need more data
		}
		if len(key) > p.maxKeyLen {
			p.setError(fmt.Errorf("key too long: %d > %d", len(key), p.maxKeyLen))
			return 0
		}
		p.path = append(p.path, PathElement{Key: key})
		p.emitEvent(ParseEvent{Type: EventKey, Key: key, Path: p.copyPath()})
		p.state = stateExpectColon
		return p.pos - start
	}

	// Bare identifier key
	if isIdentStart(ch) {
		start := p.pos
		j := p.pos
		for j < len(p.buffer) && isIdentContinue(p.buffer[j]) {
			j++
		}
		// A bare key running to the buffer end may still be extended.
		if j == len(p.buffer) && !p.atEnd {
			return 0
		}
		key := string(p.buffer[start:j])
		p.pos = j
		if len(key) > p.maxKeyLen {
			p.setError(fmt.Errorf("key too long: %d > %d", len(key), p.maxKeyLen))
			return 0
		}
		p.path = append(p.path, PathElement{Key: key})
		p.emitEvent(ParseEvent{Type: EventKey, Key: key, Path: p.copyPath()})
		p.state = stateExpectColon
		return p.pos - start
	}

	p.setError(errors.New("expected key"))
	return 0
}

func (p *IncrementalParser) parseNumber() int {
	start := p.pos
	buf := p.buffer
	j := p.pos

	// Sign
	if j < len(buf) && buf[j] == '-' {
		j++
	}

	// Integer part
	for j < len(buf) && isDigit(buf[j]) {
		j++
	}

	isFloat := false

	// Decimal part
	if j < len(buf) && buf[j] == '.' {
		if j+1 < len(buf) && isDigit(buf[j+1]) {
			isFloat = true
			j += 2
			for j < len(buf) && isDigit(buf[j]) {
				j++
			}
		} else if j+1 == len(buf) && !p.atEnd {
			// A trailing '.' might begin a fractional part once more arrives.
			return 0
		}
	}

	// Exponent
	if j < len(buf) && (buf[j] == 'e' || buf[j] == 'E') {
		isFloat = true
		j++
		if j < len(buf) && (buf[j] == '+' || buf[j] == '-') {
			j++
		}
		for j < len(buf) && isDigit(buf[j]) {
			j++
		}
	}

	// If the number runs to the buffer end it may be extended by more input.
	if j == len(buf) && !p.atEnd {
		return 0
	}

	p.pos = j
	numStr := string(buf[start:j])
	if len(numStr) > p.maxValueLen {
		p.setError(fmt.Errorf("value too long: %d > %d", len(numStr), p.maxValueLen))
		return 0
	}
	var value *GValue

	if isFloat {
		f, err := strconv.ParseFloat(numStr, 64)
		if err != nil || math.IsNaN(f) || math.IsInf(f, 0) {
			p.setError(fmt.Errorf("invalid number: %s", numStr))
			return 0
		}
		value = Float(f)
	} else {
		i, err := strconv.ParseInt(numStr, 10, 64)
		if err != nil {
			p.setError(fmt.Errorf("invalid number: %s", numStr))
			return 0
		}
		value = Int(i)
	}

	p.emitEvent(ParseEvent{Type: EventValue, Value: value, Path: p.copyPath()})
	p.state = stateAfterValue
	return p.pos - start
}

func (p *IncrementalParser) parseString() int {
	str, consumed := p.scanString()
	if consumed == 0 {
		if p.atEnd {
			p.setError(errors.New("unterminated string"))
		}
		return 0
	}
	p.emitEvent(ParseEvent{Type: EventValue, Value: Str(str), Path: p.copyPath()})
	p.state = stateAfterValue
	return consumed
}

func (p *IncrementalParser) scanString() (string, int) {
	if p.pos >= len(p.buffer) || p.buffer[p.pos] != '"' {
		return "", 0
	}

	start := p.pos
	p.pos++ // Skip opening quote

	var sb []byte
	for p.pos < len(p.buffer) {
		ch := p.buffer[p.pos]
		if ch == '"' {
			p.pos++ // Skip closing quote
			return string(sb), p.pos - start
		}
		if ch == '\\' {
			p.pos++
			if p.pos >= len(p.buffer) {
				p.pos = start // Reset - need more data
				return "", 0
			}
			escaped := p.buffer[p.pos]
			switch escaped {
			case 'n':
				sb = append(sb, '\n')
			case 'r':
				sb = append(sb, '\r')
			case 't':
				sb = append(sb, '\t')
			case '\\':
				sb = append(sb, '\\')
			case '"':
				sb = append(sb, '"')
			default:
				sb = append(sb, escaped)
			}
			p.pos++
		} else {
			sb = append(sb, ch)
			p.pos++
		}
		if len(sb) > p.maxValueLen {
			p.setError(fmt.Errorf("value too long: %d > %d", len(sb), p.maxValueLen))
			return "", 0
		}
	}

	// Unterminated string - need more data
	p.pos = start
	return "", 0
}

func (p *IncrementalParser) parseRef() int {
	start := p.pos
	j := p.pos + 1 // skip ^
	for j < len(p.buffer) && isRefChar(p.buffer[j]) {
		j++
	}
	// A reference that runs to the buffer end may have more characters coming.
	if j == len(p.buffer) && !p.atEnd {
		return 0
	}
	if j-(start+1) > p.maxValueLen {
		p.setError(fmt.Errorf("value too long: %d > %d", j-(start+1), p.maxValueLen))
		return 0
	}

	refStr := p.buffer[start+1 : j]
	p.pos = j

	// Parse prefix:value
	prefix, value := "", string(refStr)
	for i, ch := range refStr {
		if ch == ':' {
			prefix = string(refStr[:i])
			value = string(refStr[i+1:])
			break
		}
	}

	p.emitEvent(ParseEvent{Type: EventValue, Value: ID(prefix, value), Path: p.copyPath()})
	p.state = stateAfterValue
	return p.pos - start
}

func (p *IncrementalParser) parseIdentifier() int {
	start := p.pos
	j := p.pos
	for j < len(p.buffer) && isIdentContinue(p.buffer[j]) {
		j++
	}

	// If the identifier reaches the buffer end it may be extended, and we cannot
	// yet see whether a '{' (struct) or '(' (sum) follows. Wait for more input.
	if j == len(p.buffer) && !p.atEnd {
		return 0
	}

	if j-start > p.maxValueLen {
		p.setError(fmt.Errorf("value too long: %d > %d", j-start, p.maxValueLen))
		return 0
	}
	ident := string(p.buffer[start:j])

	// Struct / sum are determined by the immediately following delimiter.
	if j < len(p.buffer) {
		switch p.buffer[j] {
		case '{':
			p.pos = j + 1
			if !p.pushStack(stateInObject, ident, "") {
				return 0
			}
			p.emitEvent(ParseEvent{Type: EventStartObject, TypeName: ident, Path: p.copyPath()})
			p.state = stateExpectKey
			return p.pos - start
		case '(':
			p.pos = j + 1
			if !p.pushStack(stateExpectValue, "", ident) {
				return 0
			}
			p.emitEvent(ParseEvent{Type: EventStartSum, Tag: ident, Path: p.copyPath()})
			p.state = stateExpectValue
			return p.pos - start
		}
	}

	// Keyword / boolean / null, else a bare string.
	p.pos = j
	var value *GValue
	switch ident {
	case "true", "t":
		value = Bool(true)
	case "false", "f":
		value = Bool(false)
	case "null", "none", "nil":
		value = Null()
	default:
		value = Str(ident)
	}
	p.emitEvent(ParseEvent{Type: EventValue, Value: value, Path: p.copyPath()})
	p.state = stateAfterValue
	return p.pos - start
}

func (p *IncrementalParser) pushStack(state parseState, typeName, tag string) bool {
	if len(p.stack)+1 > p.maxDepth {
		p.setError(fmt.Errorf("max depth exceeded: %d", p.maxDepth))
		return false
	}
	p.stack = append(p.stack, parseStackFrame{
		state:    state,
		typeName: typeName,
		tag:      tag,
		count:    0,
		pathLen:  len(p.path),
	})
	return true
}

// updatePathIndex sets the path element for the current item of the list frame.
// The element lives at frame.pathLen; deeper elements (from a previous sibling's
// children) are truncated so nested lists get correctly nested indices.
func (p *IncrementalParser) updatePathIndex(frame *parseStackFrame) {
	if len(p.path) == frame.pathLen {
		p.path = append(p.path, PathElement{IsIndex: true, Index: frame.count})
		return
	}
	p.path = p.path[:frame.pathLen+1]
	p.path[frame.pathLen] = PathElement{IsIndex: true, Index: frame.count}
}

func (p *IncrementalParser) copyPath() []PathElement {
	result := make([]PathElement, len(p.path))
	copy(result, p.path)
	return result
}

func (p *IncrementalParser) emitEvent(event ParseEvent) {
	if p.handler != nil {
		if event.Type == EventError {
			if p.handlingErrorEvent {
				return
			}
			p.handlingErrorEvent = true
			defer func() {
				p.handlingErrorEvent = false
			}()
		}
		if err := p.handler(event); err != nil {
			if event.Type == EventError || p.handlingErrorEvent {
				if p.err == nil {
					p.err = err
				}
				p.state = stateError
				return
			}
			p.setError(err)
		}
	}
}

func (p *IncrementalParser) setError(err error) {
	if err == nil {
		return
	}
	if p.state == stateError && p.err != nil {
		return
	}
	p.err = err
	p.state = stateError
	p.emitEvent(ParseEvent{Type: EventError, Error: err})
}

func isWhitespace(ch byte) bool {
	return ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r'
}
