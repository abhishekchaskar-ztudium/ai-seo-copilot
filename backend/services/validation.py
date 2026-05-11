from __future__ import annotations

import json

from .models import AIOutput, Issue, Task


def validate_ai_output(issue: Issue, ai_output: AIOutput) -> Task:
    if not issue.evidence.strip():
        raise ValueError(f"Issue '{issue.type}' is missing evidence.")

    safe_output = _strip_unverifiable_generated_content(issue, ai_output)
    explanation = safe_output.explanation.strip() or "insufficient data"

    status = "validated"
    if "insufficient data" in explanation.lower():
        status = "validated_with_insufficient_data"

    return Task(
        page=issue.url or "insufficient data",
        keyword=issue.keyword,
        issue=issue.type,
        evidence=issue.evidence,
        ai_explanation=explanation,
        actions=safe_output.actions,
        generated_content=safe_output.generated_content,
        priority_score=issue.priority_score,
        confidence_score=issue.confidence_score,
        validation_status=status,
    )


def _strip_unverifiable_generated_content(issue: Issue, ai_output: AIOutput) -> AIOutput:
    allowed_terms = {
        str(value).lower()
        for value in issue.evidence_values.values()
        if value is not None and str(value).strip()
    }
    keyword = issue.keyword.lower().strip()
    url = issue.url.lower().strip()

    data_blob = json.dumps(issue.evidence_values, ensure_ascii=True).lower()
    evidence_blob = f"{issue.evidence.lower()} {data_blob}"

    def keep(items: list[str]) -> list[str]:
        kept = []
        for item in items:
            text = item.strip()
            lowered = text.lower()
            references_known_keyword = bool(keyword and keyword in lowered)
            references_known_url = bool(url and url in lowered)
            uses_allowed_term = any(term and term in lowered for term in allowed_terms)
            is_generic = not any(token in lowered for token in ["http", ".com", ".org", ".net", "%", "$"])
            if references_known_keyword or references_known_url or uses_allowed_term or is_generic:
                kept.append(text)
        return kept

    ai_output.generated_content.titles = keep(ai_output.generated_content.titles)
    ai_output.generated_content.meta_descriptions = keep(ai_output.generated_content.meta_descriptions)
    ai_output.generated_content.headings = keep(ai_output.generated_content.headings)
    ai_output.generated_content.faqs = keep(ai_output.generated_content.faqs)

    if _contains_external_claim(ai_output.explanation, evidence_blob):
        ai_output.explanation = "insufficient data"
    ai_output.actions = keep(ai_output.actions)
    return ai_output


def _contains_external_claim(text: str, evidence_blob: str) -> bool:
    lowered = text.lower()
    suspicious_tokens = ["according to", "industry average", "google says", "search volume is"]
    return any(token in lowered and token not in evidence_blob for token in suspicious_tokens)

