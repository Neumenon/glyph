package glyph

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
)

// TensorDTypeBits maps SPEC-CANON.md §4 dtype names (cowrie SPEC-v1 §2.5) to
// bits per element.
var TensorDTypeBits = map[string]int{
	"float32": 32, "float16": 16, "bfloat16": 16, "int8": 8, "int16": 16, "int32": 32,
	"int64": 64, "uint8": 8, "uint16": 16, "uint32": 32, "uint64": 64, "float64": 64,
	"bool": 8, "qint4": 4, "qint2": 2, "qint3": 3, "ternary": 2, "binary": 1,
}

var errTensorPayload = errors.New("$tensor payload must be {dtype, shape, sha256}: known dtype, non-negative int shape, 64 lowercase hex")

// TensorRef builds {"$tensor":{dtype,shape,sha256}} for raw element bytes
// (SPEC-CANON.md §4). Only sha256(data) enters the value. Errors for an
// unknown dtype, a negative dim, or data that is not the packed size dtype and
// shape imply (little-endian, row-major, sub-byte dtypes LSB-first).
func TensorRef(dtype string, shape []int, data []byte) (*GValue, error) {
	bits, ok := TensorDTypeBits[dtype]
	if !ok {
		return nil, fmt.Errorf("unknown tensor dtype %q", dtype)
	}
	n := int64(1)
	dims := make([]int64, len(shape))
	for i, d := range shape {
		if d < 0 {
			return nil, fmt.Errorf("tensor shape has negative dim %d", d)
		}
		n *= int64(d)
		dims[i] = int64(d)
	}
	if want := (n*int64(bits) + 7) / 8; int64(len(data)) != want {
		return nil, fmt.Errorf("tensor data is %d bytes; dtype %s shape %v packs to %d", len(data), dtype, shape, want)
	}
	// Sub-byte dtypes (qint4/qint2/qint3/ternary/binary) rarely fill the last
	// byte: the unused high bits are padding and must be zero, otherwise two
	// different byte strings would name two different tensors for the same
	// elements.
	if pad := (8 - (n*int64(bits))%8) % 8; pad > 0 && len(data) > 0 {
		if last := data[len(data)-1]; last>>uint(8-pad) != 0 {
			return nil, fmt.Errorf("tensor data has non-zero padding bits for dtype %s shape %v", dtype, shape)
		}
	}
	sum := sha256.Sum256(data)
	return tensorRefValue(dtype, dims, hex.EncodeToString(sum[:])), nil
}

func tensorRefValue(dtype string, shape []int64, sha string) *GValue {
	dims := make([]*GValue, len(shape))
	for i, d := range shape {
		dims[i] = Int(d)
	}
	return Map(MapEntry{Key: "$tensor", Value: Map(
		MapEntry{Key: "dtype", Value: Str(dtype)},
		MapEntry{Key: "shape", Value: List(dims...)},
		MapEntry{Key: "sha256", Value: Str(sha)},
	)})
}

// fromTensorPayload validates a decoded {"$tensor":…} payload. There is no
// tensor GType and the digest is the same either way; validation is what
// stops an uppercase or truncated sha256 from minting a second identity for
// the same bytes.
func fromTensorPayload(v interface{}, depth int) (*GValue, error) {
	if depth > bridgeMaxDepth {
		return nil, errTensorPayload
	}
	obj, ok := v.(map[string]interface{})
	if !ok || len(obj) != 3 {
		return nil, errTensorPayload
	}
	dtype, _ := obj["dtype"].(string)
	sha, _ := obj["sha256"].(string)
	rawShape, _ := obj["shape"].([]interface{})
	if _, known := TensorDTypeBits[dtype]; !known || rawShape == nil || !isLowerHex64(sha) {
		return nil, errTensorPayload
	}
	shape := make([]int64, len(rawShape))
	for i, x := range rawShape {
		d, ok := tensorDim(x)
		if !ok {
			return nil, errTensorPayload
		}
		shape[i] = d
	}
	return tensorRefValue(dtype, shape, sha), nil
}

func tensorDim(x interface{}) (int64, bool) {
	switch n := x.(type) {
	case json.Number:
		// Strict integer syntax only ("1", not "1.0" or "1e3"), capped at
		// ±(2^53-1) so the dim stays inside the canonical int range.
		i, err := strconv.ParseInt(string(n), 10, 64)
		return i, err == nil && i >= 0 && i <= canonMaxSafeInt
	case float64:
		// Never an integer: a float64 has lost the literal spelling, so
		// "1" and "1.0" are indistinguishable here and both are rejected.
		// Integer dims arrive as json.Number via FromJSONLoose (UseNumber).
		return 0, false
	}
	return 0, false
}

func isLowerHex64(s string) bool {
	if len(s) != 64 {
		return false
	}
	for i := 0; i < len(s); i++ {
		c := s[i]
		if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f') {
			return false
		}
	}
	return true
}
