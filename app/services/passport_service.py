"""Fetch-or-compute and persist the cached Passport for a profile.

Shared by the passport endpoints (Section 9's GET /v1/passport and POST
/v1/score/recalculate) and Decision generation (Section 8.4), which both
need "the current Passport" and shouldn't duplicate the caching logic.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.passport import Passport
from app.models.profile import Profile
from app.services.scoring import ScoringResult, compute_passport


def _upsert(db: Session, profile: Profile, result: ScoringResult) -> Passport:
    passport = db.get(Passport, profile.profile_id)
    now = datetime.now(timezone.utc)
    if passport is None:
        passport = Passport(profile_id=profile.profile_id)
        db.add(passport)

    passport.generated_at = now
    passport.business_activity = result.business_activity_label
    passport.window_days = 90
    passport.transaction_volume_ghs = result.transaction_volume_ghs
    passport.avg_daily_turnover_ghs = result.avg_daily_turnover_ghs
    passport.transaction_consistency_pct = result.transaction_consistency_pct
    passport.liquidity_reliability_score = result.liquidity_reliability_score
    passport.repayment_reliability_score = result.repayment_reliability_score
    passport.fraud_risk = result.fraud_risk_label
    passport.nodal_score = result.nodal_score
    passport.risk_tier = result.risk_tier
    passport.confidence_identity = result.confidence["identity"]
    passport.confidence_cash_flow = result.confidence["cash_flow"]
    passport.confidence_stability = result.confidence["stability"]
    passport.confidence_repayment_history = result.confidence["repayment_history"]
    passport.recommended_liquidity_line_ghs = result.recommended_liquidity_line_ghs
    passport.recommended_duration_hours = result.recommended_duration_hours
    passport.risk_adjusted_price_pct = result.risk_adjusted_price_pct
    passport.reasons = result.reasons
    passport.risk_flags = result.risk_flags
    passport.excluded_categories = result.excluded_categories
    passport.sub_scores = result.sub_scores

    db.commit()
    db.refresh(passport)
    return passport


def get_or_compute_passport(db: Session, profile: Profile) -> Passport:
    """Cache-read: returns the stored Passport, computing and storing one
    only if this profile has never been scored before."""
    passport = db.get(Passport, profile.profile_id)
    if passport is None:
        passport = _upsert(db, profile, compute_passport(db, profile))
    return passport


def recalculate_passport(db: Session, profile: Profile) -> Passport:
    """Force a fresh computation and overwrite the cache — used by the
    Section 10 recalculation triggers, not by callers that just want to
    read the current score."""
    return _upsert(db, profile, compute_passport(db, profile))
