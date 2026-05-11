from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from time import sleep

import requests

from .models import AIOutput, Issue
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


logger = logging.getLogger(__name__)
CACHE_PATH = Path(__file__).resolve().parents[1] / ".cache" / "ai_responses.json"
GEMINI_REST_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class AIEngine:
    def __init__(self) -> None:
        self.provider = os.getenv("AI_PROVIDER", "gemini").lower()
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = self._create_client(self.api_key)
        self.cache = self._load_cache()

    def local_fallback(self, issue: Issue) -> AIOutput:
        return self._fallback_output(issue)

    def enrich_issue(
        self,
        issue: Issue,
        api_key: str | None = None,
        model: str | None = None,
    ) -> AIOutput:
        active_model = (model or self.model).strip() or self.model
        active_api_key = api_key or self.api_key
        explicit_api_key = bool(api_key)
        require_gemini = bool(active_api_key)
        client = self._create_client(active_api_key)
        cache_key = self._cache_key(issue, active_model)

        if client and not explicit_api_key and cache_key in self.cache:
            logger.info("Using cached Gemini enrichment for model %s and issue %s.", active_model, issue.type)
            return AIOutput.model_validate(self.cache[cache_key])

        if not client:
            if require_gemini:
                raise RuntimeError(
                    "Gemini API key is configured, but no Gemini client could be created."
                )
            logger.info("No Gemini client available; using local fallback for issue %s.", issue.type)
            output = self._fallback_output(issue)
            return output

        user_prompt = USER_PROMPT_TEMPLATE.format(
            issue_type=issue.type,
            url=issue.url or "insufficient data",
            keyword=issue.keyword or "insufficient data",
            evidence=issue.evidence,
            evidence_values=json.dumps(issue.evidence_values, ensure_ascii=True),
        )

        try:
            logger.info("Calling Gemini model %s for issue %s.", active_model, issue.type)
            content = self._generate_json(client, active_model, user_prompt)
            output = AIOutput.model_validate_json(content)
        except Exception as exc:
            logger.warning("Gemini enrichment failed for model %s and issue %s: %s", active_model, issue.type, exc)
            if require_gemini or explicit_api_key:
                raise RuntimeError(
                    f"Gemini API call failed for model '{active_model}' while enriching '{issue.type}'."
                ) from exc
            output = AIOutput(
                explanation=f"insufficient data: AI enrichment failed ({exc.__class__.__name__})",
                actions=[],
            )

        self.cache[cache_key] = output.model_dump()
        self._save_cache()
        return output

    def _fallback_output(self, issue: Issue) -> AIOutput:
        page = issue.url or "insufficient data"
        keyword = issue.keyword or issue.evidence_values.get("keyword") or "insufficient data"
        actions_by_type = {
            "Ranking Opportunity": [
                "Review the page content against the supplied keyword.",
                "Improve title, headings, and on-page coverage using only the uploaded keyword evidence.",
                "Add internal links to the page from relevant existing pages.",
            ],
            "CTR Issue": [
                "Rewrite the title and meta description to better match the supplied keyword intent.",
                "Check whether the SERP snippet promises a clearer benefit for the provided keyword.",
            ],
            "Traffic Drop": [
                "Compare the affected page or keyword with the previous known traffic value in the export.",
                "Refresh outdated content and verify technical indexability for the affected page.",
            ],
            "Link Reclamation Opportunity": [
                "Contact the referring site with the supplied broken backlink source and target.",
                "Restore the target page or add a relevant redirect if the destination moved.",
            ],
            "Competitor Gap": [
                "Create or improve content targeting the supplied competitor keyword.",
                "Analyze the competitor URL from the upload before drafting final content.",
            ],
            "Competitor Opportunity": [
                "Review the competitor domain and compare its strongest topics against your current content.",
                "Prioritize content gaps, internal links, and page updates where the competitor has the clearest advantage.",
                "Use the uploaded competitor metrics to decide whether this domain belongs in the next SEO sprint.",
            ],
        }
        titles = [] if keyword == "insufficient data" else [f"{keyword}: Practical Guide"]
        meta = [] if keyword == "insufficient data" else [f"Learn about {keyword} with a focused guide based on verified site data."]
        headings = [] if keyword == "insufficient data" else [f"What to Know About {keyword}", f"How to Improve Results for {keyword}"]
        faqs = [] if keyword == "insufficient data" else [f"What is the best next step for {keyword}?"]
        return AIOutput(
            explanation=f"{issue.type} detected for {page}. Evidence: {issue.evidence}",
            actions=actions_by_type.get(issue.type, ["Review the supplied evidence and decide the next SEO action."]),
            generated_content={
                "titles": titles,
                "meta_descriptions": meta,
                "headings": headings,
                "faqs": faqs,
            },
        )

    def _create_client(self, api_key: str | None = None):
        if self.provider != "gemini" or not api_key:
            return None
        try:
            from google import genai
        except ImportError:
            logger.info("google-genai is not installed; using Gemini REST API client.")
            return {"api_key": api_key, "transport": "rest"}
        return genai.Client(api_key=api_key)

    def _generate_json(self, client, model: str, user_prompt: str) -> str:
        if isinstance(client, dict) and client.get("transport") == "rest":
            return self._generate_json_rest(client["api_key"], model, user_prompt)

        from google.genai import types

        response = client.models.generate_content(
            model=model,
            contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIOutput,
                temperature=0.2,
            ),
        )

        if getattr(response, "parsed", None):
            parsed = response.parsed
            if isinstance(parsed, AIOutput):
                return parsed.model_dump_json()
            return AIOutput.model_validate(parsed).model_dump_json()

        return response.text or "{}"

    def _generate_json_rest(self, api_key: str, model: str, user_prompt: str) -> str:
        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_prompt}"}],
                },
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }
        response = None
        for attempt in range(3):
            response = requests.post(
                GEMINI_REST_URL.format(model=model),
                params={"key": api_key},
                json=request_body,
                timeout=60,
            )
            if response.ok:
                break
            if response.status_code not in RETRYABLE_STATUS_CODES or attempt == 2:
                _raise_gemini_http_error(response)
            sleep(1.5 * (attempt + 1))

        if response is None:
            raise RuntimeError("Gemini request did not complete.")

        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text

    def _cache_key(self, issue: Issue, model: str) -> str:
        raw = json.dumps(
            {"provider": self.provider, "model": model, "issue": issue.model_dump()},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_cache(self) -> dict[str, dict]:
        if not CACHE_PATH.exists():
            return {}
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid AI cache file at %s", CACHE_PATH)
            return {}

    def _save_cache(self) -> None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(self.cache, indent=2), encoding="utf-8")


def _raise_gemini_http_error(response: requests.Response) -> None:
    message = response.text[:500].replace("\n", " ").strip()
    raise RuntimeError(f"Gemini HTTP {response.status_code}: {message or response.reason}")
