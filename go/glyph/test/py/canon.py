#!/usr/bin/env python3
"""
GLYPH Cross-Implementation Canonicalization Script (Python)

Called by Go tests to verify that Go and Python implementations produce
identical output for the same input.

Usage:
  python3 canon.py <command> [args...]

Commands:
  canonicalize-loose <json-string>
    Parse JSON and emit canonical loose form

  canonicalize-loose-llm <json-string>
    Same but with LLM mode options (uses _ for null)

  build-key-dict <json-string>
    Build key dictionary from a JSON value

  parse-patch <patch-string>
    Parse a @patch block and return summary as JSON

Output: JSON with { success: bool, result?: string, error?: string }
"""

import json
import sys
import os

# Add the py/ directory to sys.path so we can import glyph without installation.
# This file lives at go/glyph/test/py/canon.py; py/ is four levels up.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PY_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "..", "py"))
if _PY_ROOT not in sys.path:
    sys.path.insert(0, _PY_ROOT)

try:
    from glyph.loose import (
        from_json_loose,
        canonicalize_loose,
        llm_loose_canon_opts,
    )
    from glyph.patch import parse_patch
except Exception as e:
    print(json.dumps({"success": False, "error": f"import error: {e}"}))
    sys.exit(1)

try:
    from glyph.loose import canonicalize_loose_with_opts
    _HAS_WITH_OPTS = True
except ImportError:
    _HAS_WITH_OPTS = False


def cmd_canonicalize_loose(json_str: str) -> dict:
    try:
        data = json.loads(json_str)
        gv = from_json_loose(data)
        result = canonicalize_loose(gv)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cmd_canonicalize_loose_llm(json_str: str) -> dict:
    try:
        data = json.loads(json_str)
        gv = from_json_loose(data)
        if _HAS_WITH_OPTS:
            opts = llm_loose_canon_opts()
            result = canonicalize_loose_with_opts(gv, opts)
        else:
            # Fallback: use default canonicalize_loose (uses _ for null by default)
            result = canonicalize_loose(gv)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cmd_build_key_dict(json_str: str) -> dict:
    """Build key dictionary from a JSON value.

    Returns a sorted JSON array of unique keys found in the value.
    """
    try:
        from glyph.loose import from_json_loose
        from glyph.types import GType

        data = json.loads(json_str)
        gv = from_json_loose(data)

        keys: set = set()

        def collect_keys(v):
            if v is None:
                return
            t = v.type
            if t == GType.MAP:
                for entry in v.map_val:
                    keys.add(entry.key)
                    collect_keys(entry.value)
            elif t == GType.STRUCT:
                for entry in v.struct_val.fields:
                    keys.add(entry.key)
                    collect_keys(entry.value)
            elif t == GType.LIST:
                for item in v.list_val:
                    collect_keys(item)

        collect_keys(gv)
        sorted_keys = sorted(keys)
        return {"success": True, "result": json.dumps(sorted_keys)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def cmd_parse_patch(patch_str: str) -> dict:
    try:
        patch = parse_patch(patch_str)
        result = {
            "schemaId": patch.schema_id,
            "baseFingerprint": patch.base_fingerprint,
            "opsCount": len(patch.ops),
        }
        return {"success": True, "result": json.dumps(result)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    args = sys.argv[1:]
    if not args:
        print(json.dumps({"success": False, "error": "no command given"}))
        sys.exit(1)

    command = args[0]
    rest = args[1:]

    if command == "canonicalize-loose":
        if not rest:
            print(json.dumps({"success": False, "error": "missing json argument"}))
            sys.exit(1)
        result = cmd_canonicalize_loose(rest[0])

    elif command == "canonicalize-loose-llm":
        if not rest:
            print(json.dumps({"success": False, "error": "missing json argument"}))
            sys.exit(1)
        result = cmd_canonicalize_loose_llm(rest[0])

    elif command == "build-key-dict":
        if not rest:
            print(json.dumps({"success": False, "error": "missing json argument"}))
            sys.exit(1)
        result = cmd_build_key_dict(rest[0])

    elif command == "parse-patch":
        if not rest:
            print(json.dumps({"success": False, "error": "missing patch argument"}))
            sys.exit(1)
        result = cmd_parse_patch(rest[0])

    else:
        result = {
            "success": False,
            "error": f"unknown command: {command}. Use: canonicalize-loose, canonicalize-loose-llm, build-key-dict, parse-patch",
        }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
