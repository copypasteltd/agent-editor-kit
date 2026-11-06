"""Small deterministic RGBA8 PNG encoder; no image-library or network dependency."""
import struct
import zlib
from .native import require, integer


def encode(width, height, rgba):
    require(integer(width, 1, 4096) and integer(height, 1, 4096) and width * height <= 3840 * 2160
            and len(rgba) == width * height * 4, 'TEXT_PNG_BUDGET', 'Invalid bounded RGBA canvas')
    def chunk(name, body):
        return struct.pack('>I', len(body)) + name + body + struct.pack('>I', zlib.crc32(name + body) & 0xFFFFFFFF)
    scanlines = b''.join(b'\0' + rgba[row * width * 4:(row + 1) * width * 4] for row in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scanlines, 6)) + chunk(b'IEND', b''))
