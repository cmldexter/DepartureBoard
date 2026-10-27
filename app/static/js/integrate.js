// The integrate page: curl lines filled with this host and this install's token.
(() => {
  "use strict";
  const main = document.querySelector("main.integrate");
  if (!main) return;
  const TOKEN = main.dataset.token;
  const hostInput = document.getElementById("host");
  const reveal = document.getElementById("reveal");

  const base = () => hostInput.value.trim().replace(/\/+$/, "") || main.dataset.base;
  const tok = (show) => (show ? TOKEN : "$TOKEN");

  // Each snippet: title, the curl line (a function of host + token), and what comes back.
  const SNIPPETS = {
    now: {
      title: "Post a message now (JSON)",
      curl: (h, t) => `curl -X POST ${h}/api/messages/now \\
  -H "Authorization: Bearer ${t}" \\
  -H "Content-Type: application/json" \\
  -d '{"text":"DINNER AT 7\\nBRING A COAT"}'`,
      response: `201 Created · {"id": 12, "state": "live", "priority": 1, "rows": [["D","I","N","N","E","R"," ","A","T"," ","7", …]], "used": 23, "capacity": 132, …}`,
    },
    "now-plain": {
      title: "Post a message now (plain text)",
      curl: (h, t) => `curl -X POST ${h}/api/messages/now \\
  -H "Authorization: Bearer ${t}" \\
  -H "Content-Type: text/plain" \\
  --data 'BACK IN 10 MIN {orange}'`,
      response: `201 Created · the same message object. Made for Home Assistant's rest_command, n8n, a cron line.`,
    },
    window: {
      title: "Show it between two times",
      curl: (h, t) => `curl -X POST ${h}/api/messages \\
  -H "Authorization: Bearer ${t}" \\
  -H "Content-Type: application/json" \\
  -d '{"text":"HAPPY BIRTHDAY NICK {yellow}","starts_at":"${iso(7)}","ends_at":"${iso(23)}","priority":5,"show_seconds":60}'`,
      response: `201 Created · "state": "scheduled" until starts_at, then "live", then "expired". show_seconds: it holds the board a minute per turn when equals rotate (the default is the display's rotate_seconds).`,
    },
    daily: {
      title: "Every day between two times",
      curl: (h, t) => `curl -X POST ${h}/api/messages \\
  -H "Authorization: Bearer ${t}" \\
  -H "Content-Type: application/json" \\
  -d '{"text":"STANDUP 09:30 {blue}","repeat":"daily","repeat_start":"09:00","repeat_end":"10:00"}'`,
      response: `201 Created · live 09:00–10:00 every day in the server's timezone.`,
    },
    weekly: {
      title: "On weekdays only",
      curl: (h, t) => `curl -X POST ${h}/api/messages \\
  -H "Authorization: Bearer ${t}" \\
  -H "Content-Type: application/json" \\
  -d '{"text":"BINS OUT TONIGHT","repeat":"weekly","repeat_days":4,"repeat_start":"18:00","repeat_end":"23:00"}'`,
      response: `201 Created · Wednesdays 18:00–23:00 (repeat_days 4 = Wed).`,
    },
    image: {
      title: "Upload a picture, then use its token",
      curl: (h, t) => `curl -X POST ${h}/api/images \\
  -H "Authorization: Bearer ${t}" \\
  -F "file=@cat.png" -F "slug=cat"
# → {"slug":"cat","url":"/images/cat","token":"{img:cat}", …}
curl -X POST ${h}/api/messages/now \\
  -H "Authorization: Bearer ${t}" \\
  -H "Content-Type: text/plain" \\
  --data 'HELLO {img:cat}'`,
      response: `201 Created on each. PNG, JPEG, GIF or WebP up to 5 MB; the same slug replaces.`,
    },
    qr: {
      title: "A QR code the server makes, drawn whole so a phone scans it",
      curl: (h, t) => `curl -X POST ${h}/api/images/qr \\
  -H "Authorization: Bearer ${t}" \\
  -H "Content-Type: application/json" \\
  -d '{"slug":"menu","data":"https://example.com/menu"}'
# → {"slug":"menu","token":"{img:menu}","w":4,"h":3,"solid":true,"qr":{"data":"https://example.com/menu"}, …}
curl -X POST ${h}/api/messages/now \\
  -H "Authorization: Bearer ${t}" \\
  -H "Content-Type: text/plain" \\
  --data $'SCAN FOR THE MENU\\n{img:menu}'`,
      response: `201 Created on each; the same slug again remakes the code (200) and keeps its size. 4 × 3 cells scan from the sofa on Compact.`,
    },
    list: {
      title: "What is live right now",
      curl: (h, t) => `curl ${h}/api/messages?state=live \\
  -H "Authorization: Bearer ${t}"`,
      response: `200 · [ {"id": 12, "text": "…", "state": "live", …}, … ] — also ?state=scheduled, expired, disabled, or no filter.`,
    },
    delete: {
      title: "Remove a message",
      curl: (h, t) => `curl -X DELETE ${h}/api/messages/12 \\
  -H "Authorization: Bearer ${t}"`,
      response: `204 No Content. Or disable it and keep it: PATCH /api/messages/12 with {"enabled": false}.`,
    },
    preset: {
      title: "Change the display",
      curl: (h, t) => `curl -X PATCH ${h}/api/settings \\
  -H "Authorization: Bearer ${t}" \\
  -H "Content-Type: application/json" \\
  -d '{"grid_preset":"large","theme":"walnut","animation":80}'`,
      response: `200 · the full settings object. Presets: compact (6×22), large (8×28), custom with rows 4–10 and cols 16–36.`,
    },
    board: {
      title: "What the board shows now",
      curl: (h) => `curl -i ${h}/api/board/current`,
      response: `200 · {"stamp": "…", "message_id": 12, "rows": [[…]], "settings": {…}} with an ETag; send it back as If-None-Match for 304.`,
    },
  };

  function iso(hour) {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    d.setHours(hour, 0, 0, 0);
    const pad = (n) => String(n).padStart(2, "0");
    const off = -d.getTimezoneOffset();
    const sign = off >= 0 ? "+" : "-";
    const a = Math.abs(off);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00:00${sign}${pad(Math.floor(a / 60))}:${pad(a % 60)}`;
  }

  function render() {
    const show = reveal.checked;
    document.querySelectorAll(".snippet").forEach((el) => {
      const s = SNIPPETS[el.dataset.kind];
      if (!s) return;
      if (!el.firstChild) {
        el.innerHTML = `<div class="row"><h3></h3><button type="button" class="link copy"><svg class="icon" aria-hidden="true"><use href="#lucide-copy"/></svg> Copy</button></div><pre class="code" tabindex="0"></pre><p class="muted response"></p>`;
        el.querySelector("h3").textContent = s.title;
        el.querySelector(".response").textContent = s.response;
        el.querySelector(".copy").addEventListener("click", async () => {
          // The clipboard always gets the real token: a pasted line must work as is.
          const text = s.curl(base(), TOKEN);
          try {
            await navigator.clipboard.writeText(text);
            flash(el.querySelector(".copy"), "Copied (with your token)");
          } catch {
            flash(el.querySelector(".copy"), "Select and copy the text");
          }
        });
      }
      el.querySelector("pre").textContent = s.curl(base(), tok(show));
    });
  }

  function flash(btn, text) {
    const old = btn.textContent;
    btn.textContent = text;
    setTimeout(() => (btn.textContent = old), 2500);
  }

  hostInput.addEventListener("input", render);
  reveal.addEventListener("change", render);

  document.getElementById("test").addEventListener("click", async () => {
    const out = document.getElementById("test-result");
    out.textContent = "…";
    try {
      const r = await fetch(`${base()}/api/health`, { cache: "no-store" });
      const j = await r.json();
      out.textContent = r.ok ? `OK — DepartureBoard ${j.version} answers at ${base()}` : `HTTP ${r.status}`;
    } catch (e) {
      out.textContent = `No answer from ${base()} (from this browser). The lines may still work from another machine on the LAN.`;
    }
  });

  render();
})();
