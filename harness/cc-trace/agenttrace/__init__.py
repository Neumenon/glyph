"""agenttrace — a host-agnostic agent-trace model with pluggable capture adapters.

This is *example/benchmark* material that consumes the GLYPH codec; it is not
part of the codec's product surface (see the repo README). The core model
(`schema`, `replay`, `encode`, `bench`) knows nothing about any particular agent
host. Claude Code is adapter #1, implemented in `normalize`.

The encoders deliberately drive the real in-repo GLYPH implementation under
`py/` rather than reimplementing the format — the whole point is to measure the
actual codec on a real workload. We add `py/` to sys.path on import so the
harness runs from a checkout without installing `glyph-py`.
"""
import pathlib
import sys

# harness/cc-trace/agenttrace/__init__.py -> repo root is parents[3]
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_PY = _REPO_ROOT / "py"
if _PY.is_dir() and str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

from .schema import FIELDS, EVENT_TYPES, PHASES, normalize_keys, validate_event  # noqa: E402
from .normalize import normalize  # noqa: E402
from .encode import FORMATS, encode, decode  # noqa: E402
from .replay import replay  # noqa: E402
from .bench import bench, format_report  # noqa: E402

__all__ = [
    "FIELDS",
    "EVENT_TYPES",
    "PHASES",
    "normalize_keys",
    "validate_event",
    "normalize",
    "FORMATS",
    "encode",
    "decode",
    "replay",
    "bench",
    "format_report",
]
