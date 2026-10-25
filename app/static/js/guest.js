// The guest page: a counter and a preview of how the line reads on the flaps (capitals, digits,
// the few marks the set has; the rest turns blank). Works without this script too.
(() => {
  const text = document.getElementById("text");
  const count = document.getElementById("count");
  const preview = document.getElementById("preview");
  const file = document.querySelector('input[name="photo"]');
  const name = document.getElementById("photo-name");
  if (!text) return;
  let known = null; // the flap set's characters, once fetched
  fetch("/static/flapset.json")
    .then((r) => r.json())
    .then((set) => {
      known = new Set(set.sequence);
      render();
    })
    .catch(() => {});
  const emoji = /\p{Extended_Pictographic}/u;
  const strip = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "");
  function render() {
    count.textContent = String(text.value.length);
    if (!known) return;
    preview.textContent = "";
    const up = strip(text.value).toUpperCase();
    let blanks = 0;
    for (const ch of up) {
      const span = document.createElement("span");
      if (ch === " " || known.has(ch) || emoji.test(ch) || ch === "{" || ch === "}") span.textContent = ch;
      else {
        span.textContent = "·";
        span.className = "blank";
        span.title = `${ch} is not on the flaps`;
        blanks += 1;
      }
      preview.appendChild(span);
    }
    if (blanks) preview.appendChild(document.createTextNode(` (${blanks} blank)`));
  }
  text.addEventListener("input", render);
  render();
  if (file) {
    file.addEventListener("change", () => {
      const f = file.files[0];
      const size = !f ? "" : f.size >= 1024 * 1024 ? `${(f.size / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(f.size / 1024))} KB`;
      name.textContent = f ? `${f.name} · ${size}` : "";
    });
  }
})();
