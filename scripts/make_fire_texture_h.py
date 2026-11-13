#!/usr/bin/env python3
"""Generate fire_texture.h with raw RGB bytes from fire_spritesheet.png.

main.cpp uses raw RGB (no PNG decoder at runtime) — single header, no external
image library. Output: `static const unsigned char kFireTexRGB[512*512*3]`.
"""
import struct
import zlib
import sys
from pathlib import Path

DEMO_DIR = Path("/home/z/my-project/download/demo_intro")
PNG_PATH = DEMO_DIR / "fire_spritesheet.png"
OUT_PATH = DEMO_DIR / "fire_texture.h"

# --- Minimal PNG decoder (RGB, non-interlaced, 8-bit only) ---
# We control the source PNG so we can assume these constraints.

def read_png(path):
    """Return (width, height, rgb_bytes) for an RGB8 non-interlaced PNG."""
    data = path.read_bytes()
    # PNG signature
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos = 8
    width = height = bit_depth = color_type = None
    idat_chunks = []
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos+4])[0]
        ctype = data[pos+4:pos+8]
        chunk_data = data[pos+8:pos+8+length]
        # CRC = data[pos+8+length:pos+12+length]
        pos = pos + 12 + length
        if ctype == b"IHDR":
            (width, height, bit_depth, color_type,
             _comp, _filt, _inter) = struct.unpack(">IIBBBBB", chunk_data)
            if bit_depth != 8:
                raise ValueError(f"only 8-bit supported (got {bit_depth})")
            if color_type != 2:  # 2 = RGB
                raise ValueError(f"only RGB (type 2) supported (got {color_type})")
        elif ctype == b"IDAT":
            idat_chunks.append(chunk_data)
        elif ctype == b"IEND":
            break
    if width is None:
        raise ValueError("IHDR not found")
    raw = zlib.decompress(b"".join(idat_chunks))
    # Apply filter per scanline (first byte of each row = filter type).
    channels = 3
    stride = width * channels
    out = bytearray()
    prev_row = bytearray(stride)
    for y in range(height):
        row_start = y * (stride + 1)
        filt = raw[row_start]
        row = bytearray(raw[row_start+1: row_start+1+stride])
        if filt == 0:    # None
            pass
        elif filt == 1:  # Sub
            for i in range(channels, stride):
                row[i] = (row[i] + row[i-channels]) & 0xFF
        elif filt == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif filt == 3:  # Average
            for i in range(stride):
                a = row[i-channels] if i >= channels else 0
                b = prev_row[i]
                row[i] = (row[i] + (a + b) // 2) & 0xFF
        elif filt == 4:  # Paeth
            for i in range(stride):
                a = row[i-channels] if i >= channels else 0
                b = prev_row[i]
                c = prev_row[i-channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pred = a
                elif pb <= pc:
                    pred = b
                else:
                    pred = c
                row[i] = (row[i] + pred) & 0xFF
        else:
            raise ValueError(f"unknown filter {filt}")
        out.extend(row)
        prev_row = row
    return width, height, bytes(out)

print(f"Decoding {PNG_PATH}...")
w, h, rgb = read_png(PNG_PATH)
print(f"  {w}x{h}, {len(rgb)} bytes RGB")

# Emit C header. Format: 12 bytes per line as hex literals.
with OUT_PATH.open("w") as f:
    f.write("// ===================================================================\n")
    f.write("// fire_texture.h\n")
    f.write("// -------------------------------------------------------------------\n")
    f.write("// Декодированные RGB-байты fire_spritesheet.png (4x6 спрайт-лист).\n")
    f.write("// Сгенерировано скриптом scripts/make_fire_texture_h.py.\n")
    f.write("// Не редактировать вручную — регенерируйте скриптом.\n")
    f.write("// ===================================================================\n\n")
    f.write("#pragma once\n\n")
    f.write(f"static const int kFireTexWidth  = {w};\n")
    f.write(f"static const int kFireTexHeight = {h};\n")
    f.write(f"static const unsigned char kFireTexRGB[{w}*{h}*3] = {{\n")
    per_line = 12
    for i in range(0, len(rgb), per_line):
        chunk = rgb[i:i+per_line]
        f.write("    " + ", ".join(f"0x{b:02x}" for b in chunk) + ",\n")
    f.write("};\n")
print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
