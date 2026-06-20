package glyph

import "fmt"

// SchemaError is a single lint finding produced by Schema.Check().
type SchemaError struct {
	TypeName  string // Type where the error occurred
	FieldName string // Field where the error occurred (empty for type-level errors)
	Code      string // Machine-readable code (e.g. "duplicate_field_name")
	Message   string // Human-readable message
}

func (e SchemaError) Error() string {
	if e.FieldName != "" {
		return fmt.Sprintf("%s.%s: [%s] %s", e.TypeName, e.FieldName, e.Code, e.Message)
	}
	return fmt.Sprintf("%s: [%s] %s", e.TypeName, e.Code, e.Message)
}

// Check validates schema consistency and returns a slice of SchemaError.
// A nil (or empty) return means the schema is valid.
//
// Rules checked:
//  1. Each map key equals its TypeDef.Name (internal consistency).
//  2. No duplicate field names per struct.
//  3. No duplicate wire keys per struct; wire keys must not collide with any field name.
//  4. No duplicate positive FIDs for pack-enabled structs.
//  5. Every field in a pack-enabled struct must have FID > 0.
//  6. Every FieldDef.FID must be >= 1 if set (no zero or negative FID).
//  7. Constraint kinds must match the field type (constraint_type_mismatch).
//  8. Map key types must be str, int, or id (unsupported_map_key_type).
//  9. If a required field has a Default value, emit a warning-level code
//     required_field_has_default (flagged fork: warn, not error).
func (s *Schema) Check() []SchemaError {
	var errs []SchemaError

	for mapKey, td := range s.Types {
		// Rule 1: map key must equal TypeDef.Name
		if td.Name != mapKey {
			errs = append(errs, SchemaError{
				TypeName: mapKey,
				Code:     "name_key_mismatch",
				Message:  fmt.Sprintf("type map key %q does not match TypeDef.Name %q", mapKey, td.Name),
			})
		}

		if td.Kind != TypeDefStruct || td.Struct == nil {
			continue
		}

		// Rule 2: no duplicate field names
		fieldNameSeen := make(map[string]bool)
		for _, fd := range td.Struct.Fields {
			if fieldNameSeen[fd.Name] {
				errs = append(errs, SchemaError{
					TypeName:  td.Name,
					FieldName: fd.Name,
					Code:      "duplicate_field_name",
					Message:   fmt.Sprintf("duplicate field name %q in struct %s", fd.Name, td.Name),
				})
			}
			fieldNameSeen[fd.Name] = true
		}

		// Rule 3: no duplicate wire keys, and wire keys must not collide with any field name
		wireKeySeen := make(map[string]bool)
		for _, fd := range td.Struct.Fields {
			if fd.WireKey == "" {
				continue
			}
			// Collides with a field name?
			if fieldNameSeen[fd.WireKey] && fd.WireKey != fd.Name {
				errs = append(errs, SchemaError{
					TypeName:  td.Name,
					FieldName: fd.Name,
					Code:      "duplicate_wire_key",
					Message:   fmt.Sprintf("wire key %q in field %q collides with another field name in struct %s", fd.WireKey, fd.Name, td.Name),
				})
			}
			if wireKeySeen[fd.WireKey] {
				errs = append(errs, SchemaError{
					TypeName:  td.Name,
					FieldName: fd.Name,
					Code:      "duplicate_wire_key",
					Message:   fmt.Sprintf("duplicate wire key %q in struct %s", fd.WireKey, td.Name),
				})
			}
			wireKeySeen[fd.WireKey] = true
		}

		// Rules 4, 5, 6: FID validity
		fidSeen := make(map[int]string) // fid -> first field name
		for _, fd := range td.Struct.Fields {
			// Rule 6: FID must be >= 1 if set (no zero stored means "unset"; only check if explicitly > 0 from user perspective — but FID=0 means unassigned, so only flag negative)
			if fd.FID < 0 {
				errs = append(errs, SchemaError{
					TypeName:  td.Name,
					FieldName: fd.Name,
					Code:      "invalid_fid",
					Message:   fmt.Sprintf("field %q in struct %s has invalid FID %d (must be >= 1 if set)", fd.Name, td.Name, fd.FID),
				})
			}

			if td.PackEnabled {
				// Rule 5: every field must have FID > 0
				if fd.FID <= 0 {
					errs = append(errs, SchemaError{
						TypeName:  td.Name,
						FieldName: fd.Name,
						Code:      "missing_fid_in_packed_struct",
						Message:   fmt.Sprintf("field %q in packed struct %s has no FID assigned", fd.Name, td.Name),
					})
				} else {
					// Rule 4: no duplicate FIDs
					if first, dup := fidSeen[fd.FID]; dup {
						errs = append(errs, SchemaError{
							TypeName:  td.Name,
							FieldName: fd.Name,
							Code:      "duplicate_fid",
							Message:   fmt.Sprintf("duplicate FID %d in packed struct %s (fields %q and %q)", fd.FID, td.Name, first, fd.Name),
						})
					} else {
						fidSeen[fd.FID] = fd.Name
					}
				}
			}
		}

		// Rules 7, 8, 9: constraint and field type checks
		for _, fd := range td.Struct.Fields {
			// Flagged fork: required field with default (warn, not error)
			if !fd.Optional && fd.Default != nil {
				errs = append(errs, SchemaError{
					TypeName:  td.Name,
					FieldName: fd.Name,
					Code:      "required_field_has_default",
					Message:   fmt.Sprintf("required field %q in struct %s has a default value (ambiguous intent; consider making optional)", fd.Name, td.Name),
				})
			}

			// Rule 8: map key type must be str, int, or id
			checkMapKeyType(td.Name, fd.Name, fd.Type, &errs)

			// Rule 7: constraint kind must match field type
			for _, c := range fd.Constraints {
				if c.Kind == ConstraintOptional {
					// consumed into FieldDef.Optional; not a value constraint
					continue
				}
				if err := checkConstraintType(td.Name, fd.Name, c, fd.Type); err != nil {
					errs = append(errs, *err)
				}
			}
		}
	}

	return errs
}

// checkMapKeyType recursively checks that any map in the TypeSpec has a valid key type.
func checkMapKeyType(typeName, fieldName string, ts TypeSpec, errs *[]SchemaError) {
	switch ts.Kind {
	case TypeSpecMap:
		if ts.KeyType != nil {
			k := ts.KeyType.Kind
			if k != TypeSpecStr && k != TypeSpecInt && k != TypeSpecID {
				*errs = append(*errs, SchemaError{
					TypeName:  typeName,
					FieldName: fieldName,
					Code:      "unsupported_map_key_type",
					Message:   fmt.Sprintf("field %q in %s: map key type %s is not supported (must be str, int, or id)", fieldName, typeName, ts.KeyType.String()),
				})
			}
		}
		if ts.ValType != nil {
			checkMapKeyType(typeName, fieldName, *ts.ValType, errs)
		}
	case TypeSpecList:
		if ts.Elem != nil {
			checkMapKeyType(typeName, fieldName, *ts.Elem, errs)
		}
	}
}

// checkConstraintType verifies that a constraint kind is valid for the field type.
func checkConstraintType(typeName, fieldName string, c Constraint, ts TypeSpec) *SchemaError {
	kind := ts.Kind

	switch c.Kind {
	case ConstraintMin, ConstraintMax, ConstraintRange:
		if kind != TypeSpecInt && kind != TypeSpecFloat {
			return &SchemaError{
				TypeName:  typeName,
				FieldName: fieldName,
				Code:      "constraint_type_mismatch",
				Message:   fmt.Sprintf("constraint %s requires int or float field, got %s", c.Kind.constraintName(), ts.String()),
			}
		}
	case ConstraintMinLen, ConstraintMaxLen, ConstraintLen, ConstraintNonEmpty:
		if kind != TypeSpecStr && kind != TypeSpecBytes && kind != TypeSpecList {
			return &SchemaError{
				TypeName:  typeName,
				FieldName: fieldName,
				Code:      "constraint_type_mismatch",
				Message:   fmt.Sprintf("constraint %s requires str, bytes, or list field, got %s", c.Kind.constraintName(), ts.String()),
			}
		}
	case ConstraintRegex:
		if kind != TypeSpecStr {
			return &SchemaError{
				TypeName:  typeName,
				FieldName: fieldName,
				Code:      "constraint_type_mismatch",
				Message:   fmt.Sprintf("constraint regex requires str field, got %s", ts.String()),
			}
		}
	case ConstraintEnum:
		if kind != TypeSpecStr {
			return &SchemaError{
				TypeName:  typeName,
				FieldName: fieldName,
				Code:      "constraint_type_mismatch",
				Message:   fmt.Sprintf("constraint enum requires str field, got %s", ts.String()),
			}
		}
	case ConstraintUnique:
		if kind != TypeSpecList {
			return &SchemaError{
				TypeName:  typeName,
				FieldName: fieldName,
				Code:      "constraint_type_mismatch",
				Message:   fmt.Sprintf("constraint unique requires list field, got %s", ts.String()),
			}
		}
	}
	return nil
}

// constraintName returns a human-readable name for the constraint kind.
func (k ConstraintKind) constraintName() string {
	switch k {
	case ConstraintMin:
		return "min"
	case ConstraintMax:
		return "max"
	case ConstraintRange:
		return "range"
	case ConstraintMinLen:
		return "minlen"
	case ConstraintMaxLen:
		return "maxlen"
	case ConstraintLen:
		return "len"
	case ConstraintNonEmpty:
		return "nonempty"
	case ConstraintRegex:
		return "regex"
	case ConstraintEnum:
		return "enum"
	case ConstraintUnique:
		return "unique"
	case ConstraintOptional:
		return "optional"
	default:
		return "unknown"
	}
}
