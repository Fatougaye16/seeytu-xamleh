/* Seeytu-Xamleh frontend, built to the imported Claude Design UI.
   Four views behind a nav stack, one WebSocket, no build step. */

/* Icon paths lifted from the design's ICONS map. */
const ICONS = {
  scout: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20 20l-4-4",
  architect: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  builder: "M15 12l5.5-5.5a2.8 2.8 0 0 0-4-4L11 8M3 21l6-6M8.5 5.5 18.5 15.5",
  publisher: "M4 20h4L20 8a2.8 2.8 0 0 0-4-4L4 16v4ZM14 6l4 4",
  check: "m4 12 5 5L20 6",
  queued: "M12 8v8M8 12h8",
  failed: "M15 9l-6 6M9 9l6 6",
};

const AGENTS = [
  {
    key: "scout", name: "The Scout", step: "Agent 01",
    blurb: "Surveys the field and separates settled ground from open questions.",
    task: "Surveying sources",
  },
  {
    key: "architect", name: "The Architect", step: "Agent 02",
    blurb: "Turns the research into an ordered path with checkpoints.",
    task: "Sequencing modules",
  },
  {
    key: "builder", name: "The Builder", step: "Agent 03",
    blurb: "Specifies a project that proves you learned the thing.",
    task: "Drafting the spec",
  },
  {
    key: "publisher", name: "The Publisher", step: "Agent 04",
    blurb: "Drafts the post, the article, and the reference page.",
    task: "Waiting on spec",
  },
];

const EXAMPLES = [
  "Retrieval-augmented generation",
  "Kalman filters",
  "Postgres query planning",
  "Wolof orthography",
  "CRDTs",
  "Options pricing",
];

const VIEW_TITLES = {
  home: "Home",
  resources: "My resources",
  pipeline: "Pipeline",
  results: "Results",
};

/* Targets from the Publisher prompt — displayed, never enforced. */
const WORD_TARGETS = { linkedin: [150, 300], substack: [800, 1500] };

const el = (id) => document.getElementById(id);

const state = {
  view: "home",
  stack: [],
  runId: null,
  socket: null,
  run: null,
  activeTab: null,
  topic: "",
  streaming: "",
  agentStates: {},
  runStart: null,
  timer: null,
  resources: [],
  resourcesAvailable: true,
  focusBeforeSettings: null,
};

/* --- Small helpers ----------------------------------------------------- */

function svg(path, size, width = 1.8) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="${width}" stroke-linecap="round"
    stroke-linejoin="round"><path d="${path}"/></svg>`;
}

function toast(message) {
  const node = document.createElement("div");
  node.className = "toast";
  node.setAttribute("role", "status");
  node.textContent = message;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 1800);
}

marked.setOptions({ breaks: false, gfm: true });

function renderMarkdown(target, markdown) {
  // Model-generated content: sanitize before it becomes HTML.
  target.innerHTML = DOMPurify.sanitize(marked.parse(markdown || ""));
  target.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: options.body ? { "Content-Type": "application/json" } : {},
    ...options,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    const error = new Error(detail.detail?.message || detail.detail || response.statusText);
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

/* --- Navigation -------------------------------------------------------- */

function showView(name, { push = true } = {}) {
  if (push && name !== state.view) state.stack.push(state.view);
  state.view = name;

  ["home", "resources", "pipeline", "results"].forEach((view) => {
    el(`view-${view}`).classList.toggle("is-active", view === name);
  });

  el("view-title").textContent = VIEW_TITLES[name];
  el("back-button").hidden = name === "home";
  el("back-label").textContent = state.stack.length
    ? VIEW_TITLES[state.stack[state.stack.length - 1]]
    : "Home";

  const wantsCrumb = name === "pipeline" || name === "results";
  el("crumb").hidden = !wantsCrumb || !state.topic;
  el("crumb").textContent = state.topic;

  el("resources-nav").classList.toggle("is-active", name === "resources");
  window.scrollTo({ top: 0 });
}

function goBack() {
  const previous = state.stack.pop() || "home";
  showView(previous, { push: false });
}

/* --- Home -------------------------------------------------------------- */

function buildExamples() {
  const wrap = el("example-chips");
  wrap.innerHTML = "";
  EXAMPLES.forEach((topic) => {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = topic;
    chip.onclick = () => {
      el("topic-input").value = topic;
      startRun(topic);
    };
    wrap.appendChild(chip);
  });
}

function buildAgentGrid() {
  el("agent-grid").innerHTML = AGENTS.map((agent) => `
    <div class="agent-cell">
      <div class="agent-cell-icon">${svg(ICONS[agent.key], 22)}</div>
      <div class="agent-cell-name">${agent.name}</div>
      <div class="agent-cell-blurb">${agent.blurb}</div>
    </div>`).join("");
}

async function checkHealth() {
  const note = el("health-note");
  try {
    const health = await api("/api/health");
    if (!health.ollama) {
      note.textContent = `${health.error} → ${health.hint || ""}`;
      note.classList.add("is-error");
      el("model-pill").textContent = "no model";
      return;
    }
    note.classList.remove("is-error");
    note.textContent = "";
    // Plain label in the chrome; the exact model stays available on hover and
    // in Settings for anyone who cares which one is running.
    state.mode = health.mode;
    const pill = el("model-pill");
    pill.textContent = health.mode === "cloud" ? "Cloud AI" : "On this computer";
    pill.title = health.model;
  } catch (error) {
    note.textContent = `Backend unreachable: ${error.message}`;
    note.classList.add("is-error");
  }
}

/* --- Pipeline ---------------------------------------------------------- */

function buildPipelineCards() {
  state.agentStates = {};
  el("pipeline-grid").innerHTML = AGENTS.map((agent, index) => {
    state.agentStates[agent.key] = "queued";
    return `
      <div class="pipe-card" id="pipe-${agent.key}">
        <div class="pipe-top">
          <span class="pipe-dot">${svg(ICONS[agent.key], 18)}</span>
          <span class="pipe-state">queued</span>
        </div>
        <div>
          <div class="pipe-step">${agent.step}</div>
          <div class="pipe-name">${agent.name}</div>
          <div class="pipe-task">${index === 0 ? agent.task : "Waiting"}</div>
        </div>
        <div class="pipe-track"><div class="pipe-bar"></div></div>
      </div>`;
  }).join("");

  el("live-body").innerHTML = AGENTS.map((agent) => `
    <div class="live-entry is-queued" id="live-${agent.key}">
      <span class="live-mark">${svg(ICONS.queued, 18)}</span>
      <div class="live-main">
        <div class="live-name">${agent.name}</div>
        <div class="live-note">Queued.</div>
      </div>
    </div>`).join("");
}

function setAgentState(key, status, { task, barWidth } = {}) {
  state.agentStates[key] = status;
  const card = el(`pipe-${key}`);
  if (card) {
    card.classList.toggle("is-running", status === "running");
    card.classList.toggle("is-done", status === "done");
    card.classList.toggle("is-failed", status === "failed");
    card.querySelector(".pipe-state").textContent =
      status === "done" ? "complete" : status;
    if (task) card.querySelector(".pipe-task").textContent = task;
    if (barWidth !== undefined) card.querySelector(".pipe-bar").style.width = barWidth;
  }

  const entry = el(`live-${key}`);
  if (!entry) return;
  entry.classList.toggle("is-queued", status === "queued");
  entry.classList.toggle("is-running", status === "running");
  entry.classList.toggle("is-done", status === "done");
  entry.classList.toggle("is-failed", status === "failed");
  const marks = { queued: ICONS.queued, running: ICONS.builder, done: ICONS.check, failed: ICONS.failed };
  entry.querySelector(".live-mark").innerHTML =
    svg(marks[status] || ICONS.queued, 18, status === "done" ? 2.2 : 1.8);
}

function agentEntryBody(key) {
  return el(`live-${key}`).querySelector(".live-main");
}

function startTimer() {
  state.runStart = Date.now();
  clearInterval(state.timer);
  state.timer = setInterval(updateMeta, 1000);
  updateMeta();
}

function stopTimer() {
  clearInterval(state.timer);
  state.timer = null;
}

function elapsedLabel() {
  if (!state.runStart) return "0s";
  const seconds = Math.round((Date.now() - state.runStart) / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
}

function updateMeta() {
  const done = Object.values(state.agentStates).filter((s) => s === "done").length;
  el("pipeline-meta").textContent =
    `${elapsedLabel()} so far · ${done} of ${AGENTS.length} agents finished`;
}

async function startRun(topicOverride) {
  const topic = (topicOverride || el("topic-input").value || "").trim();
  if (!topic) {
    toast("Enter a topic first");
    el("topic-input").focus();
    return;
  }

  state.topic = topic;
  state.streaming = "";
  buildPipelineCards();
  el("pipeline-eyebrow").textContent = "Pipeline running";
  el("pipeline-topic").textContent = topic;
  el("live-stats").textContent = "starting";
  el("live-led").style.display = "";
  el("retry-button").hidden = true;
  el("view-results-button").hidden = true;
  el("cancel-button").hidden = false;
  startTimer();
  showView("pipeline");

  try {
    const { run_id } = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({ topic }),
    });
    state.runId = run_id;
    sessionStorage.setItem("seeytu-run", run_id);
    connectSocket(run_id);
  } catch (error) {
    el("live-stats").textContent = "failed to start";
    setAgentState("scout", "failed");
    agentEntryBody("scout").querySelector(".live-note").textContent =
      `Could not start: ${error.message}`;
    stopTimer();
  }
}

function connectSocket(runId) {
  // The server buffers every event and replays it on connect, so nothing
  // emitted between POST /api/run and now is lost — and this is also how a
  // reload re-attaches to a run already in flight.
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws/pipeline/${runId}`);
  state.socket = socket;
  socket.onmessage = (message) => handleEvent(JSON.parse(message.data));
  socket.onerror = () => {
    el("live-stats").textContent = "connection lost — reload to re-attach";
  };
}

function handleEvent(event) {
  switch (event.type) {
    case "queued":
      el("live-stats").textContent = "queued";
      el("pipeline-eyebrow").textContent = "Waiting for a slot";
      agentEntryBody("scout").querySelector(".live-note").textContent = event.message;
      break;

    case "agent_start": {
      state.streaming = "";
      const agent = AGENTS.find((a) => a.key === event.agent);
      setAgentState(event.agent, "running", { task: agent?.task, barWidth: "8%" });
      const body = agentEntryBody(event.agent);
      body.innerHTML = `
        <div class="live-name">${agent?.name || event.agent}</div>
        <div class="live-text"></div>
        <div class="live-progress"><span></span></div>`;
      updateMeta();
      break;
    }

    case "agent_thinking":
      // Some models reason before answering. How many tokens that took is
      // meaningless to a reader; that something is happening is not.
      el("live-stats").textContent = "Thinking…";
      break;

    case "agent_token": {
      state.streaming += event.delta;
      el("live-stats").textContent = "Writing…";
      const text = agentEntryBody(event.agent).querySelector(".live-text");
      if (text) renderMarkdown(text, state.streaming);
      // Rough progress: the bar is a sign of life, not a measurement.
      const card = el(`pipe-${event.agent}`);
      if (card) {
        const pct = Math.min(92, 8 + Math.round(state.streaming.length / 60));
        card.querySelector(".pipe-bar").style.width = `${pct}%`;
      }
      break;
    }

    case "agent_complete": {
      setAgentState(event.agent, "done", { task: "Complete", barWidth: "100%" });
      const words = event.output.trim().split(/\s+/).length;
      const body = agentEntryBody(event.agent);
      const preview = event.output.trim().slice(0, 320);
      body.innerHTML = `
        <div class="live-name">${AGENTS.find((a) => a.key === event.agent)?.name}</div>
        <div class="live-text"></div>
        <div class="live-chips"><span class="live-chip">${words.toLocaleString()} words</span></div>`;
      renderMarkdown(
        body.querySelector(".live-text"),
        preview + (event.output.length > preview.length ? "…" : "")
      );
      updateMeta();
      break;
    }

    case "pipeline_complete":
      stopTimer();
      el("cancel-button").hidden = true;
      el("view-results-button").hidden = false;
      el("pipeline-eyebrow").textContent = "All done";
      el("live-led").style.display = "none";
      el("live-stats").textContent = "Finished";
      sessionStorage.removeItem("seeytu-run");
      loadRun(event.run_id, { push: true });
      loadHistory();
      break;

    case "cancelled":
      stopTimer();
      el("cancel-button").hidden = true;
      el("live-led").style.display = "none";
      el("pipeline-eyebrow").textContent = "Stopped";
      el("live-stats").textContent = "Stopped — nothing was saved";
      break;

    case "error": {
      stopTimer();
      el("cancel-button").hidden = true;
      el("retry-button").hidden = false;
      el("live-led").style.display = "none";
      el("pipeline-eyebrow").textContent = "Something went wrong";
      el("live-stats").textContent = "Stopped";
      if (event.agent) {
        setAgentState(event.agent, "failed", { task: "Failed" });
        const body = agentEntryBody(event.agent);
        body.innerHTML = `
          <div class="live-name">${AGENTS.find((a) => a.key === event.agent)?.name}</div>
          <div class="live-note"></div>`;
        body.querySelector(".live-note").textContent =
          `${event.message}${event.hint ? ` → ${event.hint}` : ""}`;
      }
      break;
    }
  }
}

async function cancelRun() {
  if (!state.runId) return;
  await api(`/api/run/${state.runId}/cancel`, { method: "POST" });
  el("live-stats").textContent = "cancelling…";
}

async function retryRun() {
  if (!state.runId) return;
  el("retry-button").hidden = true;
  el("cancel-button").hidden = false;
  el("pipeline-eyebrow").textContent = "Retrying";
  el("live-led").style.display = "";
  startTimer();
  try {
    await api(`/api/run/${state.runId}/retry`, { method: "POST" });
    connectSocket(state.runId);
  } catch (error) {
    el("live-stats").textContent = `retry failed: ${error.message}`;
    el("retry-button").hidden = false;
    stopTimer();
  }
}

async function reattachToRunInProgress() {
  const runId = sessionStorage.getItem("seeytu-run");
  if (!runId) return;
  try {
    const runState = await api(`/api/run/${runId}/state`);
    if (!["queued", "running", "cancelling"].includes(runState.status)) {
      sessionStorage.removeItem("seeytu-run");
      return;
    }
    state.runId = runId;
    state.topic = runState.topic;
    buildPipelineCards();
    el("pipeline-topic").textContent = runState.topic;
    el("pipeline-eyebrow").textContent = "Re-attaching";
    startTimer();
    showView("pipeline", { push: false });
    connectSocket(runId);
  } catch {
    sessionStorage.removeItem("seeytu-run");
  }
}

/* --- Results ----------------------------------------------------------- */

async function loadRun(runId, { push = true } = {}) {
  try {
    state.run = await api(`/api/runs/${runId}`);
  } catch (error) {
    toast(`Could not open that run: ${error.message}`);
    return;
  }
  state.topic = state.run.topic;
  state.activeTab = state.run.files[0]?.key || null;
  el("results-topic").textContent = state.run.topic;

  const created = (state.run.created_at || "").slice(0, 10);
  const meta = el("results-meta");
  meta.textContent =
    `${state.run.files.length} documents · ${created}`;
  // The model that produced it is real provenance, just not headline chrome.
  meta.title = [state.run.model, state.run.mode].filter(Boolean).join(" · ");

  const warning = el("results-warning");
  if (state.run.missing_sections?.length) {
    warning.hidden = false;
    warning.textContent =
      "Some pieces could not be separated into their own documents this time. " +
      `Nothing is missing — you'll find everything in the "${
        state.run.files.find((f) => f.key === "combined")?.label || "full draft"
      }" tab.`;
  } else {
    warning.hidden = true;
  }

  buildTabs();
  renderActiveTab();
  showView("results", { push });
  markHistoryActive(runId);
}

function buildTabs() {
  const tabs = el("result-tabs");
  tabs.innerHTML = "";
  state.run.files.forEach((file) => {
    const target = WORD_TARGETS[file.key];
    const off = target && (file.word_count < target[0] || file.word_count > target[1]);
    const tab = document.createElement("button");
    tab.className = "tab" + (file.key === state.activeTab ? " is-active" : "");
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(file.key === state.activeTab));
    if (target) tab.title = `Target ${target[0]}–${target[1]} words`;
    tab.append(document.createTextNode(file.label));
    const count = document.createElement("span");
    count.className = "tab-count" + (off ? " out-of-range" : "");
    count.textContent = `${file.word_count}w`;
    tab.append(count);
    tab.onclick = () => {
      state.activeTab = file.key;
      buildTabs();
      renderActiveTab();
    };
    tabs.appendChild(tab);
  });
}

function activeFile() {
  return state.run?.files.find((file) => file.key === state.activeTab);
}

function renderActiveTab() {
  const file = activeFile();
  renderMarkdown(el("result-panel"), file?.content || "");
  el("active-file").textContent = file?.filename || "";
  el("copy-linkedin-button").hidden = state.activeTab !== "linkedin";
}

async function copyActive() {
  const file = activeFile();
  if (!file) return;
  await navigator.clipboard.writeText(file.content);
  toast("Copied!");
}

async function copyForLinkedIn() {
  const file = activeFile();
  if (!file || !state.run) return;
  const response = await fetch(`/api/runs/${state.run.run_id}/${file.filename}?plain=1`);
  await navigator.clipboard.writeText(await response.text());
  toast("Copied — ready to paste into LinkedIn");
}

function downloadActive() {
  const file = activeFile();
  if (!file) return;
  const blob = new Blob([file.content], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = file.filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

function downloadAll() {
  if (!state.run) return;
  window.location.href = `/api/runs/${state.run.run_id}/archive`;
}

/* --- History ----------------------------------------------------------- */

async function loadHistory() {
  const list = el("history-list");
  let runs;
  try {
    runs = await api("/api/runs");
  } catch (error) {
    list.innerHTML = "";
    const failed = document.createElement("li");
    failed.className = "empty-state";
    failed.textContent = `Could not load history: ${error.message}`;
    list.append(failed);
    return;
  }

  list.innerHTML = "";
  if (!runs.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No runs yet.";
    list.append(empty);
    return;
  }

  runs.forEach((run) => {
    const item = document.createElement("li");
    item.className = "history-item";
    item.dataset.runId = run.run_id;

    // textContent throughout: run.topic is user input, so interpolating it
    // would be an injection sink and a quote would break the title attribute.
    const top = document.createElement("div");
    top.className = "history-top";
    const dot = document.createElement("span");
    dot.className = "history-dot";
    const topic = document.createElement("div");
    topic.className = "history-topic";
    topic.textContent = run.topic;
    topic.title = run.topic;
    top.append(dot, topic);

    const bottom = document.createElement("div");
    bottom.className = "history-bottom";
    const date = document.createElement("span");
    date.className = "history-date";
    date.textContent = (run.created_at || "").slice(0, 10);
    const actions = document.createElement("span");
    actions.className = "history-actions";

    const rerun = document.createElement("button");
    rerun.className = "icon-action";
    rerun.title = "Run this topic again — your earlier results are kept";
    rerun.innerHTML = svg("M21 12a9 9 0 1 1-3-6.7M21 3v6h-6", 14, 2);
    rerun.onclick = (clickEvent) => {
      clickEvent.stopPropagation();
      startRun(run.topic);
    };

    const remove = document.createElement("button");
    remove.className = "icon-action is-danger";
    remove.title = "Delete";
    remove.innerHTML = svg("M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13", 14, 2);
    remove.onclick = async (clickEvent) => {
      clickEvent.stopPropagation();
      if (!confirm(`Delete "${run.topic}" and all its documents? This can't be undone.`)) return;
      await api(`/api/runs/${run.run_id}`, { method: "DELETE" });
      if (state.run?.run_id === run.run_id) showView("home");
      loadHistory();
    };

    actions.append(rerun, remove);
    bottom.append(date, actions);
    item.append(top, bottom);
    item.onclick = () => loadRun(run.run_id);
    list.appendChild(item);
  });
}

function markHistoryActive(runId) {
  document.querySelectorAll(".history-item").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.runId === runId);
  });
}

/* --- Resources --------------------------------------------------------- */

async function loadResources() {
  const list = el("res-list");
  try {
    const payload = await api("/api/resources");
    state.resources = payload.resources;
    state.resourcesAvailable = true;
    el("dropzone-hint").textContent = payload.hint;
  } catch (error) {
    state.resourcesAvailable = false;
    list.innerHTML = "";
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent =
      error.status === 404
        ? "Your library isn't available right now."
        : `Couldn't load your library: ${error.message}`;
    list.append(empty);
    return;
  }
  renderResources();
}

function renderResources() {
  const list = el("res-list");
  const active = state.resources.filter((r) => r.enabled).length;
  el("resource-count").textContent = String(state.resources.length);
  el("res-stats").textContent = state.resources.length
    ? `${active} of ${state.resources.length} in use · ` +
      `${state.resources.reduce((sum, r) => sum + (r.words || 0), 0).toLocaleString()} words`
    : "Nothing added yet";

  list.innerHTML = "";
  if (!state.resources.length) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "Nothing yet. Add a file, a link, or a note above.";
    list.append(empty);
    return;
  }

  state.resources.forEach((resource) => {
    const row = document.createElement("li");
    row.className = "res-row" + (resource.enabled ? "" : " is-off");

    const kind = document.createElement("span");
    kind.className = "res-kind";
    kind.textContent = resource.kind;

    const main = document.createElement("div");
    main.className = "res-main";
    const name = document.createElement("div");
    name.className = "res-name";
    name.textContent = resource.name;
    name.title = resource.name;
    const meta = document.createElement("div");
    meta.className = "res-meta";
    meta.textContent = resource.meta;
    main.append(name, meta);

    const status = document.createElement("span");
    status.className = "res-status" + (resource.error ? " is-error" : "");
    status.textContent = resource.error || "Ready";

    const toggle = document.createElement("button");
    toggle.className = "switch" + (resource.enabled ? " is-on" : "");
    toggle.title = "Include in runs";
    toggle.setAttribute("aria-pressed", String(resource.enabled));
    toggle.innerHTML = "<span></span>";
    toggle.onclick = async () => {
      await api(`/api/resources/${resource.id}/toggle`, { method: "POST" });
      loadResources();
    };

    const remove = document.createElement("button");
    remove.className = "icon-action is-danger";
    remove.title = "Remove";
    remove.innerHTML = svg("M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13", 15, 1.8);
    remove.onclick = async () => {
      if (!confirm(`Remove "${resource.name}" from the library?`)) return;
      await api(`/api/resources/${resource.id}`, { method: "DELETE" });
      loadResources();
    };

    row.append(kind, main, status, toggle, remove);
    list.appendChild(row);
  });
}

async function uploadFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;
  for (const file of files) {
    try {
      const text = await file.text();
      await api("/api/resources", {
        method: "POST",
        body: JSON.stringify({ kind: "file", name: file.name, content: text }),
      });
    } catch (error) {
      toast(`${file.name}: ${error.message}`);
    }
  }
  loadResources();
}

async function addLink() {
  const url = el("link-input").value.trim();
  if (!url) return;
  const button = el("link-button");
  button.disabled = true;
  button.textContent = "Fetching…";
  try {
    await api("/api/resources", {
      method: "POST",
      body: JSON.stringify({ kind: "url", name: url }),
    });
    el("link-input").value = "";
    loadResources();
  } catch (error) {
    toast(`Could not fetch: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "Fetch";
  }
}

async function addNote() {
  const content = el("note-input").value.trim();
  const name = el("note-name").value.trim() || "Pasted note";
  if (!content) {
    toast("Paste some text first");
    return;
  }
  try {
    await api("/api/resources", {
      method: "POST",
      body: JSON.stringify({ kind: "note", name, content }),
    });
    el("note-input").value = "";
    el("note-name").value = "";
    loadResources();
  } catch (error) {
    toast(`Could not save: ${error.message}`);
  }
}

/* --- Settings ---------------------------------------------------------- */

async function openSettings() {
  state.focusBeforeSettings = document.activeElement;
  el("settings-layer").hidden = false;
  el("settings-close").focus();

  // /api/models queries Ollama and takes seconds; /api/config and /api/profile
  // are instant. Awaiting all three together left the whole panel blank for as
  // long as the slowest one, so they are populated independently.
  const modelsPromise = api("/api/models");
  const select = el("model-select");
  select.innerHTML = "";
  const loading = document.createElement("option");
  loading.textContent = "Loading models…";
  select.append(loading);
  select.disabled = true;

  try {
    const [cfg, profile] = await Promise.all([api("/api/config"), api("/api/profile")]);
    setTemperature(cfg.temperature);
    el("profile-editor").value = profile.content;
    // The privacy consequence differs by mode, and it is the part worth saying.
    el("profile-privacy").textContent =
      state.mode === "cloud"
        ? "Sent to the AI service with every request, along with your topic."
        : "Stays on this computer — nothing is sent anywhere.";

    const models = await modelsPromise;
    select.disabled = false;
    select.innerHTML = "";
    for (const [label, names] of [
      ["Cloud — faster, needs an internet connection", models.cloud],
      ["On this computer — private, but slower", models.local],
    ]) {
      if (!names.length) continue;
      const group = document.createElement("optgroup");
      group.label = label;
      names.forEach((name) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        option.selected = name === cfg.model;
        group.append(option);
      });
      select.append(group);
    }
    // A configured-but-absent model (the cloud default while signed out) would
    // otherwise leave the dropdown showing something other than what will run.
    if (!Array.from(select.options).some((o) => o.selected)) {
      const option = document.createElement("option");
      option.value = cfg.model;
      option.textContent = `${cfg.model} — not available`;
      option.selected = true;
      select.prepend(option);
    }
  } catch (error) {
    select.disabled = false;
    loading.textContent = "Could not load models";
    toast(`Could not load settings: ${error.message}`);
  }
}

function closeSettings() {
  el("settings-layer").hidden = true;
  state.focusBeforeSettings?.focus?.();
}

function setTemperature(value) {
  const number = Number(value);
  const pct = `${Math.round(number * 100)}%`;
  el("temperature-slider").value = value;
  // A word says more than "0.70" to someone who has never tuned a model.
  el("temperature-value").textContent =
    number <= 0.3 ? "Focused" : number >= 0.75 ? "Creative" : "Balanced";
  el("temp-fill").style.width = pct;
  el("temp-knob").style.left = pct;
}

async function saveSettings() {
  try {
    await api("/api/config", {
      method: "PUT",
      body: JSON.stringify({
        model: el("model-select").value,
        temperature: Number(el("temperature-slider").value),
      }),
    });
    await api("/api/profile", {
      method: "PUT",
      body: JSON.stringify({ content: el("profile-editor").value }),
    });
    toast("Saved — applies to the next run");
    checkHealth();
    closeSettings();
  } catch (error) {
    toast(`Save failed: ${error.message}`);
  }
}

/* --- Theme ------------------------------------------------------------- */

function applyTheme(theme) {
  document.body.classList.toggle("light", theme === "light");
  localStorage.setItem("seeytu-theme", theme);
  document.querySelectorAll("#theme-segmented button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.theme === theme);
  });
}

/* --- Wiring ------------------------------------------------------------ */

el("start-button").onclick = () => startRun();
el("topic-input").onkeydown = (keyEvent) => {
  if (keyEvent.key === "Enter") startRun();
};
el("new-topic-button").onclick = () => {
  el("topic-input").value = "";
  showView("home");
  el("topic-input").focus();
};
el("resources-nav").onclick = () => {
  showView("resources");
  loadResources();
};
el("back-button").onclick = goBack;
el("cancel-button").onclick = cancelRun;
el("retry-button").onclick = retryRun;
el("view-results-button").onclick = () => state.runId && loadRun(state.runId);

el("copy-button").onclick = copyActive;
el("copy-linkedin-button").onclick = copyForLinkedIn;
el("download-button").onclick = downloadActive;
el("download-all-button").onclick = downloadAll;

el("settings-button").onclick = openSettings;
el("settings-close").onclick = closeSettings;
el("settings-backdrop").onclick = closeSettings;
el("settings-save").onclick = saveSettings;
el("settings-reset").onclick = () => {
  setTemperature(0.7);
  toast("Reset — press Save to apply");
};
el("temperature-slider").oninput = (inputEvent) => setTemperature(inputEvent.target.value);
el("theme-segmented").onclick = (clickEvent) => {
  const theme = clickEvent.target.closest("button")?.dataset.theme;
  if (theme) applyTheme(theme);
};

el("browse-button").onclick = () => el("file-input").click();
el("file-input").onchange = (changeEvent) => uploadFiles(changeEvent.target.files);
el("link-button").onclick = addLink;
el("note-button").onclick = addNote;

const dropzone = el("dropzone");
["dragenter", "dragover"].forEach((type) =>
  dropzone.addEventListener(type, (dragEvent) => {
    dragEvent.preventDefault();
    dropzone.classList.add("is-over");
  })
);
["dragleave", "drop"].forEach((type) =>
  dropzone.addEventListener(type, () => dropzone.classList.remove("is-over"))
);
dropzone.addEventListener("drop", (dropEvent) => {
  dropEvent.preventDefault();
  uploadFiles(dropEvent.dataTransfer?.files);
});

document.addEventListener("keydown", (keyEvent) => {
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
  if (keyEvent.key === "Escape") {
    if (!el("settings-layer").hidden) {
      closeSettings();
      return;
    }
    if (!typing && state.view !== "home") goBack();
  }
  if (keyEvent.key === "/" && !typing) {
    keyEvent.preventDefault();
    showView("home");
    el("topic-input").focus();
  }
});

applyTheme(localStorage.getItem("seeytu-theme") || "dark");
buildExamples();
buildAgentGrid();
buildPipelineCards();
showView("home", { push: false });
// Host and port live in the tooltip, not the label — the label just needs to
// reassure the reader that this is not a website.
el("sidebar-foot").title = location.host;
checkHealth();
loadHistory();
loadResources();
reattachToRunInProgress();
