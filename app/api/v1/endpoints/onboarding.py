from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import NodeType
from app.models.profile import Profile, Source
from app.schemas.profile import OnboardingRequest, ProfileOut

router = APIRouter(tags=["onboarding"])


@router.post(
    "/onboarding/{node_type}",
    response_model=ProfileOut,
    status_code=status.HTTP_201_CREATED,
)
def create_profile(
    node_type: NodeType,
    payload: OnboardingRequest,
    db: Session = Depends(get_db),
) -> ProfileOut:
    if payload.onboarding_channel == "agent_assisted" and not payload.assisting_agent_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="assisting_agent_id is required when onboarding_channel is agent_assisted",
        )

    profile = Profile(
        node_type=node_type,
        onboarding_channel=payload.onboarding_channel,
        assisting_agent_id=payload.assisting_agent_id,
        ghana_card_number=payload.identity.ghana_card_number,
        identity_verification_status=payload.identity.verification_status,
    )
    profile.sources = [
        Source(
            source_type=s.source_type,
            provider=s.provider,
            entry_method=s.entry_method,
            entry_value=s.value,
            tier=s.tier,
        )
        for s in payload.sources
    ]

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return ProfileOut.from_model(profile)


@router.get("/onboarding/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: str, db: Session = Depends(get_db)) -> ProfileOut:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileOut.from_model(profile)
