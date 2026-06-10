let state = null;
let restartRequired = false;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 3200);
}

async function loadState(refreshProjects = false) {
  const path = refreshProjects ? "/api/projects/refresh" : "/api/state";
  if (refreshProjects) {
    const result = await api(path, { method: "POST", body: "{}" });
    state.projects = result.projects;
  } else {
    state = await api(path);
  }
  render();
}

function render() {
  renderStatus();
  renderPlugins();
  renderProjects();
  renderProfiles();
  renderBackups();
  renderAudit();
}

function renderStatus() {
  const enabled = state.enabledPlugins || [];
  $("enabledCount").textContent = enabled.length;
  $("enabledList").textContent = enabled.length ? enabled.join(", ") : "Lean mode: no plugins enabled.";
  $("projectCount").textContent = state.projects.length;
  $("backupCount").textContent = state.backups.length;
  const restart = $("restartState");
  restart.classList.toggle("pending", restartRequired);
  restart.querySelector("strong").textContent = restartRequired ? "Restart required" : "Clean";
  restart.querySelector("p").textContent = restartRequired
    ? "Plugin config changed. Restart Codex when ready."
    : "No pending plugin reload.";
  $("restartCodex").classList.toggle("hidden", !restartRequired);
}

function renderPlugins() {
  const query = $("pluginSearch").value.toLowerCase();
  const grid = $("pluginGrid");
  grid.innerHTML = "";
  state.plugins
    .filter((plugin) => `${plugin.name} ${plugin.description}`.toLowerCase().includes(query))
    .forEach((plugin) => {
      const card = document.createElement("article");
      card.className = "plugin-card";
      card.innerHTML = `
        <header>
          <div>
            <div class="plugin-title">
              <span class="dot ${plugin.enabled ? "on" : ""}"></span>
              <h3>${escapeHtml(plugin.name)}</h3>
            </div>
            <p>${escapeHtml(plugin.description)}</p>
          </div>
          <label class="switch" title="Toggle ${escapeHtml(plugin.name)}">
            <input type="checkbox" ${plugin.enabled ? "checked" : ""}>
            <span class="slider"></span>
          </label>
        </header>
      `;
      card.querySelector("input").addEventListener("change", async (event) => {
        const checked = event.target.checked;
        const result = await api(`/api/plugins/${encodeURIComponent(plugin.name)}`, {
          method: "PATCH",
          body: JSON.stringify({ enabled: checked }),
        });
        restartRequired = result.restartRequired;
        toast(`${plugin.name} ${checked ? "enabled" : "disabled"}. Restart required.`);
        await loadState();
      });
      grid.appendChild(card);
    });
}

function renderProjects() {
  const query = $("projectSearch").value.toLowerCase();
  const list = $("projectList");
  list.innerHTML = "";
  state.projects
    .filter((project) => project.project.toLowerCase().includes(query))
    .sort((a, b) => (b.tokenUsage || 0) - (a.tokenUsage || 0))
    .forEach((project) => {
      const name = project.project.split("/").filter(Boolean).pop() || project.project;
      const card = document.createElement("article");
      card.className = "project-card";
      const chips = project.plugins.length
        ? project.plugins.map((plugin) => `<span class="chip ${plugin.confidence}">${escapeHtml(plugin.name)} · ${plugin.confidence}</span>`).join("")
        : `<span class="chip">No strong plugin signal</span>`;
      const evidence = project.plugins.slice(0, 3).map((plugin) => {
        const details = plugin.evidence && plugin.evidence.length ? plugin.evidence.join("; ") : plugin.description;
        return `<div class="evidence"><strong>${escapeHtml(plugin.name)}:</strong> ${escapeHtml(details)}</div>`;
      }).join("");
      card.innerHTML = `
        <header>
          <div>
            <h3>${escapeHtml(name)}</h3>
            <div class="project-path">${escapeHtml(project.project)}</div>
          </div>
          <p>${formatNumber(project.tokenUsage || 0)} tokens observed</p>
        </header>
        <div class="chips">${chips}</div>
        ${evidence}
      `;
      list.appendChild(card);
    });
}

function renderProfiles() {
  const grid = $("profileGrid");
  grid.innerHTML = "";
  Object.entries(state.profiles).forEach(([name, plugins]) => {
    const card = document.createElement("article");
    card.className = "profile-card";
    card.innerHTML = `
      <h3>${escapeHtml(labelize(name))}</h3>
      <p>${plugins.length ? escapeHtml(plugins.join(", ")) : "No plugins enabled."}</p>
      <button class="primary">Apply ${escapeHtml(labelize(name))}</button>
    `;
    card.querySelector("button").addEventListener("click", async () => {
      const result = await api(`/api/profiles/${encodeURIComponent(name)}/apply`, {
        method: "POST",
        body: "{}",
      });
      restartRequired = result.restartRequired;
      toast(`${labelize(name)} applied. Restart required.`);
      await loadState();
    });
    grid.appendChild(card);
  });
}

function renderBackups() {
  const list = $("backupList");
  list.innerHTML = "";
  state.backups.slice(0, 30).forEach((backup) => {
    const row = document.createElement("article");
    row.className = "backup-row";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(backup.name)}</strong>
        <p>${escapeHtml(backup.modified)} · ${formatNumber(backup.size)} bytes</p>
      </div>
      <button class="secondary">Restore</button>
    `;
    row.querySelector("button").addEventListener("click", async () => {
      const result = await api("/api/backups/restore", {
        method: "POST",
        body: JSON.stringify({ name: backup.name }),
      });
      restartRequired = result.restartRequired;
      toast("Backup restored. Restart required.");
      await loadState();
    });
    list.appendChild(row);
  });
}

function renderAudit() {
  const list = $("auditList");
  list.innerHTML = "";
  state.audit.forEach((event) => {
    const row = document.createElement("article");
    row.className = "audit-row";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(event.event)}</strong>
        <p>${escapeHtml(event.timestamp)}</p>
      </div>
      <p>${escapeHtml(JSON.stringify(event.payload))}</p>
    `;
    list.appendChild(row);
  });
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.tab).classList.add("active");
    });
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function labelize(value) {
  return value.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value);
}

setupTabs();
$("pluginSearch").addEventListener("input", renderPlugins);
$("projectSearch").addEventListener("input", renderProjects);
$("refreshProjects").addEventListener("click", async () => {
  toast("Refreshing project inference...");
  await loadState(true);
  toast("Project inference refreshed.");
});
$("restoreLatest").addEventListener("click", async () => {
  const result = await api("/api/backups/restore", {
    method: "POST",
    body: JSON.stringify({ name: "latest" }),
  });
  restartRequired = result.restartRequired;
  toast("Latest backup restored. Restart required.");
  await loadState();
});
$("restartCodex").addEventListener("click", async () => {
  await api("/api/restart-codex", { method: "POST", body: "{}" });
  toast("Codex restart scheduled.");
});

loadState().catch((error) => toast(error.message));
