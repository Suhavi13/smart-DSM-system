"""Pydantic contracts owned by the recommendation service."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RecommendationEvidenceResponse(BaseModel):
    evidenceType: Literal["sensor", "external"]
    label: str
    sourceName: str
    sourceCodes: list[str] = Field(default_factory=list)
    value: float
    unit: str
    timestamp: datetime | str | None = None
    comparison: str
    details: str


class RecommendationRuleResponse(BaseModel):
    ruleId: str
    condition: str


class RecommendationItemResponse(BaseModel):
    recommendationId: str
    recommendationVersion: int = 1
    category: str
    title: str
    description: str
    reason: str
    priority: Literal["High", "Medium", "Low"]
    status: Literal["triggered"]
    rule: RecommendationRuleResponse
    evidence: list[RecommendationEvidenceResponse]


class RecommendationEvaluationResponse(BaseModel):
    ruleId: str
    ruleName: str
    triggered: bool
    summary: str


class SkippedRecommendationRuleResponse(BaseModel):
    ruleId: str
    reason: str


class RecommendationServiceResponse(BaseModel):
    datasetType: str
    generatedAt: datetime
    rulesEvaluated: int
    recommendationCount: int
    dataNotice: str
    recommendations: list[RecommendationItemResponse]
    evaluations: list[RecommendationEvaluationResponse]
    skippedRules: list[SkippedRecommendationRuleResponse]
