package glyph

import (
	"fmt"
	"strings"
)

// ParseDocument parses a GLYPH document that may contain @schema directives
// and @tab blocks (top-level or embedded). It composes the lower-level
// Parse* and Tabular APIs into a single high-level entry point.
//
// Supported input formats:
//
//	@tab _ [col1 col2]
//	|v1|v2|
//	@end
//
//	{messages=@tab _ [content role]\n|hello|user|\n system="prompt"}
//
//	@schema#abc @keys=[k1 k2]\n{#0=v1 #1=v2}
func ParseDocument(input string) (*GValue, error) {
	return ParseDocumentWithRegistries(input, NewSchemaRegistry())
}

// ParseDocumentWithRegistries parses a GLYPH document using the given
// schema registry.
func ParseDocumentWithRegistries(input string, schemaReg *SchemaRegistry) (*GValue, error) {
	lines := strings.Split(input, "\n")

	var valueLines []string
	for _, line := range lines {
		if strings.TrimSpace(line) == "" {
			continue
		}
		valueLines = append(valueLines, line)
	}

	if len(valueLines) == 0 {
		return nil, fmt.Errorf("no value found in input")
	}

	valueStr := strings.Join(valueLines, "\n")
	trimmedValue := strings.TrimSpace(valueStr)

	switch {
	case strings.HasPrefix(trimmedValue, "@tab _"):
		gv, err := ParseTabularLoose(valueStr)
		if err != nil {
			return nil, fmt.Errorf("parse tabular: %w", err)
		}
		return gv, nil

	case strings.Contains(valueStr, "=@tab _"):
		gv, err := parseMapWithEmbeddedTab(valueStr)
		if err != nil {
			return nil, fmt.Errorf("parse embedded tab: %w", err)
		}
		return gv, nil

	default:
		gv, _, err := ParseLoosePayload(valueStr, schemaReg)
		if err != nil {
			return nil, fmt.Errorf("parse value: %w", err)
		}
		return gv, nil
	}
}

// parseMapWithEmbeddedTab parses a map that contains embedded @tab blocks.
// Example: {messages=@tab _ [content role]\n|hello|user|\n system="value"}
func parseMapWithEmbeddedTab(input string) (*GValue, error) {
	input = strings.TrimSpace(input)

	if !strings.HasPrefix(input, "{") {
		return nil, fmt.Errorf("expected { at start of map")
	}

	input = input[1:]

	if !strings.HasSuffix(strings.TrimSpace(input), "}") {
		return nil, fmt.Errorf("expected } at end of map")
	}
	input = strings.TrimSpace(input)
	input = input[:len(input)-1]

	var entries []MapEntry
	remaining := input

	for len(remaining) > 0 {
		remaining = strings.TrimSpace(remaining)
		if remaining == "" {
			break
		}

		eqIdx := strings.Index(remaining, "=")
		if eqIdx < 0 {
			break
		}

		key := strings.TrimSpace(remaining[:eqIdx])
		remaining = remaining[eqIdx+1:]

		if strings.HasPrefix(strings.TrimSpace(remaining), "@tab _") {
			tabStart := strings.Index(remaining, "@tab _")
			tabContent := remaining[tabStart:]

			var tabEnd int
			if endIdx := strings.Index(tabContent, "@end"); endIdx >= 0 {
				tabEnd = endIdx + 4
			} else {
				lines := strings.Split(tabContent, "\n")
				foundEnd := false
				for i, line := range lines {
					trimmed := strings.TrimLeft(line, " \t")
					if i > 0 && !strings.HasPrefix(trimmed, "|") && strings.Contains(trimmed, "=") {
						tabEnd = strings.Index(tabContent, "\n"+line)
						if tabEnd < 0 {
							tabEnd = len(tabContent)
						}
						foundEnd = true
						break
					}
				}
				if !foundEnd {
					tabEnd = len(tabContent)
				}
			}

			tabBlock := strings.TrimSpace(tabContent[:tabEnd])
			remaining = strings.TrimSpace(tabContent[tabEnd:])

			tabValue, err := ParseTabularLoose(tabBlock)
			if err != nil {
				return nil, fmt.Errorf("parse @tab for key %s: %w", key, err)
			}

			entries = append(entries, MapEntry{Key: key, Value: tabValue})
		} else {
			var valueEnd int
			found := false

			for i := 0; i < len(remaining); i++ {
				if remaining[i] == ' ' || remaining[i] == '\n' {
					rest := strings.TrimLeft(remaining[i:], " \t\n")
					if len(rest) > 0 && isDocKeyStart(rest) {
						valueEnd = i
						found = true
						break
					}
				}
			}
			if !found {
				valueEnd = len(remaining)
			}

			valueStr := strings.TrimSpace(remaining[:valueEnd])
			remaining = strings.TrimSpace(remaining[valueEnd:])

			val, _, err := ParseLoosePayload(valueStr, nil)
			if err != nil {
				val = Str(valueStr)
			}

			entries = append(entries, MapEntry{Key: key, Value: val})
		}
	}

	return Map(entries...), nil
}

// isDocKeyStart checks if a string looks like it starts with "key=".
func isDocKeyStart(s string) bool {
	for i, c := range s {
		if c == '=' {
			return i > 0
		}
		if !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_') {
			if c == '"' && i == 0 {
				continue
			}
			return false
		}
	}
	return false
}
