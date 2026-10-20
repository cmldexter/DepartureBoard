# Putting the board on a TV

This guide grows with the project. The short version today:

1. Run `docker compose up --build` on any machine that stays on (a laptop, a mini PC, a Raspberry Pi).
2. Find that machine's address on your network (`hostname -I` on Linux, System Settings → Network on macOS).
3. On the TV, open `http://<address>:8080` in a browser and use the fullscreen button.

What works best, in order:

| Setup | Notes |
|---|---|
| A laptop or mini PC over HDMI | Easiest. Any modern browser. |
| Raspberry Pi in Chromium kiosk mode | Most reliable for a board on a wall. Autostart instructions coming. |
| Fire TV / Google TV stick with a browser | Works; keep-awake uses the video fallback. |
| The TV's built-in browser | Old and sleepy on most sets. Try it; expect to need a stick. |
| Apple TV | No browser — AirPlay the page from a Mac or iPhone. |

A note on staying awake: browsers only allow the Screen Wake Lock on HTTPS or `localhost`, so
over a plain `http://192.168…` address the board keeps the screen on by playing a silent, muted
video — the same trick video sites use. It works on every browser we have tried that can play
video at all.
