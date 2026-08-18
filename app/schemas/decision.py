import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import RecommendationType, RiskLabel


class PartnerOut(BaseModel):
    partner_id: str
    name: str
    max_risk_tier: RiskLabel
    capacity_multiplier: float
    price_adjustment_pct: float


class DecisionRequest(BaseModel):
    profile_id: uuid.UUID
    requested_amount_ghs: float = Field(gt=0)
    requested_duration_hours: int | None = Field(default=None, gt=0)
    issued_to_partner_id: str


class DecisionOut(BaseModel):
    decision_id: uuid.UUID
    profile_id: uuid.UUID
    recommendation: RecommendationType
    amount_ghs: float
    duration_hours: int
    risk_tier: RiskLabel
    reasons: list[str]
    risk_flags: list[str]
    issued_at: datetime
    issued_to_partner_id: str


class MarketplaceOfferOut(BaseModel):
    partner_id: str
    partner_name: str
    amount_ghs: float
    duration_hours: int
    price_pct: float
    reasons: list[str]


class MarketplaceOffersResponse(BaseModel):
    profile_id: uuid.UUID
    generated_at: datetime
    offers: list[MarketplaceOfferOut]
