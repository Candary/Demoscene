#!/usr/bin/env python3
"""Visual regression testing: compare two BMP frames pixel-by-pixel.

Usage:
  python3 compare_frames.py <frame_v1.bmp> <frame_v2.bmp> [--threshold N]

Output:
  - Average pixel difference (0-255)
  - Max pixel difference
  - Number of pixels that differ
  - PASS/FAIL verdict
"""
import sys
import struct
from pathlib import Path


def read_bmp(path):
    """Read BMP file, return (width, height, pixels as list of (R,G,B) tuples)."""
    data = Path(path).read_bytes()
    if data[:2] != b'BM':
        raise ValueError(f"Not a BMP file: {path}")
    
    # Parse headers
    file_size = struct.unpack_from('<I', data, 2)[0]
    pixel_offset = struct.unpack_from('<I', data, 10)[0]
    width = struct.unpack_from('<i', data, 18)[0]
    height = struct.unpack_from('<i', data, 22)[0]
    bpp = struct.unpack_from('<H', data, 28)[0]
    
    if bpp != 24:
        raise ValueError(f"Only 24-bit BMP supported, got {bpp}-bit")
    
    row_size = ((width * 3 + 3) // 4) * 4
    abs_height = abs(height)
    top_down = height < 0
    
    pixels = []
    for row in range(abs_height):
        y = row if top_down else (abs_height - 1 - row)
        offset = pixel_offset + y * row_size
        row_pixels = []
        for x in range(width):
            b = data[offset + x * 3]
            g = data[offset + x * 3 + 1]
            r = data[offset + x * 3 + 2]
            row_pixels.append((r, g, b))
        pixels.append(row_pixels)
    
    return width, abs_height, pixels


def compare_frames(path1, path2, threshold=5.0):
    """Compare two BMP files. Returns (avg_diff, max_diff, mismatch_pixels, total_pixels)."""
    w1, h1, px1 = read_bmp(path1)
    w2, h2, px2 = read_bmp(path2)
    
    if w1 != w2 or h1 != h2:
        print(f"Size mismatch: {w1}x{h1} vs {w2}x{h2}")
        return None
    
    total_diff = 0
    max_diff = 0
    mismatch_count = 0
    total_pixels = w1 * h1
    
    for y in range(h1):
        for x in range(w1):
            r1, g1, b1 = px1[y][x]
            r2, g2, b2 = px2[y][x]
            dr = abs(r1 - r2)
            dg = abs(g1 - g2)
            db = abs(b1 - b2)
            pixel_diff = (dr + dg + db) / 3
            total_diff += pixel_diff
            max_diff = max(max_diff, dr, dg, db)
            if pixel_diff > threshold:
                mismatch_count += 1
    
    avg_diff = total_diff / total_pixels
    return avg_diff, max_diff, mismatch_count, total_pixels


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 compare_frames.py <frame1.bmp> <frame2.bmp> [--threshold N]")
        sys.exit(1)
    
    path1 = sys.argv[1]
    path2 = sys.argv[2]
    threshold = 5.0  # default: 5 out of 255
    
    if '--threshold' in sys.argv:
        idx = sys.argv.index('--threshold')
        threshold = float(sys.argv[idx + 1])
    
    result = compare_frames(path1, path2, threshold)
    if result is None:
        sys.exit(1)
    
    avg_diff, max_diff, mismatch_count, total_pixels = result
    mismatch_pct = (mismatch_count / total_pixels) * 100
    
    print(f"Frame 1: {path1}")
    print(f"Frame 2: {path2}")
    print(f"Resolution: {total_pixels} pixels")
    print(f"Average diff: {avg_diff:.2f} / 255")
    print(f"Max diff:     {max_diff} / 255")
    print(f"Mismatch pixels: {mismatch_count} ({mismatch_pct:.2f}%) at threshold {threshold}")
    
    if avg_diff < threshold:
        print(f"✅ PASS: frames match (avg diff {avg_diff:.2f} < {threshold})")
    else:
        print(f"❌ FAIL: visual regression detected (avg diff {avg_diff:.2f} >= {threshold})")
        sys.exit(1)


if __name__ == "__main__":
    main()
