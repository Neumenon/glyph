// go_emitter.go — Emit GS1-T frames using the real Go stream package.
// Used by test_gs1_cross_lang.py to verify Python→Go wire compatibility.
//
// Usage:
//
//	go run go_emitter.go
//
// Writes a fixed set of GS1-T frames to stdout then exits.
// The exact frames are documented in test_gs1_cross_lang.py.
package main

import (
	"os"

	stream "github.com/Neumenon/glyph/go/stream"
)

func main() {
	w := stream.NewWriter(os.Stdout)

	// Frame 1 — minimal doc  (matches TestWriter_MinimalFrame golden)
	_ = w.WriteFrame(&stream.Frame{
		Version: 1, SID: 0, Seq: 0,
		Kind: stream.KindDoc, Payload: []byte("{}"),
	})

	// Frame 2 — ack with empty payload  (matches TestWriter_EmptyPayload golden)
	_ = w.WriteAck(1, 42)

	// Frame 3 — patch with newline-containing payload
	payload := "@patch\nset .x 1\nset .y 2\n@end"
	_ = w.WriteFrame(&stream.Frame{
		Version: 1, SID: 1, Seq: 1,
		Kind: stream.KindPatch, Payload: []byte(payload),
	})

	// Frame 4 — final=true doc
	_ = w.WriteFrame(&stream.Frame{
		Version: 1, SID: 1, Seq: 999,
		Kind: stream.KindDoc, Payload: []byte("done"), Final: true,
	})

	// Frame 5 — large sid/seq (uint64 max)
	maxU64 := uint64(0xFFFFFFFFFFFFFFFF)
	_ = w.WriteFrame(&stream.Frame{
		Version: 1, SID: maxU64, Seq: maxU64,
		Kind: stream.KindDoc, Payload: []byte("x"),
	})
}
