"""Read a QR code back from a PNG, the way a phone would — a tiny reader for a greyscale PNG
(what segno writes) handing one grey byte per pixel to zxing-cpp. No Pillow, no numpy."""

import struct
import zlib

import zxingcpp


def _unfilter(kind: int, cur: bytearray, prev: bytearray) -> bytearray:
    """Undo one PNG scanline filter (bpp = 1 byte for 1- and 8-bit grey)."""
    for x in range(len(cur)):
        a = cur[x - 1] if x else 0
        b = prev[x]
        c = prev[x - 1] if x else 0
        if kind == 1:
            cur[x] = (cur[x] + a) & 255
        elif kind == 2:
            cur[x] = (cur[x] + b) & 255
        elif kind == 3:
            cur[x] = (cur[x] + ((a + b) >> 1)) & 255
        elif kind == 4:
            pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
            pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
            cur[x] = (cur[x] + pred) & 255
    return cur


def grey_png(data: bytes) -> tuple[int, int, bytes]:
    """Width, height and one grey byte per pixel of a non-interlaced 1- or 8-bit greyscale PNG."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", data[16:29])
    assert ctype == 0 and depth in (1, 8) and interlace == 0, (ctype, depth, interlace)
    i, idat = 8, b""
    while i < len(data):
        (ln,) = struct.unpack(">I", data[i : i + 4])
        if data[i + 4 : i + 8] == b"IDAT":
            idat += data[i + 8 : i + 8 + ln]
        i += 12 + ln
    raw = zlib.decompress(idat)
    stride = (w * depth + 7) // 8
    out = bytearray()
    prev = bytearray(stride)
    for y in range(h):
        row = raw[y * (stride + 1) : (y + 1) * (stride + 1)]
        bits = _unfilter(row[0], bytearray(row[1:]), prev)
        prev = bits
        if depth == 8:
            out += bits[:w]
        else:
            for x in range(w):
                out.append(255 if (bits[x >> 3] >> (7 - (x & 7))) & 1 else 0)
    return w, h, bytes(out)


def decode_qr(data: bytes) -> str | None:
    w, h, grey = grey_png(data)
    view = memoryview(grey).cast("B", shape=[h, w])
    found = zxingcpp.read_barcode(view, formats=zxingcpp.BarcodeFormat.QRCode)
    return found.text if found else None
