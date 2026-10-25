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

  // What a cell paints for a sequence index: chips are a colour, not a glyph.
  function glyphFor(index) {
    const ch = SEQUENCE[index];
    return ch === undefined || ch === " " || ch.charAt(0) === "{" ? "" : ch;
  }

  function chipOf(index) {
    const ch = SEQUENCE[index];
    return ch && ch.charAt(0) === "{" ? ch.slice(1, -1) : null;
  }

  // A face: what one half of a flap shows. `special` is a token cell the sequence has no
  // index for — {emoji: "🎉"} (a glyph) or {img, w, h, x, y, fit, ar} (one part of a picture
  // that covers w × h cells; a bare {img} is one stretched cell) — shown on a blank.
  function faceOf(index, special) {
    if (special && special.emoji) return { text: special.emoji, chip: null, img: null, emoji: true };
    if (special && special.img) return { text: "", chip: null, img: special.img, emoji: false };
    return { text: glyphFor(index), chip: chipOf(index), img: null, emoji: false };
  }

  // Cell geometry in px, measured once per show() (and again after a resize): a picture that
  // spans cells is drawn as one background sized to the whole block and offset per part.
  let metrics = null;
  function invalidateMetrics() {
    metrics = null;
  }
  function measure(cellEl) {
    const cs = getComputedStyle(cellEl);
    const board = cellEl.parentElement;
    const gap = board ? parseFloat(getComputedStyle(board).columnGap) || 0 : 0;
    metrics = { cw: parseFloat(cs.width) || 0, ch: parseFloat(cs.height) || 0, gap };
    return metrics;
  }

  // Background size and position for one part of a picture, on the top (hy = 0) or bottom
  // half (hy = half a cell) of its cell. `contain` keeps the shape inside the block and centres
  // it, `cover` fills and crops, `stretch` fills.
  function slice(img, cellEl, bottom) {
    const m = metrics || measure(cellEl);
    const W = (img.w || 1) * m.cw + ((img.w || 1) - 1) * m.gap;
    const H = (img.h || 1) * m.ch + ((img.h || 1) - 1) * m.gap;
    let dw = W;
    let dh = H;
    if (img.ar && img.fit !== "stretch") {
      const wide = img.ar >= W / H;
      if ((img.fit === "cover") !== wide) {
        dw = W;
        dh = W / img.ar;
      } else {
        dh = H;
        dw = H * img.ar;
      }
    }
    const ox = (W - dw) / 2 - (img.x || 0) * (m.cw + m.gap);
    const oy = (H - dh) / 2 - (img.y || 0) * (m.ch + m.gap) - (bottom ? m.ch / 2 : 0);
    return { size: `${dw}px ${dh}px`, position: `${ox}px ${oy}px` };
  }

  function paint(halfEl, glyphEl, face, bottom) {
    glyphEl.textContent = face.text;
    glyphEl.classList.toggle("emoji", face.emoji);
    if (face.chip) halfEl.setAttribute("data-chip", face.chip);
    else halfEl.removeAttribute("data-chip");
    const img = face.img;
    // a solid block is drawn whole by the board's overlay layer; its flaps stay blank
    const url = img && !img.solid ? `url("/images/${img.img}")` : "";
    if (halfEl.style.backgroundImage !== url) halfEl.style.backgroundImage = url;
    // a legacy one-cell picture keeps the stylesheet's 100% 200% split; a block gets its slice
    const legacy = !img || img.solid || (img.w === undefined && img.fit === undefined);
    const s = legacy ? { size: "", position: "" } : slice(img, halfEl.parentElement, bottom);
    if (halfEl.style.backgroundSize !== s.size) halfEl.style.backgroundSize = s.size;
    if (halfEl.style.backgroundPosition !== s.position) halfEl.style.backgroundPosition = s.position;
  }

  // One flip = one Web Animation on the leaf (not a CSS class): a class toggled off and on
  // again inside one style flush is no change to the engine, so a flip that ended in the same
  // frame as two catch-up steps never restarted and its landing never ran — cells stuck with
  // the old bottom half under the new top (seen on a TV and a busy laptop after a theme change).
  // An Animation object per step is unambiguous: finish → land, cancel → gone.
  const FLIP_FRAMES = [{ transform: "rotateX(0deg)" }, { transform: "rotateX(-180deg)" }];
  let flipMs = 70;
  function setFlipMs(ms) {
    flipMs = Math.max(1, Number(ms) || 70);
  }
  function stopFlip(cell) {
    const anim = cell.anim;
    if (!anim) return;
    cell.anim = null;
    anim.cancel();
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
      topEl: q(".half.top"),
      bottomEl: q(".half.bottom"),
      frontEl: q(".face.front"),
      backEl: q(".face.back"),
      top: q(".half.top .glyph"),
      bottom: q(".half.bottom .glyph"),
      front: q(".face.front .glyph"),
      back: q(".face.back .glyph"),
      current: index === undefined ? indexOf(q(".half.top .glyph").textContent) : index,
      special: null,
      pending: null,
      pendingSpecial: null,
      anim: null,
    };
    return cell;
  }

  // The leaf has landed: the bottom half and the leaf's front now show the character.
  function commit(cell) {
    if (cell.pending === null) return;
    const face = faceOf(cell.pending, cell.pendingSpecial);
    paint(cell.bottomEl, cell.bottom, face, true);
    paint(cell.frontEl, cell.front, face, false);
    cell.pending = null;
    cell.pendingSpecial = null;
    stopFlip(cell); // the leaf returns to rest showing the front, which now carries the face
    if (landHook) landHook(cell);
  }

  // Called with a cell whenever its leaf has landed (board.js shows a solid block's overlay once
  // every cell beneath it has).
  let landHook = null;
  function onLand(fn) {
    landHook = fn;
  }

  function sameSpecial(a, b) {
    if ((a && a.emoji) !== (b && b.emoji)) return false;
    const ia = a && a.img;
    const ib = b && b.img;
    if (!ia && !ib) return true;
    if (!ia || !ib) return false;
    return ["img", "w", "h", "x", "y", "fit", "ar", "solid", "qr"].every((k) => ia[k] === ib[k]);
  }

  // Show `index` (with an optional special token). With flip=true the leaf animates from the
  // current face; otherwise every half is painted directly.
  function setCell(cell, index, flip, special) {
    special = special || null;
    if (index === cell.current && sameSpecial(special, cell.special) && cell.pending === null) {
      return;
    }
    if (!flip || typeof cell.leaf.animate !== "function") {
      cell.pending = null;
      cell.pendingSpecial = null;
      stopFlip(cell);
      const face = faceOf(index, special);
      paint(cell.topEl, cell.top, face, false);
      paint(cell.bottomEl, cell.bottom, face, true);
      paint(cell.frontEl, cell.front, face, false);
      paint(cell.backEl, cell.back, face, true);
      cell.current = index;
      cell.special = special;
      return;
    }
    // A flip still in the air lands first.
    commit(cell);
    const from = faceOf(cell.current, cell.special);
    const to = faceOf(index, special);
    paint(cell.frontEl, cell.front, from, false);
    paint(cell.bottomEl, cell.bottom, from, true);
    paint(cell.topEl, cell.top, to, false);
    paint(cell.backEl, cell.back, to, true);
    cell.pending = index;
    cell.pendingSpecial = special;
    cell.current = index;
    cell.special = special;
    const anim = cell.leaf.animate(FLIP_FRAMES, { duration: flipMs, easing: "ease-in", fill: "forwards" });
    anim.onfinish = () => {
      if (cell.anim === anim) commit(cell);
    };
    cell.anim = anim;
  }

  window.Flap = {
    SEQUENCE,
    CHIPS,
    BLANK,
    normalize,
    indexOf,
    glyphFor,
    chipOf,
    faceOf,
    sameSpecial,
    setFlipMs,
    invalidateMetrics,
    slice,
    stepsBetween,
    next,
    buildCell,
    adoptCell,
    setCell,
    commit,
    onLand,
  };
})();
