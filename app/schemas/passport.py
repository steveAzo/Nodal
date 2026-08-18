import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import BusinessActivityLabel, RiskLabel


class RecalculateRequest(BaseModel):
    profile_id: uuid.UUID


class ConfidenceByCategory(BaseModel):
    identity: int
    cash_flow: int
    stability: int
    repayment_history: int


class PassportOut(BaseModel):
    profile_id: uuid.UUID
    generated_at: datetime
    business_activity: BusinessActivityLabel
    window_days: int
    transaction_volume_ghs: float
    avg_daily_turnover_ghs: float
    transaction_consistency_pct: float
    liquidity_reliability_score: float
    repayment_reliability_score: float
    fraud_risk: RiskLabel
    nodal_score: float
    risk_tier: RiskLabel
    confidence_by_category: ConfidenceByCategory
    recommended_liquidity_line_ghs: float
    recommended_duration_hours: int
    risk_adjusted_price_pct: float

    # Beyond the spec's literal Section 8.3 shape: the same explainability
    # pattern Section 8.4 uses for Decision objects, applied to the score
    # itself so every number here is traceable to a named input.
    reasons: list[str]
    risk_flags: list[str]
    excluded_categories: list[str]
    sub_scores: dict[str, float | None]
