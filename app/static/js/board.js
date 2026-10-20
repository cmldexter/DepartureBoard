// The board: a grid of split-flap cells, a refresh animation that flips every changed cell
// through the sequence to its target with the columns cascading left to right, and the
// animation setting (0 = instant, 1 = fastest, 100 = the pace of a mechanical board).
//
// Data arrives as { rows: ["…", …], settings: { rows, cols, animation } } — the shape of
// GET /api/board/current. Until the board polls it, ?demo feeds built-in messages.
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

  const settings = { rows: 0, cols: 0, animation: 60 };
  let cells = []; // row-major cell records
  let target = []; // row-major sequence indices the board is heading to
  let active = new Map(); // cell position → { nextAt }
  let rafId = 0;

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
    active = new Map();
  }

  // Text rows → sequence indices, padded or cut to the grid.
  function toIndices(rows) {
    const out = new Array(settings.rows * settings.cols).fill(Flap.BLANK);
    for (let r = 0; r < settings.rows; r += 1) {
      const line = Array.from(rows[r] || "");
      for (let c = 0; c < settings.cols; c += 1) {
        out[r * settings.cols + c] = c < line.length ? Flap.indexOf(line[c]) : Flap.BLANK;
      }
    }
    return out;
  }

  function tick(now) {
    rafId = 0;
    active.forEach((entry, pos) => {
      const cell = cells[pos];
      while (entry.nextAt <= now && cell.current !== target[pos]) {
        Flap.setCell(cell, Flap.next(cell.current), true);
        entry.nextAt += entry.stepMs;
      }
      if (cell.current === target[pos]) active.delete(pos);
    });
    if (active.size) rafId = requestAnimationFrame(tick);
  }

  // Show these rows of text. Unchanged cells do not move.
  function show(rows) {
    const next = toIndices(rows);
    if (instant()) {
      active = new Map();
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
      next.forEach((idx, pos) => Flap.setCell(cells[pos], idx, false));
      target = next;
      return;
    }
    const step = stepMs(settings.animation);
    const stagger = step * STAGGER_RATIO;
    frameEl.style.setProperty("--flip-ms", `${Math.round(step)}ms`);
    const now = performance.now();
    next.forEach((idx, pos) => {
      target[pos] = idx;
      if (cells[pos].current === idx) {
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

  // New settings from a poll: a size change re-lays the grid, a pace change applies to the
  // next show(). Returns true when the grid was rebuilt.
  function applySettings(next) {
    if (!next) return false;
    if (next.animation !== undefined) settings.animation = Number(next.animation);
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

  window.Board = { show, applySettings, settings, stepMs };

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
    ];
    const DEMO_EVERY_MS = 7000;
    const centered = (lines) =>
      lines.map((line) => {
        const pad = Math.max(0, Math.floor((settings.cols - line.length) / 2));
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
