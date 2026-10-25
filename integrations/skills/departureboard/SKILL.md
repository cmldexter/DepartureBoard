---
name: departureboard
description: Put messages on a DepartureBoard split-flap display and schedule them (a window, daily, weekly), upload a picture for the board, or change the display preset, through its HTTP API with a bearer token. Use when the user asks to show, post, schedule, clear or change something on "the board", "the departure board", "the split-flap" or "the TV board".
---

# DepartureBoard

An open-source split-flap departure board for a TV. One server on the LAN serves the board page
and a small JSON API. Everything the settings page does, the API does.

## You need

- `DB_URL` — where the board is, e.g. `http://192.168.1.20:8080` (ask if unknown; `GET $DB_URL/api/health` answers `{"ok": true}`).
- `DB_TOKEN` — the bearer token. It is in the environment, a `.env`, or the user pastes it. Never print it back.

Every call except the two public ones sends `Authorization: Bearer $DB_TOKEN`.

## The calls

| Task | Call |
|---|---|
| Show something **now** | `POST /api/messages/now` — body `{"text": "…"}` or `Content-Type: text/plain` with the text. Goes live immediately above everything else |
| Show it **for a while** | `POST /api/messages` — `{"text": "…", "starts_at": "2026-10-21T07:00:00-04:00", "ends_at": "2026-10-21T23:00:00-04:00"}` (ISO-8601 with offset; either end optional) |
| **Every day** at a time | `POST /api/messages` — `{"text": "…", "repeat": "daily", "repeat_start": "09:00", "repeat_end": "10:00"}` (server timezone; an end before the start crosses midnight) |
| On **weekdays** | `POST /api/messages` — `{"text": "…", "repeat": "weekly", "repeat_days": 31, "repeat_start": "18:00", "repeat_end": "23:00"}` — `repeat_days` sums Mon 1 · Tue 2 · Wed 4 · Thu 8 · Fri 16 · Sat 32 · Sun 64 |
| Priority | `"priority": 0–100` on any message; the highest live one shows; equals take turns, each for the display's `rotate_seconds` |
| Its **own time** on the board | `"show_seconds": 5–600` on any message (also on `/now`): how long it holds the board when taking turns; omit it for the default |
| What is on | `GET /api/messages?state=live` (also `scheduled`, `expired`, `disabled`, or no filter) |
| Change / pause | `PATCH /api/messages/{id}` with the fields to change, e.g. `{"enabled": false}` |
| Remove | `DELETE /api/messages/{id}` → 204 |
| A **picture** on the board | `POST /api/images` multipart `file` (PNG/JPEG/GIF/WebP ≤ 5 MB) + optional `slug`; the response gives `"token": "{img:slug}"` to put in a message and `suggested` blocks; `PATCH /api/images/{slug}` `{"w": 9, "h": 1, "fit": "contain"}` sizes it in cells (or write `{img:slug@9x1}`) |
| A **QR code** on the board | `POST /api/images/qr` `{"slug": "menu", "data": "https://…"}` (data ≤ 1024) → `{"token": "{img:menu}", "w": 4, "h": 3, "solid": true, …}`; put the token in a message — two calls. It is drawn whole over its 4 × 3 block so a phone scans it from the sofa; the same slug again remakes it. `{"solid": true}` on `PATCH /api/images/{slug}` draws any picture whole |
| **Guests** post to the board | `POST /api/guest/rotate` → `{"token", "url"}` opens a public phone page `/guest/<token>` that posts a line or a photo into a queue (off until then; `PATCH /api/settings {"guest_token": ""}` closes it); `POST /api/guest/qr` makes `{img:guest-qr}` and a disabled `SCAN TO POST A PHOTO` message; `GET /api/posts?status=pending` lists what waits; `POST /api/posts/{id}/approve` makes an ordinary message from a post (`source: guest`; `note` says why it was left disabled when it did not fit); `/reject`; `DELETE /api/posts?status=all` clears. `PATCH /api/settings` `{"guest_auto_approve": true, "guest_priority": 1, "guest_show_seconds": 15}` |
| **Switch boards** | `GET /api/profiles` lists the saved boards (`active`, `changed`); `POST /api/profiles/{slug}/save` `{"name": "Party"}` saves the live board — messages and display — under a slug; `POST /api/profiles/{slug}/load` puts a saved one on the TV (replaces the live board in one transaction; `kept_disabled` names messages that did not fit its grid); `/copy` `{"slug", "name"}`, `PATCH` `{"name"}`, `DELETE`; `GET`/`PUT /api/profiles/{slug}` is the JSON file itself. Save before you switch when the user may want the live board back |
| The display | `PATCH /api/settings` — `{"grid_preset": "compact"|"large"|"custom", "rows", "cols", "animation": 0–100, "sound_enabled", "sound_volume": 0–1, "theme": "classic-black"|"walnut"|"arctic-white"|"midnight", "idle_text", "poll_seconds", "rotate_seconds", "timer_ring": "off"|"own"|"all", "cell_radius": 0–12, "cell_gap": 0–100, "split_line": 0–3}` (partial; the last three are the shape of a flap — `0, 10, 0` is Picture mode for a banner across the flaps) |
| Public: what the TV shows | `GET /api/board/current` (no token); `GET /images/{slug}` |
| Reference | `GET /docs` (Swagger), `GET /llms.txt` |

## Writing the text

- The board is a grid: **Compact 6 rows × 22 columns** (132 cells) or **Large 8 × 28** (224). Read
  the current size from `GET /api/settings` (`rows`, `cols`) before composing anything long.
- Rows split on `\n`; a row longer than the board word-wraps. A message that needs more rows than
  the board has is a **422** that says so — shorten it, do not retry blindly.
- Text is uppercased; accents are stripped; characters the flap set lacks become a blank and are
  listed in the response's `unknown`. The set: A–Z, 0–9, `! @ # $ ( ) - + & = ; : ' " % , . / ? °`.
- Token cells, **one cell each**: `{red}` `{orange}` `{yellow}` `{green}` `{blue}` `{violet}` `{white}` `{black}`
  (a solid coloured flap) and any emoji. `{img:slug}` is an uploaded picture at its block size (w × h cells;
  an unknown slug is a 422, a block wider than the board is a 422 that says so); `{img:slug@WxH}` sizes it inline.
  A QR code (`POST /api/images/qr`) is a picture like any other, drawn whole over its block; keep its 4 × 3 and put words beside it (`SCAN FOR THE MENU`).
- Keep it board-like: short lines, capitals, a chip or an emoji as an accent, not a paragraph.

## Do not

- Do not loop-post. One request per message; the board polls every few seconds on its own.
- Do not post the same text repeatedly to "refresh" it — it is already live.
- Do not guess the host or the token; ask.
- Do not print the token in output or write it into files other than the user's `.env`.

## Worked example

User: *"Put HAPPY BIRTHDAY NICK on the board tomorrow from 7am to 11pm, make it stand out."*

1. `GET $DB_URL/api/settings` → `cols: 22`, so `HAPPY BIRTHDAY NICK {yellow}` (21 cells) fits one row.
2. Compute tomorrow 07:00 and 23:00 in the user's offset, e.g. `2026-10-21T07:00:00-04:00`.
3. `POST $DB_URL/api/messages` with
   `{"text": "HAPPY BIRTHDAY NICK {yellow}", "starts_at": "2026-10-21T07:00:00-04:00", "ends_at": "2026-10-21T23:00:00-04:00", "priority": 5}`
4. Reply with the state from the response (`scheduled`) and the id, so the user can remove it.

Written against DepartureBoard 0.3.0 (API as of 2026-10-25; `show_seconds` and `timer_ring` need 0.3.0 or later; QR codes, `solid`, the flap shape and guests need 0.4.0 or later).
