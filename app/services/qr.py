"""A QR code as a picture the server makes (segno, pure Python — no Pillow).

Error correction M, a 4-module quiet zone, dark on white whatever the theme: a QR needs its
own contrast. Rendered at a fixed 10 px per module so the file is small; the board scales it,
drawn whole over its block (`solid`) so no gap or split line cuts a module.
"""

import io

import segno

MAX_DATA = 1024  # characters; a URL or a line of text
SCALE = 10  # px per module
BORDER = 4  # modules of quiet zone
BLOCK_W, BLOCK_H = 4, 3  # a new QR's block in cells — square-ish (a cell is 1 × 1.45)


def png(data: str) -> bytes:
    code = segno.make(data, error="m")
    buf = io.BytesIO()
    code.save(buf, kind="png", scale=SCALE, border=BORDER, dark="#000", light="#fff")
    return buf.getvalue()
