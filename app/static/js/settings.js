// The settings page: messages, display, images, guests. Plain fetch to the API with the session
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

  // ---- tabs: six panels, hash-addressed (#messages), the last one remembered per browser.
  // Sections keep their ids inside the panels; a hash naming a section opens its tab and scrolls
  // to it. The live card sits in an aside: pinned beside every tab above 1100 px, shown under the
  // Board tab below that and moved off-stage (never display:none — it is the page's heartbeat)
  // while another tab shows.
  const desktop = window.matchMedia("(min-width: 1100px)");
  const side = $("#side");
  const TABS = ["board", "messages", "pictures", "guests", "boards", "setup"];
  const TAB_OF = { live: "board", look: "board", display: "board", backdrop: "board", flaps: "board", frame: "board", images: "pictures", calendar: "boards", addresses: "setup", token: "setup" };
  const tabButtons = TABS.map((t) => $(`#tab-${t}`));
  let currentTab = "";
  function tabForHash(hash) {
    const id = (hash || "").replace(/^#/, "");
    if (TABS.includes(id)) return id;
    if (TAB_OF[id]) return TAB_OF[id];
    const el = id && document.getElementById(id);
    const panel = el && el.closest(".panel");
    return panel ? panel.id.replace("panel-", "") : "";
  }
  function showTab(name, { focus = false, scrollTo = "" } = {}) {
    if (!TABS.includes(name)) name = "board";
    currentTab = name;
    for (const t of TABS) {
      const on = t === name;
      const btn = $(`#tab-${t}`);
      btn.setAttribute("aria-selected", String(on));
      btn.tabIndex = on ? 0 : -1;
      $(`#panel-${t}`).hidden = !on;
    }
    const off = name !== "board" && !desktop.matches;
    side.classList.toggle("offstage", off); // keeps the live frame alive while another tab shows
    side.setAttribute("aria-hidden", String(off));
    side.inert = off;
    try {
      localStorage.setItem("departureboard.tab", name);
    } catch {
      /* private mode, blocked storage: the hash still works */
    }
    if (focus) $(`#tab-${name}`).focus();
    if (scrollTo) {
      const el = document.getElementById(scrollTo);
      if (el) el.scrollIntoView({ block: "start" });
    }
  }
  function openHash(hash, focus) {
    const id = (hash || "").replace(/^#/, "");
    const name = tabForHash(hash);
    if (!name) return false;
    showTab(name, { focus, scrollTo: TABS.includes(id) ? "" : id });
    return true;
  }
  tabButtons.forEach((btn, i) => {
    const name = TABS[i];
    btn.addEventListener("click", () => {
      showTab(name, { focus: true });
      history.replaceState(null, "", `#${name}`);
    });
    btn.addEventListener("keydown", (ev) => {
      const step = { ArrowRight: 1, ArrowLeft: -1, Home: -i, End: TABS.length - 1 - i }[ev.key];
      if (step === undefined) return;
      ev.preventDefault();
      const next = TABS[(i + step + TABS.length) % TABS.length];
      showTab(next, { focus: true });
      history.replaceState(null, "", `#${next}`);
    });
  });
  window.addEventListener("hashchange", () => openHash(location.hash, false));
  desktop.addEventListener("change", () => {
    showTab(currentTab);
    placePreview();
  });
  {
    let remembered = "";
    try {
      remembered = localStorage.getItem("departureboard.tab") || "";
    } catch {
      /* no storage */
    }
    if (!openHash(location.hash, false)) showTab(TABS.includes(remembered) ? remembered : "board");
  }
  // a link to a section elsewhere on the page (the README, a toast) opens its tab
  document.addEventListener("click", (ev) => {
    const a = ev.target.closest('a[href^="#"]');
    if (a && openHash(a.getAttribute("href"), false)) ev.preventDefault();
  });

  // ---- the phone: a sheet is a screen of its own. A block that lives in a section (a form, the
  // theme chooser) is moved into the dialog, the host makes the change, and Back — or a save —
  // puts the block back and returns to the screen they came from. Nothing is duplicated.
  const phone = window.matchMedia("(max-width: 700px)");
  const sheet = $("#sheet");
  const sheetBody = $("#sheet-body");
  let sheetHome = null; // where the block came from: { el, parent, next }
  function openSheet(el, title) {
    if (!el) return;
    closeSheet();
    sheetHome = { el, parent: el.parentNode, next: el.nextSibling };
    sheetBody.appendChild(el);
    $("#sheet-title").textContent = title;
    if (!sheet.open) sheet.showModal();
    document.body.classList.add("sheet-open");
    sheet.scrollTop = 0;
    const first = el.querySelector("input:not([type=hidden]):not(.sr-only):not([type=file]), select, textarea, [role=radio][tabindex='0'], button");
    if (first) first.focus();
  }
  function closeSheet() {
    if (!sheetHome) return;
    const { el, parent, next } = sheetHome;
    sheetHome = null;
    parent.insertBefore(el, next);
    if (sheet.open) sheet.close();
    document.body.classList.remove("sheet-open");
    // Back on a form that was mid-edit: it goes home closed, not half-open on the main screen
    // (a form with an <input name="id"> answers form.id with that input — read the attribute)
    const id = el.getAttribute("id");
    if (id === "message-form" && !el.hidden) closeForm();
    if (id === "calendar-form" && !$("#calendar-cancel").hidden) $("#calendar-cancel").click();
  }
  // a block's job is done (saved, applied): back to the screen it came from
  function sheetDone(el) {
    if (sheetHome && el && (sheetHome.el === el || sheetHome.el.contains(el))) {
      const opener = document.querySelector(`[data-sheet="${sheetHome.el.getAttribute("id")}"]`);
      closeSheet();
      if (opener) opener.focus();
    }
  }
  sheet.addEventListener("close", closeSheet); // Esc, or the browser's own back gesture
  $("#sheet-back").addEventListener("click", closeSheet);
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-sheet]");
    if (!b) return;
    openSheet(document.getElementById(b.dataset.sheet), b.dataset.title || b.textContent.trim());
  });
  phone.addEventListener("change", () => {
    if (!phone.matches) closeSheet();
    syncLiveStrip();
  });
  // an empty state's button goes to the block that fills it: its sheet on a phone, the block
  // itself (its tab shown, its first control focused) on a desk
  function reach(blockId, sel) {
    const block = document.getElementById(blockId);
    if (!block) return;
    const panel = block.closest(".panel");
    if (panel) showTab(panel.id.replace("panel-", ""));
    const launcher = document.querySelector(`[data-sheet="${blockId}"]`);
    if (phone.matches && launcher) {
      launcher.click();
    } else {
      block.scrollIntoView({ block: "start" });
    }
    const control = sel && block.querySelector(sel);
    if (control) {
      control.focus({ preventScroll: true });
      if (control.type === "file") control.click();
    }
  }
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-reach]");
    if (b) reach(b.dataset.reach, b.dataset.sel || "");
  });
  // the live card on a phone: a strip that says what is on, the picture on tap
  const liveSection = $("#live");
  const liveToggle = $("#live-toggle");
  let liveExpanded = false;
  function syncLiveStrip() {
    const mini = phone.matches && !liveExpanded;
    liveSection.classList.toggle("mini", mini);
    liveToggle.setAttribute("aria-expanded", String(!mini));
    liveToggle.textContent = mini ? "Show" : "Hide";
  }
  liveToggle.addEventListener("click", () => {
    liveExpanded = !liveExpanded;
    syncLiveStrip();
  });
  syncLiveStrip();

  // ---- show something now: the line a host types from the sofa
  const nowForm = $("#now-form");
  const NOW_LABEL = { 30: "30 seconds", 120: "2 minutes", 600: "10 minutes" };
  nowForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const text = nowForm.text.value.trim();
    if (!text) return;
    const secs = nowForm.show_seconds.value ? Number(nowForm.show_seconds.value) : null;
    try {
      await api("/api/messages/now", { method: "POST", body: { text, show_seconds: secs } });
      nowForm.text.value = "";
      $("#now-status").textContent = `${text} — on the TV ${secs ? `for ${NOW_LABEL[secs]} when taking turns` : "until it is replaced"}.`;
      toast(`On the board: ${text}`);
      await loadMessages();
      refreshLive();
    } catch (e) {
      toast(e.message, true);
    }
  });

  // ---- Copy buttons: the addresses, the walkthrough's address and token.
  document.addEventListener("click", async (ev) => {
    const b = ev.target.closest(".copy[data-copy]");
    if (!b) return;
    try {
      await navigator.clipboard.writeText(b.dataset.copy);
      toast(`${b.dataset.copy.length > 40 ? "Copied" : b.dataset.copy + " copied"}.`);
    } catch {
      toast(b.dataset.copy);
    }
  });

  // ---- boards: the live board saved under a name, switched, copied, renamed, deleted. The
  // listing says which is active and whether the live board changed since it was saved (the dot).
  let boards = [];
  let activeBoard = null; // the listing entry of the active profile, or null
  const boardStatus = $("#boards-status");
  const boardSwitch = $("#board-switch");
  const slugify = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "board";
  const fmtSaved = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "");
  let renderBoards = function () {
    activeBoard = boards.find((b) => b.active) || null;
    $("#board-name").textContent = activeBoard ? activeBoard.name : "unsaved board";
    $("#board-dot").hidden = !(activeBoard && activeBoard.changed);
    $("#tab-boards-dot").hidden = !(activeBoard && activeBoard.changed);
    $("#board-meta").textContent = activeBoard ? `${activeBoard.messages} message${activeBoard.messages === 1 ? "" : "s"} · saved ${fmtSaved(activeBoard.saved_at)}${activeBoard.pictures_missing.length ? ` · missing ${activeBoard.pictures_missing.map((s) => `{img:${s}}`).join(" ")}` : ""}` : "— Save as… keeps it under a name";
    const current = boardSwitch.value;
    boardSwitch.textContent = "";
    boardSwitch.append(new Option("Switch…", ""));
    for (const b of boards) boardSwitch.append(new Option(`${b.name} · ${b.messages} message${b.messages === 1 ? "" : "s"}${b.saved_at ? ` · ${fmtSaved(b.saved_at)}` : ""}${b.active ? " (this board)" : ""}`, b.slug));
    boardSwitch.value = boards.some((b) => b.slug === current) ? current : "";
    boardSwitch.disabled = !boards.length;
    for (const id of ["board-duplicate", "board-rename", "board-delete"]) $(`#${id}`).disabled = !activeBoard;
    $("#boards-empty").hidden = boards.length > 0;
  };
  $("#boards-empty-save").addEventListener("click", () => $("#board-save-as").click());
  async function loadProfiles() {
    boards = await api("/api/profiles");
    renderBoards();
  }
  async function refreshAll() {
    await loadVideos();
    await loadMessages();
    await loadDisplay();
    await loadImages();
    if (!form.hidden) preview();
    refreshLive();
  }
  async function saveBoard(slug, name, said) {
    try {
      const out = await api(`/api/profiles/${slug}/save`, { method: "POST", body: name ? { name } : {} });
      await loadProfiles();
      boardStatus.textContent = said || `Saved as ${out.name}.`;
      toast(`${out.name} saved — ${out.messages} message${out.messages === 1 ? "" : "s"} and the display.`);
    } catch (e) {
      toast(e.message, true);
    }
  }
  $("#board-save").addEventListener("click", () => {
    if (activeBoard) saveBoard(activeBoard.slug, null, `${activeBoard.name} saved.`);
    else $("#board-save-as").click();
  });
  $("#board-save-as").addEventListener("click", () => {
    const name = prompt("Save this board as…", activeBoard ? activeBoard.name : "Party");
    if (!name || !name.trim()) return;
    const slug = slugify(name.trim());
    const taken = boards.find((b) => b.slug === slug);
    if (taken && !(activeBoard && taken.slug === activeBoard.slug) && !confirm(`Overwrite the saved board “${taken.name}”?`)) return;
    saveBoard(slug, name.trim());
  });
  boardSwitch.addEventListener("change", async () => {
    const slug = boardSwitch.value;
    if (!slug) return;
    const target = boards.find((b) => b.slug === slug);
    if (activeBoard && activeBoard.changed && !confirm(`Switch to “${target.name}”? This board has changes since it was saved.`)) {
      boardSwitch.value = "";
      return;
    }
    if (!activeBoard && messages.length && !confirm(`Switch to “${target.name}”? This board is not saved; its messages are replaced.`)) {
      boardSwitch.value = "";
      return;
    }
    try {
      const out = await api(`/api/profiles/${slug}/load`, { method: "POST" });
      await loadProfiles();
      await refreshAll();
      const kept = out.kept_disabled.length;
      boardStatus.textContent = `${out.name} is on the board${kept ? ` — ${kept} message${kept === 1 ? "" : "s"} did not fit and ${kept === 1 ? "is" : "are"} disabled` : ""}.`;
      toast(`${out.name} loaded — the TV follows on its next poll.`);
      boardSwitch.value = "";
      boardSwitch.focus();
    } catch (e) {
      toast(e.message, true);
      boardSwitch.value = "";
    }
  });
  $("#board-duplicate").addEventListener("click", async () => {
    if (!activeBoard) return;
    $("#board-more").open = false;
    const name = prompt("Name for the copy", `${activeBoard.name} copy`);
    if (!name || !name.trim()) return;
    try {
      const out = await api(`/api/profiles/${activeBoard.slug}/copy`, { method: "POST", body: { slug: slugify(name.trim()), name: name.trim() } });
      await loadProfiles();
      boardStatus.textContent = `${out.name} saved as a copy — Switch… to open it.`;
      toast(`${out.name} is a copy of ${activeBoard.name}.`);
    } catch (e) {
      toast(e.message, true);
    }
  });
  $("#board-rename").addEventListener("click", async () => {
    if (!activeBoard) return;
    $("#board-more").open = false;
    const name = prompt("Rename this board", activeBoard.name);
    if (!name || !name.trim() || name.trim() === activeBoard.name) return;
    try {
      await api(`/api/profiles/${activeBoard.slug}`, { method: "PATCH", body: { name: name.trim() } });
      await loadProfiles();
      boardStatus.textContent = `Renamed to ${name.trim()}.`;
    } catch (e) {
      toast(e.message, true);
    }
  });
  $("#board-delete").addEventListener("click", async () => {
    if (!activeBoard) return;
    $("#board-more").open = false;
    if (!confirm(`Delete the saved board “${activeBoard.name}”? What is on the TV stays as it is.`)) return;
    try {
      const was = activeBoard.name;
      await api(`/api/profiles/${activeBoard.slug}`, { method: "DELETE" });
      await loadProfiles();
      boardStatus.textContent = `${was} deleted — this board is unsaved now.`;
      $("#board-save-as").focus();
    } catch (e) {
      toast(e.message, true);
    }
  });

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

  // ---- the board in a frame: the live card polls on its own and tells us what it shows; the
  // form preview never polls and paints the rows we post. Both are this origin's board page.
  const liveFrame = $("#live-board");
  const previewFrame = $("#preview-board");
  const liveNow = $("#live-now");
  let liveId = null; // message id the live frame shows; null = idle
  let liveKnown = false; // has the live frame reported yet?
  let liveLookedUp = undefined; // an id we reloaded the list for (a message made via the API)
  let liveTimer = null; // { seconds, remaining, at } while the board rotates; counted down here
  let liveTick = 0;
  let lastPreview = null; // the last board:show; resent when the preview frame says it is ready

  function post(frame, msg) {
    if (frame && frame.contentWindow) frame.contentWindow.postMessage(msg, location.origin);
  }
  const refreshLive = () => {
    post(liveFrame, { type: "board:refresh" });
    loadProfiles().catch(() => {}); // every change ends here: the Boards strip's dot follows
  };

  window.addEventListener("message", (e) => {
    if (e.origin !== location.origin || !e.data || typeof e.data.type !== "string") return;
    const fromLive = !!liveFrame && e.source === liveFrame.contentWindow;
    const fromPreview = !!previewFrame && e.source === previewFrame.contentWindow;
    if (e.data.type === "board:current" && fromLive) {
      liveId = e.data.message_id;
      liveKnown = true;
      const t = e.data.timer;
      liveTimer = t && t.seconds > 0 ? { seconds: t.seconds, remaining: t.remaining, at: performance.now() } : null;
      clearInterval(liveTick);
      liveTick = liveTimer ? window.setInterval(renderLive, 1000) : 0;
      renderLive();
    } else if (e.data.type === "board:ready" && fromPreview && lastPreview) {
      post(previewFrame, lastPreview);
    }
    // a poll that brought new settings re-applied the saved background and flap shape; put the drafts back
    if (e.data.type === "board:current" && fromLive && (bgDirty() || flapDirty() || frameDirty())) {
      post(liveFrame, { type: "board:settings", settings: { ...bgDraft, ...flapDraft, ...frameDraft } });
    }
  });

  const firstLine = (text) => (text.split("\n").find((l) => l.trim()) || text).trim();
  const fmtUntil = (m) => {
    if (m.ends_at) return `until ${new Date(m.ends_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}`;
    if (m.repeat !== "none" && m.repeat_end) return `until ${m.repeat_end}`;
    return "until it is replaced";
  };
  function renderLive() {
    if (!liveNow) return;
    if (!liveKnown) {
      liveNow.textContent = "Waiting for the board…";
      return;
    }
    if (liveId === null) {
      liveNow.innerHTML = 'Idle — the board shows the idle text. <button type="button" class="link" data-reach="display-form" data-sel="input[name=idle_text]">Set it in Display</button>';
      return;
    }
    const m = messages.find((x) => x.id === liveId);
    if (!m) {
      liveNow.textContent = "Live now: a message that is not in the list yet…";
      if (liveLookedUp !== liveId) {
        liveLookedUp = liveId;
        loadMessages().catch(() => {});
      }
      return;
    }
    let line = `Live now: ${firstLine(m.text)} · ${fmtUntil(m)}`;
    if (liveTimer) {
      const left = Math.max(0, Math.round(liveTimer.remaining - (performance.now() - liveTimer.at) / 1000));
      line += ` · next in ${left} s`;
    }
    liveNow.textContent = line;
  }

  // ---- messages
  const form = $("#message-form");
  const rowsEl = $("#message-rows");
  const display = $("#display-form");
  let messages = [];
  let formOpener = null; // the button that opened the form; focus goes back to it on close

  async function loadMessages() {
    messages = await api("/api/messages");
    if (!messages.length) {
      rowsEl.innerHTML = '<tr><td colspan="4"><p class="empty" id="messages-empty"><span>Nothing scheduled yet.</span> <button type="button" class="small">Write your first message</button></p></td></tr>';
      $("#messages-empty button").addEventListener("click", () => $("#new-message").click());
      renderLive();
      return;
    }
    rowsEl.textContent = "";
    for (const m of messages) {
      const tr = document.createElement("tr");
      tr.dataset.id = m.id;
      tr.innerHTML = `<td class="state"><label class="switch"><input type="checkbox" role="switch"><span class="track" aria-hidden="true"></span></label><span class="badge ${m.state}">${m.state}</span></td>
        <td class="text"></td><td class="muted"></td>
        <td class="actions"><button type="button" class="link edit">Edit</button> <button type="button" class="link delete">Delete</button></td>`;
      $(".text", tr).textContent = m.text;
      $(".muted", tr).textContent = `${fmtWhen(m)} · p${m.priority}${m.show_seconds ? ` · ${m.show_seconds} s` : ""}`;
      const sw = $(".switch input", tr);
      sw.checked = m.enabled;
      sw.setAttribute("aria-label", `Enabled: ${firstLine(m.text) || "blank message"}`);
      sw.addEventListener("change", () => toggleEnabled(m, tr, sw));
      $(".edit", tr).addEventListener("click", (ev) => openForm(m, ev.currentTarget));
      $(".delete", tr).addEventListener("click", async () => {
        if (!confirm(`Delete “${m.text.slice(0, 40)}”?`)) return;
        try {
          await api(`/api/messages/${m.id}`, { method: "DELETE" });
          toast("Deleted.");
          await loadMessages();
          refreshLive();
          $("#new-message").focus();
        } catch (e) {
          toast(e.message, true);
        }
      });
      rowsEl.appendChild(tr);
    }
    renderLive();
  }

  // The row switch: PATCH {enabled} alone; the state badge follows the response. The row is
  // updated in place so focus stays on the switch; on error the switch goes back and says why.
  async function toggleEnabled(m, tr, sw) {
    const enabled = sw.checked;
    try {
      const saved = await api(`/api/messages/${m.id}`, { method: "PATCH", body: { enabled } });
      Object.assign(m, saved); // the edit form opens on the new state
      const badge = $(".badge", tr);
      badge.className = `badge ${saved.state}`;
      badge.textContent = saved.state;
      toast(enabled ? `Enabled — now ${saved.state}.` : "Disabled.");
      refreshLive();
    } catch (e) {
      sw.checked = !enabled;
      toast(e.message, true);
    }
  }

  // Focus the Edit button of a row (after the list was rebuilt), else "New message".
  function focusRow(id) {
    const btn = id && $(`tr[data-id="${id}"] .edit`, rowsEl);
    (btn || $("#new-message")).focus();
  }

  function syncRepeatUi() {
    const repeat = form.repeat.value;
    $("#repeat-days").hidden = repeat !== "weekly";
    const timed = repeat !== "none";
    $("#repeat-start-label").hidden = !timed;
    $("#repeat-end-label").hidden = !timed;
    $("#repeat-hint").hidden = !timed;
  }

  // The form's preview block: inside the form, or pinned under the live card while the form is
  // open on a wide screen — one frame, moved, never duplicated.
  function placePreview() {
    const block = document.querySelector("#message-form .preview, #side .preview");
    if (!block) return;
    if (desktop.matches && !form.hidden) {
      if (block.parentElement !== side) side.appendChild(block);
    } else if (block.parentElement !== form) {
      form.insertBefore(block, form.querySelector(".grid2"));
    }
  }

  function openForm(m, opener) {
    formOpener = opener || null;
    if (previewFrame && !previewFrame.getAttribute("src")) previewFrame.src = "/?embed&preview";
    form.hidden = false;
    placePreview();
    if (phone.matches) openSheet(form, m ? "Edit message" : "New message");
    $("#message-error").hidden = true;
    $("#message-form-title").textContent = m ? "Edit message" : "New message";
    form.id.value = m ? m.id : "";
    form.text.value = m ? m.text : "";
    form.priority.value = m ? m.priority : 0;
    form.show_seconds.value = m && m.show_seconds ? m.show_seconds : "";
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

  function closeForm() {
    form.hidden = true;
    placePreview();
    sheetDone(form);
    if (formOpener && formOpener.isConnected) formOpener.focus();
    else focusRow(Number(form.id.value) || 0);
    formOpener = null;
  }

  $("#new-message").addEventListener("click", (ev) => openForm(null, ev.currentTarget));
  $("#message-cancel").addEventListener("click", closeForm);
  form.repeat.addEventListener("change", syncRepeatUi);

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const days = $$('input[name="day"]:checked', form).reduce((n, cb) => n + Number(cb.value), 0);
    const body = {
      text: form.text.value,
      priority: Number(form.priority.value),
      show_seconds: form.show_seconds.value ? Number(form.show_seconds.value) : null,
      enabled: form.enabled.checked,
      starts_at: fromLocalInput(form.starts_at.value),
      ends_at: fromLocalInput(form.ends_at.value),
      repeat: form.repeat.value,
      repeat_days: form.repeat.value === "weekly" ? days : 0,
      repeat_start: form.repeat.value !== "none" && form.repeat_start.value ? form.repeat_start.value : null,
      repeat_end: form.repeat.value !== "none" && form.repeat_end.value ? form.repeat_end.value : null,
    };
    try {
      const id = form.id.value;
      const saved = id
        ? await api(`/api/messages/${id}`, { method: "PATCH", body })
        : await api("/api/messages", { method: "POST", body });
      form.hidden = true;
      placePreview();
      sheetDone(form);
      toast(id ? "Saved." : "On the board.");
      await loadMessages();
      refreshLive();
      focusRow(saved && saved.id);
      formOpener = null;
    } catch (e) {
      const err = $("#message-error");
      err.textContent = e.message;
      err.hidden = false;
    }
  });

  // ---- look & feel: the theme swatches apply at once (one PATCH, the row-switch pattern)
  let currentTheme = "classic-black";
  const swatches = $$("#theme-choices .swatch");
  function markTheme(theme) {
    currentTheme = theme;
    swatches.forEach((b) => {
      const on = b.dataset.theme === theme;
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on ? 0 : -1;
    });
    if (lastPreview) {
      lastPreview.settings.theme = theme;
      post(previewFrame, lastPreview);
    }
  }
  async function chooseTheme(theme, focus) {
    const was = currentTheme;
    markTheme(theme);
    try {
      const saved = await api("/api/settings", { method: "PATCH", body: { theme } });
      markTheme(saved.theme);
      $("#look-status").textContent = `${theme.replace(/-/g, " ")} — the TV picks it up on its next poll.`;
      refreshLive();
      sheetDone($("#look-theme"));
    } catch (e) {
      markTheme(was);
      toast(e.message, true);
    }
    if (focus) swatches.find((b) => b.dataset.theme === currentTheme)?.focus();
  }
  swatches.forEach((b, i) => {
    b.addEventListener("click", () => chooseTheme(b.dataset.theme, false));
    b.addEventListener("keydown", (ev) => {
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
      if (!step) return;
      ev.preventDefault();
      const next = swatches[(i + step + swatches.length) % swatches.length];
      chooseTheme(next.dataset.theme, true);
    });
  });

  // ---- look & feel: a picture behind the board. The frames follow the draft at once through
  // board:settings; Save writes the four settings in one PATCH; Clear removes the picture now.
  const bgForm = $("#backdrop-form");
  const bgChoices = $("#backdrop-choices");
  const bgStatus = $("#backdrop-status");
  const BG = ["background_image", "background_blur", "background_dim", "background_fit"];
  const bgDraft = { background_image: "", background_blur: 12, background_dim: 30, background_fit: "cover" };
  let bgSaved = { ...bgDraft };
  const bgDirty = () => BG.some((k) => bgDraft[k] !== bgSaved[k]);
  const bgSwatches = () => $$(".swatch", bgChoices);
  function markBg(value) {
    bgDraft.background_image = value;
    const all = bgSwatches();
    let found = false;
    all.forEach((b) => {
      const on = b.dataset.bg === value;
      found = found || on;
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on ? 0 : -1;
    });
    if (!found && all.length) all[0].tabIndex = 0; // the picture is gone: None takes the tab stop
  }
  function showBgDraft() {
    $("#blur-value").textContent = `${bgDraft.background_blur} px`;
    $("#dim-value").textContent = `${bgDraft.background_dim} %`;
    const msg = { type: "board:settings", settings: { ...bgDraft } };
    post(liveFrame, msg);
    post(previewFrame, msg);
  }
  function fillBgForm(s) {
    BG.forEach((k) => (bgSaved[k] = s[k]));
    Object.assign(bgDraft, bgSaved);
    bgForm.background_blur.value = bgDraft.background_blur;
    bgForm.background_dim.value = bgDraft.background_dim;
    bgForm.background_fit.value = bgDraft.background_fit;
    markBg(bgDraft.background_image);
    showBgDraft();
  }
  // The video tiles: one per upload, the clip's first frame as the thumb (the media fragment makes
  // Safari paint one), a play mark, a cross that deletes the file.
  function renderBgVideos(items) {
    $$(".tile", bgChoices).forEach((t) => t.remove());
    for (const v of items) {
      const tile = document.createElement("div");
      tile.className = "tile";
      tile.innerHTML = '<button type="button" class="swatch video" role="radio" aria-checked="false" tabindex="-1"><video muted playsinline preload="metadata" aria-hidden="true"></video><span class="play" aria-hidden="true">▶ video</span><span></span></button><button type="button" class="remove" aria-label="Delete this video" title="Delete this video">×</button>';
      const b = $(".swatch", tile);
      b.dataset.bg = `video:${v.slug}`;
      $("video", b).src = `${v.url}?v=${v.bytes}#t=0.5`;
      $("span:not(.play)", b).textContent = v.slug;
      $(".remove", tile).dataset.slug = v.slug;
      bgChoices.appendChild(tile);
    }
    markBg(bgDraft.background_image);
  }
  async function loadVideos() {
    renderBgVideos(await api("/api/videos"));
  }
  function renderBgUploads(items) {
    bgSwatches().filter((b) => b.dataset.bg.startsWith("img:")).forEach((b) => b.remove());
    for (const img of items) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "swatch";
      b.setAttribute("role", "radio");
      b.dataset.bg = `img:${img.slug}`;
      b.tabIndex = -1;
      b.innerHTML = '<img alt="" width="320" height="180" loading="lazy"><span></span>';
      $("img", b).src = `${img.url}?v=${img.bytes}`;
      $("span", b).textContent = img.slug;
      bgChoices.appendChild(b);
    }
    markBg(bgDraft.background_image);
  }
  const bgName = (v) => (v.startsWith("img:") ? v.slice(4) : v.startsWith("builtin:") ? v.slice(8) : v.startsWith("video:") ? `the video ${v.slice(6)}` : "none");
  function pickBg(value, focus) {
    // a moving picture under a blur filter is what a TV stick cannot afford: a video starts sharp
    if (value.startsWith("video:") && !bgDraft.background_image.startsWith("video:") && bgDraft.background_blur === bgSaved.background_blur) {
      bgDraft.background_blur = 0;
      bgForm.background_blur.value = 0;
    }
    markBg(value);
    showBgDraft();
    bgStatus.textContent = value ? `${bgName(value)} on the card — Save to put it on the TV.` : "No picture — Save to take it off the TV.";
    if (focus) bgSwatches().find((b) => b.dataset.bg === value)?.focus();
  }
  bgChoices.addEventListener("click", async (e) => {
    const x = e.target.closest(".remove");
    if (x) {
      const slug = x.dataset.slug;
      if (!confirm(`Delete the video ${slug}? If it is on the TV, the TV goes back to no picture.`)) return;
      try {
        await api(`/api/videos/${slug}`, { method: "DELETE" });
        if (bgDraft.background_image === `video:${slug}`) bgDraft.background_image = "";
        if (bgSaved.background_image === `video:${slug}`) bgSaved.background_image = "";
        await loadVideos();
        showBgDraft();
        bgStatus.textContent = `${slug} deleted.`;
        refreshLive();
      } catch (err) {
        toast(err.message, true);
      }
      return;
    }
    const b = e.target.closest(".swatch");
    if (b) pickBg(b.dataset.bg, false);
  });
  bgChoices.addEventListener("keydown", (ev) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
    const b = ev.target.closest(".swatch");
    if (!step || !b) return;
    ev.preventDefault();
    const all = bgSwatches();
    const next = all[(all.indexOf(b) + step + all.length) % all.length];
    pickBg(next.dataset.bg, true);
  });
  bgForm.background_blur.addEventListener("input", () => {
    bgDraft.background_blur = Number(bgForm.background_blur.value);
    showBgDraft();
  });
  bgForm.background_dim.addEventListener("input", () => {
    bgDraft.background_dim = Number(bgForm.background_dim.value);
    showBgDraft();
  });
  bgForm.background_fit.addEventListener("change", () => {
    bgDraft.background_fit = bgForm.background_fit.value;
    showBgDraft();
  });
  async function saveBg(body, said) {
    try {
      const saved = await api("/api/settings", { method: "PATCH", body });
      fillBgForm(saved);
      bgStatus.textContent = said;
      refreshLive();
      sheetDone(bgForm);
    } catch (e) {
      toast(e.message, true);
    }
  }
  bgForm.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const body = { ...bgDraft };
    saveBg(body, body.background_image ? "Saved — the TV picks it up on its next poll." : "Saved with no picture.");
  });
  $("#backdrop-clear").addEventListener("click", () => saveBg({ background_image: "" }, "Cleared — the blur and dim are kept for next time."));
  // A video is big: XMLHttpRequest for its upload progress; the token header as api() sends it.
  function uploadVideo(file) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/videos");
      Object.entries(HEADERS).forEach(([k, v]) => xhr.setRequestHeader(k, v)); // the session cookie goes along
      xhr.upload.addEventListener("progress", (ev) => {
        if (ev.lengthComputable) bgStatus.textContent = `Uploading ${file.name}… ${Math.round((ev.loaded / ev.total) * 100)} %`;
      });
      xhr.addEventListener("load", () => {
        let body = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch (e) {
          /* no body */
        }
        if (xhr.status >= 200 && xhr.status < 300) resolve(body);
        else reject(new Error((body && (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail))) || `${xhr.status} ${xhr.statusText}`));
      });
      xhr.addEventListener("error", () => reject(new Error("The upload failed — is the board reachable?")));
      const fd = new FormData();
      fd.append("file", file);
      xhr.send(fd);
    });
  }
  bgForm.video.addEventListener("change", async () => {
    const file = bgForm.video.files[0];
    if (!file) return;
    bgStatus.textContent = `Uploading ${file.name}…`;
    try {
      const v = await uploadVideo(file);
      bgForm.video.value = "";
      await loadVideos();
      pickBg(`video:${v.slug}`, false);
      bgStatus.textContent = `${v.slug} uploaded and on the card — Save to put it on the TV.`;
    } catch (e) {
      bgStatus.textContent = "";
      toast(e.message, true);
    }
  });
  bgForm.file.addEventListener("change", async () => {
    const file = bgForm.file.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const img = await api("/api/images", { method: "POST", form: fd });
      bgForm.file.value = "";
      await loadImages();
      pickBg(`img:${img.slug}`, false);
      bgStatus.textContent = `${img.slug} uploaded and on the card — Save to put it on the TV.`;
    } catch (e) {
      toast(e.message, true);
    }
  });

  // ---- look & feel: the shape of a flap. Three sliders the frames follow at once through
  // board:settings; Save writes the three settings in one PATCH; two presets set the draft.
  const flapForm = $("#flaps-form");
  const flapStatus = $("#flaps-status");
  const FLAPS = ["cell_radius", "cell_gap", "split_line"];
  const FLAP_CLASSIC = { cell_radius: 6, cell_gap: 35, split_line: 1 };
  const FLAP_PICTURE = { cell_radius: 0, cell_gap: 10, split_line: 0 };
  const flapDraft = { ...FLAP_CLASSIC };
  let flapSaved = { ...flapDraft };
  const flapDirty = () => FLAPS.some((k) => flapDraft[k] !== flapSaved[k]);
  function showFlapDraft() {
    $("#radius-value").textContent = `${flapDraft.cell_radius} %`;
    $("#gap-value").textContent = `${(flapDraft.cell_gap / 100).toFixed(2)} vmin`;
    $("#split-value").textContent = `${flapDraft.split_line} px`;
    FLAPS.forEach((k) => (flapForm[k].value = flapDraft[k]));
    const msg = { type: "board:settings", settings: { ...flapDraft } };
    post(liveFrame, msg);
    post(previewFrame, msg);
  }
  function fillFlapForm(s) {
    FLAPS.forEach((k) => (flapSaved[k] = Number(s[k])));
    Object.assign(flapDraft, flapSaved);
    showFlapDraft();
  }
  FLAPS.forEach((k) =>
    flapForm[k].addEventListener("input", () => {
      flapDraft[k] = Number(flapForm[k].value);
      showFlapDraft();
    }),
  );
  function presetFlaps(values, said) {
    Object.assign(flapDraft, values);
    showFlapDraft();
    flapStatus.textContent = said;
  }
  $("#flaps-picture").addEventListener("click", () => presetFlaps(FLAP_PICTURE, "Picture mode on the card — Save to put it on the TV."));
  $("#flaps-classic").addEventListener("click", () => presetFlaps(FLAP_CLASSIC, "Classic flaps on the card — Save to put them on the TV."));
  flapForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const saved = await api("/api/settings", { method: "PATCH", body: { ...flapDraft } });
      fillFlapForm(saved);
      flapStatus.textContent = "Saved — the TV picks it up on its next poll.";
      refreshLive();
      sheetDone(flapForm);
    } catch (e) {
      toast(e.message, true);
    }
  });

  // ---- look & feel: the frame. Five settings the frames follow at once through board:settings;
  // "" on a key = as the theme (the colour wells have an "as the theme" box beside them); Save
  // writes the five in one PATCH; two presets set the draft.
  const frameForm = $("#frame-form");
  const frameStatus = $("#frame-status");
  const FRAME = ["frame_color", "frame_width", "frame_radius", "frame_finish", "frame_glow", "frame_fit", "board_scale", "board_margin"];
  const FRAME_THEME = { frame_color: "", frame_width: "", frame_radius: "", frame_finish: "theme", frame_glow: "", frame_fit: "screen", board_scale: 100, board_margin: 0 };
  const FRAME_BLACK_CHROME = { frame_color: "#050308", frame_width: 2, frame_radius: 6, frame_finish: "chrome", frame_glow: "", frame_fit: "board", board_scale: 85, board_margin: 2 };
  const frameDraft = { ...FRAME_THEME };
  let frameSaved = { ...frameDraft };
  const frameDirty = () => FRAME.some((k) => frameDraft[k] !== frameSaved[k]);
  function showFrameDraft() {
    const d = frameDraft;
    frameForm.frame_color_theme.checked = d.frame_color === "";
    frameForm.frame_color.disabled = d.frame_color === "";
    if (d.frame_color) frameForm.frame_color.value = d.frame_color;
    frameForm.frame_glow_theme.checked = d.frame_glow === "";
    frameForm.frame_glow.disabled = d.frame_glow === "";
    if (d.frame_glow) frameForm.frame_glow.value = d.frame_glow;
    if (d.frame_width !== "") frameForm.frame_width.value = d.frame_width;
    if (d.frame_radius !== "") frameForm.frame_radius.value = d.frame_radius;
    $("#frame-width-value").textContent = d.frame_width === "" ? "as the theme" : `${d.frame_width} vmin`;
    const w = (d.frame_width === "" ? 3 : Number(d.frame_width)) + Number(d.board_margin);
    const capped = d.frame_radius !== "" && Number(d.frame_radius) > w * 3.4;
    $("#frame-radius-value").textContent = d.frame_radius === "" ? "as the theme" : `${d.frame_radius} vmin${capped ? " · capped by the width + margin" : ""}`;
    frameForm.frame_finish.value = d.frame_finish;
    frameForm.frame_fit.value = d.frame_fit;
    frameForm.board_scale.value = d.board_scale;
    frameForm.board_margin.value = d.board_margin;
    $("#board-scale-value").textContent = `${d.board_scale} %`;
    $("#board-margin-value").textContent = `${d.board_margin} vmin`;
    $("#frame-glow-row").hidden = d.frame_finish !== "neon";
    const msg = { type: "board:settings", settings: { ...d } };
    post(liveFrame, msg);
    post(previewFrame, msg);
  }
  function fillFrameForm(s) {
    FRAME.forEach((k) => (frameSaved[k] = s[k] === null || s[k] === undefined ? "" : s[k]));
    Object.assign(frameDraft, frameSaved);
    showFrameDraft();
  }
  frameForm.frame_color.addEventListener("input", () => {
    frameDraft.frame_color = frameForm.frame_color.value;
    showFrameDraft();
  });
  frameForm.frame_color_theme.addEventListener("change", () => {
    frameDraft.frame_color = frameForm.frame_color_theme.checked ? "" : frameForm.frame_color.value;
    showFrameDraft();
  });
  frameForm.frame_glow.addEventListener("input", () => {
    frameDraft.frame_glow = frameForm.frame_glow.value;
    showFrameDraft();
  });
  frameForm.frame_glow_theme.addEventListener("change", () => {
    frameDraft.frame_glow = frameForm.frame_glow_theme.checked ? "" : frameForm.frame_glow.value;
    showFrameDraft();
  });
  ["frame_width", "frame_radius", "board_scale", "board_margin"].forEach((k) =>
    frameForm[k].addEventListener("input", () => {
      frameDraft[k] = Number(frameForm[k].value);
      showFrameDraft();
    }),
  );
  $$('input[name="frame_finish"], input[name="frame_fit"]', frameForm).forEach((r) =>
    r.addEventListener("change", () => {
      frameDraft[r.name] = r.value;
      showFrameDraft();
    }),
  );
  function presetFrame(values, said) {
    Object.assign(frameDraft, values);
    showFrameDraft();
    frameStatus.textContent = said;
  }
  $("#frame-black-chrome").addEventListener("click", () => presetFrame(FRAME_BLACK_CHROME, "Black chrome on the card — Save to put it on the TV."));
  $("#frame-theme").addEventListener("click", () => presetFrame(FRAME_THEME, "The theme's own frame on the card — Save to put it on the TV."));
  frameForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const saved = await api("/api/settings", { method: "PATCH", body: { ...frameDraft } });
      fillFrameForm(saved);
      frameStatus.textContent = "Saved — the TV picks it up on its next poll.";
      refreshLive();
      sheetDone(frameForm);
    } catch (e) {
      toast(e.message, true);
    }
  });

  // ---- preview (the server lays the text out, so it can never differ from the board)
  let previewTimer = 0;
  async function preview() {
    const text = form.text.value;
    try {
      const p = await api("/api/messages/preview", { method: "POST", body: { text } });
      lastPreview = {
        type: "board:show",
        rows: p.rows,
        settings: { rows: p.grid_rows, cols: p.grid_cols, animation: 0, theme: currentTheme },
      };
      post(previewFrame, lastPreview);
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
    markTheme(s.theme);
    display.idle_text.value = s.idle_text;
    display.poll_seconds.value = s.poll_seconds;
    display.rotate_seconds.value = s.rotate_seconds;
    display.timer_ring.value = s.timer_ring || "off";
    form.show_seconds.placeholder = String(s.rotate_seconds); // the default a message falls back to
    fillBgForm(s);
    fillFlapForm(s);
    fillFrameForm(s);
    fillGuestForm(s);
    syncCustom();
    loadProfiles().catch(() => {});
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
      idle_text: display.idle_text.value,
      poll_seconds: Number(display.poll_seconds.value),
      rotate_seconds: Number(display.rotate_seconds.value),
      timer_ring: display.timer_ring.value,
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
      refreshLive();
      sheetDone(display);
    } catch (e) {
      toast(e.message, true);
    }
  });

  // ---- images
  const imageList = $("#image-list");
  async function loadImages() {
    const items = await api("/api/images");
    renderBgUploads(items);
    imageList.textContent = "";
    if (!items.length) {
      imageList.innerHTML = '<li class="plain"><p class="empty" id="images-empty"><span>No pictures yet.</span> <button type="button" class="small" data-reach="image-form" data-sel="input[name=file]">Upload a picture</button> <button type="button" class="small" data-reach="qr-form" data-sel="input[name=data]">Make a QR code</button></p></li>';
      return;
    }
    for (const img of items) {
      const li = document.createElement("li");
      li.innerHTML = `<img alt=""><div class="meta"><code class="token"></code>
        <button type="button" class="link copy">Copy token</button> <button type="button" class="link delete">Delete</button>
        <span class="muted size"></span><span class="muted qr-text" hidden></span> <button type="button" class="link edit" hidden>Edit text</button></div>
        <button type="button" class="link phone-only size-open">Size ›</button>
        <form class="sizing sheet-block" aria-label="Size on the board">
          <label>Wide <input type="number" name="w" min="1" max="36" required></label>
          <span class="muted">×</span>
          <label>Tall <input type="number" name="h" min="1" max="10" required></label>
          <label>Fit <select name="fit"><option value="contain">keep its shape</option><option value="cover">fill, crop</option><option value="stretch">stretch</option></select></label>
          <label class="check"><input type="checkbox" name="solid"> Draw whole</label>
          <span class="chips" role="group" aria-label="Sizes that keep its shape"></span>
          <button type="submit" class="small">Save size</button>
          <span class="muted applied" role="status"></span>
        </form>`;
      $("img", li).src = `${img.url}?v=${Date.now()}`;
      $(".token", li).textContent = img.token;
      const kb = img.bytes / 1024;
      $(".size", li).textContent = `${kb >= 1000 ? `${(kb / 1024).toFixed(1)} MB` : kb < 1 ? "under 1 KB" : `${Math.round(kb)} KB`}${img.width ? ` · ${img.width} × ${img.height} px` : ""}`;
      const sizing = $(".sizing", li);
      sizing.setAttribute("aria-label", `Size of ${img.token} on the board`);
      sizing.id = `sizing-${img.slug}`;
      $(".size-open", li).dataset.sheet = sizing.id;
      $(".size-open", li).dataset.title = `${img.token} on the board`;
      sizing.w.value = img.w;
      sizing.h.value = img.h;
      sizing.fit.value = img.fit;
      sizing.w.setAttribute("aria-label", `${img.token}: cells wide`);
      sizing.h.setAttribute("aria-label", `${img.token}: cells tall`);
      sizing.fit.setAttribute("aria-label", `${img.token}: fit`);
      sizing.solid.checked = !!img.solid;
      sizing.solid.setAttribute("aria-label", `${img.token}: draw whole over its block`);
      sizing.solid.addEventListener("change", () => sizing.requestSubmit());
      if (img.qr) {
        $(".qr-text", li).textContent = `“${img.qr.data}”`;
        $(".qr-text", li).title = img.qr.data;
        $(".qr-text", li).hidden = false;
        const edit = $(".edit", li);
        edit.hidden = false;
        edit.setAttribute("aria-label", `Edit the text of ${img.token}`);
        edit.addEventListener("click", () => {
          qrForm.data.value = img.qr.data;
          qrForm.slug.value = img.slug;
          qrStatus.textContent = `Editing ${img.token} — Make QR remakes it; the board follows on its next poll.`;
          qrForm.scrollIntoView({ block: "center", behavior: "smooth" });
          qrForm.data.focus();
        });
      }
      const chips = $(".chips", li);
      if (img.suggested.length) {
        chips.append(img.qr ? "Scans from the sofa at 4 × 3 on Compact, 5 × 4 on Large: " : "Keeps its shape at ");
        img.suggested.forEach(([w, h], i) => {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "chip";
          b.textContent = `${w} × ${h}`;
          b.setAttribute("aria-label", `${w} wide by ${h} tall`);
          b.setAttribute("aria-pressed", String(w === img.w && h === img.h));
          b.addEventListener("click", () => {
            sizing.w.value = w;
            sizing.h.value = h;
            sizing.fit.value = "contain";
            sizing.requestSubmit();
          });
          if (i) chips.append(" · ");
          chips.append(b);
        });
        if (img.w === 1 && img.h === 1 && img.width && img.width / img.height > 1.6) $(".applied", sizing).textContent = "This picture is wide — try the first size.";
        if (img.qr && !img.solid) $(".applied", sizing).textContent = "Draw whole is off — a code sliced through the flaps will not scan.";
      } else if (img.width === null) {
        chips.textContent = "Pixel size unreadable — set the cells by hand.";
      }
      sizing.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const body = { w: Number(sizing.w.value), h: Number(sizing.h.value), fit: sizing.fit.value, solid: sizing.solid.checked };
        try {
          const saved = await api(`/api/images/${img.slug}`, { method: "PATCH", body });
          Object.assign(img, saved);
          $$(".chip", chips).forEach((b) => b.setAttribute("aria-pressed", String(b.textContent === `${saved.w} × ${saved.h}`)));
          $(".applied", sizing).textContent = `${saved.w} × ${saved.h}, ${sizing.fit.selectedOptions[0].textContent}${saved.solid ? ", drawn whole" : ""} — the board picks it up on its next poll.`;
          toast(`${img.token} is ${saved.w} × ${saved.h} cells.`);
          sheetDone(sizing);
          if (!form.hidden) preview();
          await loadMessages(); // a bigger picture can overflow a message
          refreshLive();
        } catch (e) {
          toast(e.message, true);
        }
      });
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
      sheetDone(f);
      await loadImages();
      if (!form.hidden) preview();
    } catch (e) {
      toast(e.message, true);
    }
  });

  // the camera on a phone: a photo uploads the moment it is taken
  $("#image-form").camera.addEventListener("change", async () => {
    const f = $("#image-form");
    const file = f.camera.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const img = await api("/api/images", { method: "POST", form: fd });
      toast(`Uploaded. Put ${img.token} in a message.`);
      f.reset();
      sheetDone(f);
      await loadImages();
      if (!form.hidden) preview();
    } catch (e) {
      toast(e.message, true);
    }
  });

  // ---- a QR code from text or a link: the server makes the picture; the same slug remakes it
  const qrForm = $("#qr-form");
  const qrStatus = $("#qr-status");
  qrForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const body = { slug: qrForm.slug.value.trim().toLowerCase(), data: qrForm.data.value.trim() };
    try {
      const img = await api("/api/images/qr", { method: "POST", body });
      qrStatus.textContent = `${img.token} is a ${img.w} × ${img.h} code — put it in a message.`;
      toast(`${img.token} made. Put it in a message; it scans from the sofa at ${img.w} × ${img.h}.`);
      qrForm.reset();
      sheetDone(qrForm);
      await loadImages();
      if (!form.hidden) preview();
      refreshLive(); // a remade code is a new picture to the TV
    } catch (e) {
      toast(e.message, true);
    }
  });
  $("#qr-board").addEventListener("click", () => {
    const first = $("#addresses .addresses code");
    if (!first) return;
    qrForm.data.value = first.textContent.trim();
    qrForm.slug.value = "board";
    qrStatus.textContent = "Scan to open this board — Make QR.";
    qrForm.data.focus();
  });

  // ---- guests: the link, how posts show, and the queue — one GET every 10 s while the page is
  // visible; the lists re-render only when something changed, so focus stays put.
  const guestOff = $("#guest-off");
  const guestOn = $("#guest-on");
  const guestUrl = $("#guest-url");
  const guestForm = $("#guest-form");
  const guestStatus = $("#guest-status");
  const pendingList = $("#guest-pending");
  const approvedList = $("#guest-approved");
  const boardUrl = () => {
    const first = $("#addresses .addresses code");
    return first ? first.textContent.trim() : location.origin;
  };
  function showGuestLink(token) {
    guestOff.hidden = !!token;
    guestOn.hidden = !token;
    $("#guest-qr-row").hidden = !token;
    guestUrl.textContent = token ? `${boardUrl()}/guest/${token}` : "";
  }
  $("#guest-qr").addEventListener("click", async () => {
    try {
      const out = await api("/api/guest/qr", { method: "POST" });
      const where = out.enabled ? `is on the board (${out.state})` : "is in the Messages list, disabled — switch it on when the party starts";
      $("#guest-qr-note").textContent = `${out.token} carries the link; SCAN TO POST A PHOTO ${where}. Rotate remakes the code; Turn off takes the message off.`;
      toast(`${out.token} made — the message is in the list${out.enabled ? "" : ", disabled"}.`);
      await loadImages();
      await loadMessages();
      refreshLive();
      $(`tr[data-id="${out.message_id}"] .switch input`, rowsEl)?.focus();
    } catch (e) {
      toast(e.message, true);
    }
  });
  async function rotateGuest(said) {
    try {
      const link = await api("/api/guest/rotate", { method: "POST" });
      showGuestLink(link.token);
      guestUrl.textContent = link.url;
      toast(said);
      $("#guest-copy").focus();
    } catch (e) {
      toast(e.message, true);
    }
  }
  $("#guest-make").addEventListener("click", () => rotateGuest("Guests are on — put the link in a QR code (Images panel) or send it."));
  $("#guest-rotate").addEventListener("click", () => rotateGuest("New link — the old one stopped working."));
  $("#guest-close").addEventListener("click", async () => {
    if (!confirm("Turn guests off? The link stops working; the posts stay.")) return;
    try {
      const s = await api("/api/settings", { method: "PATCH", body: { guest_token: "" } });
      showGuestLink(s.guest_token);
      toast("Guests are off — the SCAN TO POST A PHOTO message, if any, is switched off.");
      await loadMessages(); // the server disabled the QR message
      refreshLive();
      $("#guest-make").focus();
    } catch (e) {
      toast(e.message, true);
    }
  });
  $("#guest-copy").addEventListener("click", async () => {
    const url = guestUrl.textContent;
    try {
      await navigator.clipboard.writeText(url);
      toast(`${url} copied.`);
    } catch {
      toast(url);
    }
  });
  function fillGuestForm(s) {
    showGuestLink(s.guest_token);
    guestForm.guest_auto_approve.checked = !!s.guest_auto_approve;
    guestForm.guest_priority.value = s.guest_priority;
    guestForm.guest_show_seconds.value = s.guest_show_seconds;
  }
  async function saveGuest(body, said) {
    try {
      fillGuestForm(await api("/api/settings", { method: "PATCH", body }));
      guestStatus.textContent = said;
    } catch (e) {
      toast(e.message, true);
    }
  }
  guestForm.guest_auto_approve.addEventListener("change", () => {
    const on = guestForm.guest_auto_approve.checked;
    saveGuest({ guest_auto_approve: on }, on ? "Auto-approve on — a post goes on the board at once; you can still remove it." : "Auto-approve off — posts wait here for you.");
  });
  for (const k of ["guest_priority", "guest_show_seconds"]) {
    guestForm[k].addEventListener("change", () => saveGuest({ [k]: Number(guestForm[k].value) }, "Saved — for posts approved from now on; edit a message to change one already on the board."));
  }
  guestForm.addEventListener("submit", (ev) => ev.preventDefault());

  const fmtAgo = (iso) => {
    const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
    return new Date(iso).toLocaleString([], { dateStyle: "short", timeStyle: "short" });
  };
  let posts = [];
  let postsSeen = ""; // the last list rendered, serialized
  let pendingBefore = -1; // pending count at the last render; a rise = new posts → a toast
  function fillPosts(list, items, empty, approved) {
    list.textContent = "";
    if (!items.length) {
      list.innerHTML = `<li class="muted">${empty}</li>`;
      return;
    }
    for (const p of items) {
      const li = document.createElement("li");
      li.dataset.id = p.id;
      li.innerHTML = `<img alt="" hidden><span class="thumb" aria-hidden="true">“ ”</span>
        <div class="meta"><span class="line"></span> <span class="muted who"></span> <span class="badge" hidden></span></div>
        <div class="actions"></div>`;
      if (p.image) {
        const img = $("img", li);
        img.src = `/images/${p.image}`;
        img.alt = `Photo${p.nick ? ` from ${p.nick}` : ""}`;
        img.hidden = false;
        $(".thumb", li).remove();
      }
      $(".line", li).textContent = p.text || (p.image ? "(a photo)" : "");
      $(".who", li).textContent = `${p.nick ? `— ${p.nick} · ` : ""}${fmtAgo(p.created_at)}`;
      const who = p.nick || `post ${p.id}`;
      const actions = $(".actions", li);
      if (approved) {
        const badge = $(".badge", li);
        const state = p.message_id ? p.message_state : "removed";
        badge.hidden = false;
        badge.className = `badge ${state}`;
        badge.textContent = state === "disabled" ? "did not fit" : state;
        if (state === "disabled") badge.title = "The message is in the list, disabled — make the board bigger or edit it.";
        actions.innerHTML = '<button type="button" class="link remove">Remove</button>';
        const b = $(".remove", actions);
        b.setAttribute("aria-label", `Remove ${who} from the board`);
        b.addEventListener("click", async () => {
          if (!confirm(`Take ${who}'s post off the board? Its photo is deleted too.`)) return;
          await postAction(p, "reject", "Removed from the board.");
          $("#guest-approved-heading").focus();
        });
      } else {
        actions.innerHTML = '<button type="button" class="small approve">Approve</button> <button type="button" class="link reject">Reject</button>';
        $(".approve", actions).setAttribute("aria-label", `Approve ${who}`);
        $(".reject", actions).setAttribute("aria-label", `Reject ${who}`);
        $(".approve", actions).addEventListener("click", async () => {
          const out = await postAction(p, "approve", "On the board — the TV picks it up on its next poll.");
          if (out && out.note) toast(`Approved, but it does not fit: ${out.note} The message is in the list, disabled.`, true);
          focusNextPending();
        });
        $(".reject", actions).addEventListener("click", async () => {
          await postAction(p, "reject", "Rejected — nothing on the board.");
          focusNextPending();
        });
      }
      list.appendChild(li);
    }
  }
  function focusNextPending() {
    ($(".approve", pendingList) || $("#guest-pending-heading")).focus();
  }
  async function postAction(p, action, said) {
    try {
      const out = await api(`/api/posts/${p.id}/${action}`, { method: "POST" });
      toast(said);
      await loadPosts();
      await loadMessages();
      if (action === "reject") await loadImages(); // the photo is gone from the Images panel
      refreshLive();
      return out;
    } catch (e) {
      toast(e.message, true);
      return null;
    }
  }
  function renderPosts() {
    const pending = posts.filter((p) => p.status === "pending");
    const approved = posts.filter((p) => p.status === "approved");
    for (const el of [$("#guests-waiting"), $("#guests-count")]) {
      el.hidden = !pending.length;
      el.textContent = `${pending.length} waiting`;
    }
    document.title = `${pending.length ? `(${pending.length}) ` : ""}Settings · DepartureBoard`;
    if (pendingBefore >= 0 && pending.length > pendingBefore) {
      const n = pending.length - pendingBefore;
      toast(`${n} new guest post${n > 1 ? "s" : ""} waiting for you.`);
    }
    pendingBefore = pending.length;
    fillPosts(pendingList, pending, "Nothing waiting.", false);
    fillPosts(approvedList, approved, "Nothing from guests on the board.", true);
    $("#guest-clear").disabled = !posts.length;
  }
  async function loadPosts() {
    const items = await api("/api/posts?status=all");
    const seen = JSON.stringify(items);
    if (seen === postsSeen) return;
    postsSeen = seen;
    posts = items;
    renderPosts();
  }
  $("#guest-clear").addEventListener("click", async () => {
    if (!confirm("Clear every guest post? Their messages come off the board and their photos are deleted.")) return;
    try {
      const out = await api("/api/posts?status=all", { method: "DELETE" });
      toast(`Cleared ${out.removed} post${out.removed === 1 ? "" : "s"} — messages and photos gone.`);
      await loadPosts();
      await loadMessages();
      await loadImages();
      refreshLive();
      $("#guests-heading").focus();
    } catch (e) {
      toast(e.message, true);
    }
  });
  setInterval(() => {
    if (document.visibilityState !== "visible") return;
    loadPosts().catch(() => {});
    loadProfiles().catch(() => {}); // the strip's dot and the Boards tab follow changes made elsewhere
  }, 10000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") loadPosts().catch(() => {});
  });

  // ---- the calendar: saved boards on dates. The grid is drawn from the plan with the same rule
  // the server applies (the later start wins); every change is applied at once so today's board
  // follows, and the strip and the live card refresh when it did.
  const calMonths = $("#calendar-months");
  const calLegend = $("#calendar-legend");
  const calForm = $("#calendar-form");
  const calList = $("#calendar-list");
  const calStatus = $("#calendar-status");
  const calEveryday = $("#calendar-everyday");
  const calToday = $("#calendar-today");
  let plan = { everyday: "", entries: [], today: { date: "", profile: null, entry_id: null, until: null }, applied: "" };
  const HUES = [38, 200, 330, 120, 270, 20, 180, 60];
  const hueOf = (slug) => HUES[boards.findIndex((b) => b.slug === slug) % HUES.length] ?? 0;
  const tint = (slug) => `hsl(${hueOf(slug)} 60% 45% / .55)`;
  const nameOf = (slug) => (boards.find((b) => b.slug === slug) || {}).name || slug;
  const dateOf = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
  const isoOf = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const fmtDay = (iso) => dateOf(iso).toLocaleDateString([], { month: "short", day: "numeric" });
  const fmtRange = (e) => (e.end === e.start ? fmtDay(e.start) : `${fmtDay(e.start)} – ${e.end ? fmtDay(e.end) : "…"}`);
  // the server's rule: the latest start wins, ties by id; an entry whose board is gone is skipped
  function entryFor(iso) {
    let best = null;
    for (const e of plan.entries) {
      if (e.missing || e.start > iso || (e.end && e.end < iso)) continue;
      if (!best || e.start > best.start || (e.start === best.start && e.id > best.id)) best = e;
    }
    return best;
  }
  function renderMonths() {
    calMonths.textContent = "";
    if (!plan.today.date) return;
    const first = dateOf(plan.today.date);
    for (let k = 0; k < 2; k++) {
      const y = first.getFullYear();
      const m = first.getMonth() + k;
      const start = new Date(y, m, 1);
      const table = document.createElement("table");
      table.className = "cal";
      const caption = document.createElement("caption");
      caption.textContent = start.toLocaleDateString([], { month: "long", year: "numeric" });
      table.appendChild(caption);
      table.innerHTML += '<thead><tr><th scope="col">Mon</th><th scope="col">Tue</th><th scope="col">Wed</th><th scope="col">Thu</th><th scope="col">Fri</th><th scope="col">Sat</th><th scope="col">Sun</th></tr></thead>';
      const body = document.createElement("tbody");
      let row = document.createElement("tr");
      const lead = (start.getDay() + 6) % 7;
      for (let i = 0; i < lead; i++) row.appendChild(document.createElement("td"));
      const days = new Date(y, m + 1, 0).getDate();
      for (let d = 1; d <= days; d++) {
        const iso = isoOf(new Date(y, m, d));
        const td = document.createElement("td");
        const b = document.createElement("button");
        b.type = "button";
        b.className = "day";
        b.dataset.date = iso;
        const e = entryFor(iso);
        const who = e ? nameOf(e.profile) : plan.everyday ? nameOf(plan.everyday) : "";
        b.innerHTML = `<span class="n"></span><span class="who"></span>`;
        $(".n", b).textContent = d;
        $(".who", b).textContent = e ? who : "";
        if (e) b.style.setProperty("--tint", tint(e.profile));
        if (iso === plan.today.date) b.classList.add("today");
        if (iso < plan.today.date) b.classList.add("past");
        b.setAttribute("aria-label", `${dateOf(iso).toLocaleDateString([], { weekday: "short", day: "numeric", month: "long" })}${iso === plan.today.date ? ", today" : ""}: ${e ? who : who ? `${who} (everyday)` : "nothing planned"}`);
        b.addEventListener("click", () => {
          calForm.id.value = "";
          calForm.start.value = iso;
          calForm.end.value = iso;
          $("#calendar-form-title").textContent = "Plan a board";
          $("#calendar-save").textContent = "Add to the plan";
          $("#calendar-cancel").hidden = true;
          calStatus.textContent = `${fmtDay(iso)} — pick a board, stretch Until if you like.`;
          if (phone.matches) openSheet(calForm, "Plan a board");
          calForm.profile.focus();
        });
        td.appendChild(b);
        row.appendChild(td);
        if (row.children.length === 7) {
          body.appendChild(row);
          row = document.createElement("tr");
        }
      }
      if (row.children.length) {
        while (row.children.length < 7) row.appendChild(document.createElement("td"));
        body.appendChild(row);
      }
      table.appendChild(body);
      calMonths.appendChild(table);
    }
    const used = [...new Set(plan.entries.filter((e) => !e.missing).map((e) => e.profile))];
    calLegend.textContent = "";
    for (const slug of used) {
      const s = document.createElement("span");
      s.className = "swatch-dot";
      s.style.setProperty("--tint", tint(slug));
      s.textContent = nameOf(slug);
      calLegend.appendChild(s);
    }
    if (plan.everyday) calLegend.append(`${used.length ? " · " : ""}plain: ${nameOf(plan.everyday)} (everyday)`);
    else if (!used.length) calLegend.textContent = "Nothing planned yet.";
  }
  function renderPlan() {
    calList.textContent = "";
    if (!plan.entries.length) {
      calList.innerHTML = '<li class="muted">No plan yet — pick a board and a day above.</li>';
    }
    for (const e of plan.entries) {
      const li = document.createElement("li");
      li.dataset.id = e.id;
      li.innerHTML = '<span class="swatch-dot"></span><span class="when"></span> · <strong class="board"></strong><span class="note muted"></span><span class="actions"><button type="button" class="link edit">Edit</button> <button type="button" class="link delete">Delete</button></span>';
      $(".swatch-dot", li).style.setProperty("--tint", e.missing ? "transparent" : tint(e.profile));
      $(".when", li).textContent = fmtRange(e);
      $(".board", li).textContent = e.missing ? `${e.profile} (board deleted — skipped)` : e.name || e.profile;
      $(".note", li).textContent = e.note ? ` · “${e.note}”` : "";
      $(".edit", li).setAttribute("aria-label", `Edit the plan for ${fmtRange(e)}`);
      $(".delete", li).setAttribute("aria-label", `Delete the plan for ${fmtRange(e)}`);
      $(".edit", li).addEventListener("click", () => {
        calForm.id.value = e.id;
        calForm.profile.value = e.missing ? "" : e.profile;
        calForm.start.value = e.start;
        calForm.end.value = e.end || "";
        calForm.note.value = e.note;
        $("#calendar-form-title").textContent = "Change the plan";
        $("#calendar-save").textContent = "Save the plan";
        $("#calendar-cancel").hidden = false;
        if (phone.matches) openSheet(calForm, "Change the plan");
        else calForm.scrollIntoView({ block: "nearest" });
        calForm.profile.focus();
      });
      $(".delete", li).addEventListener("click", async () => {
        if (!confirm(`Delete the plan for ${fmtRange(e)} (${e.name || e.profile})?`)) return;
        try {
          await api(`/api/calendar/${e.id}`, { method: "DELETE" });
          await applyAndRefresh("Deleted.");
          $("#calendar-heading").focus();
        } catch (err) {
          toast(err.message, true);
        }
      });
      calList.appendChild(li);
    }
    const t = plan.today;
    const untilText = (iso) => (!iso ? "until further notice" : iso === t.date ? "today only" : `until ${fmtDay(iso)}`);
    calToday.textContent = t.profile
      ? t.entry_id
        ? `Today: ${nameOf(t.profile)} — ${untilText(t.until)}`
        : `Today: ${nameOf(t.profile)} (the everyday board)`
      : "Today: nothing planned — the board stays as it is.";
  }
  function fillCalendarSelects() {
    for (const sel of [calForm.profile, calEveryday]) {
      const keep = sel === calEveryday ? plan.everyday : sel.value;
      sel.textContent = "";
      if (sel === calEveryday) sel.append(new Option("Stay on the last board", ""));
      for (const b of boards) sel.append(new Option(b.name, b.slug));
      sel.value = keep;
      if (sel.value !== keep) sel.value = sel === calEveryday ? "" : boards[0] ? boards[0].slug : "";
    }
    calForm.profile.disabled = calEveryday.disabled = !boards.length;
    $("#calendar-save").disabled = !boards.length;
    if (!boards.length) calStatus.textContent = "Save a board first (Save as… in the strip at the top).";
  }
  async function loadCalendar() {
    plan = await api("/api/calendar");
    fillCalendarSelects();
    renderMonths();
    renderPlan();
  }
  async function applyAndRefresh(said) {
    const out = await api("/api/calendar/apply", { method: "POST" });
    await loadCalendar();
    if (out.changed) {
      await loadProfiles(); // the names, incl. a board the switch just saved
      calStatus.textContent = `${said} ${nameOf(out.loaded)} is on the board now${out.saved_back ? ` (the previous board was saved as ${nameOf(out.saved_back)})` : ""}.`;
      await refreshAll();
    } else {
      calStatus.textContent = said;
    }
  }
  calForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const body = { profile: calForm.profile.value, start: calForm.start.value, end: calForm.end.value || null, note: calForm.note.value.trim() };
    const id = calForm.id.value;
    try {
      const e = id ? await api(`/api/calendar/${id}`, { method: "PATCH", body }) : await api("/api/calendar", { method: "POST", body });
      calForm.reset();
      calForm.id.value = "";
      $("#calendar-form-title").textContent = "Plan a board";
      $("#calendar-save").textContent = "Add to the plan";
      $("#calendar-cancel").hidden = true;
      sheetDone(calForm);
      await applyAndRefresh(`${e.name} ${id ? "planned" : "added"} for ${fmtRange(e)}.`);
      toast(`${e.name}: ${fmtRange(e)}.`);
    } catch (err) {
      toast(err.message, true);
    }
  });
  $("#calendar-cancel").addEventListener("click", () => {
    calForm.reset();
    calForm.id.value = "";
    $("#calendar-form-title").textContent = "Plan a board";
    $("#calendar-save").textContent = "Add to the plan";
    $("#calendar-cancel").hidden = true;
    calStatus.textContent = "";
    sheetDone(calForm);
  });
  calEveryday.addEventListener("change", async () => {
    try {
      await api("/api/settings", { method: "PATCH", body: { calendar_everyday: calEveryday.value } });
      await applyAndRefresh(calEveryday.value ? `${nameOf(calEveryday.value)} is the everyday board.` : "No everyday board — the last planned board stays.");
    } catch (err) {
      toast(err.message, true);
    }
  });
  // the strip's listing feeds the names and colours; redraw when it changes
  const renderBoardsBase = renderBoards;
  renderBoards = function () {
    renderBoardsBase();
    if (plan.today.date) {
      fillCalendarSelects();
      renderMonths();
      renderPlan();
    }
  };

  // ---- first run: a walkthrough the first time the page opens — four steps over the calls the
  // page makes anyway (the preset and theme PATCH, /now, the addresses, the token), a screen of
  // its own that brings you back. Done, Skip the tour and Escape set setup_done and close it;
  // Setup → Run the walkthrough again clears the key and reloads.
  const welcome = $("#welcome");
  if (welcome) {
    const steps = $$(".step", welcome);
    const dots = $$("#welcome-dots li");
    const welcomeFrame = $("#welcome-board");
    const welcomeThemes = $$("#welcome-themes .swatch");
    let step = 0;
    let finished = false;
    function showStep(i) {
      step = Math.max(0, Math.min(steps.length - 1, i));
      steps.forEach((s, j) => (s.hidden = j !== step));
      dots.forEach((d, j) => d.classList.toggle("on", j === step));
      $("#welcome-where").textContent = `${step + 1} of ${steps.length}`;
      welcome.setAttribute("aria-labelledby", `welcome-${step + 1}-title`);
      $("#welcome-screen").hidden = step > 1;
      $("#welcome-prev").hidden = step === 0;
      $("#welcome-skip").hidden = step === steps.length - 1;
      $("#welcome-next").textContent = step === steps.length - 1 ? "Done" : "Next";
      welcome.scrollTop = 0;
      const first = steps[step].querySelector('input:checked, [role="radio"][aria-checked="true"], input:not([type="radio"]), button');
      (first || $("#welcome-next")).focus();
    }
    async function finish() {
      if (finished) return;
      finished = true;
      try {
        await api("/api/settings", { method: "PATCH", body: { setup_done: "1" } });
      } catch (e) {
        toast(e.message, true);
      }
      if (welcome.open) welcome.close();
      document.body.classList.remove("sheet-open");
      welcome.remove(); // its frame stops polling
      toast("Set up. Setup → Run the walkthrough again brings this back.");
      $("#tab-board").focus();
    }
    $("#welcome-next").addEventListener("click", () => (step === steps.length - 1 ? finish() : showStep(step + 1)));
    $("#welcome-skip").addEventListener("click", () => showStep(step + 1));
    $("#welcome-prev").addEventListener("click", () => showStep(step - 1));
    $("#welcome-skip-all").addEventListener("click", finish);
    welcome.addEventListener("cancel", (ev) => {
      ev.preventDefault(); // Escape = skip
      finish();
    });
    welcome.addEventListener("close", finish); // the browser's own back gesture
    // 1 · your TV: the preset and the theme; the board in the step follows at once
    const nudge = () => {
      post(welcomeFrame, { type: "board:refresh" });
      refreshLive();
    };
    const markWelcomeTheme = (theme) =>
      welcomeThemes.forEach((b) => {
        const on = b.dataset.theme === theme;
        b.setAttribute("aria-checked", String(on));
        b.tabIndex = on ? 0 : -1;
      });
    welcomeThemes.forEach((b, i) => {
      b.addEventListener("click", async () => {
        await chooseTheme(b.dataset.theme, false);
        markWelcomeTheme(currentTheme);
        $("#welcome-1-status").textContent = `${currentTheme.replace(/-/g, " ")} — the TV has it at its next poll.`;
        nudge();
      });
      b.addEventListener("keydown", (ev) => {
        const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
        if (!d) return;
        ev.preventDefault();
        const next = welcomeThemes[(i + d + welcomeThemes.length) % welcomeThemes.length];
        next.click();
        next.focus();
      });
    });
    $$('input[name="welcome_preset"]', welcome).forEach((r) =>
      r.addEventListener("change", async () => {
        try {
          const s = await api("/api/settings", { method: "PATCH", body: { grid_preset: r.value } });
          await loadDisplay();
          $("#welcome-1-status").textContent = `${r.value}: ${s.rows} rows of ${s.cols} flaps.`;
          nudge();
        } catch (e) {
          toast(e.message, true);
        }
      }),
    );
    // 2 · the first message: on the board for two minutes, the way Show something now does it
    $("#welcome-now").addEventListener("click", async () => {
      const text = $("#welcome-text").value.trim();
      if (!text) return;
      try {
        await api("/api/messages/now", { method: "POST", body: { text, show_seconds: 120 } });
        $("#welcome-2-status").textContent = `${text} — on the TV for 2 minutes. Watch it flip.`;
        await loadMessages();
        nudge();
      } catch (e) {
        toast(e.message, true);
      }
    });
    api("/api/settings")
      .then((s) => {
        const r = welcome.querySelector(`input[name="welcome_preset"][value="${s.grid_preset}"]`);
        if (r) r.checked = true;
        markWelcomeTheme(s.theme);
        if (!finished) showStep(step);
      })
      .catch(() => {});
    welcome.showModal();
    document.body.classList.add("sheet-open");
    showStep(0);
  }
  $("#welcome-again").addEventListener("click", async () => {
    try {
      await api("/api/settings/setup_done", { method: "DELETE" });
      history.replaceState(null, "", "#board");
      location.reload();
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
  loadVideos().catch((e) => toast(e.message, true));
  loadPosts().catch((e) => toast(e.message, true));
  loadProfiles().then(() => loadCalendar()).catch((e) => toast(e.message, true));
})();
