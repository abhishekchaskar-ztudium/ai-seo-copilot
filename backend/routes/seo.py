from __future__ import annotations

import io
import json
import logging
import os
from typing import Literal

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.services.ai_engine import AIEngine
from backend.services.models import AnalyzeRequest, DatasetType, Task, UploadSummary
from backend.services.parser import parse_csv, validate_dataset
from backend.services.report import build_markdown_report, build_pdf_report
from backend.services.rule_engine import run_rule_engine
from backend.services.storage import state
from backend.services.validation import validate_ai_output


logger = logging.getLogger(__name__)
router = APIRouter()
ai_engine = AIEngine()
GEMINI_ENRICHMENT_LIMIT = int(os.getenv("GEMINI_ENRICHMENT_LIMIT", "25"))


@router.post("/upload-csv", response_model=list[UploadSummary])
async def upload_csv(
    dataset_type: DatasetType = Form(...),
    files: list[UploadFile] = File(...),
) -> list[UploadSummary]:
    summaries: list[UploadSummary] = []
    parsed_frames: list[pd.DataFrame] = []

    for file in files:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"{file.filename} is not a CSV file.")
        try:
            df = parse_csv(file.file)
            validate_dataset(dataset_type, df)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        parsed_frames.append(df)
        summaries.append(
            UploadSummary(
                dataset_type=dataset_type,
                filename=file.filename,
                rows=len(df),
                columns=list(df.columns),
            )
        )

    with state.lock:
        existing = state.datasets.get(dataset_type)
        combined = pd.concat([existing, *parsed_frames], ignore_index=True) if existing is not None else pd.concat(parsed_frames, ignore_index=True)
        state.datasets[dataset_type] = combined
        state.uploads.extend(summaries)

    return summaries


@router.post("/analyze", response_model=list[Task])
async def analyze(settings: AnalyzeRequest | None = None) -> list[Task]:
    with state.lock:
        datasets = {key: value.copy() for key, value in state.datasets.items()}

    if not datasets:
        raise HTTPException(status_code=400, detail="Upload at least one Ahrefs CSV before analysis.")

    issues = sorted(run_rule_engine(datasets), key=lambda issue: issue.priority_score, reverse=True)
    tasks: list[Task] = []
    api_key = settings.api_key.get_secret_value() if settings and settings.api_key else None
    model = settings.model if settings else None
    gemini_limit = GEMINI_ENRICHMENT_LIMIT if api_key or ai_engine.api_key else 0
    logger.info(
        "Analyze requested: datasets=%s issues=%s model=%s api_key_provided=%s gemini_limit=%s",
        list(datasets.keys()),
        len(issues),
        model or ai_engine.model,
        bool(api_key),
        gemini_limit,
    )
    gemini_successes = 0
    gemini_failures = 0
    for index, issue in enumerate(issues, start=1):
        use_gemini = index <= gemini_limit
        if use_gemini:
            try:
                ai_output = ai_engine.enrich_issue(issue, api_key=api_key, model=model)
                gemini_successes += 1
            except RuntimeError as exc:
                gemini_failures += 1
                logger.warning(
                    "Gemini enrichment stopped after %s success(es) and %s failure(s): %s",
                    gemini_successes,
                    gemini_failures,
                    exc,
                )
                ai_output = ai_engine.local_fallback(issue)
                gemini_limit = index
        else:
            ai_output = ai_engine.local_fallback(issue)

        try:
            tasks.append(validate_ai_output(issue, ai_output))
        except ValueError as exc:
            logger.warning("Rejected task for issue %s: %s", issue.type, exc)

    with state.lock:
        state.results = tasks

    logger.info(
        "Analyze complete: tasks=%s gemini_successes=%s fallback_tasks=%s",
        len(tasks),
        gemini_successes,
        max(len(tasks) - gemini_successes, 0),
    )

    return tasks


@router.get("/results", response_model=list[Task])
async def results(issue_type: str | None = None) -> list[Task]:
    with state.lock:
        tasks = list(state.results)

    if issue_type:
        tasks = [task for task in tasks if task.issue == issue_type]
    return tasks


@router.get("/export")
async def export(format: Literal["json", "csv"] = "json") -> StreamingResponse:
    with state.lock:
        rows = [task.model_dump() for task in state.results]

    if format == "json":
        payload = json.dumps(rows, indent=2)
        return StreamingResponse(
            io.BytesIO(payload.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=seo_tasks.json"},
        )

    flattened = []
    for row in rows:
        generated = row.pop("generated_content", {}) or {}
        row["titles"] = " | ".join(generated.get("titles", []))
        row["meta_descriptions"] = " | ".join(generated.get("meta_descriptions", []))
        row["headings"] = " | ".join(generated.get("headings", []))
        row["faqs"] = " | ".join(generated.get("faqs", []))
        row["actions"] = " | ".join(row.get("actions", []))
        flattened.append(row)

    df = pd.DataFrame(flattened)
    return StreamingResponse(
        io.BytesIO(df.to_csv(index=False).encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=seo_tasks.csv"},
    )


@router.get("/report")
async def report() -> StreamingResponse:
    with state.lock:
        tasks = list(state.results)

    payload = build_pdf_report(tasks)
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=seo_copilot_report.pdf"},
    )


@router.get("/report-preview")
async def report_preview() -> StreamingResponse:
    with state.lock:
        tasks = list(state.results)

    payload = build_markdown_report(tasks)
    return StreamingResponse(
        io.BytesIO(payload.encode("utf-8")),
        media_type="text/plain; charset=utf-8",
    )


@router.delete("/reset")
async def reset() -> dict[str, str]:
    with state.lock:
        state.datasets.clear()
        state.uploads.clear()
        state.results.clear()
    return {"status": "reset"}
