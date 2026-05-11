const state = {
  tasks: [],
  report: "",
  uploads: {},
  datasets: {},
};

const datasetLabels = {
  organic_keywords: "Organic Keywords",
  top_pages: "Top Pages",
  backlinks: "Backlinks",
  broken_backlinks: "Broken Backlinks",
  competitors: "Organic Competitors",
};

const stages = ["upload", "gemini", "dashboard", "report"];
let API_BASE_URL = (
  window.APP_CONFIG?.API_BASE_URL ||
  localStorage.getItem("AI_SEO_API_BASE_URL") ||
  ""
).replace(/\/$/, "");

function qs(selector) {
  return document.querySelector(selector);
}

function qsa(selector) {
  return [...document.querySelectorAll(selector)];
}

function toast(message, isError = false) {
  const el = qs("#toast");
  el.textContent = message;
  el.className = `toast show${isError ? " error" : ""}`;
  setTimeout(() => {
    el.className = "toast";
  }, 4200);
}

function setLoading(isLoading, title = "Finding SEO opportunities", copy = "Running rule checks and enriching the highest-priority issues with Gemini.") {
  const overlay = qs("#loadingOverlay");
  qs("#loadingTitle").textContent = title;
  qs("#loadingCopy").textContent = copy;
  overlay.classList.toggle("hidden", !isLoading);
  qsa("#runAnalyze, #runAnalyzeTop").forEach((button) => {
    button.disabled = isLoading;
  });
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    let detail = await response.text();
    try {
      detail = JSON.parse(detail).detail || detail;
    } catch {
      // keep raw text
    }
    throw new Error(detail);
  }
  return response;
}

function setStage(stage) {
  stages.forEach((name) => {
    qs(`#stage-${name}`).classList.toggle("active", name === stage);
    qs(`[data-stage="${name}"]`).classList.toggle("active", name === stage);
    qs(`[data-step-dot="${name}"]`).classList.toggle("active", name === stage);
  });
}

function selectedModel() {
  const model = qs("#modelSelect").value;
  if (model === "custom") {
    return qs("#customModel").value.trim();
  }
  return model;
}

async function uploadCard(card) {
  const datasetType = card.dataset.type;
  const input = card.querySelector("input[type='file']");
  const status = card.querySelector(".upload-status");
  const files = [...input.files];

  if (!files.length) {
    toast(`Choose files for ${datasetLabels[datasetType]} first.`, true);
    return;
  }

  const formData = new FormData();
  formData.append("dataset_type", datasetType);
  files.forEach((file) => formData.append("files", file));

  status.textContent = "Uploading and parsing...";
  try {
    const parsedRows = [];
    for (const file of files) {
      parsedRows.push(...parseCsv(await file.text()));
    }
    const response = await request("/upload-csv", {
      method: "POST",
      body: formData,
    });
    const summaries = await response.json();
    const rows = summaries.reduce((total, item) => total + item.rows, 0);
    state.uploads[datasetType] = { files: summaries.length, rows };
    state.datasets[datasetType] = [...(state.datasets[datasetType] || []), ...parsedRows];
    status.textContent = `${summaries.length} file(s), ${rows.toLocaleString()} rows uploaded`;
    toast(`${datasetLabels[datasetType]} uploaded.`);
  } catch (error) {
    status.textContent = "Upload failed";
    toast(error.message, true);
  }
}

async function analyze() {
  const model = selectedModel();
  if (!model) {
    toast("Choose a Gemini model or enter a custom model code.", true);
    return;
  }

  const payload = { model };
  if (Object.keys(state.datasets).length) {
    payload.datasets = state.datasets;
  }
  const apiKey = qs("#apiKey").value.trim();
  if (apiKey) {
    payload.api_key = apiKey;
  }

  toast("Analyzing uploaded data...");
  setLoading(
    true,
    "Building your SEO action plan",
    "This can take a bit for large exports. Gemini is used on the highest-priority issues, then the full report is assembled."
  );
  try {
    const response = await request("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.tasks = await response.json();
    await loadReport();
    renderDashboard();
    renderReport();
    setStage("dashboard");
    toast(`Generated ${state.tasks.length.toLocaleString()} SEO tasks.`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    setLoading(false);
  }
}

async function loadResults() {
  try {
    const response = await request("/results");
    state.tasks = await response.json();
    await loadReport();
    renderDashboard();
    renderReport();
  } catch {
    state.tasks = [];
  }
}

async function loadReport() {
  const response = await request("/report-preview");
  state.report = await response.text();
}

function groupedCounts(tasks) {
  return tasks.reduce((acc, task) => {
    acc[task.issue] = (acc[task.issue] || 0) + 1;
    return acc;
  }, {});
}

function filteredTasks() {
  const issue = qs("#issueFilter").value;
  if (!issue) {
    return state.tasks;
  }
  return state.tasks.filter((task) => task.issue === issue);
}

function renderDashboard() {
  const tasks = filteredTasks();
  const counts = groupedCounts(tasks);
  const issueNames = Object.keys(counts);
  const avgPriority = tasks.length
    ? Math.round(tasks.reduce((sum, task) => sum + task.priority_score, 0) / tasks.length)
    : 0;
  const avgConfidence = tasks.length
    ? (tasks.reduce((sum, task) => sum + task.confidence_score, 0) / tasks.length).toFixed(2)
    : "0";
  const highPriority = tasks.filter((task) => task.priority_score >= 80).length;

  qs("#taskCount").textContent = tasks.length.toLocaleString();
  qs("#issueTypeCount").textContent = issueNames.length.toLocaleString();
  qs("#highPriorityCount").textContent = highPriority.toLocaleString();
  qs("#avgConfidence").textContent = avgConfidence;
  qs("#onlineCount").textContent = state.tasks.length.toLocaleString();
  qs("#quickTasks").textContent = state.tasks.length.toLocaleString();
  qs("#quickIssues").textContent = Object.keys(groupedCounts(state.tasks)).length.toLocaleString();
  qs("#quickPriority").textContent = avgPriority.toLocaleString();

  renderIssueFilter();
  renderChart(counts);
  renderTopTasks(tasks);
  renderTable(tasks);
}

function renderIssueFilter() {
  const select = qs("#issueFilter");
  const current = select.value;
  const issueNames = Object.keys(groupedCounts(state.tasks)).sort();
  select.innerHTML = '<option value="">All issue types</option>';
  issueNames.forEach((issue) => {
    const option = document.createElement("option");
    option.value = issue;
    option.textContent = issue;
    select.appendChild(option);
  });
  select.value = issueNames.includes(current) ? current : "";
}

function renderChart(counts) {
  const chart = qs("#issueChart");
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map((entry) => entry[1]), 1);
  chart.innerHTML = entries.length
    ? entries.map(([issue, count]) => `
      <div class="bar-row">
        <strong>${escapeHtml(issue)}</strong>
        <div class="bar-track"><div class="bar-fill" style="width:${(count / max) * 100}%"></div></div>
        <span>${count}</span>
      </div>
    `).join("")
    : "<p>No issues yet.</p>";
}

function renderTopTasks(tasks) {
  const top = [...tasks].sort((a, b) => b.priority_score - a.priority_score).slice(0, 8);
  qs("#topTasks").innerHTML = top.length
    ? top.map((task) => `
      <div class="task-item">
        <strong>${escapeHtml(task.issue)} | Priority ${task.priority_score}</strong>
        <span>${escapeHtml(task.page)}${task.keyword ? ` | ${escapeHtml(task.keyword)}` : ""}</span>
      </div>
    `).join("")
    : "<p>No tasks yet.</p>";
}

function renderTable(tasks) {
  const rows = tasks.slice(0, 500).map((task) => `
    <tr>
      <td>${escapeHtml(task.issue)}</td>
      <td>${escapeHtml(task.page)}</td>
      <td>${escapeHtml(task.keyword || "")}</td>
      <td>${task.priority_score}</td>
      <td>${escapeHtml(task.evidence)}</td>
    </tr>
  `).join("");
  qs("#taskTable").innerHTML = rows || '<tr><td colspan="5">No tasks available.</td></tr>';
}

function renderReport() {
  qs("#reportPreview").textContent = state.report || "Run analysis to generate the full SEO action report.";
}

async function download(path, filename) {
  try {
    const response = await request(path);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    toast(error.message, true);
  }
}

async function resetWorkspace() {
  try {
    await request("/reset", { method: "DELETE" });
    state.tasks = [];
    state.report = "";
    state.uploads = {};
    state.datasets = {};
    qsa(".upload-status").forEach((el) => {
      el.textContent = "No files uploaded";
    });
    renderDashboard();
    renderReport();
    setStage("upload");
    toast("Workspace reset.");
  } catch (error) {
    toast(error.message, true);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function parseCsv(text) {
  const rows = splitCsv(text.replace(/^\uFEFF/, ""));
  if (rows.length < 2) {
    return [];
  }
  const headers = rows[0].map((header) => aliasColumn(normalizeColumn(header)));
  return rows.slice(1)
    .filter((row) => row.some((value) => value.trim()))
    .map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index] || ""])));
}

function splitCsv(text) {
  const delimiter = detectDelimiter(text);
  const rows = [];
  let field = "";
  let row = [];
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && quoted && next === '"') {
      field += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === delimiter && !quoted) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") {
        index += 1;
      }
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  row.push(field);
  rows.push(row);
  return rows.filter((item) => item.some((value) => value.trim()));
}

function detectDelimiter(text) {
  const firstLine = text.split(/\r?\n/, 1)[0] || "";
  return ["\t", ";", ","].sort((a, b) => firstLine.split(b).length - firstLine.split(a).length)[0];
}

function normalizeColumn(column) {
  return column.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function aliasColumn(column) {
  const aliases = {
    url: ["url", "page", "target_url", "target", "landing_page", "page_url"],
    source_url: ["source_url", "referring_page", "referring_page_url", "backlink_url"],
    keyword: ["keyword", "query", "search_query"],
    position: ["position", "current_position", "rank", "ranking_position"],
    impressions: ["impressions", "search_volume", "volume"],
    ctr: ["ctr", "click_through_rate"],
    traffic: ["traffic", "organic_traffic", "current_traffic"],
    previous_traffic: ["previous_traffic", "traffic_previous", "prev_traffic"],
    competitor: ["competitor", "competitor_domain", "competing_domain", "domain", "site", "root_domain"],
    common_keywords: ["common_keywords", "common_keyword", "intersecting_keywords"],
    unique_keywords: ["unique_keywords", "unique_keyword", "competitor_unique_keywords"],
    organic_pages: ["organic_pages", "pages"],
    status: ["status", "http_status", "link_status"],
  };
  for (const [canonical, names] of Object.entries(aliases)) {
    if (names.includes(column)) {
      return canonical;
    }
  }
  return column;
}

qsa("[data-stage]").forEach((button) => {
  button.addEventListener("click", () => setStage(button.dataset.stage));
});

qsa("[data-go]").forEach((button) => {
  button.addEventListener("click", () => setStage(button.dataset.go));
});

const apiBaseUrlInput = qs("#apiBaseUrl");
if (apiBaseUrlInput) {
  apiBaseUrlInput.value = API_BASE_URL;
  apiBaseUrlInput.addEventListener("change", () => {
    API_BASE_URL = apiBaseUrlInput.value.trim().replace(/\/$/, "");
    if (API_BASE_URL) {
      localStorage.setItem("AI_SEO_API_BASE_URL", API_BASE_URL);
      toast("Backend API URL saved.");
    } else {
      localStorage.removeItem("AI_SEO_API_BASE_URL");
      toast("Backend API URL cleared.");
    }
  });
}

qsa(".upload-card").forEach((card) => {
  const input = card.querySelector("input[type='file']");
  const status = card.querySelector(".upload-status");

  input.addEventListener("change", () => {
    const files = [...input.files];
    if (files.length) {
      const rows = files.map((file) => file.name).slice(0, 2).join(", ");
      status.textContent = files.length > 2 ? `${rows} + ${files.length - 2} more selected` : `${rows} selected`;
    }
  });

  card.querySelector(".upload-button").addEventListener("click", () => uploadCard(card));
  ["dragenter", "dragover"].forEach((eventName) => {
    card.addEventListener(eventName, (event) => {
      event.preventDefault();
      card.classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    card.addEventListener(eventName, () => card.classList.remove("dragging"));
  });
  card.addEventListener("drop", (event) => {
    event.preventDefault();
    input.files = event.dataTransfer.files;
    input.dispatchEvent(new Event("change"));
  });
});

qs("#modelSelect").addEventListener("change", () => {
  qs("#customModelWrap").classList.toggle("hidden", qs("#modelSelect").value !== "custom");
});

qs("#runAnalyze").addEventListener("click", analyze);
qs("#runAnalyzeTop").addEventListener("click", analyze);
qs("#issueFilter").addEventListener("change", renderDashboard);
qs("#resetButton").addEventListener("click", resetWorkspace);
qs("#downloadReport").addEventListener("click", () => download("/report", "seo_copilot_report.pdf"));
qs("#downloadReportSide").addEventListener("click", () => download("/report", "seo_copilot_report.pdf"));
qs("#downloadJson").addEventListener("click", () => download("/export?format=json", "seo_tasks.json"));
qs("#downloadCsv").addEventListener("click", () => download("/export?format=csv", "seo_tasks.csv"));

loadResults();
