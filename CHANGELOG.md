# Changelog

All notable changes to DepartureBoard are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Each release is a tag `vX.Y.Z`, a GitHub release
and a container image `ghcr.io/cmldexter/departureboard:X.Y.Z`.

## [Unreleased]

### Added

- **The Calendar section** (#143). Settings → Calendar: this month and the next as grids, each
  planned day tinted by its board and today outlined, a legend, the plan as a list with Edit and
  Delete, a form to plan a board (board, from, until, note; a click on a day pre-fills it), the
  everyday board, and *Today: …*. Every change is applied at once; when today's board changes the
  Boards strip and the live card follow.
- **Docs: planning boards ahead** (#144). `docs/calendar.md` (the rules — midnight in the board's
  time, the save-back, overlaps, the everyday board, a deleted board —, the file, the API), a
  README *Calendar* paragraph with a capture, `llms.txt`, the Agent Skill, `examples.sh calendar
  add|list|delete`.
- **A calendar of boards** (#142). Saved boards assigned to date ranges in `calendar.json` beside
  the profiles: `GET /api/calendar` (the plan, the everyday board, what today resolves to),
  `POST /api/calendar` (`profile`, `start`, `end` inclusive or null, `note`), `PATCH`/`DELETE
  /api/calendar/{id}`, `POST /api/calendar/apply`. A background tick (every
  `DEPARTUREBOARD_CALENDAR_TICK_SECONDS`, 30) puts the planned board on the TV at the day boundary
  in the board's timezone — **after saving the live board back into its active profile** (or into
  `unsaved-<date>` when it has none), so edits made on the Halloween board end up in
  `halloween.json`. When two entries cover a day the later start wins; an entry whose board was
  deleted is listed `missing` and skipped; the new setting `calendar_everyday` names the board
  between planned days (`""` = stay on the last one); `calendar_applied` remembers the decision.
- **The Boards strip** (#121). Under the settings page's header: *This board: Party* with
  *Switch…*, *Save*, *Save as…* and a ⋯ menu for Duplicate, Rename and Delete, each one call; a
  dot after the name when the live board differs from its saved file (`changed` on the listing);
  switching asks first when there are unsaved changes; the live card and every list follow a load.
- **Docs: boards from the API** (#132). `docs/profiles.md` (the file, what a switch replaces and
  keeps — every message travels, a `/now` one too —, the cron recipe), a README *Boards* paragraph
  with a capture, `llms.txt`, the Agent Skill, `examples.sh profile save|load|list`.
- **Boards you can switch** (#120). The live board — its messages and display settings — saved
  under a name as a plain JSON file, `profiles/<slug>.json`, in the data directory: `GET
  /api/profiles`, `POST /api/profiles/{slug}/save`, `POST /api/profiles/{slug}/load` (replaces the
  live board in one transaction; a message that does not fit the profile's own grid is kept
  disabled with its reason, a background picture that is gone is cleared), `/copy`, `PATCH`
  (rename), `DELETE`, and `GET`/`PUT /api/profiles/{slug}` for the file itself — the export and
  import format. A new display setting `active_profile` says which was loaded or saved last. The
  guest link's token is not part of a profile; pictures are shared by slug and stay on disk.
- **The QR that opens the guest page** (#116). `POST /api/guest/qr` makes the picture `guest-qr`
  from the current guest link and a ready-made message `SCAN TO POST A PHOTO` + `{img:guest-qr}`,
  disabled until you switch it on (201; 200 remade; 409 while guests are off); *Put the QR on the
  board* in Settings → Guests does the same. Rotating the link remakes the code and the TV follows
  on its next poll; turning guests off disables every message carrying the code.
- **Docs: guests and the safety story** (#117). A *Guests* section in the README with captures,
  `docs/guests.md` — what a guest can and cannot do, every limit the code enforces (a test keeps the
  numbers honest), privacy, how to end a party —, `llms.txt`, the Agent Skill and `SECURITY.md`.
- **Hosting the feed** (#115). `GET /api/posts?status=pending|approved|rejected|all`,
  `POST /api/posts/{id}/approve` and `/reject`, `DELETE /api/posts/{id}` and
  `DELETE /api/posts?status=…` (clear). **Approve = make a message**: the post's text, its photo
  below sized to the rows left on the current board, `- NICK` last, with `source: guest`, `post_id`
  (now on every message), the priority from the new display setting `guest_priority` (default 1 —
  guests take turns among themselves) and `show_seconds` from `guest_show_seconds` (default 15); a
  post that does not fit becomes a disabled message with a `note` instead of being dropped. Reject
  removes the message and the photo and keeps the row for the hour's count. `guest_auto_approve`
  puts a phone post on the TV within a poll and the thank-you page says so. Settings → **Guests**:
  the link with Copy, Rotate and Turn off, the Auto-approve switch, priority and seconds, the
  posts waiting (thumbnail, line, name, when; Approve / Reject), the posts on the board (Remove),
  Clear all, a waiting count in the page header and the tab title, a 10 s poll while the page is
  visible.
- **A guest link** (#114). The first public write path, narrow by design: `POST /api/guest/rotate`
  mints a 20-character token (the display setting `guest_token`; `""` closes the door) and
  `/guest/<token>` is one phone-sized page — a line of up to 120 characters with the flap rules
  shown as they type, an optional photo (PNG, JPEG or WebP up to 5 MB), an optional first name —
  that posts into a queue the host approves. Photos lose their metadata before they are stored
  (JPEG APP segments, PNG text and eXIf chunks, WebP EXIF and XMP) and are sized to keep their
  shape four rows tall. Twenty posts an hour from one phone, two hundred for the board; the
  page says so kindly. Nothing else about the board is reachable from it. Migration `0003`
  adds the `posts` table and `post_id` on messages.
- **A QR code on the board** (#110). `POST /api/images/qr` with `slug` and `data` (text or a URL,
  up to 1024 characters) makes a picture the server draws with `segno` (pure Python, BSD): error
  correction M, a quiet zone, dark on white whatever the theme. The same token, size, sidecar and
  panel as any upload; a new code takes 4 × 3 cells; the same slug again remakes it and keeps the
  size; `qr.data` on the image says what it carries.
- **A picture drawn whole over its block** (#111). `solid` on a picture (`PATCH /api/images/{slug}`;
  a QR code defaults to it) draws the block as one element over the grid instead of slicing it
  through the gaps and split lines — the flaps beneath flip to blank, the picture fades in once
  they have landed and out before they move again. A QR scans from the sofa; a logo keeps its lines.
- **QR codes from the Images panel** (#112). A *QR code* form beside *Upload*: text or a link, a
  slug, *Make QR*; *Scan to open this board* fills in the board's own address. A code's row shows
  its text with *Edit text*, offers the blocks that scan (4 × 3 on Compact, 5 × 4 on Large), and
  every picture's row has a *Draw whole* switch. A replaced file (an upload over a slug, a remade
  code) now carries a version on the wire, so the TV fetches the new picture on its next poll.
- **The QR docs** (#113). A README paragraph with a capture, `docs/qr.md` (sizes against distance,
  why *Draw whole* exists, the contrast rule, three recipes), `llms.txt`, the Agent Skill,
  `examples.sh qr`, the `/integrate` page, and `THIRD_PARTY.md` naming `segno` and its licence.
- **The shape of a flap** (#118). Display settings `cell_radius` (0–12, % of the cell's width),
  `cell_gap` (0–100, hundredths of a vmin) and `split_line` (0–3 px) replace three constants in the
  stylesheet; the TV follows on its next poll and repaints its picture slices for a new gap. *Look &
  feel* gains *The flaps*: three sliders the live card follows before Save, a *Picture mode* button
  (square corners, a hairline gap, no split line — a banner across the flaps loses less to the grid)
  and *Classic* to put them back. The README, `docs/backgrounds.md`, `llms.txt` and the Agent Skill
  name the three (#119).

## [0.3.0] — 2026-10-24

### Fixed

- **Flaps that never landed.** After a cascade, a few cells could keep the previous character on
  the bottom half under the new one on top, with the leaf frozen mid-air — more often on a TV or
  right after a theme change, when frames run late. The flip was a CSS class toggled off and on
  again; two catch-up steps inside one slow frame cancelled out in the style engine, the
  animation never restarted and its landing never ran. Each flip is now its own Web Animation,
  so a landing cannot be lost. Present since 0.1.0.

### Added

- **A picture behind the board** (#94). Display settings `background_image` (`""`, `img:<slug>`
  for an uploaded picture, or `builtin:<name>`), `background_blur` (0–40 px), `background_dim`
  (0–90 %) and `background_fit` (`cover` or `contain`). The board draws the picture on a layer
  under the frame, blurred and dimmed; the frame turns translucent over it and the flaps keep
  their theme. Nothing changes until a picture is set. The live card and the form preview show
  it too.
- **Four backgrounds that ship with the app** (#95): `builtin:terminal` (concrete grey),
  `builtin:wood` (dark walnut), `builtin:gala` (navy with gold bokeh, the formal one) and
  `builtin:paper` (warm off-white), drawn by the project at 1920 × 1080 under
  `app/static/backgrounds/`, each with a thumbnail. `docs/backgrounds.md` is the guide for making
  your own, with `docs/background-template.png` showing the flap boxes for both presets.
- **The background picker** (#96). Under the theme swatches, *Behind the board*: None, the
  four built-ins and every uploaded picture as swatches, an *Upload…* right there, Blur and Dim
  sliders and a Fit choice. The live card and the form preview follow every move before anything
  is saved (a `board:settings` message to the board frame); *Save background* writes the four
  settings in one call, *Clear* takes the picture off and keeps the sliders.
- **Look & feel on the settings page** (#93). The four themes as swatches under the live card;
  one click applies the theme at once and the TV follows on its next poll. The theme select left
  the Display form.
- **Pictures that fit** (#89, #90, #91). A picture has a size on the board: `w` × `h` cells and a
  `fit` (`contain` keeps its shape, `cover` fills and crops, `stretch` fills), set with
  `PATCH /api/images/{slug}` and kept in a small file beside the picture — no table, no
  migration. The upload reads the pixel size from the file's header and suggests the blocks that
  keep the shape (a 743×116 banner → 9×1, 19×2, 28×3). In a message the picture takes its block:
  placed as a word of its own, never cut, the rows beneath pushed down; `{img:slug@6x2}` sizes
  it inline. The board draws the block as a mosaic — every cell is still a flap, each painting
  its slice, so a banner reads across the gaps and assembles with the stagger. A picture
  uploaded before this release is still one cell, exactly as it was. The Images panel (#92) has
  the controls: cells wide × tall, the fit, the suggested sizes as one-click chips, and the
  pixel size next to the file size.
- **A message's own time on the board** (#98, #99, #100). `show_seconds` (5–600) on a message, or
  on `/api/messages/now`, is how long it holds the board when several messages take turns; the
  others keep the display's *Rotate every*. The rotation stays stateless — every screen shows
  the same message at the same second — and the board times its next poll to the end of the slot,
  so short slots flip on time. The message form has a *Show for* field, the row shows the value,
  the live card says *next in N s*. New Alembic revision `0002` adds the column; older databases
  upgrade on start.
- **A timer ring** (#101). The display setting `timer_ring` (*off*, *own*, *all*) draws a small
  translucent countdown in the board's top-right corner while a message's slot runs — for
  messages with their own time, or for every message taking turns. `/api/board/current` carries
  `timer {seconds, remaining, own}` while messages rotate; it is left out of the `ETag`.
- **A line on the sign-in page**, under the token help: this board is free, the mechanical one it
  imitates costs about $3,500, and a fraction of that is worth more to people still rebuilding
  after the June 2026 earthquakes in Venezuela, with a link to Direct Relief's response.

### Changed

- **Uploads may be 5 MB** (#97), up from 512 KB — a phone screenshot of a poster fits. The 413
  says so; the Images panel shows a file's size in MB past 1 MB.
- **The sign-in page says where the token is, as commands.** One labelled terminal line per way
  of running the board (the container, a `uv run` server, the first-boot log), each with a Copy
  button, and a note that every server has its own token. The old sentence offered
  `pbcopy < data/api_token` next to the container line, which pastes a dev server's token into
  the container's sign-in on a machine that has run both.

## [0.2.0] — 2026-10-21

### Added

- **The settings page shows the TV** (#62, #63, #64, #65, #74). The live board sits in a card at
  the top of the settings page (the real board page in a frame, so every theme and preset is
  exact), the message form previews what you type in the same renderer, every message row has
  an enable switch, the board's HUD gains a ⚙ button (and the `s` key) that opens the settings
  page, and the page had an accessibility pass: named controls, live regions, a focus order
  that follows the layout, and a layout that holds on a phone.
- **A name for the board** (#80, #81, #82). `DEPARTUREBOARD_HOST=dboard.localhost` (or
  `board.local`, or a name your router resolves) names the board: the settings page lists
  **Your board is at** with the name, the address you are using and the addresses the server
  sees, each with a Copy button; the integrate page pre-fills the name; the self-signed
  certificate carries it. `docs/tv-setup.md` says what resolves where. The Cast button now asks
  the browser whether the page is a secure context instead of guessing from the URL, so on
  `http://dboard.localhost` it casts without a certificate.

### Changed

- **README: a tour of the settings page** (#71, #72, #73). Screenshots of every panel (captured by
  a rig from fixture data, so they can be retaken), a short paragraph each, a side-by-side GIF of
  a message going from the form to the board, and the integrate page pictured. Casting feedback
  is invited in #79.

### Added

- **Cast to the TV** (#67, #70). A Cast button on the settings page (next to *On the TV*) and on
  the board's HUD (beside ⚙): on an `https://` board in Chrome or Edge it opens the TV picker and
  presents the board (pictures streamed from the computer, which stays on), shows the casting
  state, and reconnects after a reload. Elsewhere it opens a panel with the two ways: turn on
  HTTPS, or Chrome's ⋮ → Cast → *Cast tab*. `docs/tv-setup.md` gains *Casting from a laptop*.
- **Optional HTTPS** (#68). `DEPARTUREBOARD_TLS=self-signed` makes a certificate on first boot
  (kept under `/data/tls/`, valid for `DEPARTUREBOARD_TLS_HOSTS` plus the container's own names)
  and serves `https://` on the same port, so a TV browser can take the native wake lock.
  `DEPARTUREBOARD_TLS_CERT` / `DEPARTUREBOARD_TLS_KEY` use your own pair. Off by default; without
  it nothing changes. The login cookie is `Secure` when served over https. The container starts
  through `python -m app`.

## [0.1.0] — 2026-10-21

The first release: a board anyone can run tonight. It exists because
[@feltbykraft](https://www.instagram.com/feltbykraft/) asked for a split-flap board people
can afford — *"come find me when that exists."*

### Added

- **The board** (`/`): a split-flap display that flips, cascades left to right and clicks.
  Two presets, Compact (6 × 22, for a 42–48" TV) and Large (8 × 28, for 55–77"), or a custom
  grid; an animation setting from instant to the full mechanical pace; four themes (Classic
  black, Walnut, Arctic white, Midnight) with bundled fonts; a synthesized click with volume
  and mute; a fullscreen button that keeps the TV awake (Screen Wake Lock where the browser
  allows it, a silent video otherwise); colour chips, emoji and uploaded pictures as flaps.
- **The settings page** (`/settings`): write messages, preview them, schedule them (a window,
  a daily or weekly repeat), set the preset, theme, animation, sound and idle text, upload
  pictures. Behind a bearer token generated on first boot.
- **The API**: everything the settings page does. `POST /api/messages/now` takes a JSON or a
  plain-text body for one-line integrations; `GET /api/board/current` is public and cheap to
  poll with ETag. Swagger at `/docs`, written to be read.
- **The integrate page** (`/integrate`): copy-paste `curl` lines pre-filled with your own host
  and token, one per task, with the expected response under each.
- **The agent bundle** under `integrations/`: runnable `curl` examples, an Agent Skill
  (`SKILL.md`, read by Claude Code, Hermes Agent and others), `llms.txt` (served at
  `/llms.txt`) and a Hermes walkthrough.
- **One command**: `docker compose up -d` pulls `ghcr.io/cmldexter/departureboard` (amd64 and
  arm64, so a Raspberry Pi can host the board) and serves on port 8080; SQLite in a named
  volume; a non-root container built from a digest-pinned base.
- **Docs**: a TV setup guide (`docs/tv-setup.md`) covering laptops, Raspberry Pi kiosks, Fire
  TV, Google TV, built-in TV browsers and Apple TV, with the keep-awake matrix.

### Security

- `main` is protected: every change is a reviewed PR; CI is required.
- Dependencies are locked (`uv.lock`), the base image and `uv` are pinned by digest, GitHub
  Actions are pinned by commit, Dependabot proposes bumps.
- The release image carries a build provenance attestation:
  `gh attestation verify oci://ghcr.io/cmldexter/departureboard:0.1.0 --owner cmldexter`.
- The board endpoint and the pictures are public so the TV never holds a secret; everything
  else needs the token. CORS is off unless origins are listed.

[Unreleased]: https://github.com/cmldexter/DepartureBoard/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/cmldexter/DepartureBoard/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/cmldexter/DepartureBoard/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cmldexter/DepartureBoard/releases/tag/v0.1.0
