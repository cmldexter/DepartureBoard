# Putting the board on a TV

The server side is one command on any machine that stays on. The TV side is where the real
problems live: finding the address, going fullscreen, and keeping the screen awake. This guide
covers each device we know about. If yours is missing, or a section is wrong for your model,
[open an issue](https://github.com/cmldexter/DepartureBoard/issues/new/choose) or post in
[Discussions](https://github.com/cmldexter/DepartureBoard/discussions) with what worked.

## The one-minute version

1. On a machine that stays on (a laptop, a mini PC, a NAS, a Raspberry Pi):
   `git clone https://github.com/cmldexter/DepartureBoard.git && cd DepartureBoard && docker compose up -d`
2. Find that machine's address on your network (below).
3. On the TV, open `http://<address>:8080` in a browser and press the **⛶** button in the
   bottom-right corner. The board goes fullscreen, the clicks turn on, and the screen stays awake.
4. On your laptop or phone, open `http://<address>:8080/settings` and write a message.

The board says `SET UP AT /SETTINGS` until a message is live. It refreshes itself every few
seconds; nothing on the TV ever needs a reload.

## Finding the address

The TV needs the address of the machine running the server, not `localhost`.

| Server runs on | Find it with |
|---|---|
| Linux (incl. Raspberry Pi) | `hostname -I` |
| macOS | `ipconfig getifaddr en0` (Wi-Fi) or `en1`; or System Settings → Network |
| Windows | `ipconfig` → "IPv4 Address" |
| A NAS or home server | Its admin page shows it |

Two things make this painless:

- **Give the server machine a fixed address** in your router (a "DHCP reservation"), so the
  address you type into the TV once stays right.
- **Type the address once, then bookmark it** or set it as the browser's home page. TV remotes
  are terrible keyboards; a short hostname (`http://board.local:8080`) works on devices that
  resolve `.local` names (Macs, iPhones, most Android TV and Fire TV sticks), but a plain IP
  address works everywhere.

The port is 8080 unless you changed `DEPARTUREBOARD_PORT` in `.env`.

## Fullscreen and staying awake

Press **⛶** once. It is the one click the page needs: browsers only allow sound and fullscreen
after a user gesture. The status line that appears for a moment tells you which keep-awake path
the browser took:

| Status | What happened |
|---|---|
| *Screen stays awake* | The browser granted the **Screen Wake Lock**. Only possible on `https://` or on `localhost`. |
| *Screen stays awake (video)* | The browser could not, or would not, give the wake lock (the normal case over `http://192.168…`), so the board plays a **silent, muted, looped video** — the trick video sites use. The screen stays on as long as the page is in front. |
| *Could not keep the screen awake* | Neither worked; the browser blocked muted autoplay. Keep the screen on from the device's own settings (below) or use another browser. |
| *… use the browser's fullscreen* | The browser has no Fullscreen API; use its own fullscreen (often a menu item or `F11`) and the board hides its chrome. |

### The keep-awake matrix

| Where the board is open | Path | Notes |
|---|---|---|
| Any browser at `http://<address>:8080` over the LAN | video | The common case. Works on every browser we have tried that plays video at all. |
| Chrome / Edge / Chromium 84+, Safari 16.4+, Firefox 126+ at `http://localhost:8080` or over HTTPS | wake lock | The browser-native way. A Pi that hosts the board *and* shows it on `localhost` gets this path. |
| Chromium in **kiosk mode** (`--kiosk`) | wake lock or video, as above | A headed kiosk window takes the lock on `localhost`; the page is already fullscreen without the button. Headless Chromium refuses the lock. |
| A TV's built-in browser (Samsung, LG) | video, sometimes none | Old engines; some block muted autoplay. Expect to need a stick. |

Two things the page cannot control:

- **The TV's own sleep and eco timers.** Most sets have an "auto power off", "eco" or "no
  signal / no activity" timer that turns the TV off after a few hours regardless of what the
  input is doing. Turn it off (or set it to the maximum) in the TV's settings.
- **The screensaver of the stick or box** the browser runs on. Fire TV, Google TV and Android
  TV have their own; set it to the longest interval the device allows, or "never" where offered.

If you want the TV to also *turn itself on and off* at set times, use the TV's own on/off timer
or a smart plug. The board resumes where it was.

## Devices

### A laptop or mini PC over HDMI (easiest)

Any modern browser. Open the address, press **⛶**. The browser keeps the display awake; the
operating system's own sleep settings still apply, so set "turn display off" to never and, on a
laptop, "sleep when lid closed" to never if you close it.

To start straight into the board, launch the browser in kiosk mode:

```bash
# macOS
open -na "Google Chrome" --args --kiosk --autoplay-policy=no-user-gesture-required http://<address>:8080
# Linux
chromium --kiosk --noerrdialogs --disable-infobars --autoplay-policy=no-user-gesture-required http://<address>:8080
# Windows (PowerShell)
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk --autoplay-policy=no-user-gesture-required http://<address>:8080
```

`--kiosk` is already fullscreen; `--autoplay-policy=no-user-gesture-required` lets the
keep-awake video start without a click. The click on **⛶** is still what turns the sound on.

### Raspberry Pi in kiosk mode (most reliable for a board on a wall)

A Pi 4 or 5 with Raspberry Pi OS (desktop) and Chromium is the setup we recommend for
something that should just stay up for months. The Pi can also **host** the board: the image
is built for arm64, so `docker compose up -d` on the Pi works, and the browser can then open
`http://localhost:8080` and get the native wake lock.

1. Install Docker (`curl -fsSL https://get.docker.com | sh`, then log out and in), clone the
   repo and `docker compose up -d`. Or host the board elsewhere and only show it on the Pi.
2. Disable screen blanking: `sudo raspi-config` → Display Options → Screen Blanking → No.
3. Autostart Chromium in kiosk mode on login. On Raspberry Pi OS **Bookworm or later** (the
   labwc / Wayland desktop) add a line to `~/.config/labwc/autostart`:

   ```
   chromium --kiosk --noerrdialogs --disable-infobars --autoplay-policy=no-user-gesture-required --start-fullscreen http://localhost:8080 &
   ```

   On older releases (LXDE / X11) put the same command in
   `~/.config/lxsession/LXDE-pi/autostart` prefixed with `@`. Set the Pi to auto-login to the
   desktop (`raspi-config` → System Options → Boot / Auto Login).
4. Hide the mouse pointer: install `unclutter` (`sudo apt install unclutter`) and add
   `unclutter -idle 1 &` to the same autostart file.
5. Reboot. The board comes up without anyone touching it. Plug in a mouse once and click
   **⛶** if you want the clicks; otherwise it runs silent.

A Pi Zero or Pi 3 can show the board but the cascade is noticeably slower; the Large preset
(8 × 28) is where it starts to matter.

### Fire TV / Fire TV Stick

Amazon Silk is the built-in browser and is Chromium-based: open the address, press **⛶**, and
the board goes fullscreen with the video keep-awake. Then:

- **Screensaver:** Settings → Display & Sounds → Screensaver → Start Time → set it as long as
  the device allows (some models offer *Never*). Fire TV also sleeps after 20 minutes without
  input on some models; Settings → Display & Sounds → Sleep (where present) → never, or wake it
  with the remote.
- **Autostart:** Silk does not start on boot. For a board that survives a power cut, sideload a
  kiosk browser (Fully Kiosk Browser is the common choice; install it with the Downloader app)
  and point it at the address: it launches on boot, keeps the screen on itself, and hides its
  own chrome.

### Google TV / Android TV / Chromecast with Google TV

There is no browser out of the box. Sideload one (TV Bro is open source and built for remotes;
Fully Kiosk Browser does the kiosk job as on Fire TV), open the address, press **⛶**. Settings →
System → Screen saver → "When to start" → the longest interval offered, or "Energy saver" →
"Turn off display" → never on devices that have it.

### The TV's built-in browser (Samsung Tizen, LG webOS, Android TV sets)

Try it: open the address, press **⛶**, see what the status line says. On recent sets it works
with the video path. On older ones the engine is years old, muted autoplay is blocked, and the
set sleeps anyway. If it does not stay up overnight, a stick or a Pi is cheaper than the time
you will spend. Either way turn off *Auto Power Off* / *Eco Solution* / *Auto Off* in the
set's general settings; they turn the TV off after four hours without a remote press.

### Apple TV

No browser, so mirror the page from a Mac, iPhone or iPad with AirPlay (Control Center → Screen
Mirroring), open the address in Safari or Chrome there and press **⛶**. The wake lock runs on
the device doing the mirroring; keep it plugged in and set its auto-lock to never. A stick in
the TV's other HDMI port is the better long-term setup.

## Which preset

| TV | Preset | Grid |
|---|---|---|
| 42–48" | Compact | 6 × 22 |
| 55–77" | Large | 8 × 28 |
| Anything else | Custom | 4–10 rows, 16–36 columns |

Choose on the settings page; the TV re-lays the board on the next refresh. Themes are a matter
of the room: **Classic black** and **Midnight** for a dark wall, **Walnut** for a wooden
console, **Arctic white** for a bright kitchen.

## Troubleshooting

| What you see | What it means |
|---|---|
| `SET UP AT /SETTINGS` | No message is live right now. Write one, or check its schedule. |
| A 404 page | Wrong port, or something else answers on 8080 on that machine. Check `DEPARTUREBOARD_PORT`. |
| A small red dot, bottom-left | The board cannot reach the server; it keeps the last board and retries with a backoff. |
| No clicks | Sound needs the one click on **⛶**. Also check *Sound* on the settings page. |
| The TV turned off anyway | The TV's own eco / auto-off timer or the stick's screensaver. See *Fullscreen and staying awake*. |
| A message is late by a few seconds | The TV polls every few seconds (`poll_seconds` on the settings page). That is expected. |
