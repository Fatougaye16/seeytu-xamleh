/* Seeytu-Xamleh frontend. Three views, one WebSocket, no build step. */

const AGENTS = [
  { key: "scout", emoji: "🔍", name: "The Scout", activity: "Mapping the topic landscape" },
  { key: "architect", emoji: "📐", name: "The Architect", activity: "Designing the learning path" },
  { key: "builder", emoji: "🔨", name: "The Builder", activity: "Specifying the capstone project" },
  { key: "publisher", emoji: "✍️", name: "The Publisher", activity: "Drafting the content" },
];

const EXAMPLES = [
  "How Kafka powers real-time fintech",
  "Vector databases for AI applications",
  "Platform engineering with Kubernetes",
  "Event sourcing in healthcare systems",
  "How payment rails actually settle",
  "Feature stores for ML in logistics",
];

// Targets from the Publisher prompt. Shown, never enforced — you edit these
// before publishing, so a regeneration to fix length would be wasted effort.
const WORD_TARGETS = {
  linkedin: [150, 300],
  substack: [800, 1500],
};

const el = (id) => document.getElementById(id);

const state = {
  runId: null,
  socket: null,
  run: null,
  activeTab: null,
  streaming: "",
  thinking: 0,
  agentStart: null,
};

/* --- Markdown rendering ------------------------------------------------ */

marked.setOptions({ breaks: false, gfm: true });

function renderMarkdown(target, markdown) {
  // Sanitize before inserting: the content is model-generated, and a stray
  // script tag costs one line to neutralize.
  target.innerHTML = DOMPurify.sanitize(marked.parse(markdown || ""));
  target.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
}

function toast(message) {
  const node = document.createElement("div");
  node.className = "toast";
  node.setAttribute("role", "status");
  node.textContent = message;
  document.body.appendChild(node);
  setTimeout(() => node.remove(), 1600);
}

/* --- Views ------------------------------------------------------------- */

function showView(name) {
  ["home", "progress", "results"].forEach((view) => {
    el(`view-${view}`).classList.toggle("is-active", view === name);
  });
}

/* --- API --------------------------------------------------------------- */

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail?.message || detail.detail || response.statusText);
  }
  return response.status === 204 ? null : response.json();
}

/* --- Home -------------------------------------------------------------- */

function buildExamples() {
  el("example-chips").innerHTML = "";
  EXAMPLES.forEach((topic) => {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = topic;
    chip.onclick = () => {
      el("topic-input").value = topic;
      startRun();
    };
    el("example-chips").appendChild(chip);
  });
}

async function checkHealth() {
  const note = el("health-note");
  try {
    const health = await api("/api/health");
    if (!health.ollama) {
      note.textContent = `${health.error} → ${health.hint || ""}`;
      note.style.color = "var(--err)";
      return;
    }
    note.textContent = `Model: ${health.model} (${health.mode})`;
    note.style.color = "var(--text-dim)";
  } catch (error) {
    note.textContent = `Backend unreachable: ${error.message}`;
    note.style.color = "var(--err)";
  }
}

/* --- Progress ---------------------------------------------------------- */

function buildStepTracker() {
  el("agent-steps").innerHTML = "";
  AGENTS.forEach((agent) => {
    const item = document.createElement("li");
    item.className = "agent-step";
    item.id = `step-${agent.key}`;
    item.innerHTML = `
      <span class="agent-emoji">${agent.emoji}</span>
      <span>
        <span class="agent-name">${agent.name}</span><br>
        <span class="agent-activity">${agent.activity}</span>
      </span>
      <span class="agent-state">waiting</span>`;
    el("agent-steps").appendChild(item);
  });
}

function markStep(agentKey, status, label) {
  const node = el(`step-${agentKey}`);
  if (!node) return;
  node.classList.toggle("is-running", status === "running");
  node.classList.toggle("is-done", status === "done");
  node.classList.toggle("is-failed", status === "failed");
  node.querySelector(".agent-state").textContent = label;
}

async function startRun(topicOverride) {
  const topic = (topicOverride || el("topic-input").value).trim();
  if (!topic) {
    toast("Enter a topic first");
    el("topic-input").focus();
    return;
  }

  buildStepTracker();
  state.streaming = "";
  state.thinking = 0;
  el("live-output").innerHTML = "";
  el("retry-button").hidden = true;
  el("cancel-button").hidden = false;
  el("progress-status").textContent = "Starting…";
  showView("progress");

  try {
    const { run_id } = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({ topic }),
    });
    state.runId = run_id;
    connectSocket(run_id);
  } catch (error) {
    el("progress-status").textContent = `Could not start: ${error.message}`;
  }
}

function connectSocket(runId) {
  // The backend buffers every event and replays it on connect, so this cannot
  // miss anything emitted between POST /api/run and now — and reconnecting
  // after a refresh recovers the whole run.
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws/pipeline/${runId}`);
  state.socket = socket;
  socket.onmessage = (message) => handleEvent(JSON.parse(message.data));
  socket.onerror = () => {
    el("progress-status").textContent = "Connection lost. Reload to re-attach to this run.";
  };
}

function elapsed() {
  if (!state.agentStart) return "";
  return ` · ${Math.round((Date.now() - state.agentStart) / 1000)}s`;
}

function handleEvent(event) {
  switch (event.type) {
    case "agent_start":
      state.streaming = "";
      state.thinking = 0;
      state.agentStart = Date.now();
      markStep(event.agent, "running", `running ${event.step}/${event.total}`);
      el("progress-status").textContent =
        `Agent ${event.step} of ${event.total} is working. Output appears as it is written.`;
      break;

    case "agent_thinking":
      // Reasoning models think before answering. Without this the panel would
      // sit empty for the whole reasoning phase.
      state.thinking += 1;
      if (state.thinking % 25 === 0) {
        el("progress-status").textContent =
          `Reasoning… ${state.thinking} thought tokens${elapsed()}`;
      }
      break;

    case "agent_token":
      state.streaming += event.delta;
      renderMarkdown(el("live-output"), state.streaming);
      break;

    case "agent_complete":
      markStep(event.agent, "done", "✓ done");
      state.streaming = event.output;
      renderMarkdown(el("live-output"), state.streaming);
      break;

    case "pipeline_complete":
      el("cancel-button").hidden = true;
      el("progress-status").textContent = "Complete.";
      loadRun(event.run_id);
      loadHistory();
      break;

    case "cancelled":
      el("cancel-button").hidden = true;
      el("progress-status").textContent =
        "Cancelled — nothing was written to disk. Runs are atomic.";
      break;

    case "error": {
      el("cancel-button").hidden = true;
      if (event.agent) markStep(event.agent, "failed", "failed");
      const done = event.completed?.length || 0;
      el("progress-status").textContent =
        `${event.message}${event.hint ? ` → ${event.hint}` : ""}` +
        (done ? `  (${done} agent${done > 1 ? "s" : ""} finished; retry resumes there)` : "");
      break;
    }
  }
}

async function cancelRun() {
  if (!state.runId) return;
  await api(`/api/run/${state.runId}/cancel`, { method: "POST" });
  el("progress-status").textContent = "Cancelling…";
}

/* --- Results ----------------------------------------------------------- */

async function loadRun(runId) {
  state.run = await api(`/api/runs/${runId}`);
  state.activeTab = state.run.files[0]?.key || null;
  el("results-topic").textContent = state.run.topic;

  const created = (state.run.created_at || "").slice(0, 16).replace("T", " ");
  el("results-meta").textContent =
    [created, state.run.model, state.run.mode].filter(Boolean).join(" · ");

  const warning = el("results-warning");
  if (state.run.missing_sections?.length) {
    warning.hidden = false;
    warning.textContent =
      `The writer's output could not be split into: ` +
      `${state.run.missing_sections.join(", ")}. The full response is in the ` +
      `"Raw Writer Output" tab, so nothing was lost.`;
  } else {
    warning.hidden = true;
  }

  buildTabs();
  renderActiveTab();
  showView("results");
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
    tab.title = target ? `Target ${target[0]}–${target[1]} words` : "";
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
}

async function copyActive() {
  const file = activeFile();
  if (!file) return;
  await navigator.clipboard.writeText(file.content);
  toast("Copied!");
}

function downloadAll() {
  if (!state.run) return;
  // A plain navigation: the browser handles the zip stream and the
  // Content-Disposition filename without any blob juggling.
  window.location.href = `/api/runs/${state.run.run_id}/archive`;
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

/* --- History ----------------------------------------------------------- */

async function loadHistory() {
  const runs = await api("/api/runs");
  const list = el("history-list");
  list.innerHTML = "";

  if (!runs.length) {
    list.innerHTML = `<li class="empty-state">No runs yet. Pick a topic to start.</li>`;
    return;
  }

  runs.forEach((run) => {
    const item = document.createElement("li");
    item.className = "history-item";
    item.dataset.runId = run.run_id;

    // Built with textContent, not innerHTML: run.topic is whatever the user
    // typed, so interpolating it would be an injection sink — and a topic
    // containing a quote would break the title attribute regardless.
    const label = document.createElement("span");
    const topic = document.createElement("span");
    topic.className = "history-topic";
    topic.textContent = run.topic;
    topic.title = run.topic;
    const date = document.createElement("span");
    date.className = "history-date";
    date.textContent = (run.created_at || "").slice(0, 16).replace("T", " ");
    label.append(topic, date);

    const buttons = document.createElement("span");
    buttons.className = "history-buttons";
    const remove = document.createElement("button");
    remove.className = "history-action";
    remove.dataset.act = "delete";
    remove.title = "Delete";
    remove.textContent = "×";
    buttons.append(remove);

    item.append(label, buttons);

    item.onclick = () => loadRun(run.run_id);
    remove.onclick = async (clickEvent) => {
      clickEvent.stopPropagation();
      if (!confirm(`Delete "${run.topic}"? This removes the folder from disk.`)) return;
      await api(`/api/runs/${run.run_id}`, { method: "DELETE" });
      if (state.run?.run_id === run.run_id) showView("home");
      loadHistory();
    };
    list.appendChild(item);
  });
}

function markHistoryActive(runId) {
  document.querySelectorAll(".history-item").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.runId === runId);
  });
}

/* --- Settings ---------------------------------------------------------- */

async function openSettings() {
  el("settings-backdrop").hidden = false;
  el("settings-panel").hidden = false;

  try {
    const [models, cfg, profile] = await Promise.all([
      api("/api/models"),
      api("/api/config"),
      api("/api/profile"),
    ]);

    // /api/tags lists local models only, so cloud names come from a curated
    // list on the server. Grouping makes the speed/privacy trade-off visible.
    const select = el("model-select");
    select.innerHTML = "";
    const groups = [
      ["Cloud — fast, needs `ollama signin`", models.cloud],
      ["Installed locally — private, slower", models.local],
    ];
    for (const [label, names] of groups) {
      if (!names.length) continue;
      const group = document.createElement("optgroup");
      group.label = label;
      for (const name of names) {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        option.selected = name === cfg.model;
        group.append(option);
      }
      select.append(group);
    }
    // A configured-but-absent model (e.g. cloud default while signed out)
    // would otherwise silently show the wrong selection.
    if (!Array.from(select.options).some((option) => option.selected)) {
      const option = document.createElement("option");
      option.value = cfg.model;
      option.textContent = `${cfg.model} (not installed)`;
      option.selected = true;
      select.prepend(option);
    }
    el("model-hint").textContent =
      `num_ctx ${cfg.num_ctx} · max_tokens ${cfg.max_tokens} · ` +
      `up to ${cfg.max_concurrent_runs} concurrent runs`;

    el("temperature-slider").value = cfg.temperature;
    el("temperature-value").textContent = Number(cfg.temperature).toFixed(2);

    el("profile-editor").value = profile.content;
    el("profile-path").textContent = profile.path.split(/[\\/]/).pop();
  } catch (error) {
    toast(`Could not load settings: ${error.message}`);
  }
}

function closeSettings() {
  el("settings-backdrop").hidden = true;
  el("settings-panel").hidden = true;
}

async function saveModel() {
  await api("/api/config", {
    method: "PUT",
    body: JSON.stringify({ model: el("model-select").value }),
  });
  toast("Model updated");
  checkHealth();
}

async function saveTemperature() {
  await api("/api/config", {
    method: "PUT",
    body: JSON.stringify({ temperature: Number(el("temperature-slider").value) }),
  });
}

async function saveProfile() {
  const button = el("profile-save");
  button.disabled = true;
  try {
    await api("/api/profile", {
      method: "PUT",
      body: JSON.stringify({ content: el("profile-editor").value }),
    });
    toast("Profile saved — applies to the next run");
  } catch (error) {
    toast(`Save failed: ${error.message}`);
  } finally {
    button.disabled = false;
  }
}

/* --- Theme ------------------------------------------------------------- */

function applyTheme(theme) {
  document.body.classList.toggle("light", theme === "light");
  localStorage.setItem("seeytu-theme", theme);
}

function toggleTheme() {
  applyTheme(document.body.classList.contains("light") ? "dark" : "light");
}

/* --- Wiring ------------------------------------------------------------ */

el("start-button").onclick = () => startRun();
el("topic-input").onkeydown = (keyEvent) => {
  if (keyEvent.key === "Enter") startRun();
};
el("cancel-button").onclick = cancelRun;
el("copy-button").onclick = copyActive;
el("download-button").onclick = downloadActive;
el("download-all-button").onclick = downloadAll;
el("theme-toggle").onclick = toggleTheme;
el("theme-toggle-panel").onclick = toggleTheme;

el("settings-button").onclick = openSettings;
el("settings-close").onclick = closeSettings;
el("settings-backdrop").onclick = closeSettings;
el("model-select").onchange = saveModel;
el("temperature-slider").oninput = (inputEvent) => {
  el("temperature-value").textContent = Number(inputEvent.target.value).toFixed(2);
};
el("temperature-slider").onchange = saveTemperature;
el("profile-save").onclick = saveProfile;

document.addEventListener("keydown", (keyEvent) => {
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
  if (keyEvent.key === "Escape") {
    if (!el("settings-panel").hidden) {
      closeSettings();
      return;
    }
    if (!typing) showView("home");
  }
  if (keyEvent.key === "/" && !typing) {
    keyEvent.preventDefault();
    el("topic-input").focus();
  }
});

applyTheme(localStorage.getItem("seeytu-theme") || "dark");
buildExamples();
buildStepTracker();
checkHealth();
loadHistory();
