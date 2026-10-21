// Cast to the TV. Where the browser has the Presentation API (a secure context) and the board
// is served over https, the Cast button opens the browser's device picker and presents the
// board page: Chrome renders it offscreen on this computer and streams pictures to the TV, so
// this computer stays on. Anywhere else the button opens a panel with the two ways (turn on
// HTTPS, or the browser's own Cast menu). The settings page has the panel; the board's HUD
// button only shows where casting works. A reload reconnects to a running presentation.
//
// Exposes window.Cast = { state, start, stop }. Plain script, no modules.
(() => {
  "use strict";
  const button = document.getElementById("cast");
  if (!button) return;
  const help = document.getElementById("cast-help"); // the settings page's <dialog>
  const label = button.querySelector(".label"); // the settings page's text; the HUD has an icon
  const note = document.getElementById("cast-note"); // settings page
  const status = document.getElementById("status"); // board HUD
  const boardUrl = `${location.origin}/`;
  const KEY = "cast-presentation-id";
  const state = { status: "idle", id: null, available: null, reason: "" };

  // The API only exists in a secure context, and Chrome refuses to present an insecure URL
  // from a secure page. The browser knows which contexts it trusts (https://, localhost and
  // *.localhost names are all secure), so ask it rather than guess from the URL.
  if (!navigator.presentation || typeof PresentationRequest === "undefined") {
    state.reason = window.isSecureContext
      ? "This browser has no Presentation API (Chrome and Edge have it; Safari and Firefox do not)."
      : "This page is on http://; one-click casting needs the board on https:// or on a *.localhost name on this computer.";
  }
  let request = null;
  if (!state.reason) {
    try {
      request = new PresentationRequest([boardUrl]);
    } catch (e) {
      state.reason = `${e.name}: ${e.message}`;
    }
  }
  const canPresent = !!request;
  let connection = null;
  let statusTimer = 0;

  function say(text) {
    if (note) {
      note.textContent = text;
      note.hidden = !text;
    }
    if (status && text) {
      status.textContent = text;
      status.hidden = false;
      clearTimeout(statusTimer);
      statusTimer = setTimeout(() => (status.hidden = true), 3000);
    }
  }

  function render() {
    button.dataset.state = state.status;
    button.setAttribute("aria-pressed", state.status === "connected" ? "true" : "false");
    const text = { idle: "Cast to TV", connecting: "Connecting…", connected: "Stop casting" }[state.status];
    if (label) label.textContent = text;
    const tip = !canPresent
      ? "How to cast"
      : state.status === "connected"
        ? "Stop casting"
        : state.available === false
          ? "Cast to the TV · no TV found on the network yet"
          : "Cast to the TV · this computer stays on";
    button.title = tip;
    if (!label) button.setAttribute("aria-label", tip);
  }

  function wire(c) {
    connection = c;
    state.id = c.id;
    sessionStorage.setItem(KEY, c.id);
    state.status = c.state === "connected" ? "connected" : "connecting";
    c.onconnect = () => {
      state.status = "connected";
      say("Casting to the TV — this computer stays on.");
      render();
    };
    c.onclose = () => {
      // Our connection closed; the presentation may still be on the TV. Keep the id to reconnect.
      state.status = "idle";
      connection = null;
      render();
    };
    c.onterminate = () => {
      state.status = "idle";
      state.id = null;
      connection = null;
      sessionStorage.removeItem(KEY);
      say("Casting stopped.");
      render();
    };
    render();
  }

  async function start() {
    if (!canPresent) {
      if (help) {
        const why = document.getElementById("cast-help-why");
        if (why) why.textContent = state.reason;
        help.showModal();
      }
      return;
    }
    state.status = "connecting";
    render();
    try {
      wire(await request.start());
    } catch (e) {
      state.status = "idle";
      render();
      if (e.name === "NotFoundError") say("No TV found on the network.");
      else if (e.name === "NotAllowedError" || e.name === "AbortError") say("");
      else say(`Could not cast: ${e.name} — ${e.message}`);
    }
  }

  function stop() {
    if (connection) connection.terminate();
  }

  button.addEventListener("click", () => (state.status === "connected" ? stop() : start()));

  if (canPresent) {
    button.hidden = false; // the board's HUD renders it hidden until we know casting works here
    request.onconnectionavailable = (e) => wire(e.connection);
    request
      .getAvailability()
      .then((a) => {
        state.available = a.value;
        a.onchange = () => {
          state.available = a.value;
          render();
        };
        render();
      })
      .catch(() => {});
    const id = sessionStorage.getItem(KEY);
    if (id) request.reconnect(id).then(wire).catch(() => sessionStorage.removeItem(KEY));
  } else if (!help) {
    button.hidden = true; // the board's HUD: no panel there, the settings page explains
  }
  render();

  window.Cast = { state, start, stop };
})();
