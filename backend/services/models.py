from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr


DatasetType = Literal[
    "organic_keywords",
    "top_pages",
    "backlinks",
    "broken_backlinks",
    "competitors",
]


class Issue(BaseModel):
    type: str
    url: str = ""
    keyword: str = ""
    evidence: str
    evidence_values: dict[str, Any] = Field(default_factory=dict)
    source_dataset: DatasetType
    priority_score: int = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=1)


class GeneratedContent(BaseModel):
    titles: list[str] = Field(default_factory=list)
    meta_descriptions: list[str] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)
    faqs: list[str] = Field(default_factory=list)


class AIOutput(BaseModel):
    explanation: str
    actions: list[str] = Field(default_factory=list)
    generated_content: GeneratedContent = Field(default_factory=GeneratedContent)


class Task(BaseModel):
    page: str
    keyword: str = ""
    issue: str
    evidence: str
    ai_explanation: str
    actions: list[str]
    generated_content: GeneratedContent
    priority_score: int = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=1)
    validation_status: str = "validated"


class UploadSummary(BaseModel):
    dataset_type: DatasetType
    filename: str
    rows: int
    columns: list[str]


class AnalyzeRequest(BaseModel):
    api_key: SecretStr | None = None
    model: str = "gemini-2.5-flash"
