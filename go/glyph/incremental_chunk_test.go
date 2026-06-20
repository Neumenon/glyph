package glyph

import (
	"fmt"
	"strings"
	"testing"
)

// incremental_chunk_test.go pins the P3 deliverable: the incremental parser is
// chunk-invariant — the sequence of (non-NeedMore) events it emits is identical
// whether the input is fed all at once, one byte at a time, or split at any
// single byte boundary. This is what makes streaming safe: a consumer reacting
// to events can never observe a different document because of how the bytes
// happened to arrive.

func incrValueRepr(v *GValue) string {
	if v == nil {
		return "nil"
	}
	switch v.Type() {
	case TypeNull:
		return "null"
	case TypeBool:
		return fmt.Sprintf("b:%t", v.boolVal)
	case TypeInt:
		return fmt.Sprintf("i:%d", v.intVal)
	case TypeFloat:
		return fmt.Sprintf("f:%v", v.floatVal)
	case TypeStr:
		return fmt.Sprintf("s:%q", v.strVal)
	case TypeID:
		return fmt.Sprintf("r:%s:%s", v.idVal.Prefix, v.idVal.Value)
	default:
		return v.Type().String()
	}
}

func incrPathSig(path []PathElement) string {
	var b strings.Builder
	for _, e := range path {
		if e.IsIndex {
			fmt.Fprintf(&b, "[%d]", e.Index)
		} else {
			b.WriteString("." + e.Key)
		}
	}
	return b.String()
}

func incrEventSig(e ParseEvent) string {
	switch e.Type {
	case EventError:
		return "ERR"
	case EventValue:
		return "V|" + incrValueRepr(e.Value) + "|" + incrPathSig(e.Path)
	case EventKey:
		return "K|" + e.Key + "|" + incrPathSig(e.Path)
	case EventStartObject:
		return "SO|" + e.TypeName + "|" + incrPathSig(e.Path)
	case EventEndObject:
		return "EO|" + incrPathSig(e.Path)
	case EventStartList:
		return "SL|" + incrPathSig(e.Path)
	case EventEndList:
		return "EL|" + incrPathSig(e.Path)
	case EventStartSum:
		return "SS|" + e.Tag + "|" + incrPathSig(e.Path)
	case EventEndSum:
		return "ES|" + incrPathSig(e.Path)
	default:
		return "?"
	}
}

// collectIncrEvents feeds the chunks in order, calls End, and returns the
// signatures of every event except EventNeedMore (whose count is inherently
// chunking-dependent and therefore excluded from the invariant).
func collectIncrEvents(chunks [][]byte) []string {
	var sigs []string
	h := func(e ParseEvent) error {
		if e.Type == EventNeedMore {
			return nil
		}
		sigs = append(sigs, incrEventSig(e))
		return nil
	}
	p := NewIncrementalParser(h, DefaultIncrementalParserOptions())
	for _, c := range chunks {
		p.Feed(c)
	}
	p.End()
	return sigs
}

func sigsEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func TestIncrementalChunkInvariance(t *testing.T) {
	inputs := []string{
		// scalars
		"42", "-123", "0", "3.14", "1e5", "1.5e-3", "-0.25",
		"t", "f", "true", "false", "null", "none", "nil", "∅",
		`"hello"`, `"a b\tc\n"`, `"café"`, "hello", "bareWord",
		"^u:1", "^bare", "^team:ARS-1.2",
		// containers
		"[]", "{}", "[1 2 3]", "[1,2,3]", "{a:1 b:2}", "{a:1,b:2}", "{a=1}",
		"{a:{b:1}}", "[[1][2]]", "[[1] [2] [3]]", `[{a:1} {b:2}]`,
		`Person{name:"Al" age:30}`, "Tag(5)", "Tag()", "Sum(Inner{x:1})",
		`{x:[1 2] y:Tag(3) z:{q:^r:9}}`,
		"  [ 1 , 2 ]  ",
		// malformed
		"{a:", "[1 2", "{", "[", "{a 1}", "[1 2}", "Tag(1", "{a:1 b:}",
	}

	for _, in := range inputs {
		t.Run(in, func(t *testing.T) {
			data := []byte(in)
			want := collectIncrEvents([][]byte{data})

			// One byte at a time.
			byteChunks := make([][]byte, 0, len(data))
			for i := 0; i < len(data); i++ {
				byteChunks = append(byteChunks, data[i:i+1])
			}
			if got := collectIncrEvents(byteChunks); !sigsEqual(want, got) {
				t.Fatalf("byte-by-byte differs from feed-all\n  feed-all: %v\n  byte:     %v", want, got)
			}

			// Every single split point.
			for k := 0; k <= len(data); k++ {
				got := collectIncrEvents([][]byte{data[:k], data[k:]})
				if !sigsEqual(want, got) {
					t.Fatalf("split at byte %d differs from feed-all\n  feed-all: %v\n  split:    %v", k, want, got)
				}
			}
		})
	}
}

// TestIncrementalParserFinishesContainers directly asserts the close-token stall
// is gone: a complete container, fed whole, emits its End event and no error.
func TestIncrementalParserFinishesContainers(t *testing.T) {
	cases := []struct {
		input string
		end   string // expected terminal structural event signature
	}{
		{"{a=1}", "EO|"},
		{"{a:1 b:2}", "EO|"},
		{"[1 2 3]", "EL|"},
		{"Tag(5)", "ES|"},
		{`Person{name:"Al" age:30}`, "EO|"},
		{"{outer:{inner:1}}", "EO|"},
	}
	for _, tc := range cases {
		t.Run(tc.input, func(t *testing.T) {
			sigs := collectIncrEvents([][]byte{[]byte(tc.input)})
			for _, s := range sigs {
				if s == "ERR" {
					t.Fatalf("unexpected error event for %q: %v", tc.input, sigs)
				}
			}
			if len(sigs) == 0 || sigs[len(sigs)-1] != tc.end {
				t.Errorf("expected %q to finish with %q, got %v", tc.input, tc.end, sigs)
			}
		})
	}
}

// TestIncrementalSiblingPathsDoNotAccumulate verifies the path stack is popped
// between object fields and list elements (siblings get sibling paths, not
// nested ones).
func TestIncrementalSiblingPathsDoNotAccumulate(t *testing.T) {
	var keyPaths []string
	h := func(e ParseEvent) error {
		if e.Type == EventKey {
			keyPaths = append(keyPaths, incrPathSig(e.Path))
		}
		return nil
	}
	p := NewIncrementalParser(h, DefaultIncrementalParserOptions())
	p.Feed([]byte("{a:1 b:2 c:3}"))
	p.End()

	want := []string{".a", ".b", ".c"}
	if !sigsEqual(keyPaths, want) {
		t.Errorf("sibling keys accumulated paths: got %v, want %v", keyPaths, want)
	}
}
