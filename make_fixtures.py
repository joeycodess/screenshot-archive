"""Generate deterministic, valid synthetic PNG fixtures without dependencies."""
import argparse
import os
import struct
import zlib
from pathlib import Path


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(index):
    width, height = 256, 160
    seed = index.to_bytes(4, "big")
    pixels = b"".join(
        b"\0" + bytes((seed[(x + y) % 4] + x + y) % 256 for x in range(width))
        for y in range(height)
    )
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


def generate(folder, count):
    folder.mkdir()
    for index in range(count):
        path = folder / f"sample-{index:04d}.png"
        path.write_bytes(png(index))
        stamp = 1767225600 + index
        os.utime(path, (stamp, stamp))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--count", type=int, default=12)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    generate(args.folder, args.count)
