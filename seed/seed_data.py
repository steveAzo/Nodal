"""Synthetic demo data for dev/testing.

Populates a handful of Nodal profiles across all three node types, each with
sources, an active consent, and (where relevant) a 90-day trailing transaction
history — so Phase 3's scoring engine has something realistic to compute over.

Re-running this script clears any previously seeded demo profiles first
(identified by the "GHA-DEMO-" Ghana Card prefix) and recreates them, so it's
safe to run repeatedly.

Run from the project root: python -m seed.seed_data
"""

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.consent import Consent
from app.models.enums import (
    ConsentStatus,
    Direction,
    EntryMethod,
    EventType,
    IdentityVerificationStatus,
    NodeType,
    OnboardingChannel,
    SourceType,
)
from app.models.ingestion_event import IngestionEvent
from app.models.profile import Profile, Source

RNG_SEED = 42
WINDOW_DAYS = 90
DEFAULT_SCOPES = ["liquidity_assessment", "eligibility_calculation", "fraud_detection"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clear_demo_profiles(db: Session) -> None:
    demo_profiles = db.scalars(
        select(Profile).where(Profile.ghana_card_number.like("GHA-DEMO-%"))
    ).all()
    for profile in demo_profiles:
        db.delete(profile)
    db.commit()


def _grant_consent(db: Session, profile: Profile, source_type: SourceType) -> Consent:
    now = _utcnow()
    consent = Consent(
        profile_id=profile.profile_id,
        source_type=source_type,
        scopes=DEFAULT_SCOPES,
        excluded_scopes=["initiate_transactions"],
        granted_at=now,
        expires_at=now + timedelta(days=90),
        status=ConsentStatus.active,
    )
    db.add(consent)
    db.flush()
    return consent


def _add_source(
    db: Session,
    profile: Profile,
    source_type: SourceType,
    provider: str,
    tier: int,
    entry_method: EntryMethod,
    *,
    entry_value: str | None = None,
    consent: Consent | None = None,
    connected_days_ago: int = 0,
) -> Source:
    # Backdating matters: the fraud sub-score flags sources connected in the
    # last 3 days as "new" (Section 10). An "established" demo profile with
    # connected_at defaulting to right-now would trigger that flag for no
    # real reason every time the script runs.
    connected_at = _utcnow() - timedelta(days=connected_days_ago)
    source = Source(
        profile_id=profile.profile_id,
        source_type=source_type,
        provider=provider,
        tier=tier,
        entry_method=entry_method,
        entry_value=entry_value,
        consent_id=consent.consent_id if consent else None,
        connected_at=connected_at,
        last_synced_at=_utcnow() if tier >= 1 else None,
    )
    db.add(source)
    db.flush()
    return source


def _generate_transactions(
    db: Session,
    profile: Profile,
    source: Source,
    consent: Consent,
    *,
    count: int,
    amount_range: tuple[float, float],
    inflow_ratio: float,
    reference_prefix: str,
    rng: random.Random,
    growth: bool = False,
) -> None:
    window_start = _utcnow() - timedelta(days=WINDOW_DAYS)
    for i in range(count):
        day_offset = (i / count) * WINDOW_DAYS if growth else rng.uniform(0, WINDOW_DAYS)
        occurred_at = window_start + timedelta(days=day_offset, seconds=rng.uniform(0, 86400))
        growth_factor = 1 + (day_offset / WINDOW_DAYS) if growth else 1.0
        amount = round(rng.uniform(*amount_range) * growth_factor, 2)
        direction = Direction.in_ if rng.random() < inflow_ratio else Direction.out
        db.add(
            IngestionEvent(
                profile_id=profile.profile_id,
                source_id=source.id,
                consent_id=consent.consent_id,
                event_type=EventType.transaction,
                direction=direction,
                amount_ghs=amount,
                reference=f"{reference_prefix}{i:04d}",
                occurred_at=occurred_at,
            )
        )
    db.flush()


def seed(db: Session, rng: random.Random) -> list[str]:
    created: list[str] = []

    # 1. MoMo Agent — established, Tier 3, high-frequency small transactions.
    #    This is the richest node per the spec — the one the demo should lean on.
    agent_strong = Profile(
        node_type=NodeType.momo_agent,
        onboarding_channel=OnboardingChannel.agent_assisted,
        assisting_agent_id="AG-00001",
        ghana_card_number="GHA-DEMO-0001",
        identity_verification_status=IdentityVerificationStatus.api_verified,
    )
    db.add(agent_strong)
    db.flush()
    consent = _grant_consent(db, agent_strong, SourceType.momo)
    source = _add_source(
        db, agent_strong, SourceType.momo, "MTN", 3, EntryMethod.api_link,
        consent=consent, connected_days_ago=150,
    )
    _generate_transactions(
        db, agent_strong, source, consent,
        count=300, amount_range=(60, 850), inflow_ratio=0.6,
        reference_prefix="MP-STRONG-", rng=rng,
    )
    created.append(f"{agent_strong.profile_id}  momo_agent | strong, Tier 3, 300 txns")

    # 2. MoMo Agent — thin file: only a token-verified source, no transaction
    #    history yet. Exercises the "missing category isn't scored as zero" rule.
    agent_thin = Profile(
        node_type=NodeType.momo_agent,
        onboarding_channel=OnboardingChannel.ussd,
        ghana_card_number="GHA-DEMO-0002",
        identity_verification_status=IdentityVerificationStatus.self_declared,
    )
    db.add(agent_thin)
    db.flush()
    _add_source(
        db, agent_thin, SourceType.momo, "Telecel", 1, EntryMethod.receipt_id,
        entry_value="TL240801.1200.B00099",
    )
    created.append(f"{agent_thin.profile_id}  momo_agent | thin file, Tier 1, no txn history")

    # 3. Individual — Tier 3 momo + Tier 1 utility, moderate activity.
    individual = Profile(
        node_type=NodeType.individual,
        onboarding_channel=OnboardingChannel.app,
        ghana_card_number="GHA-DEMO-0003",
        identity_verification_status=IdentityVerificationStatus.self_declared,
    )
    db.add(individual)
    db.flush()
    consent_i = _grant_consent(db, individual, SourceType.momo)
    source_i = _add_source(
        db, individual, SourceType.momo, "AT", 3, EntryMethod.api_link,
        consent=consent_i, connected_days_ago=150,
    )
    _generate_transactions(
        db, individual, source_i, consent_i,
        count=40, amount_range=(10, 250), inflow_ratio=0.45,
        reference_prefix="AT-IND-", rng=rng,
    )
    _add_source(
        db, individual, SourceType.utility, "ECG", 1, EntryMethod.token_id,
        entry_value="2222-3333-4444-5555-6666", connected_days_ago=150,
    )
    created.append(f"{individual.profile_id}  individual | Tier 3 momo (40 txns) + Tier 1 utility")

    # 4. SME — Tier 3 payment gateway with a growth trend across the window,
    #    the strongest "Business Activity" signal for the scoring engine.
    sme = Profile(
        node_type=NodeType.sme,
        onboarding_channel=OnboardingChannel.app,
        ghana_card_number="GHA-DEMO-0004",
        identity_verification_status=IdentityVerificationStatus.api_verified,
    )
    db.add(sme)
    db.flush()
    consent_s = _grant_consent(db, sme, SourceType.payment_gateway)
    source_s = _add_source(
        db, sme, SourceType.payment_gateway, "Paystack", 3, EntryMethod.api_link,
        consent=consent_s, connected_days_ago=150,
    )
    _generate_transactions(
        db, sme, source_s, consent_s,
        count=90, amount_range=(120, 700), inflow_ratio=1.0,
        reference_prefix="PSK-", rng=rng, growth=True,
    )
    created.append(f"{sme.profile_id}  sme | Tier 3, 90-day growth trend, 90 txns")

    db.commit()
    return created


def main() -> None:
    Base.metadata.create_all(bind=engine)
    rng = random.Random(RNG_SEED)
    db = SessionLocal()
    try:
        _clear_demo_profiles(db)
        created = seed(db, rng)
    finally:
        db.close()

    print(f"Seeded {len(created)} demo profiles:")
    for line in created:
        print(f"  - {line}")


if __name__ == "__main__":
    main()
