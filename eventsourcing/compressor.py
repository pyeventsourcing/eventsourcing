from __future__ import annotations

import zlib
from typing import override

from eventsourcing.persistence import Compressor


class ZlibCompressor(Compressor):
    @override
    def compress(self, data: bytes) -> bytes:
        """Compress bytes using zlib."""
        return zlib.compress(data)

    @override
    def decompress(self, data: bytes) -> bytes:
        """Decompress bytes using zlib."""
        return zlib.decompress(data)
