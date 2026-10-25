# A picture behind the board

The board can sit on a picture: a poster from your phone, blurred into a mood for a party, or
one of the four that ship with the app for a quieter look. The flaps keep their theme; the frame
turns translucent over the picture; the board stays readable.

## The four-click version

1. Snip the poster on your phone or laptop (a screenshot is fine) and send it to the computer
   with the settings page.
2. **Settings → Look & feel → Behind the board → Upload…** and pick the file. It appears as a
   swatch and is selected.
3. Drag **Blur** until the picture is a mood rather than a poster — 12 px is the default, 20–30
   hides the words — and **Dim** until the flaps read; the live card follows every move.
4. **Save background.** The TV picks it up on its next poll.

**Clear** takes the picture away and keeps your blur and dim for next time. The same four settings
are on the API — `PATCH /api/settings` with `background_image`, `background_blur`,
`background_dim` and `background_fit` — so a script can set the party look and take it down.

## The ones that ship

| `builtin:terminal` | `builtin:wood` |
|---|---|
| ![Terminal](../app/static/backgrounds/thumbs/terminal.jpg) concrete grey, a departures hall | ![Wood](../app/static/backgrounds/thumbs/wood.jpg) dark walnut planks |
| **`builtin:gala`** | **`builtin:paper`** |
| ![Gala](../app/static/backgrounds/thumbs/gala.jpg) deep navy with gold bokeh — the formal one | ![Paper](../app/static/backgrounds/thumbs/paper.jpg) warm off-white, made for Arctic White |

They are drawn by the project, 1920 × 1080, 20–110 KB each, under `app/static/backgrounds/`.

## Making your own

- **Size.** 1920 × 1080 (16:9) fills a TV with nothing cropped. Any size works: **fill** (the
  default) scales the picture to cover the screen and crops the overflow; **fit** shows all of it
  and leaves the theme's colour around the edges.
- **The safe area.** The flaps cover a box in the middle; whatever is under them is hidden. The
  template below has that box drawn for both presets. What shows is the strips above and below
  the board and a narrow band at the sides, all at 35 % frame colour, so a subject placed in the
  top strip reads and anything under the flaps does not matter.
- **Blur and dim.** Blur (0–40 px) softens; dim (0–90 %) darkens. A busy photo wants both; a
  flat texture wants neither. The defaults are 12 px and 30 %.
- **The upload limit is 5 MB.** A phone screenshot is 1–3 MB; a camera photo may need resizing.
  PNG, JPEG, GIF or WebP.
- **The cost.** The TV loads the picture once per page load and caches it, so a big file costs
  the first paint and nothing after. Blur is rendered by the browser on the TV; a Raspberry Pi
  handles 40 px at 1080p, a Fire TV Stick is happier below 20.

![The template: the flap boxes for Compact and Large drawn on a 1920 × 1080 canvas](background-template.png)

`docs/background-template.png` is that template at full size — open it in any editor, put your
picture on a layer beneath, and keep the subject outside the dashed boxes.

## Where the pictures live

An uploaded background is an ordinary picture in the Images panel: it has a token and can be put
in a message like any other. Deleting it there removes the background too; the board falls back
to the theme's colour.
