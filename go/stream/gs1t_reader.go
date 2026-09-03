package stream

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"strconv"
	"strings"
)

// MaxHeaderSize is the maximum number of bytes read for a single header line.
// A header line longer than this will be rejected to prevent unbounded memory
// allocation via ReadString('\n').
const MaxHeaderSize = 64 * 1024 // 64 KiB

// Reader reads GS1-T (text) frames from an io.Reader.
type Reader struct {
	r          *bufio.Reader
	maxPayload int
	verifyCRC  bool
}

// ReaderOption configures a Reader.
type ReaderOption func(*Reader)

// WithMaxPayload sets the maximum payload size (default: 64 MiB).
func WithMaxPayload(max int) ReaderOption {
	return func(r *Reader) {
		r.maxPayload = max
	}
}

// WithCRCVerification enables CRC verification.
func WithCRCVerification() ReaderOption {
	return func(r *Reader) {
		r.verifyCRC = true
	}
}

// NewReader creates a new GS1-T frame reader.
func NewReader(r io.Reader, opts ...ReaderOption) *Reader {
	reader := &Reader{
		r:          bufio.NewReaderSize(r, MaxHeaderSize),
		maxPayload: MaxPayloadSize,
		verifyCRC:  true, // verify by default
	}
	for _, opt := range opts {
		opt(reader)
	}
	return reader
}

// Next reads and returns the next frame.
// Returns io.EOF when no more frames are available.
func (r *Reader) Next() (*Frame, error) {
	// Read header line, bounded to MaxHeaderSize to prevent DoS via a line
	// with no newline (bufio.ReadString would otherwise grow unboundedly).
	line, isPrefix, err := r.r.ReadLine()
	if err != nil {
		if err == io.EOF && len(line) == 0 {
			return nil, io.EOF
		}
		return nil, fmt.Errorf("read header: %w", err)
	}
	if isPrefix {
		// Line exceeded the MaxHeaderSize buffer — drain and reject.
		for isPrefix {
			_, isPrefix, _ = r.r.ReadLine()
		}
		return nil, &ParseError{Reason: fmt.Sprintf("header line exceeds maximum size (%d bytes)", MaxHeaderSize), Offset: -1}
	}
	headerLine := string(line) + "\n"

	// Parse header
	frame, payloadLen, err := r.parseHeader(headerLine)
	if err != nil {
		return nil, err
	}

	// Validate the declared length BEFORE allocating: a huge len must fail
	// on the limit check, not on a huge make([]byte).
	if payloadLen > r.maxPayload {
		return nil, &ParseError{Reason: fmt.Sprintf("payload too large: %d > %d", payloadLen, r.maxPayload), Offset: -1}
	}

	// Read exact payload bytes
	if payloadLen > 0 {
		frame.Payload = make([]byte, payloadLen)
		if _, err := io.ReadFull(r.r, frame.Payload); err != nil {
			return nil, fmt.Errorf("read payload: %w", err)
		}
	} else {
		frame.Payload = nil
	}

	// Consume trailing newline (optional at EOF)
	if b, err := r.r.ReadByte(); err == nil {
		if b != '\n' {
			// Put it back - it's part of the next frame
			r.r.UnreadByte()
		}
	}

	// Verify CRC if present and verification enabled
	if r.verifyCRC && frame.CRC != nil {
		computed := ComputeCRC(frame.Payload)
		if computed != *frame.CRC {
			return nil, &CRCMismatchError{Expected: *frame.CRC, Got: computed}
		}
	}

	return frame, nil
}

// parseHeader parses the @frame{...} header line, returning the frame and
// the declared payload length. The length is returned (not pre-allocated)
// so the caller can enforce maxPayload before allocating.
func (r *Reader) parseHeader(line string) (*Frame, int, error) {
	line = strings.TrimSpace(line)

	// Check prefix
	if !strings.HasPrefix(line, "@frame{") {
		return nil, 0, &ParseError{Reason: "expected @frame{", Offset: 0}
	}

	// The header must end at the closing brace: anything after "}" on the
	// line is trailing garbage, not part of the frame.
	if !strings.HasSuffix(line, "}") {
		if !strings.Contains(line, "}") {
			return nil, 0, &ParseError{Reason: "missing closing }", Offset: len(line)}
		}
		return nil, 0, &ParseError{Reason: "trailing data after header }", Offset: len(line) - 1}
	}

	// Extract key=value content
	content := line[7 : len(line)-1]

	// Parse key=value pairs
	frame := &Frame{Version: 1}
	var payloadLen int

	for _, pair := range tokenize(content) {
		eqIdx := strings.Index(pair, "=")
		if eqIdx < 0 {
			continue // skip malformed pairs
		}
		key := pair[:eqIdx]
		val := pair[eqIdx+1:]

		switch key {
		case "v":
			v, err := strconv.ParseUint(val, 10, 8)
			if err != nil {
				return nil, 0, &ParseError{Reason: "invalid version", Offset: -1}
			}
			if v != 1 {
				return nil, 0, &ParseError{Reason: fmt.Sprintf("unsupported version %d, must be 1", v), Offset: -1}
			}
			frame.Version = uint8(v)

		case "sid":
			sid, err := strconv.ParseUint(val, 10, 64)
			if err != nil {
				return nil, 0, &ParseError{Reason: "invalid sid", Offset: -1}
			}
			frame.SID = sid

		case "seq":
			seq, err := strconv.ParseUint(val, 10, 64)
			if err != nil {
				return nil, 0, &ParseError{Reason: "invalid seq", Offset: -1}
			}
			frame.Seq = seq

		case "kind":
			kind, ok := ParseKind(val)
			if !ok {
				return nil, 0, &ParseError{Reason: "invalid kind: " + val, Offset: -1}
			}
			frame.Kind = kind

		case "len":
			l, err := strconv.ParseUint(val, 10, 32)
			if err != nil {
				return nil, 0, &ParseError{Reason: "invalid len", Offset: -1}
			}
			payloadLen = int(l)

		case "crc":
			crc, ok := parseCRC(val)
			if !ok {
				return nil, 0, &ParseError{Reason: "invalid crc: " + val, Offset: -1}
			}
			frame.CRC = &crc

		case "base":
			base, ok := parseBase(val)
			if !ok {
				return nil, 0, &ParseError{Reason: "invalid base: " + val, Offset: -1}
			}
			frame.Base = &base

		case "final":
			frame.Final = val == "true" || val == "1"

		case "flags":
			flags, err := strconv.ParseUint(val, 16, 8)
			if err == nil {
				frame.Flags = Flags(flags)
			}
		}
	}

	// Payload bytes are read by the caller after the maxPayload check.
	frame.Payload = nil

	return frame, payloadLen, nil
}

// tokenize splits key=value pairs separated by spaces or commas.
func tokenize(s string) []string {
	var tokens []string
	var current bytes.Buffer
	inQuote := false

	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c == '"':
			inQuote = !inQuote
			current.WriteByte(c)
		case (c == ' ' || c == ',' || c == '\t') && !inQuote:
			if current.Len() > 0 {
				tokens = append(tokens, current.String())
				current.Reset()
			}
		default:
			current.WriteByte(c)
		}
	}
	if current.Len() > 0 {
		tokens = append(tokens, current.String())
	}
	return tokens
}

// parseCRC parses CRC value: "crc32:XXXXXXXX" or "XXXXXXXX"
func parseCRC(val string) (uint32, bool) {
	// Strip optional prefix
	val = strings.TrimPrefix(val, "crc32:")

	if len(val) != 8 {
		return 0, false
	}

	v, err := strconv.ParseUint(val, 16, 32)
	if err != nil {
		return 0, false
	}
	return uint32(v), true
}

// parseBase parses base hash: "sha256:XXXX..." or "XXXX..."
func parseBase(val string) ([32]byte, bool) {
	// Strip optional prefix
	val = strings.TrimPrefix(val, "sha256:")
	return HexToHash(val)
}

// ReadAll reads all frames until EOF.
func (r *Reader) ReadAll() ([]*Frame, error) {
	var frames []*Frame
	for {
		frame, err := r.Next()
		if err == io.EOF {
			return frames, nil
		}
		if err != nil {
			return frames, err
		}
		frames = append(frames, frame)
	}
}
