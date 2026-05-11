from __future__ import annotations


BASE_PRIORITY = {
    "Ranking Opportunity": 72,
    "CTR Issue": 68,
    "Traffic Drop": 82,
    "Link Reclamation Opportunity": 64,
    "Competitor Gap": 76,
    "Competitor Opportunity": 70,
}


def priority_for(issue_type: str, impact: float = 0, effort: float = 3) -> int:
    base = BASE_PRIORITY.get(issue_type, 50)
    impact_boost = min(max(impact, 0), 25)
    effort_penalty = min(max(effort, 1), 10) * 2
    return int(max(0, min(100, base + impact_boost - effort_penalty)))


def confidence_for(has_url: bool, evidence_count: int, source_quality: float = 1.0) -> float:
    score = 0.55 + min(evidence_count, 4) * 0.08 + (0.07 if has_url else 0)
    return round(max(0.1, min(0.98, score * source_quality)), 2)
