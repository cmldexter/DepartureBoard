<div align="center">
  <h1>DepartureBoard</h1>
  <p><b>An open-source split-flap departure board for any TV. One command, one board.</b></p>
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
docker compose up --build
```

Then:

- On the TV, open `http://<this machine>:8080` and go fullscreen.
- On your laptop, open `http://<this machine>:8080/settings`. The token it asks for was printed
  in the server log on first boot — `docker compose logs departureboard`.

Optional: copy `.env.example` to `.env` to change the port, set your timezone, or bring your own token.

## What you get

- **The board** (`/`) — two display presets, **Compact** (6 × 22, for a 42–48" TV) and
  **Large** (8 × 28, for 55–77"), the flip animation and the click, a slider from "instant" to
  the full mechanical pace, mute, a handful of themes (frame, background, type), and a
  fullscreen button that keeps the TV awake.
- **The settings page** (`/settings`) — write messages, schedule them (a window, a daily or
  weekly repeat), choose the preset, theme, animation and sound.
- **The API** — everything the settings page does. Swagger at `/docs`.
- **The integrate page** (`/integrate`) — copy-paste `curl` lines pre-filled with your own host
  and token, so your calendar, your home automation or your agent can post to the board tonight.

> Status: the project is being built in the open. The board skeleton, the token and the
> container are here; the animation, the organizer and the integrate page land in the next
> releases. Follow the [milestones](https://github.com/cmldexter/DepartureBoard/milestones).

## Bring your own integration

We will not add a calendar panel, a chat bot or a weather widget to the UI. The board has an
API, a page that writes the `curl` for you, and an **Agent Skill** plus examples under
[`integrations/`](integrations/) so that your own agent, script or automation can drive it.
That keeps the app small and keeps your integrations yours. Share what you build in
[Discussions](https://github.com/cmldexter/DepartureBoard/discussions).

## Requests and bugs

Issues are open. Feature requests are welcome **within reason**: the board stays two pages,
needs no configuration to run, and starts from one command. Bigger ideas start as a discussion.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## Origin

This exists because [**@feltbykraft**](https://www.instagram.com/feltbykraft/) asked for it in a
thread about the real boards — *"come find me when that exists."* It exists.

## License

[GPL-3.0](LICENSE).
