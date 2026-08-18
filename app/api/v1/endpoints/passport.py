from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.passport import Passport
from app.models.profile import Profile
from app.schemas.passport import ConfidenceByCategory, PassportOut, RecalculateRequest
from app.services.scoring import ScoringResult, compute_passport

router = APIRouter(tags=["passport"])


def _to_out(passport: Passport) -> PassportOut:
    return PassportOut(
        profile_id=passport.profile_id,
        generated_at=passport.generated_at,
        business_activity=passport.business_activity,
        window_days=passport.window_days,
        transaction_volume_ghs=float(passport.transaction_volume_ghs),
        avg_daily_turnover_ghs=float(passport.avg_daily_turnover_ghs),
        transaction_consistency_pct=float(passport.transaction_consistency_pct),
        liquidity_reliability_score=float(passport.liquidity_reliability_score),
        repayment_reliability_score=float(passport.repayment_reliability_score),
        fraud_risk=passport.fraud_risk,
        nodal_score=float(passport.nodal_score),
        confidence_by_category=ConfidenceByCategory(
            identity=passport.confidence_identity,
            cash_flow=passport.confidence_cash_flow,
            stability=passport.confidence_stability,
            repayment_history=passport.confidence_repayment_history,
        ),
        recommended_liquidity_line_ghs=float(passport.recommended_liquidity_line_ghs),
        recommended_duration_hours=passport.recommended_duration_hours,
        risk_adjusted_price_pct=float(passport.risk_adjusted_price_pct),
        reasons=passport.reasons,
        risk_flags=passport.risk_flags,
        excluded_categories=passport.excluded_categories,
        sub_scores=passport.sub_scores,
    )


def _upsert_passport(db: Session, profile: Profile, result: ScoringResult) -> Passport:
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


@router.get("/passport/{profile_id}", response_model=PassportOut)
def get_passport(profile_id: str, db: Session = Depends(get_db)) -> PassportOut:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    passport = db.get(Passport, profile_id)
    if passport is None:
        # First read for this profile — nothing cached yet, compute once and
        # store it, rather than 404ing someone who hasn't been scored yet.
        result = compute_passport(db, profile)
        passport = _upsert_passport(db, profile, result)

    return _to_out(passport)


@router.post("/score/recalculate", response_model=PassportOut)
def recalculate_score(payload: RecalculateRequest, db: Session = Depends(get_db)) -> PassportOut:
    """Internal endpoint (Section 9): meant to be triggered by the
    recalculation events in Section 10 (new Tier 3+ transaction, document
    verified, token verified, repayment posted, consent revoked), not called
    directly by end-user clients. Exposed as a real endpoint here since this
    prototype has no internal service mesh to fire it automatically yet —
    see the TODO in the ingest endpoint.
    """
    profile = db.get(Profile, payload.profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    result = compute_passport(db, profile)
    passport = _upsert_passport(db, profile, result)
    return _to_out(passport)
