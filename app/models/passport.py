import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Passport(Base):
    """Cached, latest-computed Passport per profile (Section 8.3).

    One row per profile, overwritten on every recalculation — this is the
    read-cache GET /v1/passport serves from to hit the sub-500ms p95 target
    in Section 12, rather than recomputing on every read.
    """

    __tablename__ = "passports"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.profile_id", ondelete="CASCADE"), primary_key=True
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    business_activity: Mapped[str] = mapped_column(String(10), nullable=False)
    window_days: Mapped[int] = mapped_column(nullable=False, default=90)
    transaction_volume_ghs: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    avg_daily_turnover_ghs: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    transaction_consistency_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    liquidity_reliability_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    repayment_reliability_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    fraud_risk: Mapped[str] = mapped_column(String(10), nullable=False)
    nodal_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(10), nullable=False)

    confidence_identity: Mapped[int] = mapped_column(nullable=False)
    confidence_cash_flow: Mapped[int] = mapped_column(nullable=False)
    confidence_stability: Mapped[int] = mapped_column(nullable=False)
    confidence_repayment_history: Mapped[int] = mapped_column(nullable=False)

    recommended_liquidity_line_ghs: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    recommended_duration_hours: Mapped[int] = mapped_column(nullable=False)
    risk_adjusted_price_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    # Explainability trail (Section 8.4's "reasons"/"risk_flags" pattern, applied
    # here to the score itself) — every included/excluded sub-score and why.
    reasons: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    risk_flags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    excluded_categories: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    sub_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
