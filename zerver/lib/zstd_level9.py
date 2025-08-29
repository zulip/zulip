from zstd import compress as original_compress
from zstd import decompress

__all__ = ["compress", "decompress"]


def compress(data: bytes, level: int | None = None) -> bytes:
    if level is None:
        level = 9
    return original_compress(data, level)
