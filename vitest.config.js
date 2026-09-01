import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Each test builds its own JSDOM window from the real index.html, so the
    // suite runs in plain node and nothing leaks between cases.
    environment: "node",
    include: ["tests/frontend/**/*.test.js"],
  },
});
