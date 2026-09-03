package main

import (
	"fmt"

	glyph "github.com/Neumenon/glyph/go/glyph"
)

func main() {
	base := []byte(`{"x":{"a":1,"b":2}}`)
	tgt := []byte(`{"x":{"a":1}}`)
	bv, _ := glyph.FromJSONLoose(base)
	tv, _ := glyph.FromJSONLoose(tgt)
	p, err := glyph.Diff(bv, tv, "")
	if err != nil {
		panic(err)
	}
	fmt.Println("go patch ops:", len(p.Ops))
	if _, err := glyph.ApplyPatch(bv, p); err != nil {
		fmt.Println("GO FAIL:", err)
	} else {
		fmt.Println("GO OK")
	}
}
