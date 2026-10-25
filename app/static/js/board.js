// The board: a grid of split-flap cells, a refresh animation that flips every changed cell
// through the sequence to its target with the columns cascading left to right, and the
// animation setting (0 = instant, 1 = fastest, 100 = the pace of a mechanical board).
//
// Data arrives as { rows: ["…", …], settings: { rows, cols, animation } } — the shape of
// GET /api/board/current. Until the board polls it, ?demo feeds built-in messages.
//
// Framed by the settings page (same origin only): `?embed` polls as usual and reports what it
// shows; `?embed&preview` never polls and paints what the parent posts. Messages:
//   parent → board   board:show { rows, settings }   (preview)   board:refresh   (live)
//   board → parent   board:ready { preview }         board:current { message_id, stamp, timer }
//
// While messages rotate, /api/board/current carries `timer` { seconds, remaining, own }: the
// board counts the rest down locally (the ring in the corner, when the setting asks for it) and
// times its next poll to land just after the slot ends, so short slots flip on time.
//
// Exposes window.Board = { show, applySettings, settings }. Plain script, no modules.
(() => {
  "use strict";
  const Flap = window.Flap;
  const boardEl = document.getElementById("board");
  const frameEl = boardEl && boardEl.closest(".frame");
  const configEl = document.getElementById("board-config");
  if (!Flap || !boardEl || !frameEl || !configEl) return;

  const config = JSON.parse(configEl.textContent);
  const reducedMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Pace. animation 100 → 50 ms per step (normal), 1 → 10 ms; 0 → no steps at all.
  // Columns start 0.7 of a step apart. A cell's longest trip is a lap of the sequence
  // (64 steps, e.g. A → blank): at normal pace 3.2 s plus 0.7 s of cascade on 22 columns.
  const STEP_MS_MIN = 10;
  const STEP_MS_MAX = 50;
  const STAGGER_RATIO = 0.7;

  const settings = { rows: 0, cols: 0, animation: 60, theme: "classic-black", timer_ring: "off" };
  const BG_KEYS = ["background_image", "background_blur", "background_dim", "background_fit"];
  let cells = []; // row-major cell records
  let target = []; // row-major sequence indices the board is heading to
  let specials = []; // row-major token cells ({emoji} / {img}) shown once a cell lands, or null
  let active = new Map(); // cell position → { nextAt }
  let rafId = 0;
  let shownSomething = false; // has any non-blank content been shown since load?

  function stepMs(animation) {
    const a = Math.max(0, Math.min(100, Number(animation) || 0));
    if (a === 0) return 0;
    return STEP_MS_MIN + ((a - 1) / 99) * (STEP_MS_MAX - STEP_MS_MIN);
  }

  function instant() {
    return reducedMotion || stepMs(settings.animation) === 0;
  }

  // Lay the grid out for rows × cols; adopt the server-rendered cells when the size matches.
  function layout(rows, cols) {
    frameEl.style.setProperty("--rows", rows);
    frameEl.style.setProperty("--cols", cols);
    const existing = boardEl.querySelectorAll(".cell");
    cells = [];
    if (existing.length === rows * cols) {
      existing.forEach((el) => cells.push(Flap.adoptCell(el)));
    } else {
      boardEl.textContent = "";
      const frag = document.createDocumentFragment();
      for (let i = 0; i < rows * cols; i += 1) {
        const cell = Flap.buildCell(Flap.BLANK);
        cells.push(cell);
        frag.appendChild(cell.el);
      }
      boardEl.appendChild(frag);
    }
    settings.rows = rows;
    settings.cols = cols;
    target = cells.map((c) => c.current);
    specials = cells.map((c) => c.special);
    active = new Map();
  }

  // One cell of input — a character, or a token {chip} / {emoji} / {img…} — to (index, special).
  // A picture part keeps its block (w, h, x, y, fit, ar); a bare {img} is one stretched cell.
  function toCell(v) {
    if (v && typeof v === "object") {
      if (v.chip) return { index: Flap.indexOf(`{${v.chip}}`), special: null };
      if (v.emoji) return { index: Flap.BLANK, special: { emoji: v.emoji } };
      if (v.img) return { index: Flap.BLANK, special: { img: v } };
      return { index: Flap.BLANK, special: null };
    }
    return { index: Flap.indexOf(v), special: null };
  }

  // Rows (strings, or arrays of cells as the API sends them) → targets, padded or cut.
  function toTargets(rows) {
    const n = settings.rows * settings.cols;
    const idx = new Array(n).fill(Flap.BLANK);
    const sp = new Array(n).fill(null);
    for (let r = 0; r < settings.rows; r += 1) {
      const line = Array.isArray(rows[r]) ? rows[r] : Array.from(rows[r] || "");
      for (let c = 0; c < Math.min(settings.cols, line.length); c += 1) {
        const t = toCell(line[c]);
        idx[r * settings.cols + c] = t.index;
        sp[r * settings.cols + c] = t.special;
      }
    }
    return { idx, sp };
  }

  function landed(pos) {
    const cell = cells[pos];
    return cell.current === target[pos] && Flap.sameSpecial(cell.special, specials[pos]);
  }

  function tick(now) {
    rafId = 0;
    let stepped = false;
    active.forEach((entry, pos) => {
      const cell = cells[pos];
      while (entry.nextAt <= now && !landed(pos)) {
        const nextIndex = cell.current === target[pos] ? target[pos] : Flap.next(cell.current);
        // the special (emoji / picture) is shown on the step that lands on the target
        Flap.setCell(cell, nextIndex, true, nextIndex === target[pos] ? specials[pos] : null);
        entry.nextAt += entry.stepMs;
        stepped = true;
      }
      if (landed(pos)) active.delete(pos);
    });
    if (stepped && window.Sound) window.Sound.click(now); // throttled to one per frame inside
    if (active.size) rafId = requestAnimationFrame(tick);
  }

  // Show these rows (text, or the API's cell arrays). Unchanged cells do not move.
  function show(rows) {
    Flap.invalidateMetrics();
    const next = toTargets(rows);
    shownSomething = shownSomething || next.idx.some((i) => i !== Flap.BLANK) || next.sp.some(Boolean);
    if (instant()) {
      active = new Map();
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
      next.idx.forEach((idx, pos) => Flap.setCell(cells[pos], idx, false, next.sp[pos]));
      target = next.idx;
      specials = next.sp;
      return;
    }
    const step = stepMs(settings.animation);
    const stagger = step * STAGGER_RATIO;
    frameEl.style.setProperty("--flip-ms", `${Math.round(step)}ms`);
    const now = performance.now();
    next.idx.forEach((idx, pos) => {
      target[pos] = idx;
      specials[pos] = next.sp[pos];
      if (landed(pos)) {
        active.delete(pos);
        return;
      }
      if (!active.has(pos)) {
        const col = pos % settings.cols;
        active.set(pos, { nextAt: now + col * stagger, stepMs: step });
      }
    });
    if (active.size && !rafId) rafId = requestAnimationFrame(tick);
  }

  // A picture behind the board: "img:<slug>" is an upload, "builtin:<name>" ships with the app.
  // The backdrop layer takes the url, blur, dim and fit as CSS variables; <html> gets a class.
  const backdrop = document.getElementById("backdrop");
  function backdropUrl(image) {
    const v = String(image || "");
    if (/^img:[a-z0-9][a-z0-9-]{0,39}$/.test(v)) return `/images/${v.slice(4)}`;
    if (/^builtin:[a-z0-9][a-z0-9-]{0,39}$/.test(v)) return `/static/backgrounds/${v.slice(8)}.jpg`;
    return "";
  }
  function applyBackdrop(s) {
    if (!backdrop) return;
    BG_KEYS.forEach((k) => {
      if (s[k] !== undefined) settings[k] = s[k];
    });
    const url = backdropUrl(settings.background_image);
    const blur = Math.max(0, Math.min(40, Number(settings.background_blur) || 0));
    const dim = Math.max(0, Math.min(90, Number(settings.background_dim) || 0));
    backdrop.style.setProperty("--bg-image", url ? `url("${url}")` : "none");
    backdrop.style.setProperty("--bg-blur", `${blur}px`);
    backdrop.style.setProperty("--bg-dim", String(dim / 100));
    backdrop.style.setProperty("--bg-fit", settings.background_fit === "contain" ? "contain" : "cover");
    document.documentElement.classList.toggle("has-backdrop", !!url);
  }

  // The theme is a stylesheet; swapping the link's href is the whole change.
  function applyTheme(id) {
    const link = document.getElementById("theme");
    if (!link || !/^[a-z0-9-]+$/.test(id)) return;
    const href = `/static/themes/${id}.css`;
    if (link.getAttribute("href") !== href) link.setAttribute("href", href);
    settings.theme = id;
  }

  // New settings from a poll: a size change re-lays the grid, a pace change applies to the
  // next show(), sound and theme apply at once. Returns true when the grid was rebuilt.
  function applySettings(next) {
    if (!next) return false;
    if (next.animation !== undefined) settings.animation = Number(next.animation);
    if (window.Sound) window.Sound.configure(next);
    if (next.theme) applyTheme(next.theme);
    if (next.timer_ring !== undefined) {
      settings.timer_ring = String(next.timer_ring);
      renderTimer();
    }
    if (BG_KEYS.some((k) => next[k] !== undefined)) applyBackdrop(next);
    const rows = Number(next.rows) || settings.rows;
    const cols = Number(next.cols) || settings.cols;
    if (rows !== settings.rows || cols !== settings.cols) {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
      layout(rows, cols);
      return true;
    }
    return false;
  }

  layout(Number(config.rows), Number(config.cols));
  settings.animation = Number(config.animation);
  settings.theme = config.theme || settings.theme;
  settings.timer_ring = config.timer_ring || settings.timer_ring;
  applyBackdrop(config);
  if (window.Sound) window.Sound.configure(config);

  // The sound just unlocked (fullscreen click): nothing to do now — the next cascade clicks.
  function soundReady() {}

  // ---- framed by the settings page? Tell it what we show; take rows from it in preview mode.
  const framed = window.parent !== window;
  function tellParent(msg) {
    if (framed) window.parent.postMessage(msg, location.origin);
  }

  // ---- the slot timer: counted down locally between polls; drawn as the ring when asked for.
  const timerEl = document.getElementById("timer");
  const timerLeft = timerEl && timerEl.querySelector(".left");
  const timer = { seconds: 0, remaining: 0, own: false, at: 0, active: false, tick: 0 };

  function setTimer(t) {
    // t = { seconds, remaining, own } from the feed, or null when one message has the board.
    timer.active = !!(t && t.seconds > 0);
    if (timer.active) {
      timer.seconds = Number(t.seconds);
      timer.remaining = Number(t.remaining);
      timer.own = !!t.own;
      timer.at = performance.now();
    }
    renderTimer();
  }

  // Seconds left in the slot right now, from the last poll's value and the local clock.
  function timerRemaining() {
    if (!timer.active) return null;
    return Math.max(0, timer.remaining - (performance.now() - timer.at) / 1000);
  }

  function timerWanted() {
    if (!timer.active || config.preview) return false;
    if (settings.timer_ring === "all") return true;
    return settings.timer_ring === "own" && timer.own;
  }

  function renderTimer() {
    if (!timerEl || !timerLeft) return;
    const wanted = timerWanted();
    timerEl.toggleAttribute("hidden", !wanted); // an SVG element has no .hidden property
    timerEl.classList.toggle("own", timer.own);
    clearInterval(timer.tick);
    timer.tick = 0;
    if (!wanted) return;
    const paint = () => {
      const left = timerRemaining();
      const frac = timer.seconds > 0 ? Math.min(1, left / timer.seconds) : 0;
      timerLeft.style.strokeDashoffset = String(100 - frac * 100); // pathLength=100: full → empty
    };
    paint();
    timer.tick = window.setInterval(paint, reducedMotion ? 1000 : 250);
  }

  // ---- live data: poll /api/board/current; 304 means nothing changed; errors back off.
  const net = document.getElementById("net");
  const poll = { etag: null, stamp: null, message_id: null, failures: 0, timer: 0, polls: 0, notModified: 0, inFlight: false };
  const placeholderRows = cells.map((c) => c.current); // what the server rendered: keep it until there is content

  function schedule(seconds) {
    clearTimeout(poll.timer);
    poll.timer = setTimeout(fetchBoard, Math.max(1, seconds) * 1000);
  }

  // The usual poll, or sooner when the slot ends before it: land 300 ms after the boundary.
  function scheduleNext() {
    const left = timerRemaining();
    if (left === null || left + 0.3 >= settings.poll_seconds) schedule(settings.poll_seconds);
    else schedule(Math.max(1, left + 0.3));
  }

  async function fetchBoard() {
    if (poll.inFlight) return; // a refresh asked for mid-poll: the running one reschedules
    poll.inFlight = true;
    poll.polls += 1;
    try {
      const headers = poll.etag ? { "If-None-Match": poll.etag } : {};
      const r = await fetch("/api/board/current", { headers, cache: "no-store" });
      if (r.status === 304) {
        poll.notModified += 1;
        online();
        if (timer.active && timerRemaining() === 0) setTimer(null); // the slot ended but nothing moved: stop the ring
        scheduleNext();
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      poll.etag = r.headers.get("ETag");
      online();
      if (data.settings && data.settings.poll_seconds) settings.poll_seconds = data.settings.poll_seconds;
      setTimer(data.timer || null);
      if (data.stamp !== poll.stamp) {
        poll.stamp = data.stamp;
        poll.message_id = data.message_id;
        applySettings(data.settings);
        const idle = data.message_id === null && data.rows.every((row) => row.every((c) => c === " "));
        // An idle board before anything has ever shown keeps the server's placeholder
        // ("SET UP AT /SETTINGS"); after a message, idle means the idle text (or blank).
        if (!(idle && !shownSomething)) show(data.rows);
      }
      tellParent({ type: "board:current", message_id: data.message_id, stamp: data.stamp, timer: data.timer || null });
      scheduleNext();
    } catch (e) {
      poll.failures += 1;
      offline();
      schedule(Math.min(60, 2 ** poll.failures));
    } finally {
      poll.inFlight = false;
    }
  }

  function online() {
    poll.failures = 0;
    if (net) net.hidden = true;
  }
  function offline() {
    if (net) {
      net.hidden = false;
      net.title = `Cannot reach the server (${poll.failures}); retrying`;
    }
  }

  // After a resize the cells are a different size: repaint every picture part at its new slice.
  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      Flap.invalidateMetrics();
      cells.forEach((cell) => {
        if (cell.special && cell.special.img && cell.pending === null) {
          const sp = cell.special;
          cell.special = null; // force the repaint
          Flap.setCell(cell, cell.current, false, sp);
        }
      });
    }, 150);
  });

  settings.poll_seconds = Number(config.poll_seconds) || 5;
  if (!config.demo && !config.preview) fetchBoard();

  window.Board = { show, applySettings, applyTheme, applyBackdrop, settings, stepMs, soundReady, poll, fetchBoard, timer, timerRemaining };

  if (framed) {
    window.addEventListener("message", (e) => {
      if (e.origin !== location.origin || e.source !== window.parent || !e.data) return;
      if (e.data.type === "board:show" && config.preview && Array.isArray(e.data.rows)) {
        applySettings(e.data.settings);
        show(e.data.rows);
      } else if (e.data.type === "board:refresh" && !config.preview && !config.demo) {
        clearTimeout(poll.timer);
        fetchBoard();
      }
    });
    tellParent({ type: "board:ready", preview: !!config.preview });
  }

  // ---- demo feed: built-in messages so the board can be seen before any message exists ----
  if (config.demo) {
    const DEMO = [
      [
        "DEPARTURES",
        "",
        "ZRH 0715 BOARDING",
        "LHR 0740 ON TIME",
        "JFK 0805 GATE B12",
        "NRT 0930 DELAYED",
      ],
      ["", "", "ASKED FOR BY", "@FELTBYKRAFT", "", ""],
      ["", "COME FIND ME", "WHEN THAT EXISTS", "", "HERE IT IS.", ""],
      [
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "1234567890 !@#$()-+&=",
        ";:'\"%,./?°",
        "",
        "SPLIT FLAP ON A TV",
        "ONE COMMAND ONE BOARD",
      ],
      [
        "COLOUR CHIPS AND EMOJI",
        ["red", "orange", "yellow", "green", "blue", "violet", "white", "black"].map((chip) => ({ chip })),
        "",
        [..."FLIGHT ", { emoji: "🛫" }, ..." ON TIME ", { emoji: "🎉" }],
        [..."DINNER ", { emoji: "🍝" }, ..." AT 7"],
        "",
      ],
    ];
    const DEMO_EVERY_MS = 7000;
    const centered = (lines) =>
      lines.map((line) => {
        const pad = Math.max(0, Math.floor((settings.cols - line.length) / 2));
        if (Array.isArray(line)) return new Array(pad).fill(" ").concat(line);
        return " ".repeat(pad) + line;
      });
    let i = 0;
    const step = () => {
      show(i % DEMO.length === 0 ? DEMO[0] : centered(DEMO[i % DEMO.length]));
      i += 1;
      window.setTimeout(step, DEMO_EVERY_MS);
    };
    window.setTimeout(step, 1000);
  }
})();
