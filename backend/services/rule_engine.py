from __future__ import annotations

import pandas as pd

from .models import Issue
from .parser import to_number
from .scoring import confidence_for, priority_for


HIGH_IMPRESSIONS_THRESHOLD = 1000
LOW_CTR_THRESHOLD = 2.0
TRAFFIC_DROP_PERCENT_THRESHOLD = 20.0


def run_rule_engine(datasets: dict[str, pd.DataFrame]) -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(_keyword_opportunities(datasets.get("organic_keywords")))
    issues.extend(_low_ctr_issues(datasets.get("organic_keywords")))
    issues.extend(_traffic_drops(datasets.get("organic_keywords"), "organic_keywords"))
    issues.extend(_traffic_drops(datasets.get("top_pages"), "top_pages"))
    issues.extend(_broken_backlinks(datasets.get("broken_backlinks")))
    issues.extend(_competitor_gaps(datasets.get("competitors"), datasets.get("organic_keywords")))
    return issues


def _keyword_opportunities(df: pd.DataFrame | None) -> list[Issue]:
    if df is None or "position" not in df.columns:
        return []

    position = to_number(df["position"])
    matches = df[(position > 5) & (position <= 20)]
    issues = []
    for _, row in matches.iterrows():
        keyword = _value(row, "keyword")
        url = _value(row, "url")
        pos = float(to_number(pd.Series([row.get("position")])).iloc[0])
        evidence_values = {"keyword": keyword, "url": url, "position": pos}
        issues.append(
            Issue(
                type="Ranking Opportunity",
                url=url,
                keyword=keyword,
                evidence=f"Keyword '{keyword}' ranks at position {pos:g}, which is between 6 and 20.",
                evidence_values=evidence_values,
                source_dataset="organic_keywords",
                priority_score=priority_for("Ranking Opportunity", impact=max(0, 21 - pos), effort=4),
                confidence_score=confidence_for(bool(url), len(evidence_values)),
            )
        )
    return issues


def _low_ctr_issues(df: pd.DataFrame | None) -> list[Issue]:
    if df is None or not {"impressions", "ctr"}.issubset(df.columns):
        return []

    impressions = to_number(df["impressions"])
    ctr = to_number(df["ctr"])
    matches = df[(impressions >= HIGH_IMPRESSIONS_THRESHOLD) & (ctr < LOW_CTR_THRESHOLD)]
    issues = []
    for index, row in matches.iterrows():
        keyword = _value(row, "keyword")
        url = _value(row, "url")
        imp = float(impressions.loc[index])
        ctr_value = float(ctr.loc[index])
        evidence_values = {
            "keyword": keyword,
            "url": url,
            "impressions": imp,
            "ctr": ctr_value,
        }
        issues.append(
            Issue(
                type="CTR Issue",
                url=url,
                keyword=keyword,
                evidence=(
                    f"Keyword '{keyword}' has {imp:g} impressions and CTR {ctr_value:g}%, "
                    f"below the {LOW_CTR_THRESHOLD:g}% threshold."
                ),
                evidence_values=evidence_values,
                source_dataset="organic_keywords",
                priority_score=priority_for("CTR Issue", impact=min(25, imp / 1000), effort=3),
                confidence_score=confidence_for(bool(url), len(evidence_values)),
            )
        )
    return issues


def _traffic_drops(df: pd.DataFrame | None, source_dataset: str) -> list[Issue]:
    if df is None or not {"traffic", "previous_traffic"}.issubset(df.columns):
        return []

    current = to_number(df["traffic"])
    previous = to_number(df["previous_traffic"])
    drop_percent = ((previous - current) / previous.replace(0, pd.NA)) * 100
    matches = df[drop_percent.fillna(0) >= TRAFFIC_DROP_PERCENT_THRESHOLD]
    issues = []
    for index, row in matches.iterrows():
        keyword = _value(row, "keyword")
        url = _value(row, "url")
        previous_value = float(previous.loc[index])
        current_value = float(current.loc[index])
        drop_value = float(drop_percent.loc[index])
        evidence_values = {
            "keyword": keyword,
            "url": url,
            "previous_traffic": previous_value,
            "traffic": current_value,
            "drop_percent": round(drop_value, 2),
        }
        subject = url or keyword or f"row {index + 1}"
        issues.append(
            Issue(
                type="Traffic Drop",
                url=url,
                keyword=keyword,
                evidence=(
                    f"{subject} traffic declined from {previous_value:g} to {current_value:g} "
                    f"({drop_value:.1f}% drop)."
                ),
                evidence_values=evidence_values,
                source_dataset=source_dataset,  # type: ignore[arg-type]
                priority_score=priority_for("Traffic Drop", impact=min(25, drop_value / 2), effort=5),
                confidence_score=confidence_for(bool(url), len(evidence_values)),
            )
        )
    return issues


def _broken_backlinks(df: pd.DataFrame | None) -> list[Issue]:
    if df is None:
        return []

    if "status" in df.columns:
        status_text = df["status"].astype(str).str.lower()
        matches = df[status_text.str.contains("broken|404|not found|lost", regex=True, na=False)]
    else:
        matches = df

    issues = []
    for index, row in matches.iterrows():
        url = _value(row, "url") or _value(row, "target")
        source_url = _value(row, "source_url")
        status = _value(row, "status") or "broken backlink export"
        evidence_values = {"url": url, "source_url": source_url, "status": status}
        issues.append(
            Issue(
                type="Link Reclamation Opportunity",
                url=url,
                evidence=f"Broken backlink found from '{source_url or 'unknown source'}' to '{url or 'unknown target'}' with status '{status}'.",
                evidence_values=evidence_values,
                source_dataset="broken_backlinks",
                priority_score=priority_for("Link Reclamation Opportunity", impact=10, effort=3),
                confidence_score=confidence_for(bool(url), len(evidence_values), 0.92),
            )
        )
    return issues


def _competitor_gaps(
    competitors: pd.DataFrame | None, organic_keywords: pd.DataFrame | None
) -> list[Issue]:
    if competitors is None:
        return []

    if "keyword" not in competitors.columns:
        return _competitor_domain_opportunities(competitors)

    site_keywords = set()
    if organic_keywords is not None and "keyword" in organic_keywords.columns:
        site_keywords = {
            str(keyword).strip().lower()
            for keyword in organic_keywords["keyword"].dropna().tolist()
        }

    issues = []
    for index, row in competitors.iterrows():
        keyword = _value(row, "keyword")
        if not keyword or keyword.lower() in site_keywords:
            continue
        competitor = _value(row, "competitor")
        url = _value(row, "url")
        position = _value(row, "position")
        evidence_values = {
            "keyword": keyword,
            "competitor": competitor,
            "competitor_url": url,
            "position": position,
        }
        issues.append(
            Issue(
                type="Competitor Gap",
                url="",
                keyword=keyword,
                evidence=(
                    f"Competitor '{competitor or 'unknown competitor'}' ranks for keyword "
                    f"'{keyword}'{f' at position {position}' if position else ''}, but the site export does not include it."
                ),
                evidence_values=evidence_values,
                source_dataset="competitors",
                priority_score=priority_for("Competitor Gap", impact=12, effort=6),
                confidence_score=confidence_for(False, len(evidence_values), 0.9),
            )
        )
    return issues


def _competitor_domain_opportunities(competitors: pd.DataFrame) -> list[Issue]:
    if "competitor" not in competitors.columns:
        return []

    issues = []
    for index, row in competitors.iterrows():
        competitor = _value(row, "competitor")
        if not competitor:
            continue

        traffic = float(to_number(pd.Series([row.get("traffic")])).iloc[0])
        common_keywords = float(to_number(pd.Series([row.get("common_keywords")])).iloc[0])
        unique_keywords = float(to_number(pd.Series([row.get("unique_keywords")])).iloc[0])
        organic_pages = float(to_number(pd.Series([row.get("organic_pages")])).iloc[0])
        evidence_values = {
            "competitor": competitor,
            "traffic": traffic,
            "common_keywords": common_keywords,
            "unique_keywords": unique_keywords,
            "organic_pages": organic_pages,
        }
        metric_bits = []
        if traffic:
            metric_bits.append(f"organic traffic {traffic:g}")
        if common_keywords:
            metric_bits.append(f"{common_keywords:g} common keywords")
        if unique_keywords:
            metric_bits.append(f"{unique_keywords:g} unique keywords")
        if organic_pages:
            metric_bits.append(f"{organic_pages:g} organic pages")
        metrics = ", ".join(metric_bits) if metric_bits else "domain-level competitor metrics"

        impact = min(25, (traffic / 1000) + (unique_keywords / 100) + (common_keywords / 250))
        issues.append(
            Issue(
                type="Competitor Opportunity",
                url="",
                keyword=competitor,
                evidence=(
                    f"Organic competitor '{competitor}' appears in the uploaded competitor export "
                    f"with {metrics}."
                ),
                evidence_values=evidence_values,
                source_dataset="competitors",
                priority_score=priority_for("Competitor Opportunity", impact=impact, effort=6),
                confidence_score=confidence_for(False, len(evidence_values), 0.88),
            )
        )
    return issues


def _value(row: pd.Series, key: str) -> str:
    value = row.get(key, "")
    if pd.isna(value):
        return ""
    return str(value).strip()
