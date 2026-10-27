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
//                    board:settings { settings }     (both: a draft of display settings, e.g.
//                    the background picker's sliders, applied before anything is saved)
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
  const overlaysEl = document.getElementById("overlays");
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

  const settings = { rows: 0, cols: 0, animation: 60, theme: "classic-black", timer_ring: "off", cell_radius: 6, cell_gap: 35, split_line: 1, cell_depth: "", frame_color: "", frame_width: "", frame_radius: "", frame_finish: "theme", frame_glow: "", frame_fit: "screen", frame_corners: "whole", board_scale: 100, board_margin: 0, board_position: "center", board_hidden: "" };
  const BG_KEYS = ["background_image", "background_blur", "background_dim", "background_fit", "background_motion", "background_colors"];
  // The shape of a flap: unitless numbers board.css turns into lengths (see .frame).
  const FLAP_KEYS = ["cell_radius", "cell_gap", "split_line", "cell_depth"];
  const FLAP_BOUNDS = { cell_radius: [0, 12], cell_gap: [0, 100], split_line: [0, 3], cell_depth: [0, 100] };
  // The frame: "" on any key = as the theme (no inline var); finish is an attribute on .frame.
  const FRAME_KEYS = ["frame_color", "frame_width", "frame_radius", "frame_finish", "frame_glow", "frame_fit", "frame_corners", "board_scale", "board_margin", "board_position", "board_hidden"];
  const FRAME_BOUNDS = { frame_width: [0, 10], frame_radius: [0, 30], board_scale: [25, 100], board_margin: [0, 10] };
  const FRAME_FINISHES = ["theme", "matte", "chrome", "neon"];
  const FRAME_FITS = ["screen", "board"];
  const FRAME_CORNERS = ["whole", "hide"];
  const BOARD_POSITIONS = ["center", "top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right"];
  const HEX = /^#[0-9a-f]{6}$/i;
  let cells = []; // row-major cell records
  let target = []; // row-major sequence indices the board is heading to
  let specials = []; // row-major token cells ({emoji} / {img}) shown once a cell lands, or null
  let active = new Map(); // cell position → { nextAt }
  let blocks = new Map(); // solid blocks on the way: key → { parts: [pos], anchor, img, el }
  let blockOf = []; // row-major: the key of the solid block a cell belongs to, or null
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
    if (overlaysEl) overlaysEl.textContent = "";
    blocks = new Map();
    blockOf = [];
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
    cells.forEach((c, i) => (c.pos = i));
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
    planBlocks(next.sp); // overlays that are leaving fade before their first flap moves
    if (instant()) {
      active = new Map();
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
      next.idx.forEach((idx, pos) => Flap.setCell(cells[pos], idx, false, next.sp[pos]));
      target = next.idx;
      specials = next.sp;
      blocks.forEach((b) => checkBlock(b));
      return;
    }
    const step = stepMs(settings.animation);
    const stagger = step * STAGGER_RATIO;
    Flap.setFlipMs(Math.round(step));
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

  // ---- solid blocks: a picture drawn whole over its cells (one element in #overlays), the
  // flaps beneath blank. The overlay fades in once every cell of the block has landed and fades
  // out before the first of them moves again, so the cascade still frames the picture.
  function planBlocks(sp) {
    const nextBlocks = new Map();
    blockOf = new Array(sp.length).fill(null);
    sp.forEach((s, pos) => {
      const img = s && s.img;
      if (!img || !img.solid) return;
      const anchor = pos - (img.y || 0) * settings.cols - (img.x || 0);
      const key = `${anchor}:${img.img}:${img.w}x${img.h}:${img.fit}:${img.v || 0}`; // a remade file is a new overlay
      let b = nextBlocks.get(key);
      if (!b) {
        b = { key, anchor, img, parts: [], el: null };
        nextBlocks.set(key, b);
      }
      b.parts.push(pos);
      blockOf[pos] = key;
    });
    blocks.forEach((old, key) => {
      const kept = nextBlocks.get(key);
      if (kept && old.el) kept.el = old.el; // still there: keep the element, keep it showing
      else if (old.el) dropOverlay(old.el);
    });
    blocks = nextBlocks;
  }
  function dropOverlay(el) {
    el.classList.remove("on");
    const gone = () => el.remove();
    if (reducedMotion) gone();
    else setTimeout(gone, 400);
  }
  // The block's box in the stage's coordinates, from the anchor cell's own box and the grid's
  // gap — the same metrics the mosaic slices use.
  function placeOverlay(b) {
    const anchorEl = cells[b.anchor] && cells[b.anchor].el;
    if (!anchorEl || !b.el) return;
    const stage = overlaysEl.getBoundingClientRect();
    const a = anchorEl.getBoundingClientRect();
    const gap = parseFloat(getComputedStyle(boardEl).columnGap) || 0;
    const w = b.img.w || 1;
    const h = b.img.h || 1;
    b.el.style.left = `${a.left - stage.left}px`;
    b.el.style.top = `${a.top - stage.top}px`;
    b.el.style.width = `${w * a.width + (w - 1) * gap}px`;
    b.el.style.height = `${h * a.height + (h - 1) * gap}px`;
  }
  function placeOverlays() {
    blocks.forEach((b) => placeOverlay(b));
  }
  function blockLanded(b) {
    return b.parts.every((pos) => landed(pos) && cells[pos].pending === null);
  }
  function checkBlock(b) {
    if (!b || !overlaysEl || b.el || !blockLanded(b)) return;
    const el = document.createElement("div");
    el.className = `overlay${b.img.qr ? " qr" : ""}`;
    el.dataset.fit = b.img.fit || "contain";
    el.style.backgroundImage = `url("/images/${b.img.img}${b.img.v ? `?v=${b.img.v}` : ""}")`;
    b.el = el;
    overlaysEl.appendChild(el);
    placeOverlay(b);
    requestAnimationFrame(() => el.classList.add("on")); // after the first paint, so it fades in
  }
  Flap.onLand((cell) => {
    const key = blockOf[cell.pos];
    if (key) checkBlock(blocks.get(key));
  });

  // Behind the board: "img:<slug>" is an upload, "builtin:<name>" ships with the app, "video:<slug>"
  // is an uploaded clip the <video> child plays muted in a loop, "gradient:<preset>" is a living
  // backdrop drawn here — one .field child per colour, drifting at background_motion. The backdrop
  // layer takes the url, blur, dim and fit as CSS variables; <html> gets a class (two for a video
  // or a gradient).
  const backdrop = document.getElementById("backdrop");
  const backdropVideo = document.getElementById("backdrop-video");
  let presets = {};
  try {
    presets = JSON.parse((backdrop && backdrop.dataset.presets) || "{}");
  } catch (e) {
    presets = {};
  }
  const HEX6 = /^#[0-9a-f]{6}$/;
  // The colours a gradient draws: the host's own (2–4 valid ones) else the preset's; null = no gradient.
  function gradientColors(image, own) {
    const m = /^gradient:([a-z0-9][a-z0-9-]{0,39})$/.exec(String(image || ""));
    if (!m || !presets[m[1]]) return null;
    const mine = String(own || "").split(",").map((c) => c.trim().toLowerCase()).filter((c) => HEX6.test(c));
    return mine.length >= 2 && mine.length <= 4 ? mine : presets[m[1]];
  }
  // The fields are rebuilt only when the colours change — a poll must not restart their drift.
  function applyFields(colors) {
    const sig = colors ? colors.join(",") : "";
    if (backdrop.dataset.fields === sig) return;
    backdrop.dataset.fields = sig;
    backdrop.querySelectorAll(".field").forEach((f) => f.remove());
    if (!colors) {
      backdrop.style.removeProperty("--bg-ground");
      return;
    }
    backdrop.style.setProperty("--bg-ground", colors[colors.length - 1]);
    colors.forEach((c) => {
      const f = document.createElement("div");
      f.className = "field";
      f.style.setProperty("--c", c);
      backdrop.insertBefore(f, backdropVideo);
    });
  }
  function backdropUrl(image) {
    const v = String(image || "");
    if (/^img:[a-z0-9][a-z0-9-]{0,39}$/.test(v)) return `/images/${v.slice(4)}`;
    if (/^builtin:[a-z0-9][a-z0-9-]{0,39}$/.test(v)) return `/static/backgrounds/${v.slice(8)}.jpg`;
    if (/^video:[a-z0-9][a-z0-9-]{0,39}$/.test(v)) return `/videos/${v.slice(6)}`;
    return "";
  }
  // The clip: src set only when it changes (a poll must not restart it); under reduced motion, or
  // at background_motion 0, it rests on its first frame, a still.
  function applyVideo(url, still) {
    if (!backdropVideo) return;
    if (!url) {
      if (backdropVideo.getAttribute("src")) {
        backdropVideo.pause();
        backdropVideo.removeAttribute("src");
        backdropVideo.load();
      }
      return;
    }
    if (backdropVideo.getAttribute("src") !== url) {
      backdropVideo.setAttribute("src", url);
      backdropVideo.load();
    }
    if (reducedMotion || still) {
      backdropVideo.pause();
      backdropVideo.currentTime = 0;
    } else {
      const p = backdropVideo.play();
      if (p && p.catch) p.catch(() => {});
    }
  }
  function applyBackdrop(s) {
    if (!backdrop) return;
    BG_KEYS.forEach((k) => {
      if (s[k] !== undefined) settings[k] = s[k];
    });
    const url = backdropUrl(settings.background_image);
    const isVideo = String(settings.background_image || "").startsWith("video:");
    const colors = gradientColors(settings.background_image, settings.background_colors);
    const blur = colors ? 0 : Math.max(0, Math.min(40, Number(settings.background_blur) || 0));
    const dim = Math.max(0, Math.min(90, Number(settings.background_dim) || 0));
    const motion = Math.max(0, Math.min(100, Number(settings.background_motion) || 0));
    backdrop.style.setProperty("--bg-image", url && !isVideo ? `url("${url}")` : "none");
    backdrop.style.setProperty("--bg-blur", `${blur}px`);
    backdrop.style.setProperty("--bg-dim", String(dim / 100));
    backdrop.style.setProperty("--bg-fit", settings.background_fit === "contain" ? "contain" : "cover");
    // one way across in 15 s at motion 100, 90 s at 0 — which pauses instead
    backdrop.style.setProperty("--bg-cycle", `${Math.round(15 + (100 - motion) * 0.75)}s`);
    backdrop.style.setProperty("--bg-play", motion === 0 ? "paused" : "running");
    document.documentElement.classList.toggle("has-backdrop", !!url || !!colors);
    document.documentElement.classList.toggle("has-video", isVideo && !!url);
    document.documentElement.classList.toggle("has-gradient", !!colors);
    applyFields(colors);
    applyVideo(isVideo ? url : "", motion === 0);
  }

  // The frame (display settings frame_*): inline vars on .frame only for the keys that are set —
  // "" leaves the theme's own value; the finish is an attribute board.css styles.
  function applyFrame(s) {
    FRAME_KEYS.forEach((k) => {
      if (s[k] === undefined) return;
      const v = s[k] === null ? "" : String(s[k]).trim();
      if (k === "frame_finish") settings[k] = FRAME_FINISHES.includes(v) ? v : "theme";
      else if (k === "frame_fit") settings[k] = FRAME_FITS.includes(v) ? v : "screen";
      else if (k === "frame_corners") settings[k] = FRAME_CORNERS.includes(v) ? v : "whole";
      else if (k === "board_position") settings[k] = BOARD_POSITIONS.includes(v) ? v : "center";
      else if (k === "board_hidden") settings[k] = v === "1" ? "1" : "";
      else if (k === "frame_color" || k === "frame_glow") settings[k] = HEX.test(v) ? v.toLowerCase() : "";
      else if (v === "" && k !== "board_scale" && k !== "board_margin") settings[k] = "";
      else {
        const [lo, hi] = FRAME_BOUNDS[k];
        settings[k] = Math.max(lo, Math.min(hi, Number(v) || 0));
      }
    });
    const set = (name, value) => (value === "" ? frameEl.style.removeProperty(name) : frameEl.style.setProperty(name, value));
    set("--frame-color", settings.frame_color);
    set("--frame-glow", settings.frame_glow);
    set("--frame-n", settings.frame_width === "" ? "" : String(settings.frame_width));
    set("--frame-radius", settings.frame_radius === "" ? "" : String(settings.frame_radius));
    set("--board-scale", String(settings.board_scale));
    set("--board-margin", String(settings.board_margin));
    frameEl.dataset.finish = settings.frame_finish;
    frameEl.dataset.fit = settings.frame_fit;
    frameEl.dataset.corners = settings.frame_corners;
    frameEl.dataset.position = settings.board_position;
    frameEl.dataset.hidden = settings.board_hidden;
  }

  // Corners, gap, split line and depth go on the frame, where the server rendered them inline for
  // the first paint ("" on the depth = the theme's own: no inline var). A new gap resizes every
  // cell, so the picture slices are measured and painted again.
  function applyFlapShape(s) {
    const oldGap = settings.cell_gap;
    FLAP_KEYS.forEach((k) => {
      if (s[k] === undefined) return;
      const [lo, hi] = FLAP_BOUNDS[k];
      if (k === "cell_depth" && (s[k] === "" || s[k] === null)) {
        settings[k] = "";
        return;
      }
      settings[k] = Math.max(lo, Math.min(hi, Number(s[k]) || 0));
    });
    frameEl.style.setProperty("--cell-radius", String(settings.cell_radius));
    frameEl.style.setProperty("--cell-gap", String(settings.cell_gap));
    frameEl.style.setProperty("--split-line", String(settings.split_line));
    if (settings.cell_depth === "") frameEl.style.removeProperty("--cell-depth");
    else frameEl.style.setProperty("--cell-depth", String(settings.cell_depth));
    if (settings.cell_gap !== oldGap) repaintPictures();
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
    if (FLAP_KEYS.some((k) => next[k] !== undefined)) applyFlapShape(next);
    if (FRAME_KEYS.some((k) => next[k] !== undefined)) applyFrame(next);
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
  applyFlapShape(config);
  applyFrame(config);
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

  // After a resize (or a new gap) the cells are a different size: repaint every picture part at
  // its new slice.
  function repaintPictures() {
    Flap.invalidateMetrics();
    cells.forEach((cell) => {
      if (cell.special && cell.special.img && cell.pending === null) {
        const sp = cell.special;
        cell.special = null; // force the repaint
        Flap.setCell(cell, cell.current, false, sp);
      }
    });
    placeOverlays();
  }
  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(repaintPictures, 150);
  });

  settings.poll_seconds = Number(config.poll_seconds) || 5;
  if (!config.demo && !config.preview) fetchBoard();

  window.Board = { show, applySettings, applyTheme, applyBackdrop, applyFlapShape, applyFrame, placeOverlays, settings, stepMs, soundReady, poll, fetchBoard, timer, timerRemaining };

  if (framed) {
    window.addEventListener("message", (e) => {
      if (e.origin !== location.origin || e.source !== window.parent || !e.data) return;
      if (e.data.type === "board:show" && config.preview && Array.isArray(e.data.rows)) {
        applySettings(e.data.settings);
        show(e.data.rows);
      } else if (e.data.type === "board:refresh" && !config.preview && !config.demo) {
        clearTimeout(poll.timer);
        fetchBoard();
      } else if (e.data.type === "board:settings" && e.data.settings && typeof e.data.settings === "object") {
        applySettings(e.data.settings);
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
