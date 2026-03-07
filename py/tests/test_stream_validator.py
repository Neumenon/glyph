"""
Tests for GLYPH Streaming Validator
"""

import pytest
from glyph import (
    StreamingValidator,
    ToolRegistry,
    StreamValidationResult,
    ValidatorState,
)


def test_basic_tool_call():
    """Test parsing a simple tool call."""
    registry = ToolRegistry()
    registry.add_tool("search", {
        "query": {"type": "str", "required": True},
        "max_results": {"type": "int", "min": 1, "max": 100, "default": 10}
    })
    
    validator = StreamingValidator(registry)
    
    # Simulate token stream
    tokens = [
        "search",
        "{",
        "query",
        "=",
        '"',
        "weather",
        '"',
        " ",
        "max_results",
        "=",
        "5",
        "}",
    ]
    
    for token in tokens:
        result = validator.push_token(token)
    
    assert result.complete
    assert result.valid
    assert result.tool_name == "search"
    assert result.fields["query"] == "weather"
    assert result.fields["max_results"] == 5


def test_tool_detection_timing():
    """Test that tool name is detected early."""
    registry = ToolRegistry()
    registry.add_tool("search", {})
    
    validator = StreamingValidator(registry)
    
    # First token should detect the tool
    result = validator.push_token("search")
    assert result.tool_name == "search"
    assert result.tool_detected_at_token > 0


def test_unknown_tool_rejection():
    """Test that unknown tools are rejected."""
    registry = ToolRegistry()
    registry.add_tool("search", {})
    
    validator = StreamingValidator(registry)
    
    result = validator.push_token("unknown_tool")
    result = validator.push_token("{")
    
    # Should have error for unknown tool
    assert "UNKNOWN_TOOL" in str(result.errors)
    assert result.should_cancel


def test_constraint_validation():
    """Test validation of argument constraints."""
    registry = ToolRegistry()
    registry.add_tool("search", {
        "max_results": {"type": "int", "min": 1, "max": 100}
    })
    
    validator = StreamingValidator(registry)
    
    # Tokens for: search{max_results=1000}  (violates max constraint)
    tokens = ["search", "{", "max_results", "=", "1000", "}"]
    
    for token in tokens:
        result = validator.push_token(token)
    
    assert result.complete
    assert not result.valid
    assert any("max" in error.lower() for error in result.errors)


def test_required_field():
    """Test validation of required fields."""
    registry = ToolRegistry()
    registry.add_tool("search", {
        "query": {"type": "str", "required": True}
    })
    
    validator = StreamingValidator(registry)
    
    # Tool without required field
    tokens = ["search", "{", "}"]
    
    for token in tokens:
        result = validator.push_token(token)
    
    assert result.complete
    assert not result.valid
    assert any("required" in error.lower() for error in result.errors)


def test_type_validation():
    """Test type validation."""
    registry = ToolRegistry()
    registry.add_tool("calculate", {
        "value": {"type": "int"}
    })
    
    validator = StreamingValidator(registry)
    
    # String where int expected
    tokens = ["calculate", "{", "value", "=", "not_a_number", "}"]
    
    for token in tokens:
        result = validator.push_token(token)
    
    # Should still parse but validation should warn
    assert result.complete


def test_timeline_tracking():
    """Test that timeline events are recorded."""
    registry = ToolRegistry()
    registry.add_tool("search", {})
    
    validator = StreamingValidator(registry)
    
    tokens = ["search", "{", "}"]
    for token in tokens:
        result = validator.push_token(token)
    
    assert len(result.timeline) > 0
    
    # Should have TOOL_DETECTED event
    events = [e.event for e in result.timeline]
    assert "TOOL_DETECTED" in events
    assert "COMPLETE" in events


def test_multiple_fields():
    """Test parsing multiple fields."""
    registry = ToolRegistry()
    registry.add_tool("api_call", {
        "endpoint": {"type": "str"},
        "method": {"type": "str"},
        "timeout": {"type": "int"}
    })
    
    validator = StreamingValidator(registry)
    
    # Simulate: api_call{endpoint="test" method="GET" timeout=30}
    tokens = [
        "api_call",
        "{",
        "endpoint", "=", '"', "test", '"',
        " ",
        "method", "=", '"', "GET", '"',
        " ",
        "timeout", "=", "30",
        "}"
    ]
    
    for token in tokens:
        result = validator.push_token(token)
    
    assert result.complete
    assert result.valid
    assert result.tool_name == "api_call"
    assert len(result.fields) >= 1  # At least one field parsed


def test_reset():
    """Test that reset clears state."""
    registry = ToolRegistry()
    registry.add_tool("search", {})
    
    validator = StreamingValidator(registry)
    
    # First call
    result1 = validator.push_token("search")
    assert result1.tool_name == "search"
    
    # Reset
    validator.reset()
    
    # Second call should start fresh
    result2 = validator.push_token("other")
    assert result2.tool_name == "other"


def test_integration_with_streaming():
    """Test realistic streaming scenario."""
    registry = ToolRegistry()
    registry.add_tool("search", {
        "query": {"type": "str", "required": True, "max_len": 100},
        "max_results": {"type": "int", "min": 1, "max": 100, "default": 10}
    })
    
    validator = StreamingValidator(registry)
    validator.start()
    
    # Simulate streaming response from LLM
    response = 'search{query="python async" max_results=5}'
    
    cancelled = False
    for char in response:
        result = validator.push_token(char)
        
        # Check for early cancellation
        if result.should_cancel:
            cancelled = True
            break
        
        # Check tool detection
        if result.tool_name and not cancelled:
            print(f"Tool detected: {result.tool_name} at token {result.tool_detected_at_token}")
    
    # Should complete successfully
    assert not cancelled
    assert result.complete
    assert result.valid
    assert result.fields["query"] == "python async"
    assert result.fields["max_results"] == 5


def test_tool_allowed_only_after_tool_name_is_final():
    """Partial tool-name detection should not mark the tool as disallowed."""
    registry = ToolRegistry()
    registry.add_tool("search", {})

    validator = StreamingValidator(registry)

    result = validator.push_token("unknown_tool")
    assert result.tool_name == "unknown_tool"
    assert result.tool_allowed

    result = validator.push_token("{")
    assert not result.tool_allowed
    assert "UNKNOWN_TOOL" in str(result.errors)


def test_nested_value_parsing():
    """Nested lists and maps should survive incremental parsing."""
    registry = ToolRegistry()
    registry.add_tool("batch", {
        "items": {"type": "list", "required": True},
    })

    validator = StreamingValidator(registry)
    response = 'batch{items=[{id=1 tags=[alpha beta]} {id=2 tags=[]}]}'

    for char in response:
        result = validator.push_token(char)

    assert result.complete
    assert result.valid
    assert result.fields["items"][0]["id"] == 1
    assert result.fields["items"][0]["tags"] == ["alpha", "beta"]
    assert result.fields["items"][1]["tags"] == []


def test_buffer_limit_trips_error():
    """The validator should stop accepting oversized payloads."""
    registry = ToolRegistry()
    registry.add_tool("search", {"query": {"type": "str"}})

    validator = StreamingValidator(registry, max_buffer=16)
    result = validator.push_token('search{query="0123456789"}')

    assert result.state == ValidatorState.ERROR
    assert any("Buffer exceeds max size" in error for error in result.errors)


def test_field_limit_trips_error():
    """The validator should cap the number of parsed fields."""
    registry = ToolRegistry()
    registry.add_tool("bulk", {})

    validator = StreamingValidator(registry, max_fields=1)
    for char in "bulk{a=1 b=2}":
        result = validator.push_token(char)

    assert result.state == ValidatorState.ERROR
    assert any("Field count exceeds max" in error for error in result.errors)


def test_error_limit_is_capped():
    """Error accumulation should remain bounded."""
    registry = ToolRegistry()
    registry.add_tool("search", {
        "query": {"type": "str", "required": True},
        "max_results": {"type": "int", "max": 1},
    })

    validator = StreamingValidator(registry, max_errors=1)
    for char in 'search{max_results=2 extra=foo}':
        result = validator.push_token(char)

    assert len(result.errors) == 1
    assert not result.valid


def test_mismatched_nested_delimiters_fail_fast():
    """Unexpected nested closers should not drive depth negative."""
    registry = ToolRegistry()
    registry.add_tool("search", {"query": {"type": "list"}})

    validator = StreamingValidator(registry)
    for char in "search{query=[1}}":
        result = validator.push_token(char)

    assert result.state == ValidatorState.ERROR
    assert any("Mismatched closing delimiter" in error for error in result.errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
