"""Marketplace / Routing Engine (Section 7, layer 7).

A hackathon prototype has one real sponsor relationship (Forms Capital), but
the spec calls for a routing engine that ranks *eligible* funding partners
against a profile's assessment - so this models a small, static partner
catalog rather than hard-coding a single partner into the decision logic.
Swapping this for a real partner registry later is a config change, not a
rewrite of the ranking logic.
"""

from dataclasses import dataclass

from app.models.enums import RiskLabel
from app.models.passport import Passport

_RISK_RANK = {RiskLabel.low: 0, RiskLabel.medium: 1, RiskLabel.high: 2}


@dataclass(frozen=True)
class Partner:
    partner_id: str
    name: str
    max_risk_tier: RiskLabel  # riskiest profile this partner will fund
    capacity_multiplier: float  # applied to the profile's recommended_liquidity_line_ghs
    price_adjustment_pct: float  # added on top of the profile's risk_adjusted_price_pct


# A more risk-tolerant partner charges more and offers less per profile -
# the trade-off that makes "nobody blocked, but priced for risk" concrete
# rather than just a slogan.
_CATALOG: list[Partner] = [
    Partner(
        partner_id="forms-capital",
        name="Forms Capital",
        max_risk_tier=RiskLabel.medium,
        capacity_multiplier=1.0,
        price_adjustment_pct=0.0,
    ),
    Partner(
        partner_id="community-mfi-trust",
        name="Community MFI Trust",
        max_risk_tier=RiskLabel.high,
        capacity_multiplier=0.5,
        price_adjustment_pct=0.8,
    ),
]


@dataclass
class MarketplaceOffer:
    partner_id: str
    partner_name: str
    amount_ghs: float
    duration_hours: int
    price_pct: float
    reasons: list[str]


def list_partners() -> list[Partner]:
    """The catalog itself, for discovery - e.g. GET /v1/marketplace/partners
    - so a valid issued_to_partner_id doesn't have to be reverse-engineered
    from an offers response or from reading this file."""
    return list(_CATALOG)


def rank_offers(passport: Passport) -> list[MarketplaceOffer]:
    """Eligible offers, ranked cheapest first. A partner is eligible if its
    risk appetite covers the profile's risk_tier; an active fraud signal
    takes the profile out of the marketplace entirely, same as it does for
    Decision generation - a risky-but-legitimate profile can still find a
    partner, a profile actively flagged for fraud can't find any."""
    if RiskLabel(passport.fraud_risk) == RiskLabel.high:
        return []

    capacity = float(passport.recommended_liquidity_line_ghs)
    if capacity <= 0:
        return []

    profile_risk_rank = _RISK_RANK[RiskLabel(passport.risk_tier)]
    base_price = float(passport.risk_adjusted_price_pct)

    offers: list[MarketplaceOffer] = []
    for partner in _CATALOG:
        if profile_risk_rank > _RISK_RANK[partner.max_risk_tier]:
            continue

        # Floored at 50, not just rounded: an eligible partner offering GHS 0
        # is nonsensical, and round-half-to-even can otherwise land exactly
        # there for small capacities (e.g. round(25 / 50) * 50 == 0).
        amount = max(50, round((capacity * partner.capacity_multiplier) / 50) * 50)
        offers.append(
            MarketplaceOffer(
                partner_id=partner.partner_id,
                partner_name=partner.name,
                amount_ghs=float(amount),
                duration_hours=passport.recommended_duration_hours,
                price_pct=round(base_price + partner.price_adjustment_pct, 1),
                reasons=[
                    f"risk_tier '{passport.risk_tier}' is within {partner.name}'s accepted "
                    f"range (up to '{partner.max_risk_tier.value}')."
                ],
            )
        )

    offers.sort(key=lambda offer: offer.price_pct)
    return offers
