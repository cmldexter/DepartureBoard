// Fullscreen and keep-awake. The button is the one user gesture the page needs: it goes
// fullscreen, keeps the screen awake, and unlocks the sound. Also the HUD's fade and the `s`
// shortcut to the settings page.
//
// Keep-awake: navigator.wakeLock (secure contexts only — localhost or HTTPS) when it works,
// otherwise a muted, looped, inline, 1-second video kept playing (what NoSleep.js does); a TV
// on http://192.168.x.x gets the video. Both are re-acquired when the tab becomes visible
// again, and released when fullscreen ends.
//
// Exposes window.Wake = { enter, exit, state }. Plain script, no modules.
(() => {
  "use strict";
  const button = document.getElementById("fullscreen");
  const status = document.getElementById("status");
  const video = document.getElementById("keep-awake");
  const root = document.documentElement;
  if (!button || !status || !video) return;

  const state = { active: false, path: "none", fullscreen: false };
  let lock = null;
  let statusTimer = 0;

  function say(text) {
    status.textContent = text;
    status.hidden = false;
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => (status.hidden = true), 3000);
  }

  function isFullscreen() {
    return !!(document.fullscreenElement || document.webkitFullscreenElement);
  }

  async function requestFullscreen() {
    const el = root;
    const fn = el.requestFullscreen || el.webkitRequestFullscreen;
    if (!fn) return false;
    try {
      await fn.call(el, { navigationUI: "hide" });
      return true;
    } catch {
      return false;
    }
  }

  async function acquire() {
    if (navigator.wakeLock && window.isSecureContext) {
      try {
        lock = await navigator.wakeLock.request("screen");
        lock.addEventListener("release", () => {
          lock = null;
        });
        state.path = "lock";
        return "lock";
      } catch {
        /* not allowed here; fall through to the video */
      }
    }
    try {
      video.currentTime = 0;
      await video.play();
      state.path = "video";
      return "video";
    } catch {
      state.path = "none";
      return "none";
    }
  }

  function releaseAll() {
    if (lock) {
      lock.release().catch(() => {});
      lock = null;
    }
    if (!video.paused) video.pause();
    state.path = "none";
  }

  const LABEL = { lock: "Screen stays awake", video: "Screen stays awake (video)", none: "Could not keep the screen awake" };

  async function enter() {
    if (window.Sound) {
      const on = await window.Sound.unlock();
      if (on && window.Board) window.Board.soundReady();
    }
    const fs = await requestFullscreen();
    state.fullscreen = fs;
    if (!fs) document.body.classList.add("kiosk"); // no API: hide our chrome, let the browser's own fullscreen do the rest
    state.active = true;
    const path = await acquire();
    root.dataset.wake = path;
    say(fs ? LABEL[path] : `${LABEL[path]} · use the browser's fullscreen`);
  }

  function exit() {
    state.active = false;
    state.fullscreen = false;
    releaseAll();
    root.dataset.wake = "none";
    document.body.classList.remove("kiosk");
  }

  button.addEventListener("click", () => {
    if (state.active && isFullscreen()) {
      (document.exitFullscreen || document.webkitExitFullscreen).call(document).catch(() => {});
    } else {
      enter();
    }
  });

  const onFsChange = () => {
    if (state.active && !isFullscreen() && state.fullscreen) exit();
    document.body.classList.toggle("fullscreen", isFullscreen());
  };
  document.addEventListener("fullscreenchange", onFsChange);
  document.addEventListener("webkitfullscreenchange", onFsChange);

  document.addEventListener("visibilitychange", async () => {
    if (!state.active || document.visibilityState !== "visible") return;
    const path = await acquire();
    root.dataset.wake = path;
  });

  // Keep the button discoverable on a TV: show it on any pointer or key activity, then fade.
  let hideTimer = 0;
  const wake = () => {
    document.body.classList.add("hud-visible");
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => document.body.classList.remove("hud-visible"), 4000);
  };
  ["pointermove", "pointerdown", "keydown", "touchstart"].forEach((e) =>
    document.addEventListener(e, wake, { passive: true })
  );
  wake();

  // `s` opens the settings page in a new tab — for a keyboard or a TV remote without a pointer.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "s" || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
    window.open("/settings", "_blank", "noopener");
  });

  window.Wake = { enter, exit, state };
})();
