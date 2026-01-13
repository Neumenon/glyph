package glyph

import (
	"testing"
)

func TestIsPoolRef(t *testing.T) {
	tests := []struct {
		input string
		want  bool
	}{
		{"S1", true},
		{"O1", true},
		{"P42", true},
		{"ABC123", true},
		{"m", false},       // lowercase - entity prefix
		{"t", false},       // lowercase
		{"S", false},       // no digit
		{"1S", false},      // starts with digit
		{"", false},        // empty
		{"ARS-LIV", false}, // contains dash
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := IsPoolRef(tt.input)
			if got != tt.want {
				t.Errorf("IsPoolRef(%q) = %v, want %v", tt.input, got, tt.want)
			}
		})
	}
}

func TestParsePoolRef(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		want    PoolRef
		wantErr bool
	}{
		{
			name:  "simple",
			input: "^S1:0",
			want:  PoolRef{PoolID: "S1", Index: 0},
		},
		{
			name:  "higher_index",
			input: "^S1:42",
			want:  PoolRef{PoolID: "S1", Index: 42},
		},
		{
			name:  "object_pool",
			input: "^O1:5",
			want:  PoolRef{PoolID: "O1", Index: 5},
		},
		{
			name:    "missing_caret",
			input:   "S1:0",
			wantErr: true,
		},
		{
			name:    "entity_ref_not_pool",
			input:   "^m:ARS",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParsePoolRef(tt.input)
			if (err != nil) != tt.wantErr {
				t.Errorf("ParsePoolRef() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err != nil {
				return
			}
			if got.PoolID != tt.want.PoolID {
				t.Errorf("PoolID = %q, want %q", got.PoolID, tt.want.PoolID)
			}
			if got.Index != tt.want.Index {
				t.Errorf("Index = %d, want %d", got.Index, tt.want.Index)
			}
		})
	}
}

func TestPoolRef_String(t *testing.T) {
	ref := PoolRef{PoolID: "S1", Index: 5}
	want := "^S1:5"
	got := ref.String()
	if got != want {
		t.Errorf("PoolRef.String() = %q, want %q", got, want)
	}
}

func TestPool(t *testing.T) {
	pool := &Pool{
		ID:   "S1",
		Kind: PoolKindString,
	}

	// Add entries
	idx0 := pool.Add(Str("Hello"))
	idx1 := pool.Add(Str("World"))
	idx2 := pool.Add(Int(42))

	if idx0 != 0 || idx1 != 1 || idx2 != 2 {
		t.Errorf("Indices should be 0, 1, 2, got %d, %d, %d", idx0, idx1, idx2)
	}

	// Get entries
	v0 := pool.Get(0)
	if v0 == nil || v0.AsStr() != "Hello" {
		t.Error("Get(0) should return Hello")
	}

	v2 := pool.Get(2)
	if v2 == nil || v2.AsInt() != 42 {
		t.Error("Get(2) should return 42")
	}

	// Out of range
	if pool.Get(-1) != nil {
		t.Error("Get(-1) should return nil")
	}
	if pool.Get(100) != nil {
		t.Error("Get(100) should return nil")
	}
}

func TestPool_String(t *testing.T) {
	pool := &Pool{
		ID:   "S1",
		Kind: PoolKindString,
		Entries: []*GValue{
			Str("hello"),
			Str("world"),
			Int(42),
		},
	}

	got := pool.String()
	want := "@pool.str id=S1 [hello world 42]"
	if got != want {
		t.Errorf("Pool.String() = %q, want %q", got, want)
	}
}

func TestPoolRegistry(t *testing.T) {
	registry := NewPoolRegistry()

	// Define pool
	pool := &Pool{
		ID:   "S1",
		Kind: PoolKindString,
		Entries: []*GValue{
			Str("system prompt"),
			Str("tool:search"),
		},
	}
	registry.Define(pool)

	// Get pool
	got := registry.Get("S1")
	if got == nil {
		t.Fatal("Get should return pool")
	}
	if got.ID != "S1" {
		t.Errorf("Pool ID = %q, want S1", got.ID)
	}

	// Non-existent pool
	if registry.Get("S2") != nil {
		t.Error("Get should return nil for non-existent pool")
	}

	// Resolve reference
	ref := PoolRef{PoolID: "S1", Index: 0}
	resolved := registry.Resolve(ref)
	if resolved == nil || resolved.AsStr() != "system prompt" {
		t.Error("Resolve should return correct value")
	}

	// Resolve non-existent
	badRef := PoolRef{PoolID: "S2", Index: 0}
	if registry.Resolve(badRef) != nil {
		t.Error("Resolve should return nil for non-existent pool")
	}

	// Clear
	registry.Clear("S1")
	if registry.Get("S1") != nil {
		t.Error("Pool should be cleared")
	}
}

func TestParsePool(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		wantID  string
		wantLen int
		wantErr bool
	}{
		{
			name:    "string_pool",
			input:   `@pool.str id=S1 [hello world]`,
			wantID:  "S1",
			wantLen: 2,
		},
		{
			name:    "with_quoted",
			input:   `@pool.str id=S1 ["hello world" simple]`,
			wantID:  "S1",
			wantLen: 2,
		},
		{
			name:    "object_pool",
			input:   `@pool.obj id=O1 [42 t]`,
			wantID:  "O1",
			wantLen: 2,
		},
		{
			name:    "missing_id",
			input:   `@pool.str [hello]`,
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParsePool(tt.input)
			if (err != nil) != tt.wantErr {
				t.Errorf("ParsePool() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err != nil {
				return
			}
			if got.ID != tt.wantID {
				t.Errorf("Pool ID = %q, want %q", got.ID, tt.wantID)
			}
			if len(got.Entries) != tt.wantLen {
				t.Errorf("Entries len = %d, want %d", len(got.Entries), tt.wantLen)
			}
		})
	}
}

func TestPoolRefValue(t *testing.T) {
	v := PoolRefValue("S1", 5)

	if !v.IsPoolRef() {
		t.Error("IsPoolRef should return true")
	}

	ref := v.AsPoolRef()
	if ref.PoolID != "S1" {
		t.Errorf("PoolID = %q, want S1", ref.PoolID)
	}
	if ref.Index != 5 {
		t.Errorf("Index = %d, want 5", ref.Index)
	}
}

func TestAutoInterner(t *testing.T) {
	registry := NewPoolRegistry()
	interner := NewAutoInterner(registry, AutoInternOpts{
		MinLength:   10,
		MinOccurs:   2,
		MaxPoolSize: 100,
	})

	shortString := "short"
	longString := "This is a longer string that should be interned"

	// Short string - never interned
	v1 := interner.Process(shortString)
	v2 := interner.Process(shortString)
	if v1.IsPoolRef() || v2.IsPoolRef() {
		t.Error("Short strings should not be interned")
	}

	// Long string - first occurrence
	v3 := interner.Process(longString)
	if v3.IsPoolRef() {
		t.Error("First occurrence should not be interned")
	}

	// Long string - second occurrence (should intern)
	v4 := interner.Process(longString)
	if !v4.IsPoolRef() {
		t.Error("Second occurrence should be interned")
	}

	// Verify pool was created
	pool := registry.Get("S1")
	if pool == nil {
		t.Error("Pool should be created")
	}

	// Verify reference resolves correctly
	ref := v4.AsPoolRef()
	resolved := registry.Resolve(ref)
	if resolved == nil || resolved.AsStr() != longString {
		t.Error("Reference should resolve to original string")
	}
}

func TestParsePool_EscapedBackslash(t *testing.T) {
	// Test strings with escaped backslashes
	tests := []struct {
		name    string
		input   string
		want    []string
		wantLen int
	}{
		{
			name:    "string_ending_with_backslash",
			input:   `@pool.str id=S1 ["test\\" normal]`,
			want:    []string{`test\`, "normal"},
			wantLen: 2,
		},
		{
			name:    "escaped_quote",
			input:   `@pool.str id=S1 ["say \"hello\"" simple]`,
			want:    []string{`say "hello"`, "simple"},
			wantLen: 2,
		},
		{
			name:    "multiple_escapes",
			input:   `@pool.str id=S1 ["a\\b\\c" "d\"e"]`,
			want:    []string{`a\b\c`, `d"e`},
			wantLen: 2,
		},
		{
			name:    "backslash_then_quote",
			input:   `@pool.str id=S1 ["end\\\\" other]`,
			want:    []string{`end\\`, "other"},
			wantLen: 2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			pool, err := ParsePool(tt.input)
			if err != nil {
				t.Fatalf("ParsePool failed: %v", err)
			}
			if len(pool.Entries) != tt.wantLen {
				t.Fatalf("Expected %d entries, got %d", tt.wantLen, len(pool.Entries))
			}
			for i, want := range tt.want {
				got := pool.Entries[i].AsStr()
				if got != want {
					t.Errorf("Entry %d = %q, want %q", i, got, want)
				}
			}
		})
	}
}
