<div align="center">
  <h1>DepartureBoard</h1>
  <p><b>An open-source split-flap departure board for any TV. One command, one board.</b></p>
  <img src="docs/media/board-demo.gif" alt="The board flipping from a departures list to a message, one column after another" width="800">
  <p><sub>The Compact preset (6 × 22) running the built-in demo — <code>http://&lt;host&gt;:8080/?demo</code></sub></p>
</div>

---

The real split-flap boards start above $2,000. Most people who want one want the look, the
clicks and the ritual of a message flipping into place — and a TV on the wall is already paid
for. DepartureBoard gives you that: a browser page that behaves like the board, and a settings
page to put messages on it and schedule them.

## Quick start

```bash
git clone https://github.com/cmldexter/DepartureBoard.git
cd DepartureBoard
docker compose up -d
```

That pulls the published image (`ghcr.io/cmldexter/departureboard`, amd64 and arm64, so a
Raspberry Pi can host it) and serves on port 8080. Then:

- On the TV, open `http://<this machine>:8080` and press the **⛶** button: fullscreen, clicks on,
  screen kept awake. The TV side, device by device, is in [**docs/tv-setup.md**](docs/tv-setup.md).
- On your laptop, open `http://<this machine>:8080/settings`. The token it asks for was printed
  in the server log on first boot. To get it again without reading logs:

  ```bash
  docker compose exec departureboard cat /data/api_token            # the container
  pbcopy < data/api_token                                            # a `uv run` dev server, macOS: straight to the clipboard
  xclip -selection clipboard < data/api_token                        # Linux
  ```

Optional: copy `.env.example` to `.env` to change the port, set your timezone, bring your own
token, **give the board a name** (`DEPARTUREBOARD_HOST=dboard.localhost`; what a name does and
does not do is in the [TV guide](docs/tv-setup.md#giving-the-board-a-name)), or **pin a version**
for a board on a wall (`DEPARTUREBOARD_IMAGE=ghcr.io/cmldexter/departureboard:0.2.0`).
Every image is built by [a public workflow](.github/workflows/release.yml) with a provenance
attestation: `gh attestation verify oci://ghcr.io/cmldexter/departureboard:0.2.0 --owner cmldexter`.

To build from source instead: `docker compose -f compose.yaml -f compose.dev.yaml up --build`,
or `uv sync && uv run fastapi dev app/main.py` for a dev server on port 8000.

## What you get

- **The board** (`/`) — two display presets, **Compact** (6 × 22, for a 42–48" TV) and
  **Large** (8 × 28, for 55–77"), the flip animation and the click, a slider from "instant" to
  the full mechanical pace, mute, four themes, colour chips, emoji and your own pictures as
  flaps, and a fullscreen button that keeps the TV awake.
- **The settings page** (`/settings`) — write messages, preview them, schedule them (a window,
  a daily or weekly repeat), choose the preset, theme, animation and sound, upload pictures.
- **Cast to the TV** — a Cast button on the settings page and the board sends the board to a
  Chromecast or Google TV from Chrome (the board on `https://`, one line in `.env`); Chrome's own
  Cast menu works on any board. The laptop stays on; a stick or a Pi runs the board alone.
- **The API** — everything the settings page does. Swagger at `/docs`.
- **The integrate page** (`/integrate`) — copy-paste `curl` lines pre-filled with your own host
  and token, so your calendar, your home automation or your agent can post to the board tonight.

## The settings page

Everything on the board comes from `/settings`: one page, on a laptop or a phone, signed in with
the token the first boot printed.

<img src="docs/media/settings-live.png" alt="The top of the settings page: the board as the TV shows it, a Cast button, and the line naming the live message" width="800">

**On the TV.** The page opens with the board as the TV sees it, live, and the message that is
showing now. **Cast to TV** sends the board to a Chromecast or Google TV from Chrome (with the
board on `https://`; otherwise the button explains the two ways). Casting is new and we have one
TV to try it on: tell us how it holds up for you in [#79](https://github.com/cmldexter/DepartureBoard/issues/79).

<img src="docs/media/settings-messages.png" alt="The messages table: a switch and a state badge, the text, when it shows, Edit and Delete" width="800">

**Messages.** One row each: a switch that turns the message off and on without opening it, its
state (live, scheduled, expired, disabled), the text, when it shows, Edit and Delete.

<img src="docs/media/settings-form.png" alt="The edit form with the preview rendered as the board, the schedule fields and the capacity line" width="800">

**Writing one.** The preview is the board itself: your theme, the chips, emoji and pictures,
and a line that says how many cells the message uses and what cannot be shown. One line per
row, or let it wrap. Three kinds of schedule: a window from one date and time to another, every
day between two times, or chosen weekdays between two times (a window that ends before it starts
crosses midnight). When several messages are live the highest priority wins and equals take
turns, each for the display's *Rotate every* unless the message sets its own *Show for* — a
birthday line can hold the board for a minute while a reminder takes ten seconds. The optional
timer ring, a small translucent countdown in the board's corner, shows how long the current
message has left.

<img src="docs/media/form-to-tv.gif" alt="Typing a message on the settings page; on the next poll the board flips to it" width="800">

<img src="docs/media/settings-display.png" alt="The display form: preset, animation, sound, theme, idle text, poll and rotate intervals" width="800">

**Look & feel.** Four theme swatches under the live card; click one and the TV follows on its
next poll, nothing to save.

**Display.** The preset for your TV size (Compact 6 × 22, Large 8 × 28, or your own), the
animation pace from instant to the mechanical click, sound and volume, the idle text
for when nothing is live, how often the TV polls, the default time each message gets when
several take turns, and whether the timer ring shows (off, only for messages with their own
time, or for every message taking turns).

<img src="docs/media/settings-images.png" alt="The images panel: upload a picture, get a token, give it a size in cells" width="800">

**Pictures.** Upload a PNG, JPEG, GIF or WebP and it becomes a token like `{img:cat}`. Give the
picture a size in cells on the panel — a wide banner reads best across a row — and it keeps its
shape inside that block (or fills it, or stretches, your choice). The panel suggests the sizes
that keep the shape from the file's own pixel size. In a message the picture takes its block,
pushing the lines beneath it down; `{img:cat@9x1}` sizes it for one message only.

**The token.** At the bottom of the page, generated on first boot (or set with
`DEPARTUREBOARD_API_TOKEN`). The TV needs none; the settings page and every write to the API do.

<img src="docs/media/settings-phone.png" alt="The messages table on a phone" width="300">

The page works on a phone. For the TV side, read [docs/tv-setup.md](docs/tv-setup.md); to
post from a script, a calendar or an agent, open `/integrate` (pictured below).

## Themes

| | |
|---|---|
| **Classic black** ![Classic black](docs/media/theme-classic-black.png) | **Walnut** ![Walnut](docs/media/theme-walnut.png) |
| **Arctic white** ![Arctic white](docs/media/theme-arctic-white.png) | **Midnight** ![Midnight](docs/media/theme-midnight.png) |

Each theme is one stylesheet under `app/static/themes/` with its font bundled, so the board
works on a LAN with no internet. A new theme is a welcome pull request.

Behind any theme can sit a picture: four ship with the app (*terminal*, *wood*, *gala*, *paper*)
and your own uploads work too, blurred and dimmed to taste. [docs/backgrounds.md](docs/backgrounds.md)
has the four-click recipe, the safe area and a 1920 × 1080 template.

## Bring your own integration

<img src="docs/media/integrate.png" alt="The integrate page: curl lines pre-filled with this host and token, with a Test it button" width="800">

We will not add a calendar panel, a chat bot or a weather widget to the UI. The board has an
API, and we ship three things so that your own agent, script or automation can drive it:

1. **The integrate page** — `http://<this machine>:8080/integrate`, behind the same token as
   settings: copy-paste `curl` lines pre-filled with your host and your token, one per task
   (post now, a window, daily, weekly, a picture, list, delete, the display), with the expected
   response under each. The complete reference is `/docs` (Swagger, generated from the code).
2. **The shortest call** — `POST /api/messages/now` takes a plain-text body, so a cron line,
   Home Assistant's `rest_command` or an n8n node is one line:

   ```bash
   curl -X POST http://<this machine>:8080/api/messages/now \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: text/plain" --data 'DINNER AT 7'
   ```
3. **The agent bundle** under [`integrations/`](integrations/): runnable `curl` examples, an
   **Agent Skill** (`SKILL.md`, the format Claude Code, Hermes Agent and others read) and
   `llms.txt` (also served at `/llms.txt`).

That keeps the app small and keeps your integrations yours. CORS is off; set
`DEPARTUREBOARD_CORS_ORIGINS` to a comma-separated list of origins if a browser app elsewhere
must call the API. Share what you build in
[Discussions → Show and tell](https://github.com/cmldexter/DepartureBoard/discussions/categories/show-and-tell).

## Requests and bugs

Issues are open. Feature requests are welcome **within reason**: the board stays two pages,
needs no configuration to run, and starts from one command. Bigger ideas start as a
[discussion](https://github.com/cmldexter/DepartureBoard/discussions/categories/ideas).
[CONTRIBUTING.md](CONTRIBUTING.md) has three examples each way of what fits and what does not.
Releases are listed in [CHANGELOG.md](CHANGELOG.md).

## Origin

This exists because [**@feltbykraft**](https://www.instagram.com/feltbykraft/) asked for it in a
thread about the real boards — *"come find me when that exists."* It exists.

## License

[GPL-3.0](LICENSE).
