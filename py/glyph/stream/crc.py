"""
CRC-32 IEEE for GS1.

Algorithm: CRC-32 IEEE (polynomial 0xEDB88320, reflected/LSB-first).
This is the standard Ethernet/zlib CRC-32, identical to Go's hash/crc32.IEEE
and the JS lookup-table implementation in js/src/stream/crc.ts.

Wire-format identity: compute_crc(b) must return the same uint32 as
Go's crc32.Checksum(b, crc32.MakeTable(crc32.IEEE)).

Test vectors (from go/stream/gs1t_test.go TestCRC_KnownValues):
  b""      -> 0x00000000
  b"a"     -> 0xe8b7be43
  b"abc"   -> 0x352441c2
  b"hello" -> 0x3610a686
"""

from __future__ import annotations

import struct

# ---------------------------------------------------------------------------
# CRC-32 IEEE lookup table — polynomial 0xEDB88320 (reflected)
# Matches Go crc32.MakeTable(crc32.IEEE) and js/src/stream/crc.ts.
# ---------------------------------------------------------------------------

_POLY = 0xEDB88320
_TABLE: list[int] = []

for _i in range(256):
    _crc = _i
    for _j in range(8):
        if _crc & 1:
            _crc = (_crc >> 1) ^ _POLY
        else:
            _crc >>= 1
    _TABLE.append(_crc & 0xFFFFFFFF)

del _i, _j, _crc


def compute_crc(data: bytes) -> int:
    """Compute CRC-32 IEEE of *data*. Returns a 32-bit unsigned integer."""
    crc = 0xFFFFFFFF
    for byte in data:
        crc = _TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF


def verify_crc(data: bytes, expected: int) -> bool:
    """Return True iff compute_crc(data) == expected."""
    return compute_crc(data) == (expected & 0xFFFFFFFF)


def crc_to_hex(crc: int) -> str:
    """Convert a CRC-32 value to an 8-character lowercase hex string."""
    return f"{crc & 0xFFFFFFFF:08x}"


def parse_crc(s: str) -> int | None:
    """Parse CRC from hex string (optionally prefixed with ``crc32:``)."""
    if s.startswith("crc32:"):
        s = s[6:]
    if len(s) != 8:
        return None
    try:
        return int(s, 16) & 0xFFFFFFFF
    except ValueError:
        return None
