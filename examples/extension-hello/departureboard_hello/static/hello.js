// The Hello tab: read the greeting, save it. Same rules as the core's page — the session cookie
// authenticates, and every write carries the page header so a cross-site form cannot do it.
(() => {
  "use strict";
  const form = document.getElementById("hello-form");
  if (!form) return;
  const input = form.querySelector("input[name=greeting]");
  const status = document.getElementById("hello-status");
  const headers = { "X-Requested-With": "DepartureBoard", "Content-Type": "application/json" };
  fetch("/api/hello", { headers }).then((r) => r.json()).then((d) => { input.value = d.greeting || ""; });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = form.querySelector("button[type=submit]");
    btn.setAttribute("aria-busy", "true");
    try {
      const r = await fetch("/api/hello", { method: "PUT", headers, body: JSON.stringify({ greeting: input.value }) });
      status.textContent = r.ok ? "Saved." : `Not saved (${r.status}).`;
    } finally {
      btn.removeAttribute("aria-busy");
    }
  });
})();
