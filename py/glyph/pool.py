"""
GLYPH Pool References

Pool-based deduplication for strings and objects. Matches Go's
`glyph.Pool`/`glyph.PoolRegistry` semantics. Pool refs use the
`^<PoolID>:<Index>` wire format; pool definitions use
`@pool.str id=S1 [...]` and `@pool.obj id=O1 [...]`.
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .types import GType, GValue, PoolRef


class PoolKind(Enum):
    STRING = "str"
    OBJECT = "obj"


def is_pool_ref_id(ref: str) -> bool:
    """Check if a string is a valid pool ID (uppercase letters + at least one digit)."""
    if len(ref) < 2:
        return False
    if not ("A" <= ref[0] <= "Z"):
        return False
    saw_digit = False
    for c in ref[1:]:
        if c.isdigit():
            saw_digit = True
        elif not ("A" <= c <= "Z"):
            return False
    return saw_digit


class ParsePoolError(ValueError):
    """Raised when pool wire format fails to parse."""


def parse_pool_ref(input: str) -> PoolRef:
    """Parse a pool reference from `^S1:0` format."""
    if not input.startswith("^"):
        raise ParsePoolError("pool ref must start with ^")
    body = input[1:]
    colon = body.find(":")
    if colon < 0:
        raise ParsePoolError("pool ref must contain colon")
    pool_id = body[:colon]
    if not is_pool_ref_id(pool_id):
        raise ParsePoolError(f"invalid pool ID: {pool_id}")
    try:
        index = int(body[colon + 1:])
    except ValueError as e:
        raise ParsePoolError(f"invalid pool index: {body[colon + 1:]}") from e
    return PoolRef(pool_id, index)


class Pool:
    """A single named pool of values."""

    def __init__(self, pool_id: str, kind: PoolKind) -> None:
        self.id = pool_id
        self.kind = kind
        self.entries: List[GValue] = []
        self._lock = threading.RLock()

    def add(self, value: GValue) -> int:
        with self._lock:
            if self.kind == PoolKind.STRING and value.type != GType.STR:
                raise ParsePoolError(
                    f"pool {self.id} is a string pool but got {value.type}"
                )
            self.entries.append(value)
            return len(self.entries) - 1

    def get(self, index: int) -> GValue:
        with self._lock:
            if index < 0 or index >= len(self.entries):
                raise IndexError(
                    f"pool {self.id}[{index}] out of bounds (len={len(self.entries)})"
                )
            return self.entries[index]

    def __len__(self) -> int:
        return len(self.entries)


class PoolRegistry:
    """Thread-safe registry of pools keyed by pool ID."""

    def __init__(self) -> None:
        self._pools: Dict[str, Pool] = {}
        self._lock = threading.RLock()

    def register(self, pool: Pool) -> None:
        with self._lock:
            self._pools[pool.id] = pool

    def get(self, pool_id: str) -> Optional[Pool]:
        with self._lock:
            return self._pools.get(pool_id)

    def resolve(self, ref: PoolRef) -> GValue:
        pool = self.get(ref.pool_id)
        if pool is None:
            raise ParsePoolError(f"pool not found: {ref.pool_id}")
        return pool.get(ref.index)

    def ids(self) -> List[str]:
        with self._lock:
            return sorted(self._pools.keys())


def emit_pool(pool: Pool) -> str:
    """Emit canonical pool-definition wire format."""
    from .loose import canonicalize_loose

    header = f"@pool.{pool.kind.value} id={pool.id}"
    body = " ".join(canonicalize_loose(v) for v in pool.entries)
    return f"{header} [{body}]"


def parse_pool(input: str) -> Pool:
    """Parse a `@pool.str` or `@pool.obj` definition."""
    from .parse import parse  # local import avoids circular dep at module load

    s = input.strip()
    if s.startswith("@pool.str"):
        kind = PoolKind.STRING
        rest = s[len("@pool.str"):].lstrip()
    elif s.startswith("@pool.obj"):
        kind = PoolKind.OBJECT
        rest = s[len("@pool.obj"):].lstrip()
    else:
        raise ParsePoolError("pool must start with @pool.str or @pool.obj")

    if not rest.startswith("id="):
        raise ParsePoolError("pool missing id= field")
    rest = rest[len("id="):]

    i = 0
    while i < len(rest) and not rest[i].isspace() and rest[i] != "[":
        i += 1
    pool_id = rest[:i]
    if not is_pool_ref_id(pool_id):
        raise ParsePoolError(f"invalid pool ID: {pool_id}")

    body = rest[i:].lstrip()
    if not body.startswith("[") or not body.endswith("]"):
        raise ParsePoolError("pool body must be bracketed list")

    list_gv = parse(body)
    if list_gv.type != GType.LIST:
        raise ParsePoolError("pool body did not parse as list")

    pool = Pool(pool_id, kind)
    for entry in list_gv.as_list():
        if kind == PoolKind.STRING and entry.type != GType.STR:
            raise ParsePoolError(
                f"@pool.str {pool_id} entry is not a string: {entry.type}"
            )
        pool.entries.append(entry)
    return pool


def split_document(input: str) -> Tuple[List[str], str]:
    """
    Split a document into @pool.* definition lines and the remaining value.

    Pool definitions appear at the top separated from the value by a blank line
    (or newline). Returns (pool_def_blocks, value_text).
    """
    text = input.lstrip()
    pools: List[str] = []
    while text.startswith("@pool."):
        depth = 0
        i = 0
        n = len(text)
        in_str = False
        esc = False
        while i < n:
            c = text[i]
            if esc:
                esc = False
            elif in_str:
                if c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
            i += 1
        if depth != 0:
            raise ParsePoolError("unbalanced brackets in pool definition")
        pools.append(text[:i])
        text = text[i:].lstrip()
    return pools, text


def parse_document(input: str) -> Tuple[PoolRegistry, GValue]:
    """Parse a document with optional leading @pool.* definitions."""
    from .parse import parse

    registry = PoolRegistry()
    pool_blocks, value_text = split_document(input)
    for block in pool_blocks:
        registry.register(parse_pool(block))
    if not value_text:
        raise ParsePoolError("document has no value")
    return registry, parse(value_text)


def resolve_pool_refs(value: GValue, registry: PoolRegistry) -> GValue:
    """Recursively replace POOL_REF values with their resolved pool entries."""
    t = value.type
    if t == GType.POOL_REF:
        return registry.resolve(value.as_pool_ref()).clone()
    if t == GType.LIST:
        return GValue.list_(*[resolve_pool_refs(v, registry) for v in value.as_list()])
    if t == GType.MAP:
        from .types import MapEntry
        return GValue.map_(
            *[MapEntry(e.key, resolve_pool_refs(e.value, registry)) for e in value.as_map()]
        )
    if t == GType.STRUCT:
        from .types import MapEntry
        sv = value.as_struct()
        return GValue.struct(
            sv.type_name,
            *[MapEntry(f.key, resolve_pool_refs(f.value, registry)) for f in sv.fields],
        )
    if t == GType.SUM:
        sm = value.as_sum()
        inner = resolve_pool_refs(sm.value, registry) if sm.value is not None else None
        return GValue.sum(sm.tag, inner)
    return value.clone()
