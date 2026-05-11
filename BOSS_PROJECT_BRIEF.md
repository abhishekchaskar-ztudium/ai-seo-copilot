# AI SEO Copilot - Project Brief

## One-Line Idea

AI SEO Copilot turns large Ahrefs CSV exports into a prioritized SEO action plan with clear evidence, AI-assisted recommendations, and a polished PDF report that a marketing or SEO team can act on immediately.

## The Problem

SEO tools such as Ahrefs provide a lot of useful data, but the exports are usually large, repetitive, and hard to convert into actual work. A team may download thousands of rows for keywords, pages, backlinks, broken links, or competitors, but still needs to manually answer:

- Which issues matter most?
- Which pages should be fixed first?
- What evidence supports each task?
- What should the content or SEO team actually do next?
- How can the work be presented clearly to managers or clients?

This project solves that gap by converting raw SEO data into prioritized tasks and a readable executive report.

## What The System Does

AI SEO Copilot is a local web application with a FastAPI backend and a staged frontend workflow.

The user uploads Ahrefs CSV exports for:

- Organic keywords
- Top pages
- Backlinks
- Broken backlinks
- Competitor keyword data

The backend parses the data, normalizes common column names, runs deterministic SEO rules, and creates issues such as:

- Ranking opportunities
- CTR issues
- Traffic drops
- Broken backlink reclamation opportunities
- Competitor keyword gaps

After that, Gemini is used to enrich each validated issue with:

- A plain-English explanation
- Recommended actions
- Suggested titles
- Suggested meta descriptions
- Heading ideas
- FAQ ideas

The final output is a prioritized SEO task dashboard and a formatted PDF report.

## Why This Is Useful

The value of the project is not just AI text generation. The important part is that the AI only works after the rule engine has detected real issues from uploaded data.

This makes the system more reliable because:

- The rule engine finds the problem from measurable SEO data.
- Priority and confidence are calculated before AI enrichment.
- Gemini explains and expands on the issue, but does not invent the issue.
- Validation rejects weak or unsupported AI output.
- The final report keeps evidence attached to every recommendation.

This gives the team a practical workflow: data first, AI second, action last.

## Workflow

1. Upload Ahrefs CSV files.
2. Choose a Gemini model and optionally paste a Gemini API key.
3. Run analysis.
4. Review dashboard KPIs and task breakdown.
5. Filter tasks by issue type.
6. Export task data as JSON or CSV if needed.
7. Download a formatted PDF report for review, execution, or sharing.

## Gemini Model Options

The app includes practical Gemini model choices:

- Gemini 2.5 Flash: recommended default for speed and quality
- Gemini 2.5 Pro: best quality for complex reasoning
- Gemini 2.5 Flash-Lite: fastest and lowest-cost option
- Gemini 2.0 Flash: fallback model
- Custom model code: useful when Google AI Studio exposes a newer model to the account

This gives flexibility depending on cost, quality, and availability.

## Report Output

The PDF report is designed for both managers and execution teams.

It includes:

- Cover page
- Executive summary
- KPI tiles
- Summarized report section
- Top 10 tasks to start with
- Issue breakdown
- Execution work plan
- Highest-priority tasks
- Full task detail section

This helps a manager quickly understand the SEO situation while still giving the team enough detail to take action.

## Business Benefits

AI SEO Copilot can help reduce the manual time needed to review SEO exports and prepare action reports.

Key benefits:

- Faster SEO audits
- Clear task prioritization
- Less manual spreadsheet review
- Better reporting for clients or managers
- Evidence-backed AI recommendations
- Repeatable workflow for future Ahrefs exports

## Technical Architecture

The project is intentionally simple and maintainable.

- Frontend: staged web UI served by FastAPI, plus a Streamlit interface
- Backend: FastAPI
- Data processing: pandas
- Validation and schemas: Pydantic
- AI provider: Gemini through `google-genai`
- Report output: generated PDF
- Storage: in-memory state for local usage

The core logic is separated into services:

- CSV parsing
- Rule engine
- AI enrichment
- Validation
- Report generation
- Export handling

This separation makes the project easier to extend later.

## Current Scope

The current version is best suited for local SEO analysis and demo usage. It stores uploaded data in memory and is designed for a single local session.

For production, the next steps would be:

- Add user login
- Store uploads and results in a database
- Add project-level workspaces
- Add client branding to reports
- Add background jobs for large datasets
- Add historical comparison between multiple Ahrefs exports
- Deploy the backend and frontend securely

## Summary

AI SEO Copilot is a practical AI-assisted SEO workflow. It does not replace SEO judgment; it reduces the time spent turning raw exports into a clear action plan.

The main idea is simple: upload SEO data, detect real issues with rules, enrich those issues with Gemini, and produce a clean PDF report that can be shared with decision-makers or used directly by the SEO team.
