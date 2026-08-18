from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.decision import Decision
from app.models.profile import Profile
from app.schemas.decision import (
    DecisionOut,
    DecisionRequest,
    MarketplaceOfferOut,
    MarketplaceOffersResponse,
    PartnerOut,
)
from app.services.decision import build_decision
from app.services.marketplace import list_partners, rank_offers
from app.services.passport_service import get_or_compute_passport

router = APIRouter(tags=["decision"])


@router.get("/marketplace/partners", response_model=list[PartnerOut])
def get_marketplace_partners() -> list[PartnerOut]:
    """The partner catalog itself - where a caller finds a valid
    issued_to_partner_id/partner_id before ever generating a decision or
    requesting offers."""
    return [
        PartnerOut(
            partner_id=partner.partner_id,
            name=partner.name,
            max_risk_tier=partner.max_risk_tier,
            capacity_multiplier=partner.capacity_multiplier,
            price_adjustment_pct=partner.price_adjustment_pct,
        )
        for partner in list_partners()
    ]


@router.post("/decision", response_model=DecisionOut, status_code=status.HTTP_201_CREATED)
def create_decision(payload: DecisionRequest, db: Session = Depends(get_db)) -> DecisionOut:
    profile = db.get(Profile, payload.profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    passport = get_or_compute_passport(db, profile)
    result = build_decision(passport, payload.requested_amount_ghs, payload.requested_duration_hours)

    decision = Decision(
        profile_id=payload.profile_id,
        recommendation=result.recommendation,
        amount_ghs=result.amount_ghs,
        duration_hours=result.duration_hours,
        risk_tier=result.risk_tier,
        reasons=result.reasons,
        risk_flags=result.risk_flags,
        issued_to_partner_id=payload.issued_to_partner_id,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    return DecisionOut(
        decision_id=decision.decision_id,
        profile_id=decision.profile_id,
        recommendation=decision.recommendation,
        amount_ghs=float(decision.amount_ghs),
        duration_hours=decision.duration_hours,
        risk_tier=decision.risk_tier,
        reasons=decision.reasons,
        risk_flags=decision.risk_flags,
        issued_at=decision.issued_at,
        issued_to_partner_id=decision.issued_to_partner_id,
    )


@router.get("/marketplace/offers", response_model=MarketplaceOffersResponse)
def get_marketplace_offers(profile_id: str, db: Session = Depends(get_db)) -> MarketplaceOffersResponse:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    passport = get_or_compute_passport(db, profile)
    offers = rank_offers(passport)

    return MarketplaceOffersResponse(
        profile_id=profile.profile_id,
        generated_at=datetime.now(timezone.utc),
        offers=[
            MarketplaceOfferOut(
                partner_id=offer.partner_id,
                partner_name=offer.partner_name,
                amount_ghs=offer.amount_ghs,
                duration_hours=offer.duration_hours,
                price_pct=offer.price_pct,
                reasons=offer.reasons,
            )
            for offer in offers
        ],
    )
