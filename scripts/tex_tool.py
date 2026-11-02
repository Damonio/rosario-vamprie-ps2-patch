"""
Texture tool for PS2 Rosario + Vampire Capu 2 (.tex container).
Pure Python standard library implementation (no PIL/Pillow dependency).
Supports decoding .tex textures to PNG and encoding PNG to .tex.
Handles PS2 GS 8-bit CLUT swizzling and median-cut color quantization.
"""

import os
import sys
import struct
import zlib
from collections import Counter


def swizzle_palette(pal_bytes: bytes) -> bytes:
    """
    PS2 GS 8-bit CLUT (Color Look-Up Table) swizzling.
    For each block of 32 colors, entries 8..15 swap places with 16..23.
    This operation is an involution (swizzle(swizzle(x)) == x).
    """
    out = bytearray(pal_bytes)
    for i in range(0, 256, 32):
        for j in range(8):
            idx1 = (i + 8 + j) * 4
            idx2 = (i + 16 + j) * 4
            out[idx1:idx1+4], out[idx2:idx2+4] = pal_bytes[idx2:idx2+4], pal_bytes[idx1:idx1+4]
    return bytes(out)


def decode_png(png_bytes: bytes) -> tuple[int, int, bytearray]:
    """
    Decodes a standard PNG into (width, height, rgba_bytearray).
    Supports 8-bit RGBA (color_type 6) and 8-bit RGB (color_type 2).
    """
    if png_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError("Invalid PNG header")
    pos = 8
    w, h, color_type = 0, 0, 0
    idat = bytearray()
    while pos < len(png_bytes):
        length = struct.unpack('>I', png_bytes[pos:pos+4])[0]
        tag = png_bytes[pos+4:pos+8]
        data = png_bytes[pos+8:pos+8+length]
        if tag == b'IHDR':
            w, h, bit_depth, color_type = struct.unpack('>IIBB', data[:10])
            if bit_depth != 8 or color_type not in (2, 6):
                raise ValueError(f"Unsupported PNG bit depth {bit_depth} or color type {color_type}")
        elif tag == b'IDAT':
            idat.extend(data)
        elif tag == b'IEND':
            break
        pos += 12 + length

    decomp = zlib.decompress(bytes(idat))
    bpp = 4 if color_type == 6 else 3
    stride = w * bpp
    raw = bytearray(decomp)
    rgba = bytearray(w * h * 4)

    prev_row = bytearray(stride)
    curr_row = bytearray(stride)
    src_pos = 0

    for y in range(h):
        filter_type = raw[src_pos]
        src_pos += 1
        curr_row[:] = raw[src_pos : src_pos + stride]
        src_pos += stride

        if filter_type == 1:  # Sub
            for i in range(bpp, stride):
                curr_row[i] = (curr_row[i] + curr_row[i - bpp]) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(stride):
                curr_row[i] = (curr_row[i] + prev_row[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(stride):
                left = curr_row[i - bpp] if i >= bpp else 0
                up = prev_row[i]
                curr_row[i] = (curr_row[i] + ((left + up) >> 1)) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(stride):
                a = curr_row[i - bpp] if i >= bpp else 0
                b = prev_row[i]
                c = prev_row[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                curr_row[i] = (curr_row[i] + pr) & 0xFF

        prev_row[:] = curr_row

        dst_off = y * w * 4
        if bpp == 4:
            rgba[dst_off : dst_off + w * 4] = curr_row
        else:
            for x in range(w):
                rgba[dst_off + x*4 : dst_off + x*4 + 3] = curr_row[x*3 : x*3 + 3]
                rgba[dst_off + x*4 + 3] = 255

    return w, h, rgba


def encode_png(width: int, height: int, rgba_bytes: bytes | bytearray) -> bytes:
    """Encodes raw RGBA bytes into standard PNG bytes."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # Filter type 0: None
        raw.extend(rgba_bytes[y * width * 4 : (y + 1) * width * 4])

    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(bytes(raw), level=6)) + chunk(b'IEND', b'')


def quantize_rgba(rgba_bytes: bytes | bytearray, max_colors: int = 256) -> tuple[list[tuple[int, int, int, int]], bytes]:
    """
    Quantizes RGBA pixels to a 256-color palette using median-cut partitioning.
    Returns (palette, indices_bytes).
    """
    pixels = [tuple(rgba_bytes[i:i+4]) for i in range(0, len(rgba_bytes), 4)]
    counts = Counter(pixels)

    if len(counts) <= max_colors:
        palette = list(counts.keys())
        while len(palette) < max_colors:
            palette.append((0, 0, 0, 0))
        c_map = {c: i for i, c in enumerate(palette)}
        return palette, bytes(c_map[p] for p in pixels)

    has_transparent = any(c[3] < 16 for c in counts)
    usable_colors = max_colors - 1 if has_transparent else max_colors
    opaque_counts = [(c, n) for c, n in counts.items() if c[3] >= 16]

    boxes = [opaque_counts]
    while len(boxes) < usable_colors:
        best_box_idx, best_score, best_axis = -1, -1, 0
        for b_idx, box in enumerate(boxes):
            if len(box) <= 1:
                continue
            mins = [min(c[k] for c, _ in box) for k in range(4)]
            maxs = [max(c[k] for c, _ in box) for k in range(4)]
            ranges = [maxs[k] - mins[k] for k in range(4)]
            max_r = max(ranges)
            axis = ranges.index(max_r)
            score = max_r * sum(n for _, n in box)
            if score > best_score:
                best_score, best_box_idx, best_axis = score, b_idx, axis
        if best_box_idx == -1:
            break
        box_to_split = boxes.pop(best_box_idx)
        box_to_split.sort(key=lambda x: x[0][best_axis])
        mid = len(box_to_split) // 2
        boxes.append(box_to_split[:mid])
        boxes.append(box_to_split[mid:])

    palette = [(0, 0, 0, 0)] if has_transparent else []
    for box in boxes:
        tw = sum(n for _, n in box)
        avg_c = tuple(int(sum(c[k] * n for c, n in box) / tw) for k in range(4)) if tw else box[0][0]
        palette.append(avg_c)
    while len(palette) < max_colors:
        palette.append((0, 0, 0, 0))

    cache = {}
    start_i = 1 if has_transparent else 0
    num_boxes = len(boxes) + start_i

    def nearest(c):
        if c[3] < 16 and has_transparent:
            return 0
        best_i, best_d = start_i, 1e9
        r, g, b, a = c
        for i in range(start_i, num_boxes):
            pr, pg, pb, pa = palette[i]
            d = (r - pr)**2 * 2 + (g - pg)**2 * 4 + (b - pb)**2 * 3 + (a - pa)**2 * 4
            if d < best_d:
                best_d, best_i = d, i
                if d == 0:
                    break
        return best_i

    for c in counts:
        cache[c] = nearest(c)

    indices = bytes(cache[p] for p in pixels)
    return palette, indices


def tex_to_rgba(tex_bytes: bytes) -> tuple[int, int, bytearray]:
    """
    Decodes .tex data to (width, height, rgba_bytearray).
    """
    fmt, w, h, pal_cnt, pix_sz, rsvd = struct.unpack('<HHHHII', tex_bytes[:16])
    if pal_cnt != 256:
        raise ValueError(f"Unsupported pal_cnt: {pal_cnt}")

    pixel_data = tex_bytes[16 : 16 + pix_sz]
    raw_pal = tex_bytes[16 + pix_sz : 16 + pix_sz + 1024]
    pal = swizzle_palette(raw_pal)

    rgba = bytearray(w * h * 4)
    for i, idx in enumerate(pixel_data):
        r, g, b, a_ps2 = pal[idx * 4 : (idx + 1) * 4]
        a_scaled = min(255, a_ps2 * 2) if a_ps2 <= 128 else 255
        rgba[i * 4 : (i + 1) * 4] = [r, g, b, a_scaled]

    return w, h, rgba


def tex_to_png(tex_bytes: bytes) -> bytes:
    """Converts .tex data to PNG bytes."""
    w, h, rgba = tex_to_rgba(tex_bytes)
    return encode_png(w, h, rgba)


def rgba_to_tex(w: int, h: int, rgba_bytes: bytes | bytearray, fmt: int = 1) -> bytes:
    """
    Encodes RGBA bytes into a PS2 .tex byte string.
    Quantizes to 256 colors, converts alpha to PS2 range (0..128), and applies GS swizzling.
    """
    palette, indices = quantize_rgba(rgba_bytes, max_colors=256)

    # Convert palette to PS2 CLUT (RGBA with A in 0..128)
    pal_raw = bytearray()
    for r, g, b, a in palette:
        a_ps2 = min(128, round(a * 128 / 255))
        pal_raw.extend([r, g, b, a_ps2])

    swizzled_pal = swizzle_palette(bytes(pal_raw))
    header = struct.pack('<HHHHII', fmt, w, h, 256, len(indices), 0)
    return header + indices + swizzled_pal


def png_to_tex(png_bytes: bytes, fmt: int = 1) -> bytes:
    """Converts standard PNG bytes into PS2 .tex format."""
    w, h, rgba = decode_png(png_bytes)
    return rgba_to_tex(w, h, rgba, fmt=fmt)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage:")
        print("  python scripts/tex_tool.py extract <input.tex> <output.png>")
        print("  python scripts/tex_tool.py inject  <input.png> <output.tex>")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    in_file = sys.argv[2]
    out_file = sys.argv[3]

    if cmd == 'extract':
        with open(in_file, 'rb') as f:
            png_data = tex_to_png(f.read())
        with open(out_file, 'wb') as f:
            f.write(png_data)
        print(f"Extracted {in_file} -> {out_file} ({len(png_data)} bytes)")
    elif cmd == 'inject':
        with open(in_file, 'rb') as f:
            tex_data = png_to_tex(f.read())
        with open(out_file, 'wb') as f:
            f.write(tex_data)
        print(f"Injected {in_file} -> {out_file} ({len(tex_data)} bytes)")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
