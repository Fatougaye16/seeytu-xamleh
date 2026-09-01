import { describe, it, expect } from "vitest";
import { boot, frame } from "./harness.js";

const token = (delta) => ({ type: "agent_token", agent: "scout", step: 1, delta });
const start = { type: "agent_start", agent: "scout", step: 1, total: 4 };

describe("streaming render", () => {
  it("does not render markdown synchronously on every token", async () => {
    const { handleEvent, calls } = boot();
    handleEvent(start);
    const before = calls.parse;

    for (let i = 0; i < 50; i += 1) handleEvent(token("x"));

    expect(calls.parse - before).toBe(0);
  });

  it("coalesces a burst of tokens into a single render", async () => {
    const { window, handleEvent, calls } = boot();
    handleEvent(start);
    const before = calls.parse;

    for (let i = 0; i < 50; i += 1) handleEvent(token("x"));
    await frame(window);

    expect(calls.parse - before).toBe(1);
  });

  it("renders the whole accumulated text, not just the last token", async () => {
    const { window, handleEvent, agentEntryBody } = boot();
    handleEvent(start);

    for (const piece of ["alpha ", "beta ", "gamma"]) handleEvent(token(piece));
    await frame(window);

    const text = agentEntryBody("scout").querySelector(".live-text").textContent;
    expect(text).toContain("alpha beta gamma");
  });

  it("keeps rendering across frames as more tokens arrive", async () => {
    const { window, handleEvent, calls } = boot();
    handleEvent(start);
    const before = calls.parse;

    handleEvent(token("one"));
    await frame(window);
    handleEvent(token(" two"));
    await frame(window);

    expect(calls.parse - before).toBe(2);
  });

  it("re-highlights code blocks only once per frame, not once per token", async () => {
    const { window, handleEvent, calls } = boot();
    handleEvent(start);
    const before = calls.highlight;

    for (let i = 0; i < 30; i += 1) handleEvent(token("x"));
    await frame(window);

    expect(calls.highlight - before).toBeLessThanOrEqual(1);
  });
});

describe("pending frames are cancelled", () => {
  it("does not repaint a body that agent_complete has already replaced", async () => {
    const { window, handleEvent, calls, agentEntryBody } = boot();
    handleEvent(start);
    handleEvent(token("partial text"));

    // Completion lands before the queued frame runs.
    handleEvent({
      type: "agent_complete", agent: "scout", step: 1, output: "the final brief",
    });
    const afterComplete = calls.parse;
    await frame(window);

    expect(calls.parse).toBe(afterComplete);
    const text = agentEntryBody("scout").querySelector(".live-text").textContent;
    expect(text).toContain("the final brief");
    expect(text).not.toContain("partial text");
  });

  it("does not repaint after a run is cancelled", async () => {
    const { window, handleEvent, calls } = boot();
    handleEvent(start);
    handleEvent(token("half a sentence"));

    handleEvent({ type: "cancelled", agent: "scout", step: 1, completed: [] });
    const afterCancel = calls.parse;
    await frame(window);

    expect(calls.parse).toBe(afterCancel);
  });

  it("does not repaint after an error", async () => {
    const { window, handleEvent, calls } = boot();
    handleEvent(start);
    handleEvent(token("half a sentence"));

    handleEvent({
      type: "error", message: "Ollama fell over", hint: "ollama serve",
      agent: "scout", step: 1, completed: [],
    });
    const afterError = calls.parse;
    await frame(window);

    expect(calls.parse).toBe(afterError);
  });

  it("starts the next agent from an empty buffer", async () => {
    const { window, handleEvent, agentEntryBody } = boot();
    handleEvent(start);
    handleEvent(token("scout text"));

    handleEvent({ type: "agent_start", agent: "architect", step: 2, total: 4 });
    handleEvent({ type: "agent_token", agent: "architect", step: 2, delta: "architect text" });
    await frame(window);

    const text = agentEntryBody("architect").querySelector(".live-text").textContent;
    expect(text).toContain("architect text");
    expect(text).not.toContain("scout text");
  });
});

describe("error rendering", () => {
  it("puts the server's message in as text, never as markup", async () => {
    const { handleEvent, agentEntryBody } = boot();
    handleEvent(start);

    handleEvent({
      type: "error",
      message: "<img src=x onerror=alert(1)>",
      hint: "",
      agent: "scout",
      step: 1,
      completed: [],
    });

    const note = agentEntryBody("scout").querySelector(".live-note");
    expect(note.querySelector("img")).toBeNull();
    expect(note.textContent).toContain("<img src=x onerror=alert(1)>");
  });
});
