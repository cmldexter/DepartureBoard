// The settings page: messages, display, images. Plain fetch to the API with the session
// cookie; every write carries the page header so a cross-site form cannot do it.
(() => {
  "use strict";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const HEADERS = { "X-Requested-With": "DepartureBoard" };

  async function api(path, { method = "GET", body, form } = {}) {
    const init = { method, headers: { ...HEADERS } };
    if (form) init.body = form;
    else if (body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    const r = await fetch(path, init);
    if (r.status === 204) return null;
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ")
        : data.detail || r.statusText;
      throw new Error(detail);
    }
    return data;
  }

  let toastTimer = 0;
  function toast(text, isError) {
    const el = $("#toast");
    el.textContent = text;
    el.classList.toggle("error", !!isError);
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (el.hidden = true), 4000);
  }

  // ---- helpers for dates: the API speaks UTC ISO; inputs speak local wall time.
  const toLocalInput = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const fromLocalInput = (v) => (v ? new Date(v).toISOString() : null);
  const fmtWhen = (m) => {
    const parts = [];
    if (m.starts_at || m.ends_at) {
      const f = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "…");
      parts.push(`${f(m.starts_at)} → ${f(m.ends_at)}`);
    }
    if (m.repeat === "daily") parts.push(`daily${m.repeat_start ? ` ${m.repeat_start}–${m.repeat_end}` : ""}`);
    if (m.repeat === "weekly") {
      const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].filter((_, i) => m.repeat_days & (1 << i));
      parts.push(`${names.join(" ")}${m.repeat_start ? ` ${m.repeat_start}–${m.repeat_end}` : ""}`);
    }
    return parts.join(" · ") || "always";
  };

  // ---- cells → a mini board
  function cellText(c) {
    if (typeof c === "string") return c;
    if (c.chip) return "";
    if (c.emoji) return c.emoji;
    return "";
  }
  function renderGrid(el, rows, gridRows, gridCols) {
    el.style.setProperty("--cols", gridCols);
    el.textContent = "";
    for (let r = 0; r < gridRows; r += 1) {
      const row = rows[r] || [];
      for (let c = 0; c < gridCols; c += 1) {
        const cell = document.createElement("span");
        const v = row[c];
        cell.className = "mc";
        if (v && typeof v === "object") {
          if (v.chip) cell.classList.add("chip", `chip-${v.chip}`);
          if (v.img) {
            cell.classList.add("img");
            cell.style.backgroundImage = `url(/images/${v.img})`;
          }
          if (v.emoji) cell.classList.add("emoji");
        }
        if (r >= rows.length) cell.classList.add("empty");
        cell.textContent = v === undefined ? "" : cellText(v);
        el.appendChild(cell);
      }
    }
    el.classList.toggle("overflow", rows.length > gridRows);
  }

  // ---- messages
  const form = $("#message-form");
  const rowsEl = $("#message-rows");
  let messages = [];

  async function loadMessages() {
    messages = await api("/api/messages");
    if (!messages.length) {
      rowsEl.innerHTML = '<tr><td colspan="4" class="muted">No messages yet. The board shows the idle text.</td></tr>';
      return;
    }
    rowsEl.textContent = "";
    for (const m of messages) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td><span class="badge ${m.state}">${m.state}</span></td>
        <td class="text"></td><td class="muted"></td>
        <td class="actions"><button type="button" class="link edit">Edit</button> <button type="button" class="link delete">Delete</button></td>`;
      $(".text", tr).textContent = m.text;
      $(".muted", tr).textContent = `${fmtWhen(m)} · p${m.priority}`;
      $(".edit", tr).addEventListener("click", () => openForm(m));
      $(".delete", tr).addEventListener("click", async () => {
        if (!confirm(`Delete “${m.text.slice(0, 40)}”?`)) return;
        try {
          await api(`/api/messages/${m.id}`, { method: "DELETE" });
          toast("Deleted.");
          await loadMessages();
        } catch (e) {
          toast(e.message, true);
        }
      });
      rowsEl.appendChild(tr);
    }
  }

  function syncRepeatUi() {
    const repeat = form.repeat.value;
    $("#repeat-days").hidden = repeat !== "weekly";
    const timed = repeat !== "none";
    $("#repeat-start-label").hidden = !timed;
    $("#repeat-end-label").hidden = !timed;
    $("#repeat-hint").hidden = !timed;
  }

  function openForm(m) {
    form.hidden = false;
    $("#message-error").hidden = true;
    $("#message-form-title").textContent = m ? "Edit message" : "New message";
    form.id.value = m ? m.id : "";
    form.text.value = m ? m.text : "";
    form.priority.value = m ? m.priority : 0;
    form.enabled.checked = m ? m.enabled : true;
    form.starts_at.value = toLocalInput(m && m.starts_at);
    form.ends_at.value = toLocalInput(m && m.ends_at);
    form.repeat.value = m ? m.repeat : "none";
    $$('input[name="day"]', form).forEach((cb) => (cb.checked = !!(m && m.repeat_days & Number(cb.value))));
    form.repeat_start.value = (m && m.repeat_start) || "";
    form.repeat_end.value = (m && m.repeat_end) || "";
    syncRepeatUi();
    preview();
    form.text.focus();
    form.scrollIntoView({ block: "nearest" });
  }

  $("#new-message").addEventListener("click", () => openForm(null));
  $("#message-cancel").addEventListener("click", () => (form.hidden = true));
  form.repeat.addEventListener("change", syncRepeatUi);

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const days = $$('input[name="day"]:checked', form).reduce((n, cb) => n + Number(cb.value), 0);
    const body = {
      text: form.text.value,
      priority: Number(form.priority.value),
      enabled: form.enabled.checked,
      starts_at: fromLocalInput(form.starts_at.value),
      ends_at: fromLocalInput(form.ends_at.value),
      repeat: form.repeat.value,
      repeat_days: form.repeat.value === "weekly" ? days : 0,
      repeat_start: form.repeat.value !== "none" && form.repeat_start.value ? form.repeat_start.value : null,
      repeat_end: form.repeat.value !== "none" && form.repeat_end.value ? form.repeat_end.value : null,
    };
    try {
      if (form.id.value) await api(`/api/messages/${form.id.value}`, { method: "PATCH", body });
      else await api("/api/messages", { method: "POST", body });
      form.hidden = true;
      toast(form.id.value ? "Saved." : "On the board.");
      await loadMessages();
    } catch (e) {
      const err = $("#message-error");
      err.textContent = e.message;
      err.hidden = false;
    }
  });

  // ---- preview (the server lays the text out, so it can never differ from the board)
  let previewTimer = 0;
  async function preview() {
    const text = form.text.value;
    try {
      const p = await api("/api/messages/preview", { method: "POST", body: { text } });
      renderGrid($("#preview-grid"), p.rows, p.grid_rows, p.grid_cols);
      const bits = [`${p.used} / ${p.capacity} cells`];
      if (p.overflow) bits.push(`too long by ${p.rows.length - p.grid_rows} row${p.rows.length - p.grid_rows > 1 ? "s" : ""}`);
      if (p.unknown.length) bits.push(`shown blank: ${p.unknown.join(" ")}`);
      if (p.missing_images.length) bits.push(`upload first: ${p.missing_images.map((s) => `{img:${s}}`).join(" ")}`);
      const meta = $("#preview-meta");
      meta.textContent = bits.join(" · ");
      meta.classList.toggle("error", p.overflow || p.missing_images.length > 0);
      $("#message-save").disabled = p.overflow || p.missing_images.length > 0;
    } catch (e) {
      $("#preview-meta").textContent = e.message;
    }
  }
  form.text.addEventListener("input", () => {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(preview, 150);
  });

  // ---- display
  const display = $("#display-form");
  function syncCustom() {
    const custom = display.grid_preset.value === "custom";
    display.rows.disabled = !custom;
    display.cols.disabled = !custom;
  }
  async function loadDisplay() {
    const s = await api("/api/settings");
    display.grid_preset.value = s.grid_preset;
    display.rows.value = s.rows;
    display.cols.value = s.cols;
    display.animation.value = s.animation;
    $("#animation-value").value = s.animation;
    display.sound_enabled.checked = s.sound_enabled;
    display.sound_volume.value = s.sound_volume;
    display.theme.value = s.theme;
    display.idle_text.value = s.idle_text;
    display.poll_seconds.value = s.poll_seconds;
    display.rotate_seconds.value = s.rotate_seconds;
    syncCustom();
  }
  $$('input[name="grid_preset"]', display).forEach((r) => r.addEventListener("change", syncCustom));
  display.animation.addEventListener("input", () => ($("#animation-value").value = display.animation.value));
  display.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const body = {
      grid_preset: display.grid_preset.value,
      animation: Number(display.animation.value),
      sound_enabled: display.sound_enabled.checked,
      sound_volume: Number(display.sound_volume.value),
      theme: display.theme.value,
      idle_text: display.idle_text.value,
      poll_seconds: Number(display.poll_seconds.value),
      rotate_seconds: Number(display.rotate_seconds.value),
    };
    if (body.grid_preset === "custom") {
      body.rows = Number(display.rows.value);
      body.cols = Number(display.cols.value);
    }
    try {
      await api("/api/settings", { method: "PATCH", body });
      $("#display-status").textContent = "Saved. The board picks it up on its next poll.";
      await loadDisplay();
      if (!form.hidden) preview();
      await loadMessages(); // capacity may have changed the states' layout
    } catch (e) {
      toast(e.message, true);
    }
  });

  // ---- images
  const imageList = $("#image-list");
  async function loadImages() {
    const items = await api("/api/images");
    imageList.textContent = "";
    if (!items.length) {
      imageList.innerHTML = '<li class="muted">No pictures yet.</li>';
      return;
    }
    for (const img of items) {
      const li = document.createElement("li");
      li.innerHTML = `<img alt=""> <code class="token"></code>
        <button type="button" class="link copy">Copy token</button> <button type="button" class="link delete">Delete</button>
        <span class="muted size"></span>`;
      $("img", li).src = `${img.url}?v=${Date.now()}`;
      $(".token", li).textContent = img.token;
      $(".size", li).textContent = `${Math.round(img.bytes / 1024)} KB`;
      $(".copy", li).addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(img.token);
          toast(`${img.token} copied — paste it into a message.`);
        } catch {
          toast(img.token);
        }
      });
      $(".delete", li).addEventListener("click", async () => {
        if (!confirm(`Delete ${img.token}? Messages using it will show a blank.`)) return;
        try {
          await api(`/api/images/${img.slug}`, { method: "DELETE" });
          await loadImages();
        } catch (e) {
          toast(e.message, true);
        }
      });
      imageList.appendChild(li);
    }
  }
  $("#image-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    const fd = new FormData();
    fd.append("file", f.file.files[0]);
    if (f.slug.value) fd.append("slug", f.slug.value);
    try {
      const img = await api("/api/images", { method: "POST", form: fd });
      toast(`Uploaded. Put ${img.token} in a message.`);
      f.reset();
      await loadImages();
      if (!form.hidden) preview();
    } catch (e) {
      toast(e.message, true);
    }
  });

  // ---- server time ticks in the configured zone (rendered by the server; advance locally)
  const timeEl = $("#server-time");
  const base = new Date(timeEl.textContent.replace(" ", "T"));
  const loaded = Date.now();
  if (!Number.isNaN(base.getTime())) {
    setInterval(() => {
      const d = new Date(base.getTime() + (Date.now() - loaded));
      const pad = (n) => String(n).padStart(2, "0");
      timeEl.textContent = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }, 15000);
  }

  loadMessages().catch((e) => toast(e.message, true));
  loadDisplay().catch((e) => toast(e.message, true));
  loadImages().catch((e) => toast(e.message, true));
})();
