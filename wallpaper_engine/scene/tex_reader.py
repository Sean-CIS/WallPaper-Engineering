"""
Reader for Wallpaper Engine .tex texture files (TEXV0005 format).

Structure:
    'TEXV0005\\0' + 'TEXI0001\\0' +
    uint32 format (0=RGBA8, 8=RG88, 9=R8) +
    uint32 flags +
    uint32 tex_width, tex_height, img_width, img_height +
    uint8[4] avg_color_rgba +
    'TEXB0003\\0' +
    uint32[5] body header +
    Mip data (JPEG or LZ compressed)
"""

import io
import struct
from PIL import Image

FMT_RGBA8 = 0
FMT_RG88 = 8
FMT_R8 = 9
COMPRESS_LZ = 0xFFFFFFFF


def read_tex(data):
    """Decode a WE .tex file. Returns PIL Image (RGBA) or None."""
    if len(data) < 40:
        return None
    try:
        return _parse_texv(data)
    except Exception:
        # Fallback: scan for JPEG
        jp = data.find(b"\xff\xd8\xff")
        if jp >= 0:
            try:
                return Image.open(io.BytesIO(data[jp:])).convert("RGBA")
            except Exception:
                pass
        return None


def _parse_texv(data):
    pos = 0
    # TEXV0005\0
    pos = data.index(0, pos) + 1
    # TEXI0001\0
    pos = data.index(0, pos) + 1

    fmt, flags = struct.unpack_from("<II", data, pos); pos += 8
    tex_w, tex_h, img_w, img_h = struct.unpack_from("<IIII", data, pos); pos += 16
    avg_r, avg_g, avg_b, avg_a = struct.unpack_from("<BBBB", data, pos); pos += 4

    # TEXB0003\0
    pos = data.index(0, pos) + 1

    _, compression, mip_count, mip_w, mip_h = struct.unpack_from("<IIIII", data, pos)
    pos += 20

    # JPEG compressed
    jp = data.find(b"\xff\xd8\xff", pos)
    if jp >= 0 and compression != COMPRESS_LZ:
        je = data.find(b"\xff\xd9", jp + 2)
        jpeg_data = data[jp:je + 2] if je >= 0 else data[jp:]
        img = Image.open(io.BytesIO(jpeg_data))
        if img.size != (img_w, img_h) and img_w > 0 and img_h > 0:
            img = img.crop((0, 0, min(img.width, img_w), min(img.height, img_h)))
        return img.convert("RGBA")

    # LZ compressed
    if compression == COMPRESS_LZ:
        return _read_lz(data, pos, fmt, img_w, img_h, avg_r, avg_g, avg_b, avg_a)

    return None


def _read_lz(data, pos, fmt, w, h, avg_r, avg_g, avg_b, avg_a):
    """Decompress LZ-compressed texture."""
    bpp = 1 if fmt == FMT_R8 else (2 if fmt == FMT_RG88 else 4)
    expected = w * h * bpp

    output = bytearray()

    while pos < len(data) and len(output) < expected:
        if pos + 4 > len(data):
            break
        chunk_size = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if chunk_size == 0 or chunk_size > len(data) - pos:
            break
        chunk = data[pos:pos + chunk_size]
        pos += chunk_size
        output.extend(_lz_decode(chunk, expected - len(output)))

    if len(output) < expected:
        # Fallback to solid avg color
        return _solid(w, h, avg_r, avg_g, avg_b, avg_a, fmt)

    raw = bytes(output[:expected])

    if fmt == FMT_R8:
        return Image.frombytes("L", (w, h), raw).convert("RGBA")
    elif fmt == FMT_RG88:
        import numpy as np
        rg = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 2)
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[:, :, 0] = rg[:, :, 0]
        rgba[:, :, 1] = rg[:, :, 1]
        rgba[:, :, 3] = 255
        return Image.fromarray(rgba, "RGBA")
    else:
        return Image.frombytes("RGBA", (w, h), raw)


def _lz_decode(chunk, max_out):
    """Decode a WE LZ chunk (simple RLE/literal scheme)."""
    out = bytearray()
    i = 0
    while i < len(chunk) and len(out) < max_out:
        cmd = chunk[i]; i += 1
        if cmd < 128:
            n = cmd + 1
            end = min(i + n, len(chunk))
            out.extend(chunk[i:end])
            i = end
        else:
            n = cmd - 128 + 3
            if i < len(chunk):
                out.extend(bytes([chunk[i]]) * n)
                i += 1
    return bytes(out[:max_out])


def _solid(w, h, r, g, b, a, fmt):
    """Solid color fallback."""
    if fmt == FMT_R8:
        return Image.new("L", (w, h), r).convert("RGBA")
    return Image.new("RGBA", (w, h), (r, g, b, a))
