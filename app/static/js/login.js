// The sign-in page: Copy buttons for the "where the token is" commands. Plain script, no modules.
(() => {
  "use strict";
  for (const b of document.querySelectorAll("#where-token .copy")) {
    b.addEventListener("click", async () => {
      const was = b.textContent;
      try {
        await navigator.clipboard.writeText(b.dataset.copy);
        b.textContent = "Copied";
      } catch {
        b.textContent = "Select and copy the line";
      }
      setTimeout(() => (b.textContent = was), 1500);
    });
  }
})();
