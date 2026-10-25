"""Drop the metadata a phone attaches to a photo before it goes on a public TV.

A small pure-Python pass (no Pillow): JPEG APP1–APP13/APP15 and COM segments go (Exif, XMP, ICC,
comments; APP0 JFIF and APP14 Adobe stay — they are decoding hints, not metadata); PNG tEXt, zTXt,
iTXt and eXIf chunks go; WebP EXIF and XMP chunks go and the VP8X flags forget them. Anything not
recognised comes back untouched.
"""

import struct

_JPEG_DROP = {*range(0xE1, 0xEE), 0xEF, 0xFE}  # APP1–APP13, APP15, COM
_PNG_DROP = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}
_WEBP_DROP = {b"EXIF", b"XMP "}


def strip(data: bytes, content_type: str) -> bytes:
    if content_type == "image/jpeg" and data[:2] == b"\xff\xd8":
        return _jpeg(data)
    if content_type == "image/png" and data[:8] == b"\x89PNG\r\n\x1a\n":
        return _png(data)
    if content_type == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return _webp(data)
    return data


def _jpeg(data: bytes) -> bytes:
    out = bytearray(data[:2])
    i, n = 2, len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            return data  # not a segment boundary: leave the file alone
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if marker == 0xD9 or 0xD0 <= marker <= 0xD8 or marker == 0x01:  # standalone markers
            out += data[i : i + 2]
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker == 0xDA:  # start of scan: the rest is entropy-coded data, copied whole
            out += data[i:]
            return bytes(out)
        if marker not in _JPEG_DROP:
            out += data[i : i + 2 + length]
        i += 2 + length
    return bytes(out)


def _png(data: bytes) -> bytes:
    out = bytearray(data[:8])
    i, n = 8, len(data)
    while i + 8 <= n:
        length = struct.unpack(">I", data[i : i + 4])[0]
        kind = data[i + 4 : i + 8]
        end = i + 12 + length
        if kind not in _PNG_DROP:
            out += data[i:end]
        i = end
    return bytes(out)


def _webp(data: bytes) -> bytes:
    chunks = []
    i, n = 12, len(data)
    while i + 8 <= n:
        kind = data[i : i + 4]
        length = struct.unpack("<I", data[i + 4 : i + 8])[0]
        padded = length + (length & 1)
        body = data[i + 8 : i + 8 + padded]
        if kind not in _WEBP_DROP:
            if kind == b"VP8X" and len(body) >= 1:
                body = (
                    bytes([body[0] & ~0x0C]) + body[1:]
                )  # forget the EXIF (0x08) and XMP (0x04) flags
            chunks.append(data[i : i + 8][:4] + struct.pack("<I", length) + body)
        i += 8 + padded
    payload = b"".join(chunks)
    return b"RIFF" + struct.pack("<I", 4 + len(payload)) + b"WEBP" + payload
