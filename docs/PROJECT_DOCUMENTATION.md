# AI SEO Copilot Project Documentation

## 1. Project Overview

AI SEO Copilot is a web application that turns Ahrefs-style CSV exports into a prioritized SEO action plan.

The project has three major jobs:

1. Accept SEO datasets such as organic keywords, top pages, broken backlinks, and competitors.
2. Apply deterministic SEO rules to detect issues and calculate priority and confidence scores.
3. Optionally use Gemini to explain each issue, suggest actions, and generate SEO content ideas.

The system is intentionally hybrid:

- The rule engine decides what is true from uploaded data.
- The scoring module calculates priority and confidence.
- Gemini only enriches already-detected issues.
- Validation strips unverifiable AI output before returning final tasks.

## 2. Live Deployment

Frontend:

```text
https://ai-seo-copilot.netlify.app
```

Backend:

```text
https://ai-seo-copilot-backend.onrender.com
```

Health check:

```text
https://ai-seo-copilot-backend.onrender.com/health
```

Expected response:

```json
{"status":"ok"}
```

## 3. Project Structure

```text
backend/
  main.py                     FastAPI app, CORS, static frontend mounting, health route
  routes/
    seo.py                    API endpoints for upload, analysis, results, exports, reports, reset
  services/
    ai_engine.py              Gemini integration, local fallback enrichment, AI response cache
    models.py                 Pydantic data models
    parser.py                 CSV parsing, encoding fallback, column aliases, dataset validation
    prompts.py                Gemini system/user prompts
    report.py                 Markdown and PDF report generation
    rule_engine.py            Deterministic SEO issue detection rules
    scoring.py                Priority and confidence score formulas
    storage.py                In-memory backend state
    validation.py             AI output validation and evidence checks

frontend/
  index.html                  Static app shell
  static/
    app.js                    Browser workflow, upload, API calls, dashboard rendering
    config.js                 Hosted API base URL
    styles.css                UI styling

docs/
  README.md                   Documentation index
  PROJECT_DOCUMENTATION.md    Full technical and functional documentation
  BOSS_PROJECT_BRIEF.md       Short project brief
  sample_prompts.md           Gemini prompt reference

netlify/
  functions/
    api.mts                   Netlify Function support

render.yaml                   Render Blueprint for the FastAPI backend
netlify.toml                  Netlify frontend publish and function config
requirements.txt              Python dependencies
package.json                  Node/Netlify dependencies
README.md                     Main project README
```

## 4. Application Flow

1. User opens the Netlify frontend.
2. Frontend loads `frontend/static/config.js`.
3. `API_BASE_URL` points browser requests to the Render backend.
4. User uploads Ahrefs CSV exports in the matching upload cards.
5. Browser parses CSV rows locally for the analysis payload and also sends uploads to the backend.
6. Backend parses and validates uploaded CSV files.
7. User clicks Analyze.
8. Backend runs `run_rule_engine()` across uploaded datasets.
9. Issues are sorted by `priority_score` from highest to lowest.
10. Top issues can be enriched with Gemini, limited by `GEMINI_ENRICHMENT_LIMIT`.
11. If Gemini is unavailable or not configured, local fallback enrichment is used.
12. `validate_ai_output()` converts each issue into a final task.
13. Frontend renders KPIs, issue distribution, top tasks, task table, and report preview.
14. User can export JSON, CSV, or PDF.

## 5. Supported Dataset Types

The backend accepts these dataset types:

| Dataset type | Purpose |
|---|---|
| `organic_keywords` | Ranking, CTR, keyword, and traffic analysis |
| `top_pages` | Page-level traffic drop analysis |
| `backlinks` | Accepted for workspace context and future expansion |
| `broken_backlinks` | Link reclamation opportunities |
| `competitors` | Competitor keyword gaps or domain-level competitor opportunities |

## 6. CSV Parsing and Column Normalization

CSV parsing is handled in `backend/services/parser.py`.

The parser:

- Accepts UTF-8, UTF-16, UTF-16 LE/BE, cp1252, and latin1 encodings.
- Accepts comma, tab, and semicolon separators.
- Drops fully empty rows.
- Normalizes column names to lowercase snake case.
- Applies common Ahrefs-style column aliases.

Examples of accepted aliases:

| Canonical column | Accepted examples |
|---|---|
| `url` | `url`, `page`, `target url`, `target`, `landing page`, `page url` |
| `source_url` | `source url`, `referring page`, `referring page url`, `backlink url` |
| `keyword` | `keyword`, `query`, `search query` |
| `position` | `position`, `current position`, `rank`, `ranking position` |
| `impressions` | `impressions`, `search volume`, `volume` |
| `ctr` | `ctr`, `click through rate`, `click-through rate` |
| `traffic` | `traffic`, `organic traffic`, `current traffic` |
| `previous_traffic` | `previous traffic`, `traffic previous`, `prev traffic` |
| `competitor` | `competitor`, `competitor domain`, `competing domain`, `domain`, `site`, `root domain` |
| `status` | `status`, `http status`, `link status` |

Numeric fields are cleaned with `to_number()`:

- Percent signs are removed.
- Commas are removed.
- Whitespace is trimmed.
- Invalid values become `0`.

## 7. Dataset Validation

Validation rules:

| Dataset type | Required columns |
|---|---|
| `organic_keywords` | `keyword` |
| `top_pages` | `url` |
| `backlinks` | None |
| `broken_backlinks` | None |
| `competitors` | Must contain either `keyword` or `competitor` |

Competitor uploads support two formats:

- Keyword/content-gap export: contains `keyword`.
- Domain-level organic competitors export: contains `competitor` or a matching alias such as `domain`.

## 8. Rule Engine Summary

All deterministic SEO issue detection lives in `backend/services/rule_engine.py`.

The system currently detects:

| Issue type | Source dataset | Rule |
|---|---|---|
| Ranking Opportunity | `organic_keywords` | Position is greater than 5 and less than or equal to 20 |
| CTR Issue | `organic_keywords` | Impressions are at least 1000 and CTR is below 2 percent |
| Traffic Drop | `organic_keywords`, `top_pages` | Traffic declined by at least 20 percent |
| Link Reclamation Opportunity | `broken_backlinks` | Status contains broken, 404, not found, or lost; if no status exists, every row is treated as a broken backlink export row |
| Competitor Gap | `competitors` plus `organic_keywords` | Competitor keyword is not present in the site's uploaded organic keyword list |
| Competitor Opportunity | `competitors` | Domain-level competitor row with competitor/domain metrics |

## 9. Rule Details

### 9.1 Ranking Opportunity

Function:

```text
_keyword_opportunities()
```

Applies when:

```text
position > 5 and position <= 20
```

Meaning:

The keyword is close enough to page one or low page one that content, internal linking, or on-page optimization may improve visibility.

Evidence captured:

- `keyword`
- `url`
- `position`

Impact used for scoring:

```text
impact = max(0, 21 - position)
```

Effort used for scoring:

```text
effort = 4
```

Example:

If a keyword ranks at position 8:

```text
impact = 21 - 8 = 13
```

### 9.2 CTR Issue

Function:

```text
_low_ctr_issues()
```

Constants:

```text
HIGH_IMPRESSIONS_THRESHOLD = 1000
LOW_CTR_THRESHOLD = 2.0
```

Applies when:

```text
impressions >= 1000 and ctr < 2.0
```

Meaning:

The page/keyword is getting enough visibility but not enough clicks. This usually points to title, meta description, intent mismatch, or SERP presentation issues.

Evidence captured:

- `keyword`
- `url`
- `impressions`
- `ctr`

Impact used for scoring:

```text
impact = min(25, impressions / 1000)
```

Effort used for scoring:

```text
effort = 3
```

Example:

If impressions are 15,000:

```text
impact = min(25, 15000 / 1000)
impact = 15
```

### 9.3 Traffic Drop

Function:

```text
_traffic_drops()
```

Constant:

```text
TRAFFIC_DROP_PERCENT_THRESHOLD = 20.0
```

Applies when:

```text
((previous_traffic - traffic) / previous_traffic) * 100 >= 20
```

Meaning:

A page or keyword has lost a meaningful share of traffic compared with the previous value in the export.

Evidence captured:

- `keyword`
- `url`
- `previous_traffic`
- `traffic`
- `drop_percent`

Impact used for scoring:

```text
impact = min(25, drop_percent / 2)
```

Effort used for scoring:

```text
effort = 5
```

Example:

If traffic dropped by 50 percent:

```text
impact = min(25, 50 / 2)
impact = 25
```

### 9.4 Link Reclamation Opportunity

Function:

```text
_broken_backlinks()
```

Applies when:

```text
status contains broken, 404, not found, or lost
```

If the uploaded broken backlinks file has no `status` column, every row is considered part of the broken backlink export.

Meaning:

The site may be losing link equity because external links point to broken or missing targets.

Evidence captured:

- `url`
- `source_url`
- `status`

Impact used for scoring:

```text
impact = 10
```

Effort used for scoring:

```text
effort = 3
```

Source quality used for confidence:

```text
source_quality = 0.92
```

### 9.5 Competitor Gap

Function:

```text
_competitor_gaps()
```

Applies when:

```text
competitors CSV has a keyword column
and competitor keyword is not in organic_keywords keyword list
```

Meaning:

A competitor ranks for a keyword that the uploaded site keyword export does not include.

Evidence captured:

- `keyword`
- `competitor`
- `competitor_url`
- `position`

Impact used for scoring:

```text
impact = 12
```

Effort used for scoring:

```text
effort = 6
```

Source quality used for confidence:

```text
source_quality = 0.9
```

### 9.6 Competitor Opportunity

Function:

```text
_competitor_domain_opportunities()
```

Applies when:

```text
competitors CSV has no keyword column but has a competitor/domain column
```

Meaning:

The row identifies a domain-level organic competitor worth reviewing for topic, content, and link opportunities.

Evidence captured:

- `competitor`
- `traffic`
- `common_keywords`
- `unique_keywords`
- `organic_pages`

Impact used for scoring:

```text
impact = min(25, (traffic / 1000) + (unique_keywords / 100) + (common_keywords / 250))
```

Effort used for scoring:

```text
effort = 6
```

Source quality used for confidence:

```text
source_quality = 0.88
```

## 10. Priority Score Formula

Priority scoring lives in `backend/services/scoring.py`.

Each issue type has a base priority:

| Issue type | Base priority |
|---|---:|
| Ranking Opportunity | 72 |
| CTR Issue | 68 |
| Traffic Drop | 82 |
| Link Reclamation Opportunity | 64 |
| Competitor Gap | 76 |
| Competitor Opportunity | 70 |
| Unknown issue type fallback | 50 |

Formula:

```text
priority = base_priority + impact_boost - effort_penalty
```

Where:

```text
impact_boost = clamp(impact, minimum=0, maximum=25)
effort_penalty = clamp(effort, minimum=1, maximum=10) * 2
priority = clamp(priority, minimum=0, maximum=100)
```

Returned value:

```text
integer from 0 to 100
```

Interpretation:

| Score range | Meaning |
|---|---|
| 80-100 | High priority, should be reviewed first |
| 60-79 | Medium priority, useful sprint work |
| 0-59 | Lower priority or backlog item |

### Priority Examples

Ranking Opportunity at position 8:

```text
base = 72
impact = 21 - 8 = 13
effort = 4
effort_penalty = 4 * 2 = 8
priority = 72 + 13 - 8 = 77
```

Traffic Drop with 50 percent drop:

```text
base = 82
impact = min(25, 50 / 2) = 25
effort = 5
effort_penalty = 5 * 2 = 10
priority = 82 + 25 - 10 = 97
```

CTR Issue with 5,000 impressions:

```text
base = 68
impact = min(25, 5000 / 1000) = 5
effort = 3
effort_penalty = 3 * 2 = 6
priority = 68 + 5 - 6 = 67
```

## 11. Confidence Score Formula

Confidence scoring also lives in `backend/services/scoring.py`.

Formula:

```text
confidence = 0.55 + min(evidence_count, 4) * 0.08 + url_bonus
confidence = confidence * source_quality
confidence = clamp(confidence, minimum=0.1, maximum=0.98)
```

Where:

```text
url_bonus = 0.07 if the issue has a URL, otherwise 0
source_quality = 1.0 by default
```

Returned value:

```text
decimal from 0.10 to 0.98, rounded to 2 decimals
```

Interpretation:

| Factor | Effect |
|---|---|
| More evidence fields | Higher confidence, capped at 4 evidence fields |
| Known URL | Adds 0.07 |
| Lower source quality | Multiplies score down |
| Missing URL | No URL bonus |

### Confidence Examples

Issue with URL and 3 evidence fields:

```text
confidence = 0.55 + (3 * 0.08) + 0.07
confidence = 0.86
```

Competitor Gap with no URL, 4 evidence fields, and source quality 0.9:

```text
raw = 0.55 + (4 * 0.08)
raw = 0.87
confidence = 0.87 * 0.9
confidence = 0.78
```

Link Reclamation Opportunity with URL, 3 evidence fields, and source quality 0.92:

```text
raw = 0.55 + (3 * 0.08) + 0.07
raw = 0.86
confidence = 0.86 * 0.92
confidence = 0.79
```

## 12. AI Enrichment

AI enrichment is handled in `backend/services/ai_engine.py`.

Supported provider:

```text
Gemini
```

Environment variables:

| Variable | Purpose |
|---|---|
| `AI_PROVIDER` | Defaults to `gemini` |
| `GEMINI_API_KEY` | Gemini API key |
| `GOOGLE_API_KEY` | Alternative Gemini API key name |
| `GEMINI_MODEL` | Defaults to `gemini-2.5-flash` |
| `GEMINI_ENRICHMENT_LIMIT` | Number of top-priority issues to send to Gemini, defaults to 25 in Render config |

The frontend also allows the user to paste a Gemini API key and choose a model for the current analysis request.

Gemini receives:

- Issue type
- URL or insufficient data
- Keyword or insufficient data
- Evidence text
- Evidence values as JSON

Gemini is expected to return:

- Explanation
- Recommended actions
- Generated titles
- Generated meta descriptions
- Generated headings
- FAQs

## 13. Local Fallback Enrichment

If Gemini is not configured, or if enrichment is skipped after the limit, the backend uses deterministic fallback text.

Fallback output includes:

- A short explanation based on issue evidence.
- Issue-specific recommended actions.
- Basic generated content if a keyword exists.

This means the app can still produce a complete report without a Gemini key.

## 14. AI Validation and Safety

Validation is handled in `backend/services/validation.py`.

The validator:

- Rejects issues with empty evidence.
- Converts AI output into a final `Task`.
- Marks tasks as `validated`.
- Marks tasks as `validated_with_insufficient_data` if the explanation contains "insufficient data".
- Removes generated content that appears to reference unverifiable external URLs, metrics, or claims.
- Replaces suspicious explanations with `insufficient data`.

Suspicious phrases checked include:

```text
according to
industry average
google says
search volume is
```

Important design rule:

The AI layer does not create new facts. It can only explain or act on facts that came from uploaded evidence.

## 15. Final Task Schema

Each final task contains:

| Field | Meaning |
|---|---|
| `page` | URL or `insufficient data` |
| `keyword` | Keyword if available |
| `issue` | Issue type |
| `evidence` | Human-readable rule evidence |
| `ai_explanation` | Gemini or fallback explanation |
| `actions` | Recommended action checklist |
| `generated_content` | Titles, meta descriptions, headings, FAQs |
| `priority_score` | 0 to 100 |
| `confidence_score` | 0 to 1 |
| `validation_status` | `validated` or `validated_with_insufficient_data` |

## 16. API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Serves frontend when backend is running locally |
| `GET` | `/health` | Health check |
| `POST` | `/upload-csv` | Upload one or more CSV files for a dataset type |
| `POST` | `/analyze` | Run rules, enrich tasks, validate output |
| `GET` | `/results` | Return current tasks |
| `GET` | `/results?issue_type=CTR Issue` | Return tasks filtered by issue type |
| `GET` | `/export?format=json` | Download tasks as JSON |
| `GET` | `/export?format=csv` | Download tasks as CSV |
| `GET` | `/report` | Download PDF report |
| `GET` | `/report-preview` | Get markdown/text report preview |
| `DELETE` | `/reset` | Clear in-memory uploads and results |

## 17. Reports and Exports

Reports are generated in `backend/services/report.py`.

Available outputs:

- JSON export: raw task objects.
- CSV export: flattened task table.
- Markdown/text preview: in-app report preview.
- PDF report: formatted SEO action document.

The report includes:

- Executive summary.
- Total task count.
- Issue category count.
- Average priority.
- Average confidence.
- Issue breakdown.
- Action playbook by issue.
- Highest priority tasks.
- Execution work plan.
- Compact task inventory.

## 18. Frontend Behavior

The frontend is a static app in `frontend/`.

Important frontend files:

| File | Purpose |
|---|---|
| `frontend/index.html` | Main app markup |
| `frontend/static/app.js` | Upload flow, analysis calls, dashboard rendering, exports |
| `frontend/static/config.js` | API backend URL |
| `frontend/static/styles.css` | Styling |

The production config is:

```js
window.APP_CONFIG = {
  API_BASE_URL: "https://ai-seo-copilot-backend.onrender.com",
};
```

The app also lets users override the backend URL through the "Backend API URL" field. That value is stored in browser `localStorage` as:

```text
AI_SEO_API_BASE_URL
```

## 19. Render Deployment

Render is configured by `render.yaml`.

Current service:

```yaml
services:
  - type: web
    name: ai-seo-copilot-backend
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
```

Important environment variables:

```text
PYTHON_VERSION=3.12.7
ALLOWED_ORIGINS=https://ai-seo-copilot.netlify.app,http://localhost:8000,http://127.0.0.1:8000
GEMINI_ENRICHMENT_LIMIT=25
```

For production Gemini enrichment, add one of:

```text
GEMINI_API_KEY
GOOGLE_API_KEY
```

Render-specific requirements:

- The app must bind to `0.0.0.0`.
- The app must use Render's `$PORT`.
- `/health` must return a successful response.
- CORS must include the Netlify frontend origin.

## 20. Netlify Deployment

Netlify is configured by `netlify.toml`.

```toml
[build]
  publish = "frontend"

[functions]
  directory = "netlify/functions"
  node_bundler = "esbuild"
```

Current production site:

```text
https://ai-seo-copilot.netlify.app
```

The hosted frontend works by serving static files from `frontend/` and calling the Render API URL from `frontend/static/config.js`.

## 21. Local Development

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Run the backend:

```powershell
uvicorn backend.main:app --reload --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Optional Gemini setup:

```powershell
$env:GEMINI_API_KEY="your_api_key"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

## 22. Current Limitations

- Backend state is in memory, so uploaded data and results are lost when the service restarts.
- There is no user authentication yet.
- Multi-user production use would require per-user/session storage.
- Render free services may sleep when idle, causing first request latency.
- AI enrichment depends on Gemini API availability and key validity.
- The scoring formulas are heuristic, not a replacement for human SEO judgment.

## 23. Future Improvements

Recommended next upgrades:

- Add persistent storage for uploads and results.
- Add user authentication.
- Scope data per user/session.
- Add more Ahrefs rule types, such as cannibalization, declining rankings, missing metadata, and orphan pages.
- Add configurable thresholds for CTR, impressions, traffic drop, and position range.
- Add tests for rule engine scoring cases.
- Add a score explanation tooltip in the frontend for each task.
- Add a downloadable "score methodology" appendix in the PDF report.

## 24. Key Principle

The most important design principle is:

```text
Rules decide. Scores rank. AI explains.
```

That means every task must start from uploaded evidence, every score must come from deterministic formulas, and AI output must remain grounded in the data.
