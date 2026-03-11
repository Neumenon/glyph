package glyph

import (
	"testing"
	"time"
)

// Suite 7: Performance Cliff Detection for glyph canonicalization.

func TestPerfCliff_CanonDeepNesting(t *testing.T) {
	depths := []int{100, 500, 2000}
	opts := LLMLooseCanonOpts()
	var lastDuration time.Duration

	for _, depth := range depths {
		var v *GValue = Null()
		for i := 0; i < depth; i++ {
			v = List(v)
		}

		start := time.Now()
		_ = CanonicalizeLooseWithOpts(v, opts)
		dur := time.Since(start)

		if lastDuration > 0 && dur > lastDuration*20 {
			t.Errorf("possible quadratic blowup at depth=%d: took %v, previous %v (ratio %.1fx)",
				depth, dur, lastDuration, float64(dur)/float64(lastDuration))
		}
		lastDuration = dur
	}
}

func TestPerfCliff_CanonWideMap(t *testing.T) {
	sizes := []int{1000, 10000}
	opts := LLMLooseCanonOpts()

	for _, size := range sizes {
		entries := make([]MapEntry, size)
		for i := 0; i < size; i++ {
			entries[i] = MapEntry{
				Key:   string(rune('a' + (i % 26))),
				Value: Int(int64(i)),
			}
		}
		v := Map(entries...)

		start := time.Now()
		_ = CanonicalizeLooseWithOpts(v, opts)
		dur := time.Since(start)

		if dur > 5*time.Second {
			t.Errorf("wide map size=%d took %v, exceeds 5s threshold", size, dur)
		}
	}
}

func TestPerfCliff_CanonLargeList(t *testing.T) {
	count := 100000
	items := make([]*GValue, count)
	for i := 0; i < count; i++ {
		items[i] = Int(int64(i))
	}
	v := List(items...)
	opts := LLMLooseCanonOpts()

	start := time.Now()
	_ = CanonicalizeLooseWithOpts(v, opts)
	dur := time.Since(start)

	if dur > 5*time.Second {
		t.Errorf("100K list canon took %v, exceeds 5s threshold", dur)
	}
}
