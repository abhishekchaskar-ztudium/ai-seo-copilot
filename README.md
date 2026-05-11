# AI SEO Copilot - Ahrefs Insight to Action System

A complete hybrid SEO workflow that turns Ahrefs CSV exports into actionable SEO tasks.

The architecture is intentionally split:

- Deterministic rule engine finds every issue and calculates priority/confidence.
- AI explains issues, suggests actions, and generates SEO content.
- Validation rejects missing evidence and strips unverifiable AI output.

## Features

- Upload multiple Ahrefs CSV files for organic keywords, top pages, backlinks, broken backlinks, and competitors.
- Parse CSV exports with pandas.
- Detect ranking opportunities, CTR issues, traffic drops, broken backlink reclamation, and competitor gaps.
- Enrich rule-engine issues with Gemini when `GEMINI_API_KEY` or `GOOGLE_API_KEY` is set.
- Local fallback enrichment when no API key is configured.
- Cache AI responses in `backend/.cache/ai_responses.json`.
- Export results as JSON or CSV.
- Generate one consolidated PDF SEO action document with a summarized report section.
- Custom staged web UI with upload, Gemini setup, dashboard, task data, and report stages.
- n8n-style runtime AI settings in the UI: paste a Gemini API key and select the model before analysis.

## Project Structure

```text
backend/
  main.py
  routes/
    seo.py
  services/
    ai_engine.py
    models.py
    parser.py
    prompts.py
    rule_engine.py
    scoring.py
    storage.py
    validation.py
docs/
  README.md
  PROJECT_DOCUMENTATION.md
  BOSS_PROJECT_BRIEF.md
  sample_prompts.md
frontend/
  index.html
  static/
    app.js
    config.js
    styles.css
netlify/
  functions/
    api.mts
netlify.toml
render.yaml
requirements.txt
```

## Documentation

- Full project documentation: `docs/PROJECT_DOCUMENTATION.md`
- Project brief: `docs/BOSS_PROJECT_BRIEF.md`
- Gemini prompt reference: `docs/sample_prompts.md`

## Rule Engine

All decisions originate in `backend/services/rule_engine.py`.

- Ranking Opportunity: `position > 5 and position <= 20`
- CTR Issue: `impressions >= 1000 and ctr < 2`
- Traffic Drop: `previous_traffic` to `traffic` decline of at least 20%
- Link Reclamation Opportunity: rows in broken backlink export, or status containing broken/404/not found/lost
- Competitor Gap: competitor keyword is absent from uploaded organic keyword export

The AI layer never calculates metrics or creates issues.

## Expected CSV Columns

The parser accepts common Ahrefs-style column names and normalizes aliases.

- Organic keywords: `keyword`, optional `url`, `position`, `impressions`, `ctr`, `traffic`, `previous_traffic`
- Top pages: `url`, optional `traffic`, `previous_traffic`
- Backlinks: accepted for future expansion
- Broken backlinks: optional `url`, `source_url`, `status`
- Competitors: either `keyword` for content-gap exports, or `competitor`/`domain` for Ahrefs Organic competitors exports; optional `common_keywords`, `unique_keywords`, `traffic`, `organic_pages`, `url`, `position`

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional Gemini configuration:

```powershell
$env:GEMINI_API_KEY="your_new_rotated_api_key"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

The model defaults to `gemini-2.5-flash`, the recommended general-purpose Gemini option. The UI also includes `gemini-2.5-pro` for best quality, `gemini-2.5-flash-lite` for speed/cost, and `gemini-2.0-flash` as a fallback. If Google exposes a different model to your account, set `GEMINI_MODEL` to that exact model string or choose Custom model code in the UI.

For preview models, use the exact model code shown in Google AI Studio, for example `gemini-2.5-flash-preview-09-2025`.

You can also paste the Gemini API key directly in the web UI before clicking Analyze. That key is sent only to the FastAPI `/analyze` request and is not written to disk, cached, exported, or committed.

Run the backend:

```powershell
uvicorn backend.main:app --reload --port 8000
```

Open the custom web UI:

```text
http://127.0.0.1:8000
```

## Netlify Deployment

The project is configured for Netlify with:

- `netlify.toml`: publishes the static frontend from `frontend/`
- `netlify/functions/api.mts`: Netlify Function endpoints for upload, analyze, export, report, reset, and health
- `package.json`: Netlify build dependencies

Live site:

```text
https://ai-seo-copilot.netlify.app
```

The hosted Netlify version keeps uploaded CSV rows in the browser during the workflow and sends them to the serverless analyze endpoint. This avoids relying on a long-running Python/FastAPI process, which Netlify does not provide.

## Render Backend Deployment

The FastAPI backend is Render-ready with `render.yaml`.

Recommended Render settings:

- Service type: Web Service
- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- Python version: `3.12.7`

Render requires web services to bind to `0.0.0.0` and the `PORT` environment variable. After Render gives you a URL such as `https://ai-seo-copilot-backend.onrender.com`, open the Netlify app, go to Gemini API Setup, and paste that URL into Backend API URL.

For production Gemini enrichment, add `GEMINI_API_KEY` or `GOOGLE_API_KEY` in the Render service environment variables.

## API

- `POST /upload-csv`: multipart form with `dataset_type` and one or more `files`
- `POST /analyze`: runs rules, enriches issues, validates tasks
- `GET /results`: returns stored tasks, optional `?issue_type=CTR Issue`
- `GET /export?format=json`: downloads JSON
- `GET /export?format=csv`: downloads CSV
- `GET /report`: downloads one PDF SEO action document
- `GET /report-preview`: returns the report text for the in-app preview
- `DELETE /reset`: clears in-memory session data
- `GET /health`: health check

## Notes

This version stores uploaded data and results in memory for local usage. For production, replace `backend/services/storage.py` with persistent storage, add authentication, and scope sessions per user.
