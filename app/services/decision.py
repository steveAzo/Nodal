"""Decision & Explainability Service (Section 7, layer 6).

Turns a Passport plus a stated liquidity requirement into the explainable
Decision object from Section 8.4 - a recommendation, a capped amount and
duration, and the reasons/risk_flags a lending partner sees.

Three-way recommendation, driven by two different signals so they can't be
conflated: fraud_risk (an active anomaly signal) can decline outright, while
risk_tier (an overall creditworthiness band) only ever refers for human
review - a low-activity/thin-file profile is not treated the same as a
profile with real fraud indicators, even though both currently show up as
"risky" in a single-number view.
"""

from dataclasses import dataclass

from app.models.enums import RecommendationType, RiskLabel
from app.models.passport import Passport


@dataclass
class DecisionResult:
    recommendation: RecommendationType
    amount_ghs: float
    duration_hours: int
    risk_tier: RiskLabel
    reasons: list[str]
    risk_flags: list[str]


def build_decision(
    passport: Passport,
    requested_amount_ghs: float,
    requested_duration_hours: int | None,
) -> DecisionResult:
    capacity = float(passport.recommended_liquidity_line_ghs)
    nodal_score = float(passport.nodal_score)
    risk_tier = RiskLabel(passport.risk_tier)
    fraud_risk = RiskLabel(passport.fraud_risk)

    reasons: list[str] = []
    risk_flags: list[str] = list(passport.risk_flags)

    if fraud_risk == RiskLabel.high:
        recommendation = RecommendationType.decline
        amount_ghs = 0.0
        duration_hours = 0
        reasons.append(
            "Declined - active fraud risk indicators present. No amount is "
            "recommended regardless of Nodal Score."
        )
    elif capacity <= 0:
        recommendation = RecommendationType.refer
        amount_ghs = 0.0
        duration_hours = passport.recommended_duration_hours
        reasons.append(
            "Referred for manual review - insufficient assessed cash-flow "
            "history to recommend a safe facility amount yet."
        )
    elif risk_tier == RiskLabel.high:
        recommendation = RecommendationType.refer
        amount_ghs = min(requested_amount_ghs, capacity)
        duration_hours = requested_duration_hours or passport.recommended_duration_hours
        reasons.append(
            f"Referred for manual review - Nodal Score {nodal_score:.1f} puts this "
            "profile in the high risk_tier band; not auto-approved."
        )
    else:
        recommendation = RecommendationType.approve
        amount_ghs = min(requested_amount_ghs, capacity)
        duration_hours = passport.recommended_duration_hours
        if requested_duration_hours is not None:
            duration_hours = min(requested_duration_hours, passport.recommended_duration_hours)
        reasons.append(f"Nodal Score {nodal_score:.1f} (risk_tier: {risk_tier.value}).")
        if requested_amount_ghs > capacity:
            reasons.append(
                f"Requested GHS {requested_amount_ghs:,.2f} capped to the assessed safe "
                f"capacity of GHS {capacity:,.2f}."
            )
            risk_flags.append("Requested amount exceeded assessed safe capacity.")

    reasons.extend(passport.reasons)

    return DecisionResult(
        recommendation=recommendation,
        amount_ghs=round(amount_ghs, 2),
        duration_hours=duration_hours,
        risk_tier=risk_tier,
        reasons=reasons,
        risk_flags=risk_flags,
    )
