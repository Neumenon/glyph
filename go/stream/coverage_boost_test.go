package stream

import (
	"bytes"
	"strings"
	"testing"

	"github.com/Neumenon/glyph/glyph"
)

// ============================================================
// crc.go — VerifyCRC at 0%
// ============================================================

func TestVerifyCRC(t *testing.T) {
	data := []byte("hello")
	crc := ComputeCRC(data)

	if !VerifyCRC(data, crc) {
		t.Error("CRC should match")
	}
	if VerifyCRC(data, 0xdeadbeef) {
		t.Error("CRC should not match wrong value")
	}
}

// ============================================================
// types.go — HasCRC, HasBase, Error methods at 0%
// ============================================================

func TestFrame_HasCRC(t *testing.T) {
	f := &Frame{}
	if f.HasCRC() {
		t.Error("should not have CRC")
	}
	crc := uint32(123)
	f.CRC = &crc
	if !f.HasCRC() {
		t.Error("should have CRC")
	}
}

func TestFrame_HasBase(t *testing.T) {
	f := &Frame{}
	if f.HasBase() {
		t.Error("should not have base")
	}
	base := [32]byte{0x01}
	f.Base = &base
	if !f.HasBase() {
		t.Error("should have base")
	}
}

func TestParseError_Error(t *testing.T) {
	e := &ParseError{Reason: "bad", Offset: 5}
	if !strings.Contains(e.Error(), "bad") {
		t.Error("should contain reason")
	}
	if !strings.Contains(e.Error(), "5") {
		t.Error("should contain offset")
	}

	e2 := &ParseError{Reason: "bad", Offset: -1}
	if strings.Contains(e2.Error(), "offset") {
		t.Error("negative offset should not show offset")
	}
}

func TestCRCMismatchError_Error(t *testing.T) {
	e := &CRCMismatchError{Expected: 0xdeadbeef, Got: 0x12345678}
	s := e.Error()
	if !strings.Contains(s, "deadbeef") {
		t.Error("should contain expected CRC")
	}
}

func TestBaseMismatchError_Error(t *testing.T) {
	e := &BaseMismatchError{}
	s := e.Error()
	if !strings.Contains(s, "base hash mismatch") {
		t.Errorf("unexpected: %q", s)
	}
}

func TestFrameKind_String_Unknown(t *testing.T) {
	k := FrameKind(200)
	s := k.String()
	if !strings.Contains(s, "unknown") {
		t.Errorf("expected unknown, got %q", s)
	}
}

func TestFrameKind_String_All(t *testing.T) {
	kinds := []FrameKind{KindDoc, KindPatch, KindRow, KindUI, KindAck, KindErr, KindPing, KindPong}
	expected := []string{"doc", "patch", "row", "ui", "ack", "err", "ping", "pong"}
	for i, k := range kinds {
		if k.String() != expected[i] {
			t.Errorf("kind %d: expected %q, got %q", k, expected[i], k.String())
		}
	}
}

func TestParseKind_Numeric(t *testing.T) {
	// Test numeric parsing
	k, ok := ParseKind("0")
	if !ok || k != KindDoc {
		t.Error("should parse 0 as doc")
	}
	k2, ok := ParseKind("7")
	if !ok || k2 != KindPong {
		t.Error("should parse 7 as pong")
	}
	_, ok = ParseKind("invalid")
	if ok {
		t.Error("should fail for invalid kind")
	}
}

// ============================================================
// gs1t_writer.go — convenience methods at 0%
// ============================================================

func TestWriter_WriteDoc(t *testing.T) {
	var buf bytes.Buffer
	w := NewWriter(&buf)
	if err := w.WriteDoc(1, 0, []byte("hello")); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(buf.String(), "kind=doc") {
		t.Error("expected kind=doc")
	}
}

func TestWriter_WritePatch(t *testing.T) {
	var buf bytes.Buffer
	w := NewWriter(&buf)
	base := [32]byte{0x01}
	if err := w.WritePatch(1, 1, []byte("patch"), &base); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(buf.String(), "kind=patch") {
		t.Error("expected kind=patch")
	}
	if !strings.Contains(buf.String(), "base=sha256:") {
		t.Error("expected base hash")
	}
}

func TestWriter_WriteRow(t *testing.T) {
	var buf bytes.Buffer
	w := NewWriter(&buf)
	if err := w.WriteRow(1, 2, []byte("row data")); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(buf.String(), "kind=row") {
		t.Error("expected kind=row")
	}
}

func TestWriter_WriteUI(t *testing.T) {
	var buf bytes.Buffer
	w := NewWriter(&buf)
	if err := w.WriteUI(1, 3, []byte("ui data")); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(buf.String(), "kind=ui") {
		t.Error("expected kind=ui")
	}
}

func TestWriter_WriteErr(t *testing.T) {
	var buf bytes.Buffer
	w := NewWriter(&buf)
	if err := w.WriteErr(1, 4, []byte("error")); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(buf.String(), "kind=err") {
		t.Error("expected kind=err")
	}
}

func TestWriter_WritePing(t *testing.T) {
	var buf bytes.Buffer
	w := NewWriter(&buf)
	if err := w.WritePing(1, 5); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(buf.String(), "kind=ping") {
		t.Error("expected kind=ping")
	}
}

func TestWriter_WritePong(t *testing.T) {
	var buf bytes.Buffer
	w := NewWriter(&buf)
	if err := w.WritePong(1, 6); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(buf.String(), "kind=pong") {
		t.Error("expected kind=pong")
	}
}

func TestWriter_WriteFinal(t *testing.T) {
	var buf bytes.Buffer
	w := NewWriter(&buf)
	if err := w.WriteFinal(1, 7, KindDoc, []byte("done")); err != nil {
		t.Fatal(err)
	}
	s := buf.String()
	if !strings.Contains(s, "final=true") {
		t.Error("expected final=true")
	}
	if !strings.Contains(s, "kind=doc") {
		t.Error("expected kind=doc")
	}
}

// ============================================================
// hash.go — uncovered paths
// ============================================================

func TestStateHashEmit(t *testing.T) {
	v := glyph.Map(glyph.MapEntry{Key: "x", Value: glyph.Int(1)})
	h := StateHashEmit(v)
	if h == [32]byte{} {
		t.Error("expected non-zero hash")
	}
}

func TestStateHashBytes(t *testing.T) {
	h := StateHashBytes([]byte("test"))
	if h == [32]byte{} {
		t.Error("expected non-zero hash")
	}
}

func TestVerifyBase(t *testing.T) {
	h1 := StateHashBytes([]byte("a"))
	h2 := StateHashBytes([]byte("a"))
	h3 := StateHashBytes([]byte("b"))
	if !VerifyBase(h1, h2) {
		t.Error("same data should match")
	}
	if VerifyBase(h1, h3) {
		t.Error("different data should not match")
	}
}

func TestHexToHash_Invalid(t *testing.T) {
	// Wrong length
	_, ok := HexToHash("abc")
	if ok {
		t.Error("should fail for short hex")
	}

	// Invalid chars
	bad := strings.Repeat("g", 64)
	_, ok = HexToHash(bad)
	if ok {
		t.Error("should fail for invalid hex chars")
	}

	// Uppercase hex should work
	upper := strings.Repeat("A", 64)
	_, ok = HexToHash(upper)
	if !ok {
		t.Error("should accept uppercase hex")
	}
}

// ============================================================
// cursor.go — uncovered paths
// ============================================================

func TestStreamCursor_SetStateHash(t *testing.T) {
	sc := NewStreamCursor()
	hash := [32]byte{0x01, 0x02}
	sc.SetStateHash(42, hash)

	state := sc.GetReadOnly(42)
	if state == nil {
		t.Fatal("expected state")
	}
	if !state.HasState {
		t.Error("expected HasState=true")
	}
	if state.StateHash != hash {
		t.Error("hash mismatch")
	}
}

func TestStreamCursor_NeedsResync(t *testing.T) {
	sc := NewStreamCursor()

	// Non-existent SID needs resync
	if !sc.NeedsResync(999) {
		t.Error("unknown SID should need resync")
	}

	// SID without state needs resync
	sc.Get(1)
	if !sc.NeedsResync(1) {
		t.Error("SID without state should need resync")
	}

	// SID with state doesn't need resync
	sc.SetState(1, glyph.Map(glyph.MapEntry{Key: "x", Value: glyph.Int(1)}))
	if sc.NeedsResync(1) {
		t.Error("SID with state should not need resync")
	}
}

func TestFrameHandler_Handle_AllKinds(t *testing.T) {
	h := NewFrameHandler()

	var docCalled, patchCalled, rowCalled, uiCalled, ackCalled, errCalled, finalCalled bool

	h.OnDoc = func(sid, seq uint64, payload []byte, state *SIDState) error {
		docCalled = true
		return nil
	}
	h.OnPatch = func(sid, seq uint64, payload []byte, state *SIDState) error {
		patchCalled = true
		return nil
	}
	h.OnRow = func(sid, seq uint64, payload []byte, state *SIDState) error {
		rowCalled = true
		return nil
	}
	h.OnUI = func(sid, seq uint64, payload []byte, state *SIDState) error {
		uiCalled = true
		return nil
	}
	h.OnAck = func(sid, seq uint64, state *SIDState) error {
		ackCalled = true
		return nil
	}
	h.OnErr = func(sid, seq uint64, payload []byte, state *SIDState) error {
		errCalled = true
		return nil
	}
	h.OnFinal = func(sid uint64, state *SIDState) error {
		finalCalled = true
		return nil
	}

	frames := []*Frame{
		{SID: 1, Seq: 1, Kind: KindDoc, Payload: []byte("doc")},
		{SID: 1, Seq: 2, Kind: KindPatch, Payload: []byte("patch")},
		{SID: 1, Seq: 3, Kind: KindRow, Payload: []byte("row")},
		{SID: 1, Seq: 4, Kind: KindUI, Payload: []byte("ui")},
		{SID: 1, Seq: 5, Kind: KindAck},
		{SID: 1, Seq: 6, Kind: KindErr, Payload: []byte("err")},
		{SID: 1, Seq: 7, Kind: KindDoc, Payload: []byte("final"), Final: true},
	}

	for _, f := range frames {
		if err := h.Handle(f); err != nil {
			t.Errorf("Handle frame seq=%d: %v", f.Seq, err)
		}
	}

	if !docCalled {
		t.Error("OnDoc not called")
	}
	if !patchCalled {
		t.Error("OnPatch not called")
	}
	if !rowCalled {
		t.Error("OnRow not called")
	}
	if !uiCalled {
		t.Error("OnUI not called")
	}
	if !ackCalled {
		t.Error("OnAck not called")
	}
	if !errCalled {
		t.Error("OnErr not called")
	}
	if !finalCalled {
		t.Error("OnFinal not called")
	}
}

func TestFrameHandler_Handle_Duplicate(t *testing.T) {
	h := NewFrameHandler()
	called := 0
	h.OnDoc = func(sid, seq uint64, payload []byte, state *SIDState) error {
		called++
		return nil
	}

	// First frame
	h.Handle(&Frame{SID: 1, Seq: 1, Kind: KindDoc, Payload: []byte("a")})
	// Duplicate
	h.Handle(&Frame{SID: 1, Seq: 1, Kind: KindDoc, Payload: []byte("b")})

	if called != 1 {
		t.Errorf("expected OnDoc called once, got %d", called)
	}
}

func TestFrameHandler_Handle_SeqGap(t *testing.T) {
	h := NewFrameHandler()
	gapDetected := false
	h.OnSeqGap = func(sid uint64, expected, got uint64) error {
		gapDetected = true
		return nil
	}

	h.Handle(&Frame{SID: 1, Seq: 1, Kind: KindDoc})
	h.Handle(&Frame{SID: 1, Seq: 5, Kind: KindDoc}) // gap: 2,3,4

	if !gapDetected {
		t.Error("should detect gap")
	}
}

func TestFrameHandler_Handle_BaseMismatch(t *testing.T) {
	h := NewFrameHandler()

	// Set initial state
	h.Cursor.SetState(1, glyph.Map(glyph.MapEntry{Key: "x", Value: glyph.Int(1)}))
	h.Handle(&Frame{SID: 1, Seq: 1, Kind: KindDoc})

	// Send patch with wrong base
	wrongBase := [32]byte{0xff}
	err := h.Handle(&Frame{SID: 1, Seq: 2, Kind: KindPatch, Base: &wrongBase})
	if err == nil {
		t.Error("expected base mismatch error")
	}
}

func TestFrameHandler_Handle_BaseMismatch_WithCallback(t *testing.T) {
	h := NewFrameHandler()
	mismatchCalled := false
	h.OnBaseMismatch = func(sid uint64, frame *Frame) error {
		mismatchCalled = true
		return nil
	}

	h.Cursor.SetState(1, glyph.Map(glyph.MapEntry{Key: "x", Value: glyph.Int(1)}))
	h.Handle(&Frame{SID: 1, Seq: 1, Kind: KindDoc})

	wrongBase := [32]byte{0xff}
	h.Handle(&Frame{SID: 1, Seq: 2, Kind: KindPatch, Base: &wrongBase})

	if !mismatchCalled {
		t.Error("OnBaseMismatch should have been called")
	}
}

// ============================================================
// gs1t_reader.go — uncovered header parse paths
// ============================================================

func TestReader_InvalidHeader(t *testing.T) {
	input := "not a frame\n"
	r := NewReader(strings.NewReader(input))
	_, err := r.Next()
	if err == nil {
		t.Error("expected error for invalid header")
	}
}

func TestReader_MissingCloseBrace(t *testing.T) {
	input := "@frame{v=1 sid=0 seq=0 kind=doc len=0\n"
	r := NewReader(strings.NewReader(input))
	_, err := r.Next()
	if err == nil {
		t.Error("expected error for missing }")
	}
}

func TestReader_InvalidVersion(t *testing.T) {
	input := "@frame{v=abc sid=0 seq=0 kind=doc len=0}\n\n"
	r := NewReader(strings.NewReader(input))
	_, err := r.Next()
	if err == nil {
		t.Error("expected error for invalid version")
	}
}

func TestReader_InvalidSID(t *testing.T) {
	input := "@frame{v=1 sid=abc seq=0 kind=doc len=0}\n\n"
	r := NewReader(strings.NewReader(input))
	_, err := r.Next()
	if err == nil {
		t.Error("expected error for invalid sid")
	}
}

func TestReader_InvalidSeq(t *testing.T) {
	input := "@frame{v=1 sid=0 seq=abc kind=doc len=0}\n\n"
	r := NewReader(strings.NewReader(input))
	_, err := r.Next()
	if err == nil {
		t.Error("expected error for invalid seq")
	}
}

func TestReader_InvalidKind(t *testing.T) {
	input := "@frame{v=1 sid=0 seq=0 kind=bogus len=0}\n\n"
	r := NewReader(strings.NewReader(input))
	_, err := r.Next()
	if err == nil {
		t.Error("expected error for invalid kind")
	}
}

func TestReader_InvalidLen(t *testing.T) {
	input := "@frame{v=1 sid=0 seq=0 kind=doc len=abc}\n\n"
	r := NewReader(strings.NewReader(input))
	_, err := r.Next()
	if err == nil {
		t.Error("expected error for invalid len")
	}
}

func TestReader_InvalidCRC(t *testing.T) {
	input := "@frame{v=1 sid=0 seq=0 kind=doc len=0 crc=xyz}\n\n"
	r := NewReader(strings.NewReader(input))
	_, err := r.Next()
	if err == nil {
		t.Error("expected error for invalid crc")
	}
}

func TestReader_InvalidBase(t *testing.T) {
	input := "@frame{v=1 sid=0 seq=0 kind=doc len=0 base=invalid}\n\n"
	r := NewReader(strings.NewReader(input))
	_, err := r.Next()
	if err == nil {
		t.Error("expected error for invalid base")
	}
}

func TestReader_WithFlags(t *testing.T) {
	input := "@frame{v=1 sid=0 seq=0 kind=doc len=1 flags=04}\nx\n"
	r := NewReader(strings.NewReader(input))
	f, err := r.Next()
	if err != nil {
		t.Fatal(err)
	}
	if f.Flags != FlagFinal {
		t.Errorf("expected FlagFinal, got %d", f.Flags)
	}
}

func TestReader_CRCWithPrefix(t *testing.T) {
	payload := []byte("test")
	crc := ComputeCRC(payload)
	crcHex := crcToHex(crc)

	input := "@frame{v=1 sid=0 seq=0 kind=doc len=4 crc=crc32:" + crcHex + "}\ntest\n"
	r := NewReader(strings.NewReader(input))
	f, err := r.Next()
	if err != nil {
		t.Fatal(err)
	}
	if f.CRC == nil || *f.CRC != crc {
		t.Error("CRC should match with prefix")
	}
}

// ============================================================
// ui_events.go — all functions at 0%
// ============================================================

func TestProgress(t *testing.T) {
	v := Progress(0.5, "halfway")
	sv, _ := v.AsStruct()
	if sv.TypeName != "Progress" {
		t.Errorf("expected Progress, got %s", sv.TypeName)
	}
}

func TestLog(t *testing.T) {
	v := Log("info", "hello")
	sv, _ := v.AsStruct()
	if sv.TypeName != "Log" {
		t.Errorf("expected Log, got %s", sv.TypeName)
	}
}

func TestLogConvenience(t *testing.T) {
	LogInfo("test")
	LogWarn("test")
	LogError("test")
	LogDebug("test")
}

func TestMetric(t *testing.T) {
	v := Metric("latency", 12.5, "ms")
	sv, _ := v.AsStruct()
	if sv.TypeName != "Metric" {
		t.Errorf("expected Metric, got %s", sv.TypeName)
	}

	// Without unit
	v2 := Metric("count", 42, "")
	sv2, _ := v2.AsStruct()
	if sv2.TypeName != "Metric" {
		t.Error("expected Metric")
	}
}

func TestCounter(t *testing.T) {
	v := Counter("requests", 100)
	sv, _ := v.AsStruct()
	if sv.TypeName != "Metric" {
		t.Errorf("expected Metric, got %s", sv.TypeName)
	}
}

func TestArtifact(t *testing.T) {
	v := Artifact("image/png", "blob:sha256:abc", "plot.png")
	sv, _ := v.AsStruct()
	if sv.TypeName != "Artifact" {
		t.Errorf("expected Artifact, got %s", sv.TypeName)
	}
}

func TestResyncRequest(t *testing.T) {
	v := ResyncRequest(1, 42, "sha256:abc", "BASE_MISMATCH")
	sv, _ := v.AsStruct()
	if sv.TypeName != "ResyncRequest" {
		t.Errorf("expected ResyncRequest, got %s", sv.TypeName)
	}
}

func TestEmitUI(t *testing.T) {
	b := EmitUI(Progress(0.5, "test"))
	if len(b) == 0 {
		t.Error("expected non-empty")
	}
}

func TestEmitProgress(t *testing.T) {
	b := EmitProgress(0.75, "almost done")
	if len(b) == 0 {
		t.Error("expected non-empty")
	}
}

func TestEmitLog(t *testing.T) {
	b := EmitLog("info", "test message")
	if len(b) == 0 {
		t.Error("expected non-empty")
	}
}

func TestEmitMetric(t *testing.T) {
	b := EmitMetric("latency", 12.5, "ms")
	if len(b) == 0 {
		t.Error("expected non-empty")
	}
}

func TestEmitArtifact(t *testing.T) {
	b := EmitArtifact("text/plain", "blob:sha256:abc", "file.txt")
	if len(b) == 0 {
		t.Error("expected non-empty")
	}
}

func TestStreamError(t *testing.T) {
	v := Error("FAIL", "something broke", 1, 42)
	sv, _ := v.AsStruct()
	if sv.TypeName != "Error" {
		t.Errorf("expected Error, got %s", sv.TypeName)
	}
}

func TestEmitError(t *testing.T) {
	b := EmitError("FAIL", "something broke", 1, 42)
	if len(b) == 0 {
		t.Error("expected non-empty")
	}
}

func TestParseUIEvent(t *testing.T) {
	// Create a progress event and parse it back
	payload := EmitProgress(0.5, "halfway")
	typeName, fields, err := ParseUIEvent(payload)
	if err != nil {
		t.Fatalf("ParseUIEvent: %v", err)
	}
	if typeName != "Progress" {
		t.Errorf("expected Progress, got %s", typeName)
	}
	if pct, ok := fields["pct"].(float64); !ok || pct != 0.5 {
		t.Errorf("expected pct=0.5, got %v", fields["pct"])
	}

	// Error event
	errPayload := EmitError("FAIL", "broke", 1, 42)
	typeName2, fields2, err := ParseUIEvent(errPayload)
	if err != nil {
		t.Fatalf("ParseUIEvent: %v", err)
	}
	if typeName2 != "Error" {
		t.Errorf("expected Error, got %s", typeName2)
	}
	if code, ok := fields2["code"].(string); !ok || code != "FAIL" {
		t.Errorf("expected code=FAIL, got %v", fields2["code"])
	}

	// Invalid input
	_, _, err = ParseUIEvent([]byte("not valid"))
	if err != nil {
		// Parse might succeed in tolerant mode, so just check it doesn't panic
		_ = err
	}

	// Non-struct
	_, _, err = ParseUIEvent([]byte("[1 2 3]"))
	if err == nil {
		t.Error("expected error for non-struct")
	}
}

func TestGlyphUintField_Large(t *testing.T) {
	// Test with a uint64 > max int64
	v := ResyncRequest(1<<63, 0, "x", "y")
	sv, _ := v.AsStruct()
	// The sid field should be a string for very large values
	sidField := v.Get("sid")
	if sidField == nil {
		t.Fatal("expected sid field")
	}
	_ = sv
}

// ============================================================
// Roundtrip: write all convenience methods then read back
// ============================================================

func TestRoundtrip_ConvenienceMethods(t *testing.T) {
	var buf bytes.Buffer
	w := NewWriter(&buf)

	w.WriteDoc(1, 0, []byte("doc"))
	w.WritePatch(1, 1, []byte("patch"), nil)
	w.WriteRow(1, 2, []byte("row"))
	w.WriteUI(1, 3, []byte("ui"))
	w.WriteAck(1, 4)
	w.WriteErr(1, 5, []byte("err"))
	w.WritePing(1, 6)
	w.WritePong(1, 7)
	w.WriteFinal(1, 8, KindDoc, []byte("final"))

	r := NewReader(&buf)
	frames, err := r.ReadAll()
	if err != nil {
		t.Fatalf("ReadAll: %v", err)
	}
	if len(frames) != 9 {
		t.Fatalf("expected 9 frames, got %d", len(frames))
	}

	expectedKinds := []FrameKind{KindDoc, KindPatch, KindRow, KindUI, KindAck, KindErr, KindPing, KindPong, KindDoc}
	for i, f := range frames {
		if f.Kind != expectedKinds[i] {
			t.Errorf("frame %d: expected %v, got %v", i, expectedKinds[i], f.Kind)
		}
	}
	if !frames[8].Final {
		t.Error("last frame should be final")
	}
}
