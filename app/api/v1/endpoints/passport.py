from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.passport import Passport
from app.models.profile import Profile
from app.schemas.passport import ConfidenceByCategory, PassportOut, RecalculateRequest
from app.services.passport_service import get_or_compute_passport, recalculate_passport

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
        risk_tier=passport.risk_tier,
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


@router.get("/passport/{profile_id}", response_model=PassportOut)
def get_passport(profile_id: str, db: Session = Depends(get_db)) -> PassportOut:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return _to_out(get_or_compute_passport(db, profile))


@router.post("/score/recalculate", response_model=PassportOut)
def recalculate_score(payload: RecalculateRequest, db: Session = Depends(get_db)) -> PassportOut:
    """Internal endpoint (Section 9): meant to be triggered by the
    recalculation events in Section 10 (new Tier 3+ transaction, document
    verified, token verified, repayment posted, consent revoked), not called
    directly by end-user clients. Exposed as a real endpoint here since this
    prototype has no internal service mesh to fire it automatically yet -
    see the TODO in the ingest endpoint.
    """
    profile = db.get(Profile, payload.profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return _to_out(recalculate_passport(db, profile))
