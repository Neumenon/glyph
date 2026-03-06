//go:build agentgo

package glyph

import (
	"testing"
	"time"
)

func TestBridge_RoundTrip(t *testing.T) {
	original := Struct("Match",
		MapEntry{Key: "id", Value: ID("m", "ARS-LIV")},
		MapEntry{Key: "home", Value: Struct("Team",
			MapEntry{Key: "name", Value: Str("Arsenal")},
			MapEntry{Key: "rank", Value: Int(1)},
		)},
		MapEntry{Key: "odds", Value: List(Float(2.10), Float(3.40), Float(3.25))},
	)

	// Convert to Cowrie and back
	sjsonVal := ToSJSON(original)
	roundTripped := FromSJSON(sjsonVal)

	// Compare canonical forms
	origEmit := Emit(original)
	rtEmit := Emit(roundTripped)

	if origEmit != rtEmit {
		t.Errorf("Round-trip mismatch:\n  Original: %s\n  RoundTrip: %s", origEmit, rtEmit)
	}
}

func TestBridge_TimeValue(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Nanosecond)
	original := Time(now)

	sjsonVal := ToSJSON(original)
	roundTripped := FromSJSON(sjsonVal)

	if roundTripped.Type() != TypeTime {
		t.Fatalf("Expected time type, got %s", roundTripped.Type())
	}

	rtTime := mustAsTime(t, roundTripped)
	if !rtTime.Equal(now) {
		t.Errorf("Time mismatch: %v vs %v", now, rtTime)
	}
}
