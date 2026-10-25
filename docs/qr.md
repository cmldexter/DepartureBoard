# A QR code on the board

A QR code is a picture the server makes. On the settings page, **Images → QR code**: type a link or a
line of text, give it a slug, *Make QR*. It appears in the list with the same token as any upload —
`{img:menu}` — and goes into a message like any picture. *Scan to open this board* fills the form with
the board's own address, slug `board`.

From a script, two calls:

```bash
curl -X POST http://board:8080/api/images/qr -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"slug": "menu", "data": "https://example.com/menu"}'
curl -X POST http://board:8080/api/messages/now -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: text/plain" --data $'SCAN FOR THE MENU\n{img:menu}'
```

The same slug again remakes the code with new text and keeps its size; the TV follows on its next poll.

## Why it is drawn whole

The flaps draw a picture as a mosaic: every flap paints its slice, and the gaps and the split line
across each flap's middle cut through it. A code 25 to 33 modules wide, spread over four flaps, loses a
column of modules at every gap — it will not scan. So a QR code is **drawn whole**: one picture laid over
the block, the flaps beneath blank. It fades in once they have landed and out before they move again, so
the cascade still frames it. The switch is *Draw whole* on the picture's row (`solid` on the API), and it
is on by default for a code and off for an upload. A logo with thin lines likes it too.

Picture mode (*Look & feel → The flaps*) tightens the grid for a banner that is sliced on purpose; a
code does not need it.

## What size scans from how far

A phone reads a code when a module is big enough on the screen. Rule of thumb: **a module should be at
least 6 px on a 1080p TV**, and bigger is better from across a room.

| Board | Block | Block on a 1080p TV | A short link (25 + 8 modules) | A long text (33 + 8) |
|---|---|---|---|---|
| Compact 6 × 22 | 3 × 2 | ≈ 250 × 245 px | ≈ 7 px per module — a step away | ≈ 6 px — close |
| Compact 6 × 22 | **4 × 3** | ≈ 333 × 357 px | **≈ 10 px — the sofa, 2–3 m** | ≈ 8 px |
| Large 8 × 28 | 4 × 3 | ≈ 260 × 280 px | ≈ 8 px | ≈ 6 px |
| Large 8 × 28 | **5 × 4** | ≈ 330 × 370 px | **≈ 10 px — the sofa** | ≈ 8 px |
| either | 6 × 4 | wider than tall; the code keeps its shape inside | — | — |

Those are the blocks the panel offers (3 × 2 · 4 × 3 · 5 × 4 · 6 × 4). A bigger TV scales everything
up; distance scales with it. Keep the text short — a link, not a paragraph — so the code stays sparse.

## Contrast

A code is drawn dark on white with a quiet zone, whatever the theme — a QR needs its own contrast, and
the theme does not decide it. Do not put a code on a dimmed, blurred photo with *fit: cover*; leave
*keep its shape* so the quiet zone stays. A phone reads black on white at a glance and anything else
with effort.

## Three recipes

- **A menu or a map.** `data` = the link. Put it next to the words: `SCAN FOR THE MENU` above, the
  token on its own row.
- **The Wi-Fi.** `data` = `WIFI:T:WPA;S:<network>;P:<password>;;` — phones join from the camera. The
  password is on the TV then; use a guest network.
- **A guest link.** When the board offers guests a page to post from, its address goes in a code the
  same way (*Scan to open this board* makes one for the board itself today).

## Details

- `POST /api/images/qr` — `{"slug": "a-z0-9-", "data": "up to 1024 characters"}` → 201, or 200 when
  the slug existed (the picture is remade, the size kept). The image object carries `qr.data`.
- Error correction M, a 4-module quiet zone, 10 px per module in the file; the board scales it and
  draws it pixel-sharp.
- `PATCH /api/images/{slug}` `{"solid": true|false}` switches *Draw whole* on any picture.
- `segno` draws the codes (BSD-3-Clause; see `THIRD_PARTY.md`).
