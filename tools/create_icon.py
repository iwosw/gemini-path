"""Build a small multi-size ICO without third-party dependencies."""

import argparse
from pathlib import Path
import struct
import zlib


def chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))


def in_polygon(x, y, points):
    inside = False
    previous = points[-1]
    for current in points:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
        previous = current
    return inside


def image(size):
    bolt = [(0.52, 0.10), (0.75, 0.10), (0.58, 0.45),
            (0.76, 0.45), (0.36, 0.91), (0.45, 0.57),
            (0.25, 0.57)]
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            u, v = (x + 0.5) / size, (y + 0.5) / size
            corner = min(u, 1 - u, v, 1 - v)
            if corner < 0.02 and (min(u, 1 - u) ** 2 + min(v, 1 - v) ** 2) < 0.001:
                color = (0, 0, 0, 0)
            elif in_polygon(u, v, bolt):
                color = (103, 220, 229, 255)
            else:
                color = (27, 36, 51, 255)
            rows.extend(color)
    signature = b"\x89PNG\r\n\x1a\n"
    return (signature + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), level=9))
            + chunk(b"IEND", b""))


def icon():
    sizes = (32, 64, 256)
    images = [image(size) for size in sizes]
    offset = 6 + len(sizes) * 16
    directory = bytearray(struct.pack("<HHH", 0, 1, len(sizes)))
    for size, payload in zip(sizes, images):
        dimension = 0 if size == 256 else size
        directory.extend(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32,
                                     len(payload), offset))
        offset += len(payload)
    return bytes(directory) + b"".join(images)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/GeminiPath.ico", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(icon())
    print(args.output)


if __name__ == "__main__":
    main()
