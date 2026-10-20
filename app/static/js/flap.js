// The split-flap cell: the character sequence a mechanical board flips through, and a cell
// made of two static halves and a leaf that rotates down from the top half over the bottom.
//
//   .cell
//     .half.top    .glyph   upper half of the NEXT character (revealed as the leaf falls)
//     .half.bottom .glyph   lower half of the CURRENT character (covered as the leaf lands)
//     .leaf
//       .face.front .glyph  upper half of the CURRENT character (the leaf's visible side)
//       .face.back  .glyph  lower half of the NEXT character (the leaf's far side, seen when it has landed)
//     .split
//
// Exposes window.Flap. Plain script, no modules: the page may be opened by an old TV browser.
(() => {
  "use strict";

  // Order matters: a flip from A to C passes through B. Colour chips sit at the end so their
  // positions stay stable when they are rendered (they are not yet; they show as a blank).
  const CHIPS = ["{red}", "{orange}", "{yellow}", "{green}", "{blue}", "{violet}", "{white}", "{black}"];
  const SEQUENCE = [" "]
    .concat("ABCDEFGHIJKLMNOPQRSTUVWXYZ".split(""))
    .concat("1234567890".split(""))
    .concat("!@#$()-+&=;:'\"%,./?°".split(""))
    .concat(CHIPS);
  const INDEX = new Map(SEQUENCE.map((ch, i) => [ch, i]));
  const BLANK = 0;

  // Uppercase, strip accents, and map anything outside the set to a blank.
  function normalize(ch) {
    if (ch === undefined || ch === null) return " ";
    const s = String(ch);
    if (INDEX.has(s)) return s;
    const stripped = s.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
    return INDEX.has(stripped) ? stripped : " ";
  }

  function indexOf(ch) {
    const i = INDEX.get(normalize(ch));
    return i === undefined ? BLANK : i;
  }

  // What a cell paints for a sequence index. Chips have no glyph until they are rendered as flaps.
  function glyphFor(index) {
    const ch = SEQUENCE[index];
    return ch === undefined || ch === " " || ch.charAt(0) === "{" ? "" : ch;
  }

  // Flaps only move forward and wrap; the number of steps from one index to another.
  function stepsBetween(from, to) {
    const n = SEQUENCE.length;
    return (((to - from) % n) + n) % n;
  }

  function next(index) {
    return (index + 1) % SEQUENCE.length;
  }

  function glyphSpan(text) {
    const span = document.createElement("span");
    span.className = "glyph";
    span.textContent = text;
    return span;
  }

  function half(cls, text) {
    const el = document.createElement("div");
    el.className = cls;
    el.appendChild(glyphSpan(text));
    return el;
  }

  // Build a cell element showing `index`.
  function buildCell(index) {
    const el = document.createElement("div");
    el.className = "cell";
    const text = glyphFor(index);
    const leaf = document.createElement("div");
    leaf.className = "leaf";
    leaf.appendChild(half("face front", text));
    leaf.appendChild(half("face back", text));
    el.appendChild(half("half top", text));
    el.appendChild(half("half bottom", text));
    el.appendChild(leaf);
    const split = document.createElement("span");
    split.className = "split";
    el.appendChild(split);
    return adoptCell(el, index);
  }

  // Wrap an existing cell element (server-rendered) into a cell record.
  function adoptCell(el, index) {
    const q = (sel) => el.querySelector(sel);
    const cell = {
      el,
      leaf: q(".leaf"),
      top: q(".half.top .glyph"),
      bottom: q(".half.bottom .glyph"),
      front: q(".face.front .glyph"),
      back: q(".face.back .glyph"),
      current: index === undefined ? indexOf(q(".half.top .glyph").textContent) : index,
      pending: null,
      phase: 0,
    };
    cell.leaf.addEventListener("animationend", () => commit(cell));
    return cell;
  }

  // The leaf has landed: the bottom half and the leaf's front now show the character.
  function commit(cell) {
    if (cell.pending === null) return;
    const text = glyphFor(cell.pending);
    cell.bottom.textContent = text;
    cell.front.textContent = text;
    cell.pending = null;
    cell.leaf.classList.remove("flip-a", "flip-b");
  }

  // Show `index`. With flip=true the leaf animates from the current character; otherwise
  // every half is painted directly.
  function setCell(cell, index, flip) {
    if (index === cell.current && cell.pending === null) return;
    if (!flip) {
      cell.pending = null;
      cell.leaf.classList.remove("flip-a", "flip-b");
      const text = glyphFor(index);
      cell.top.textContent = text;
      cell.bottom.textContent = text;
      cell.front.textContent = text;
      cell.back.textContent = text;
      cell.current = index;
      return;
    }
    // A flip still in the air lands first.
    commit(cell);
    const from = glyphFor(cell.current);
    const to = glyphFor(index);
    cell.front.textContent = from;
    cell.bottom.textContent = from;
    cell.top.textContent = to;
    cell.back.textContent = to;
    cell.pending = index;
    cell.current = index;
    // Two identical animations, alternated, restart the flip without forcing a reflow.
    cell.phase ^= 1;
    cell.leaf.classList.remove(cell.phase ? "flip-a" : "flip-b");
    cell.leaf.classList.add(cell.phase ? "flip-b" : "flip-a");
  }

  window.Flap = {
    SEQUENCE,
    CHIPS,
    BLANK,
    normalize,
    indexOf,
    glyphFor,
    stepsBetween,
    next,
    buildCell,
    adoptCell,
    setCell,
    commit,
  };
})();
