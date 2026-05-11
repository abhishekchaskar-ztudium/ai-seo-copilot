import type { Config, Context } from "@netlify/functions";
import { getStore } from "@netlify/blobs";

type DatasetType = "organic_keywords" | "top_pages" | "backlinks" | "broken_backlinks" | "competitors";
type Row = Record<string, string>;
type Workspace = {
  datasets: Partial<Record<DatasetType, Row[]>>;
  uploads: Array<{ dataset_type: DatasetType; filename: string; rows: number; columns: string[] }>;
  results: Task[];
};
type Issue = {
  type: string;
  url: string;
  keyword: string;
  evidence: string;
  evidence_values: Record<string, string | number>;
  source_dataset: DatasetType;
  priority_score: number;
  confidence_score: number;
};
type Task = {
  page: string;
  keyword: string;
  issue: string;
  evidence: string;
  ai_explanation: string;
  actions: string[];
  generated_content: { titles: string[]; meta_descriptions: string[]; headings: string[]; faqs: string[] };
  priority_score: number;
  confidence_score: number;
  validation_status: string;
};

const DATASET_TYPES = new Set(["organic_keywords", "top_pages", "backlinks", "broken_backlinks", "competitors"]);
const HIGH_IMPRESSIONS_THRESHOLD = 1000;
const LOW_CTR_THRESHOLD = 2;
const TRAFFIC_DROP_PERCENT_THRESHOLD = 20;
const WORKSPACE_KEY = "default-workspace";
const BASE_PRIORITY: Record<string, number> = {
  "Ranking Opportunity": 72,
  "CTR Issue": 68,
  "Traffic Drop": 82,
  "Link Reclamation Opportunity": 64,
  "Competitor Gap": 76,
  "Competitor Opportunity": 70,
};
const COLUMN_ALIASES: Record<string, string[]> = {
  url: ["url", "page", "target url", "target", "landing page", "page url"],
  source_url: ["source url", "referring page", "referring page url", "backlink url"],
  keyword: ["keyword", "query", "search query"],
  position: ["position", "current position", "rank", "ranking position"],
  previous_position: ["previous position", "prev position", "old position"],
  impressions: ["impressions", "search volume", "volume"],
  clicks: ["clicks"],
  ctr: ["ctr", "click through rate", "click-through rate"],
  traffic: ["traffic", "organic traffic", "current traffic"],
  previous_traffic: ["previous traffic", "traffic previous", "prev traffic"],
  competitor: ["competitor", "competitor domain", "competing domain", "domain", "site", "root domain"],
  common_keywords: ["common keywords", "common keyword", "intersecting keywords"],
  unique_keywords: ["unique keywords", "unique keyword", "competitor unique keywords"],
  organic_pages: ["organic pages", "pages"],
  status: ["status", "http status", "link status"],
};

export default async (req: Request, context: Context) => {
  const path = new URL(req.url).pathname;
  try {
    if (path === "/health") return json({ status: "ok" });
    if (path === "/upload-csv" && req.method === "POST") return uploadCsv(req);
    if (path === "/analyze" && req.method === "POST") return analyze(req);
    if (path === "/results" && req.method === "GET") return results(req);
    if (path === "/export" && req.method === "GET") return exportTasks(req);
    if (path === "/report-preview" && req.method === "GET") return reportPreview();
    if (path === "/report" && req.method === "GET") return reportPdf();
    if (path === "/reset" && req.method === "DELETE") return reset();
    return json({ detail: "Not found" }, 404);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unexpected server error";
    return json({ detail: message }, 400);
  }
};

export const config: Config = {
  path: ["/upload-csv", "/analyze", "/results", "/export", "/report", "/report-preview", "/reset", "/health"],
};

async function uploadCsv(req: Request) {
  const form = await req.formData();
  const datasetType = String(form.get("dataset_type") || "") as DatasetType;
  if (!DATASET_TYPES.has(datasetType)) throw new Error("Invalid dataset_type.");
  const files = form.getAll("files").filter((item): item is File => item instanceof File);
  if (!files.length) throw new Error("Choose at least one CSV file.");

  const workspace = await loadWorkspace();
  const summaries = [];
  for (const file of files) {
    if (!file.name.toLowerCase().endsWith(".csv")) throw new Error(`${file.name} is not a CSV file.`);
    const rows = parseCsv(await file.text());
    validateDataset(datasetType, rows);
    workspace.datasets[datasetType] = [...(workspace.datasets[datasetType] || []), ...rows];
    const summary = {
      dataset_type: datasetType,
      filename: file.name,
      rows: rows.length,
      columns: Object.keys(rows[0] || {}),
    };
    summaries.push(summary);
    workspace.uploads.push(summary);
  }
  await saveWorkspace(workspace);
  return json(summaries);
}

async function analyze(req: Request) {
  const body = await safeJson(req);
  const workspace = body?.datasets
    ? { datasets: body.datasets as Workspace["datasets"], uploads: [], results: [] }
    : await loadWorkspace();
  if (!Object.keys(workspace.datasets).length) throw new Error("Upload at least one Ahrefs CSV before analysis.");
  const issues = runRuleEngine(workspace.datasets).sort((a, b) => b.priority_score - a.priority_score);
  workspace.results = issues.map((issue) => validateIssue(issue, localFallback(issue)));
  await saveWorkspace(workspace);
  return json(workspace.results);
}

async function results(req: Request) {
  const workspace = await loadWorkspace();
  const issueType = new URL(req.url).searchParams.get("issue_type");
  const tasks = issueType ? workspace.results.filter((task) => task.issue === issueType) : workspace.results;
  return json(tasks);
}

async function exportTasks(req: Request) {
  const workspace = await loadWorkspace();
  const format = new URL(req.url).searchParams.get("format") || "json";
  if (format === "csv") {
    return new Response(tasksToCsv(workspace.results), {
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename=seo_tasks.csv",
      },
    });
  }
  return new Response(JSON.stringify(workspace.results, null, 2), {
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": "attachment; filename=seo_tasks.json",
    },
  });
}

async function reportPreview() {
  const workspace = await loadWorkspace();
  return new Response(buildMarkdownReport(workspace.results), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

async function reportPdf() {
  const workspace = await loadWorkspace();
  return new Response(buildPdfReport(workspace.results), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": "attachment; filename=seo_copilot_report.pdf",
    },
  });
}

async function reset() {
  await saveWorkspace({ datasets: {}, uploads: [], results: [] });
  return json({ status: "reset" });
}

function getWorkspaceStore() {
  return getStore("seo-copilot", { consistency: "strong" });
}

async function loadWorkspace(): Promise<Workspace> {
  return (await getWorkspaceStore().get(WORKSPACE_KEY, { type: "json" })) || { datasets: {}, uploads: [], results: [] };
}

async function saveWorkspace(workspace: Workspace) {
  await getWorkspaceStore().setJSON(WORKSPACE_KEY, workspace);
}

function parseCsv(text: string): Row[] {
  const rows = splitCsv(text.replace(/^\uFEFF/, ""));
  if (rows.length < 2) throw new Error("CSV has no rows.");
  const headers = rows[0].map((header) => aliasColumn(normalizeColumn(header)));
  return rows
    .slice(1)
    .filter((row) => row.some((value) => value.trim()))
    .map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index] || ""])));
}

function splitCsv(text: string): string[][] {
  const delimiter = detectDelimiter(text);
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (char === '"' && quoted && next === '"') {
      field += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === delimiter && !quoted) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1;
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

function detectDelimiter(text: string) {
  const firstLine = text.split(/\r?\n/, 1)[0] || "";
  return ["\t", ";", ","].sort((a, b) => firstLine.split(b).length - firstLine.split(a).length)[0];
}

function normalizeColumn(column: string) {
  return column.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function aliasColumn(column: string) {
  for (const [canonical, aliases] of Object.entries(COLUMN_ALIASES)) {
    if (aliases.map(normalizeColumn).includes(column)) return canonical;
  }
  return column;
}

function validateDataset(datasetType: DatasetType, rows: Row[]) {
  const columns = new Set(Object.keys(rows[0] || {}));
  if (datasetType === "organic_keywords" && !columns.has("keyword")) throw new Error("organic_keywords CSV is missing required columns: keyword");
  if (datasetType === "top_pages" && !columns.has("url")) throw new Error("top_pages CSV is missing required columns: url");
  if (datasetType === "competitors" && !columns.has("keyword") && !columns.has("competitor")) {
    throw new Error("competitors CSV needs either a keyword column or a competitor/domain column.");
  }
}

function runRuleEngine(datasets: Workspace["datasets"]) {
  return [
    ...keywordOpportunities(datasets.organic_keywords),
    ...lowCtrIssues(datasets.organic_keywords),
    ...trafficDrops(datasets.organic_keywords, "organic_keywords"),
    ...trafficDrops(datasets.top_pages, "top_pages"),
    ...brokenBacklinks(datasets.broken_backlinks),
    ...competitorIssues(datasets.competitors, datasets.organic_keywords),
  ];
}

function keywordOpportunities(rows: Row[] = []) {
  return rows
    .filter((row) => number(row.position) > 5 && number(row.position) <= 20)
    .map((row) => {
      const position = number(row.position);
      return issue("Ranking Opportunity", row.url, row.keyword, `Keyword '${row.keyword}' ranks at position ${position}, which is between 6 and 20.`, row, "organic_keywords", 21 - position, 4);
    });
}

function lowCtrIssues(rows: Row[] = []) {
  return rows
    .filter((row) => number(row.impressions) >= HIGH_IMPRESSIONS_THRESHOLD && number(row.ctr) < LOW_CTR_THRESHOLD)
    .map((row) => issue("CTR Issue", row.url, row.keyword, `Keyword '${row.keyword}' has ${number(row.impressions)} impressions and CTR ${number(row.ctr)}%, below the ${LOW_CTR_THRESHOLD}% threshold.`, row, "organic_keywords", Math.min(25, number(row.impressions) / 1000), 3));
}

function trafficDrops(rows: Row[] = [], sourceDataset: DatasetType) {
  return rows
    .filter((row) => row.traffic !== undefined && row.previous_traffic !== undefined)
    .map((row) => ({ row, drop: ((number(row.previous_traffic) - number(row.traffic)) / Math.max(number(row.previous_traffic), 1)) * 100 }))
    .filter(({ drop }) => drop >= TRAFFIC_DROP_PERCENT_THRESHOLD)
    .map(({ row, drop }) => {
      const subject = row.url || row.keyword || "uploaded row";
      return issue("Traffic Drop", row.url, row.keyword, `${subject} traffic declined from ${number(row.previous_traffic)} to ${number(row.traffic)} (${drop.toFixed(1)}% drop).`, row, sourceDataset, Math.min(25, drop / 2), 5);
    });
}

function brokenBacklinks(rows: Row[] = []) {
  return rows
    .filter((row) => !row.status || /broken|404|not found|lost/i.test(row.status))
    .map((row) => issue("Link Reclamation Opportunity", row.url, "", `Broken backlink found from '${row.source_url || "unknown source"}' to '${row.url || "unknown target"}' with status '${row.status || "broken backlink export"}'.`, row, "broken_backlinks", 10, 3));
}

function competitorIssues(rows: Row[] = [], organicRows: Row[] = []) {
  if (!rows.length) return [];
  if (!("keyword" in rows[0])) {
    return rows.filter((row) => row.competitor).map((row) => {
      const metrics = [
        number(row.traffic) ? `organic traffic ${number(row.traffic)}` : "",
        number(row.common_keywords) ? `${number(row.common_keywords)} common keywords` : "",
        number(row.unique_keywords) ? `${number(row.unique_keywords)} unique keywords` : "",
        number(row.organic_pages) ? `${number(row.organic_pages)} organic pages` : "",
      ].filter(Boolean).join(", ") || "domain-level competitor metrics";
      const impact = Math.min(25, number(row.traffic) / 1000 + number(row.unique_keywords) / 100 + number(row.common_keywords) / 250);
      return issue("Competitor Opportunity", "", row.competitor, `Organic competitor '${row.competitor}' appears in the uploaded competitor export with ${metrics}.`, row, "competitors", impact, 6);
    });
  }
  const ownKeywords = new Set(organicRows.map((row) => String(row.keyword || "").trim().toLowerCase()).filter(Boolean));
  return rows
    .filter((row) => row.keyword && !ownKeywords.has(row.keyword.trim().toLowerCase()))
    .map((row) => issue("Competitor Gap", "", row.keyword, `Competitor '${row.competitor || "unknown competitor"}' ranks for keyword '${row.keyword}'${row.position ? ` at position ${row.position}` : ""}, but the site export does not include it.`, row, "competitors", 12, 6));
}

function issue(type: string, url = "", keyword = "", evidence: string, row: Row, sourceDataset: DatasetType, impact: number, effort: number): Issue {
  return {
    type,
    url: url || "",
    keyword: keyword || "",
    evidence,
    evidence_values: row,
    source_dataset: sourceDataset,
    priority_score: priorityFor(type, impact, effort),
    confidence_score: confidenceFor(Boolean(url), Object.keys(row).length),
  };
}

function priorityFor(type: string, impact = 0, effort = 3) {
  return Math.max(0, Math.min(100, Math.round((BASE_PRIORITY[type] || 50) + Math.min(Math.max(impact, 0), 25) - Math.min(Math.max(effort, 1), 10) * 2)));
}

function confidenceFor(hasUrl: boolean, evidenceCount: number) {
  return Number(Math.max(0.1, Math.min(0.98, 0.55 + Math.min(evidenceCount, 4) * 0.08 + (hasUrl ? 0.07 : 0))).toFixed(2));
}

function number(value: string | undefined) {
  return Number(String(value || "0").replace(/[%,$,\s]/g, "")) || 0;
}

function localFallback(issueData: Issue) {
  const keyword = issueData.keyword || issueData.evidence_values.keyword || "insufficient data";
  return {
    explanation: `${issueData.type} detected. Evidence: ${issueData.evidence}`,
    actions: actionsFor(issueData.type),
    generated_content: {
      titles: keyword === "insufficient data" ? [] : [`${keyword}: Practical Guide`],
      meta_descriptions: keyword === "insufficient data" ? [] : [`Learn about ${keyword} with a focused guide based on verified site data.`],
      headings: keyword === "insufficient data" ? [] : [`What to Know About ${keyword}`, `How to Improve Results for ${keyword}`],
      faqs: keyword === "insufficient data" ? [] : [`What is the best next step for ${keyword}?`],
    },
  };
}

function actionsFor(type: string) {
  const map: Record<string, string[]> = {
    "Ranking Opportunity": ["Review the page content against the supplied keyword.", "Improve title, headings, and on-page coverage using only the uploaded keyword evidence.", "Add internal links to the page from relevant existing pages."],
    "CTR Issue": ["Rewrite the title and meta description to better match the supplied keyword intent.", "Check whether the SERP snippet promises a clearer benefit for the provided keyword."],
    "Traffic Drop": ["Compare the affected page or keyword with the previous known traffic value in the export.", "Refresh outdated content and verify technical indexability for the affected page."],
    "Link Reclamation Opportunity": ["Contact the referring site with the supplied broken backlink source and target.", "Restore the target page or add a relevant redirect if the destination moved."],
    "Competitor Gap": ["Create or improve content targeting the supplied competitor keyword.", "Analyze the competitor URL from the upload before drafting final content."],
    "Competitor Opportunity": ["Review the competitor domain and compare its strongest topics against your current content.", "Prioritize content gaps, internal links, and page updates where the competitor has the clearest advantage."],
  };
  return map[type] || ["Review the supplied evidence and decide the next SEO action."];
}

function validateIssue(issueData: Issue, output: ReturnType<typeof localFallback>): Task {
  return {
    page: issueData.url || "insufficient data",
    keyword: issueData.keyword,
    issue: issueData.type,
    evidence: issueData.evidence,
    ai_explanation: output.explanation,
    actions: output.actions,
    generated_content: output.generated_content,
    priority_score: issueData.priority_score,
    confidence_score: issueData.confidence_score,
    validation_status: "validated",
  };
}

function buildMarkdownReport(tasks: Task[]) {
  if (!tasks.length) return "# AI SEO Copilot Report\n\nNo SEO tasks have been generated yet.\n";
  const sorted = [...tasks].sort((a, b) => b.priority_score - a.priority_score);
  const counts = countBy(sorted, (task) => task.issue);
  const lines = [
    "# AI SEO Copilot Report", "",
    "## Executive Summary", "",
    `- Total tasks found: ${sorted.length}`,
    `- Issue categories: ${Object.keys(counts).length}`,
    `- Average priority: ${average(sorted.map((task) => task.priority_score))}`,
    `- Average confidence: ${average(sorted.map((task) => task.confidence_score))}`, "",
    "## Top Tasks", "",
  ];
  sorted.slice(0, 30).forEach((task, index) => lines.push(`${index + 1}. ${task.issue} - Priority ${task.priority_score}`, `   - Page: ${task.page}${task.keyword ? ` | ${task.keyword}` : ""}`, `   - Evidence: ${task.evidence}`, `   - Do first: ${task.actions[0] || "Review evidence."}`, ""));
  lines.push("## Compact Task Inventory", "", "| # | Issue | Page / Keyword | Priority | First action |", "|---:|---|---|---:|---|");
  sorted.slice(0, 250).forEach((task, index) => lines.push(`| ${index + 1} | ${md(task.issue)} | ${md(task.page + (task.keyword ? ` / ${task.keyword}` : ""))} | ${task.priority_score} | ${md(task.actions[0] || "Review evidence.")} |`));
  if (sorted.length > 250) lines.push("", `Note: ${sorted.length - 250} additional task(s) are available in JSON/CSV export.`);
  return `${lines.join("\n")}\n`;
}

function buildPdfReport(tasks: Task[]) {
  const text = buildMarkdownReport(tasks).split("\n").slice(0, 950);
  const pages: string[][] = [];
  for (let i = 0; i < text.length; i += 44) pages.push(text.slice(i, i + 44));
  return pdfFromPages(pages.slice(0, 30));
}

function pdfFromPages(pages: string[][]) {
  const streams = pages.map((lines, pageIndex) => {
    const commands = ["BT /F1 10 Tf 44 746 Td"];
    lines.forEach((line, index) => commands.push(`${index ? "0 -15 Td " : ""}(${pdfEscape(line.slice(0, 110))}) Tj`));
    commands.push(`0 -25 Td (Page ${pageIndex + 1}) Tj ET`);
    return commands.join("\n");
  });
  const objects: string[] = ["<< /Type /Catalog /Pages 2 0 R >>"];
  const pageNums = streams.map((_, index) => 3 + index * 2);
  objects.push(`<< /Type /Pages /Kids [${pageNums.map((num) => `${num} 0 R`).join(" ")}] /Count ${streams.length} >>`);
  streams.forEach((stream, index) => {
    const pageObj = pageNums[index];
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents ${pageObj + 1} 0 R >>`);
    objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
  });
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  offsets.slice(1).forEach((offset) => { pdf += `${String(offset).padStart(10, "0")} 00000 n \n`; });
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return new TextEncoder().encode(pdf);
}

function tasksToCsv(tasks: Task[]) {
  const rows = [["issue", "page", "keyword", "priority_score", "confidence_score", "evidence", "actions"]];
  tasks.forEach((task) => rows.push([task.issue, task.page, task.keyword, String(task.priority_score), String(task.confidence_score), task.evidence, task.actions.join(" | ")]));
  return rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\n");
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

async function safeJson(req: Request) {
  try {
    return await req.json();
  } catch {
    return null;
  }
}

function countBy<T>(items: T[], getKey: (item: T) => string) {
  return items.reduce<Record<string, number>>((counts, item) => {
    const key = getKey(item);
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
}

function average(values: number[]) {
  return values.length ? Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(2)) : 0;
}

function md(value: string) {
  return value.replace(/\|/g, "/").replace(/\n/g, " ").trim();
}

function pdfEscape(value: string) {
  return value.replace(/[^\x20-\x7E]/g, "?").replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");
}
