package glyph

import (
	"testing"
)

func TestParseDocument_SimpleMap(t *testing.T) {
	input := `{a=1 b=2}`
	gv, err := ParseDocument(input)
	if err != nil {
		t.Fatalf("ParseDocument: %v", err)
	}
	if gv.Type() != TypeMap {
		t.Fatalf("expected map, got %v", gv.Type())
	}
}

func TestParseDocument_TopLevelTab(t *testing.T) {
	input := `@tab _ [id name]
|1|alice|
|2|bob|
@end`
	gv, err := ParseDocument(input)
	if err != nil {
		t.Fatalf("ParseDocument: %v", err)
	}
	if gv.Type() != TypeList {
		t.Fatalf("expected list, got %v", gv.Type())
	}
	items, _ := gv.AsList()
	if len(items) != 2 {
		t.Fatalf("expected 2 items, got %d", len(items))
	}
}

func TestParseDocument_Schema(t *testing.T) {
	input := `@schema#test @keys=[name age]
{#0=Alice #1=30}`
	gv, err := ParseDocument(input)
	if err != nil {
		t.Fatalf("ParseDocument: %v", err)
	}
	if gv.Type() != TypeMap {
		t.Fatalf("expected map, got %v", gv.Type())
	}
}

func TestParseDocument_NoValue(t *testing.T) {
	_, err := ParseDocument("")
	if err == nil {
		t.Fatal("expected error for empty input")
	}
}
