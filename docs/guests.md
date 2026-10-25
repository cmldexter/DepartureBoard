# Guests post to the board

A party trick with a small blast radius: a link for phones, off until you make it, that reaches a
queue and nothing else. This page says exactly what it can do, what it cannot, every limit the code
enforces, and how to end the evening. The numbers here are the ones in `app/services/guest.py`;
a test fails if they drift.

## Opening the door

On the settings page, **Guests → Make a link**. The board mints a 20-character token and shows the
link on the board's name, e.g. `http://dboard.localhost:8080/guest/AonlrpnJ0F4HUvHB4yAa`. *Copy* it,
or **Put the QR on the board**: that makes the picture `{img:guest-qr}` and a ready-made message
`SCAN TO POST A PHOTO` with the code under it, **disabled** until you switch it on in the Messages
list — edit or schedule it like any other. From a script, `POST /api/guest/rotate` then
`POST /api/guest/qr`.

Guests reach the link however you like: the QR on the TV, a message, a printed card. The link is
the only secret on that side; treat it like one (see *Keeping it quiet*).

## What a guest sees

One page, phone-sized, no sign-in: a line, *Add a photo*, a first name, *Post*. The line shows the
flap rules as they type (capitals, digits, a few marks; the rest turns blank). It works with
JavaScript off. After posting: *Thanks, Ana!* and whether the host approves posts or it is already on
the board. Nothing else about the board is on that page — no messages, no settings, no other
guests' posts, no address but its own.

## What a guest can and cannot do

| Can | Cannot |
|---|---|
| Leave a line of up to **120 characters** | Read messages, settings or other posts |
| Add one photo — **PNG, JPEG or WebP up to 5 MB** | Put anything on the TV unless you approve it (or you switched *Auto-approve* on) |
| Sign it with a name of up to **16 characters** | Reach the API: the guest page is the only route without the bearer token, and it only writes to the queue |
| Post again (within the limits) | Delete or edit a post, see whether it was approved, or find the link from the board |

A wrong or old link is a plain **404**, the same as any unknown page — not a sign-in prompt, so there is
nothing to learn from it.

## Approving

Posts wait in **Guests → Waiting for you** with a thumbnail, the line, the name and when; the page
header says *N waiting* while you are elsewhere on the page, the tab title too. **Approve** makes an
ordinary message from the post — the words, the photo below them sized to the rows left on the
current board, `- NAME` last — with `source: guest`, the priority from *Priority* (default 1, so
guests take turns among themselves above a priority-0 notice) and the time from *Show for*
(default 15 s). It then behaves like any message: the row switch, Edit, Delete, the timer ring. A post that
does not fit the board (a long line on a small grid) becomes a message that is **disabled** with the
reason in the response; nothing is dropped. **Reject** removes the photo and keeps nothing on the
board. **Remove** on *On the board* takes an approved post down again.

**Auto-approve** makes the message the moment the phone posts; the guest's page says *It is on the
board*. You can still remove it.

## The limits

| Limit | Value | Why |
|---|---|---|
| A line | **120 characters** | A row or two on any board |
| A name | **16 characters** | A first name, one row |
| A photo | **5 MB**, PNG, JPEG or WebP | The picture limit everywhere; GIF is not a photo |
| A photo on the board | up to **4 rows** tall, as wide as keeps its shape, never wider than the board | Sized at upload, fitted at approval |
| From one phone | **20 posts** an hour | Enough for anyone, too few for a flood |
| For the board | **200 posts** an hour | A big party; the page says *the board is busy* kindly |
| The token | **20 characters**, URL-safe | Unguessable; `PATCH /api/settings {"guest_token": "…"}` takes your own, 20–64 characters |

Rejected posts still count toward the hour; *Clear all* resets everything.

## Privacy

- **Photos lose their metadata** before they are stored: a pure-Python pass drops JPEG APP
  segments and comments (location, camera, the phone's name), PNG text and `eXIf` chunks, WebP
  `EXIF` and `XMP`. The pixels are untouched.
- **Addresses are not stored.** The hourly count keys on a short salted hash of the poster's
  address (`X-Forwarded-For`'s first hop behind a proxy) — enough to count, not enough to name.
- **A stored photo is a picture like any other**: it is served at `/images/guest-N` without a
  token from the moment it is stored, to anyone who can reach the board's port — the TV must be
  able to load it. *Reject*, *Remove* and *Clear all* delete the file.
- The thank-you page echoes the name the guest typed, nothing else.

## Ending the party

1. **Clear all** in *Guests*: every post, its message and its photo go.
2. **Turn off**: the link stops working at once and the `SCAN TO POST A PHOTO` message is
   switched off (the picture stays for next time).
3. Next time, **Make a link** again — a new token; **Put the QR on the board** remakes the code.

**Rotate** at any time mints a new link and kills the old one; a code on the board follows on the
TV's next poll.

## Keeping it quiet

The link is the whole secret. Keep it out of screenshots and public channels, and remember that a
QR on the TV is readable by anyone who can see the TV — which at a party is the point. For a
board reachable beyond the LAN, put HTTPS in front of it (see `SECURITY.md`); the guest page
carries no token, but the photos travel.

## The API

| Call | What |
|---|---|
| `POST /api/guest/rotate` | Mint a new link → `{token, url}`; the old one dies |
| `PATCH /api/settings {"guest_token": ""}` | Close the door (and disable the QR message) |
| `PATCH /api/settings {"guest_auto_approve": true, "guest_priority": 1, "guest_show_seconds": 15}` | How posts show |
| `POST /api/guest/qr` | The code and the ready-made message (201; 200 remade; 409 while off) |
| `GET /api/posts?status=pending\|approved\|rejected\|all` | The queue |
| `POST /api/posts/{id}/approve` · `/reject` | Approve → `{message_id, message_state, note}`; reject |
| `DELETE /api/posts/{id}` · `DELETE /api/posts?status=…` | Delete one; clear (`{removed}`) |
| `GET /guest/{token}` · `POST /guest/{token}` (multipart `text`, `nick`, `photo`) | The public page; no token header |
