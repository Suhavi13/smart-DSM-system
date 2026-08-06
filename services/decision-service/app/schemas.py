"""Pydantic contracts owned by the decision service."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DecisionCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recommendation_id: str = Field(
        alias="recommendationId",
        min_length=1,
        max_length=100,
    )

    recommendation_version: int = Field(
        default=1,
        alias="recommendationVersion",
        ge=1,
    )

    action: Literal["approved", "rejected"]

    comment: str | None = Field(
        default=None,
        max_length=1000,
    )

    recommendation_snapshot: dict[str, Any] = Field(
        alias="recommendationSnapshot",
    )


class DecisionResetCreate(BaseModel):
    comment: str | None = Field(
        default=None,
        max_length=1000,
    )


class DecisionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    decision_id: int = Field(alias="decisionId")

    recommendation_id: str = Field(
        alias="recommendationId"
    )

    recommendation_version: int = Field(
        alias="recommendationVersion"
    )

    stored_recommendation_id: int | None = Field(
        default=None,
        alias="storedRecommendationId",
    )

    action: str
    comment: str | None

    operator_label: str = Field(
        alias="operatorLabel"
    )

    recommendation_snapshot: dict[str, Any] = Field(
        alias="recommendationSnapshot"
    )

    created_at: datetime = Field(
        alias="createdAt"
    )

    is_active: bool = Field(
        alias="isActive"
    )

    reverted_at: datetime | None = Field(
        default=None,
        alias="revertedAt",
    )

    reverted_by: str | None = Field(
        default=None,
        alias="revertedBy",
    )

    revert_comment: str | None = Field(
        default=None,
        alias="revertComment",
    )
