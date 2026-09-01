/* Boots the real static/index.html and static/app.js in a fresh JSDOM window.
 *
 * app.js ships to the browser unbundled and declares everything at script
 * scope, so there is nothing to import. It is evaluated as-is and the internals
 * under test are handed back from the same eval, where they are still in scope.
 * The vendored libraries are stubbed: this suite is about app.js, not about
 * marked or DOMPurify. */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { JSDOM } from "jsdom";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

/** Minimal API responses, enough for the bootstrap at the bottom of app.js. */
function stubFetch(window) {
  return async (path) => {
    const body =
      path === "/api/runs" ? [] :
      path === "/api/resources" ? { resources: [], hint: "" } :
      path === "/api/health" ? { ollama: true, mode: "cloud", model: "stub" } :
      {};
    return { ok: true, status: 200, json: async () => body };
  };
}

export function boot() {
  const html = readFileSync(join(root, "static", "index.html"), "utf8");
  const dom = new JSDOM(html, {
    url: "http://localhost:8000/",
    pretendToBeVisual: true, // gives us requestAnimationFrame
    // "outside-only" gives the window a real script context for window.eval
    // without executing any <script> tags the page itself carries.
    runScripts: "outside-only",
  });
  const { window } = dom;

  const calls = { parse: 0, sanitize: 0, highlight: 0 };
  window.marked = {
    setOptions() {},
    parse(markdown) {
      calls.parse += 1;
      // Emits a code block so the highlight.js pass is actually exercised;
      // with a plain <p> the highlight assertions would be vacuously true.
      return `<pre><code>${markdown}</code></pre>`;
    },
  };
  window.DOMPurify = {
    sanitize(input) {
      calls.sanitize += 1;
      return input;
    },
  };
  window.hljs = {
    highlightElement() {
      calls.highlight += 1;
    },
  };
  window.fetch = stubFetch(window);
  // jsdom has no layout, so scrollTo is unimplemented and warns on every call.
  window.scrollTo = () => {};
  window.WebSocket = class {
    constructor() {
      this.readyState = 1;
    }
    close() {}
  };

  const source = readFileSync(join(root, "static", "app.js"), "utf8");
  // The trailing expression runs in the same scope as the script, so
  // script-scoped declarations are reachable without exporting anything.
  const internals = window.eval(
    `${source}\n;({ handleEvent, state, cancelStreamRender, scheduleStreamRender,
        renderMarkdown, agentEntryBody, buildPipelineCards })`
  );

  return { window, calls, ...internals };
}

/** Resolve after the browser has run one animation frame. */
export function frame(window) {
  return new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
}
