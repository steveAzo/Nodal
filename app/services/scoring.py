"""Deterministic weighted-sum scoring engine (Section 10).

Ships a rules-based implementation before any ML-based scoring, per the
spec's explicit instruction — the explainability requirement (Section 8.4)
depends on tracing every point of the score to a named input, which a
weighted sum can do and a trained model can't without extra work.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import BusinessActivityLabel, LedgerEntryType, RiskLabel, SourceType
from app.models.ingestion_event import IngestionEvent
from app.models.ledger import LedgerEntry
from app.models.profile import Profile, Source

WINDOW_DAYS = 90

CASH_FLOW_SOURCE_TYPES = {SourceType.momo, SourceType.bank, SourceType.payment_gateway}

# GHS/day turnover treated as "moderate" (50%) business activity per node
# type. Tuned by hand, not measured against a real population — a defensible
# starting point, to be replaced once enough live profiles exist to fit
# these against actual distributions.
BUSINESS_ACTIVITY_BASELINE_GHS = {
    "individual": 60.0,
    "sme": 400.0,
    "momo_agent": 1000.0,
}

# Sub-score weights from Section 10. Fraud is stored as a "safety" value
# (100 = no risk detected) so it combines additively like the others; the
# spec's "inverse weight" just means high fraud risk pulls the composite
# down rather than up.
WEIGHTS = {
    "business_activity": 0.25,
    "transaction_consistency": 0.20,
    "liquidity_reliability": 0.20,
    "repayment_reliability": 0.25,
    "fraud_safety": 0.10,
}

_RISK_BAND_FACILITY = {
    # risk_tier: (multiplier on avg daily turnover, duration hours)
    RiskLabel.low: (2.3, 24),
    RiskLabel.medium: (1.5, 16),
    RiskLabel.high: (0.8, 8),
}


@dataclass
class ScoringResult:
    business_activity_label: BusinessActivityLabel
    transaction_volume_ghs: float
    avg_daily_turnover_ghs: float
    transaction_consistency_pct: float
    liquidity_reliability_score: float
    repayment_reliability_score: float
    fraud_risk_label: RiskLabel
    nodal_score: float
    risk_tier: RiskLabel
    confidence: dict[str, int]
    recommended_liquidity_line_ghs: float
    recommended_duration_hours: int
    risk_adjusted_price_pct: float
    reasons: list[str]
    risk_flags: list[str]
    excluded_categories: list[str]
    sub_scores: dict[str, float | None]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _max_tier(sources: list[Source], types: set[SourceType]) -> int:
    tiers = [s.tier for s in sources if s.source_type in types]
    return max(tiers, default=0)


def _daily_series(events: list[IngestionEvent]) -> list[dict]:
    """One entry per day over the trailing window, zero-filled for days with
    no activity — the zero-fill matters: a profile with three huge days and
    87 silent ones must score worse on consistency than one with 90 steady
    days of the same total volume."""
    buckets: dict = defaultdict(lambda: {"count": 0, "net": 0.0})
    for event in events:
        day = event.occurred_at.date()
        amount = float(event.amount_ghs or 0)
        buckets[day]["count"] += 1
        buckets[day]["net"] += amount if event.direction == "in" else -amount

    today = _utcnow().date()
    return [buckets.get(today - timedelta(days=i), {"count": 0, "net": 0.0}) for i in range(WINDOW_DAYS)]


def _business_activity(
    events: list[IngestionEvent], node_type: str
) -> tuple[float, BusinessActivityLabel, float, float]:
    volume = sum(float(e.amount_ghs or 0) for e in events)
    avg_daily = volume / WINDOW_DAYS
    baseline = BUSINESS_ACTIVITY_BASELINE_GHS.get(node_type, 200.0)
    pct = min(100.0, (avg_daily / baseline) * 50)
    label = (
        BusinessActivityLabel.weak if pct < 33
        else BusinessActivityLabel.moderate if pct < 67
        else BusinessActivityLabel.strong
    )
    return pct, label, volume, avg_daily


def _transaction_consistency(events: list[IngestionEvent]) -> float:
    """100 - coefficient of variation of daily transaction counts (Section
    10's exact metric). Lower variance day-to-day = more predictable = safer
    to plan liquidity around."""
    counts = [day["count"] for day in _daily_series(events)]
    avg = mean(counts)
    if avg == 0:
        return 0.0
    cv = pstdev(counts) / avg
    return max(0.0, min(100.0, 100.0 - cv * 100))


def _liquidity_reliability(events: list[IngestionEvent]) -> float:
    """Share of active days that weren't net cash-negative. There's no
    explicit 'shortage event' in this schema (that concept belongs to a
    different product surface entirely) — this is a deliberate proxy from
    the transaction stream we do have: a day where outflow exceeds inflow
    is read as liquidity strain."""
    series = [day for day in _daily_series(events) if day["count"] > 0]
    if not series:
        return 50.0  # unreachable given the caller's gating, kept as a guard
    strain_days = sum(1 for day in series if day["net"] < 0)
    return max(0.0, min(100.0, 100.0 * (1 - strain_days / len(series))))


def _fraud_safety(events: list[IngestionEvent], sources: list[Source]) -> tuple[float, list[str]]:
    """Rule-based anomaly checks only — no trained model. Device-fingerprint
    signals from Section 10 aren't included: this prototype doesn't capture
    any device telemetry on ingestion, so there's nothing real to check
    rather than a fabricated placeholder."""
    counts = [day["count"] for day in _daily_series(events)]
    avg = mean(counts)
    threshold = max(3 * avg, 5)
    spike_days = sum(1 for count in counts if count > threshold)

    flags: list[str] = []
    penalty = 0.0
    if spike_days:
        flags.append(f"Transaction velocity spike on {spike_days} day(s) vs. the 90-day average.")
        penalty += 40.0

    recent_cutoff = _utcnow() - timedelta(days=3)
    new_sources = [
        s for s in sources
        if s.source_type in CASH_FLOW_SOURCE_TYPES and s.connected_at is not None and s.connected_at >= recent_cutoff
    ]
    if new_sources:
        flags.append(f"{len(new_sources)} newly connected data source(s) within the last 3 days.")
        penalty += 20.0

    return max(0.0, 100.0 - penalty), flags


def _weighted_composite(sub_scores: dict[str, float | None]) -> float:
    """The core rule from Section 2: a missing category is excluded from the
    sum, never scored as zero. Renormalising by the weight actually included
    is what makes that true — otherwise a profile missing three categories
    would be capped near the weight of the one it has."""
    weighted_sum = 0.0
    total_weight = 0.0
    for key, weight in WEIGHTS.items():
        value = sub_scores.get(key)
        if value is None:
            continue
        weighted_sum += value * weight
        total_weight += weight
    if total_weight == 0:
        return 50.0
    return weighted_sum / total_weight


def _recommended_facility(avg_daily_turnover_ghs: float, risk_tier: RiskLabel) -> tuple[float, int]:
    if avg_daily_turnover_ghs <= 0:
        return 0.0, 0
    multiplier, duration_hours = _RISK_BAND_FACILITY[risk_tier]
    # Floored at 50, not just rounded: real (positive) turnover recommending
    # a GHS 0 facility is nonsensical, and round-half-to-even can otherwise
    # land exactly there for small turnovers.
    rounded = max(50, round((avg_daily_turnover_ghs * multiplier) / 50) * 50)
    return float(rounded), duration_hours


def compute_passport(db: Session, profile: Profile) -> ScoringResult:
    sources = list(profile.sources)
    cash_flow_tier = _max_tier(sources, CASH_FLOW_SOURCE_TYPES)
    stability_tier = _max_tier(sources, {SourceType.utility})
    repayment_tier = _max_tier(sources, {SourceType.nodal_ledger})
    identity_tier = 3 if profile.identity_verification_status == "api_verified" else 0
    node_type = str(profile.node_type)

    events: list[IngestionEvent] = []
    if cash_flow_tier >= 1:
        source_ids = [s.id for s in sources if s.source_type in CASH_FLOW_SOURCE_TYPES]
        window_start = _utcnow() - timedelta(days=WINDOW_DAYS)
        events = list(
            db.scalars(
                select(IngestionEvent).where(
                    IngestionEvent.source_id.in_(source_ids),
                    IngestionEvent.occurred_at >= window_start,
                )
            ).all()
        )

    reasons: list[str] = []
    risk_flags: list[str] = []
    excluded: list[str] = []
    sub_scores: dict[str, float | None] = {}

    if cash_flow_tier >= 1 and events:
        activity_pct, business_activity_label, transaction_volume_ghs, avg_daily_turnover_ghs = (
            _business_activity(events, node_type)
        )
        sub_scores["business_activity"] = activity_pct
        sub_scores["transaction_consistency"] = _transaction_consistency(events)
        sub_scores["liquidity_reliability"] = _liquidity_reliability(events)
        fraud_safety_value, fraud_flags = _fraud_safety(events, sources)
        sub_scores["fraud_safety"] = fraud_safety_value
        risk_flags.extend(fraud_flags)
        reasons.append(
            f"{len(events)} transactions over the trailing {WINDOW_DAYS} days "
            f"(GHS {transaction_volume_ghs:,.2f} volume) from Tier {cash_flow_tier} cash-flow source(s)."
        )
    else:
        business_activity_label = BusinessActivityLabel.weak
        transaction_volume_ghs = 0.0
        avg_daily_turnover_ghs = 0.0
        for key in ("business_activity", "transaction_consistency", "liquidity_reliability", "fraud_safety"):
            sub_scores[key] = None
        excluded.extend(["business_activity", "transaction_consistency", "liquidity_reliability", "fraud_safety"])
        reasons.append(
            "No Tier 1+ cash-flow source with transaction history - those four sub-scores are "
            "excluded from the weighted sum (Section 2), not scored as zero."
        )

    # Repayment reliability is the one explicit override of the exclusion
    # rule (Section 10): always included, defaulting neutral rather than
    # excluded, since every profile needs a first eligibility read.
    repayment_events: list[LedgerEntry] = []
    if repayment_tier >= 1:
        repayment_events = list(
            db.scalars(
                select(LedgerEntry).where(
                    LedgerEntry.profile_id == profile.profile_id,
                    LedgerEntry.entry_type == LedgerEntryType.repayment,
                )
            ).all()
        )

    if repayment_events:
        on_time_count = sum(1 for event in repayment_events if event.on_time)
        repayment_value = (on_time_count / len(repayment_events)) * 100
        reasons.append(
            f"{on_time_count}/{len(repayment_events)} prior Nodal-financed repayments made on time."
        )
    elif repayment_tier >= 1:
        repayment_value = 50.0
        reasons.append(
            "Nodal ledger connected (facility disbursed), but no repayment recorded yet - "
            "neutral prior still applied."
        )
    else:
        repayment_value = 50.0
        reasons.append("First-time borrower - neutral prior applied to repayment reliability.")

    sub_scores["repayment_reliability"] = repayment_value

    nodal_score = _weighted_composite(sub_scores)
    risk_tier = (
        RiskLabel.low if nodal_score >= 75
        else RiskLabel.medium if nodal_score >= 50
        else RiskLabel.high
    )

    fraud_safety = sub_scores.get("fraud_safety")
    fraud_risk_label = (
        RiskLabel.low if fraud_safety is None or fraud_safety >= 80
        else RiskLabel.medium if fraud_safety >= 50
        else RiskLabel.high
    )

    recommended_line, duration_hours = _recommended_facility(avg_daily_turnover_ghs, risk_tier)
    price_pct = round(max(0.5, min(2.5, 2.5 - (nodal_score / 100) * 1.5)), 1)

    return ScoringResult(
        business_activity_label=business_activity_label,
        transaction_volume_ghs=round(transaction_volume_ghs, 2),
        avg_daily_turnover_ghs=round(avg_daily_turnover_ghs, 2),
        transaction_consistency_pct=round(sub_scores.get("transaction_consistency") or 0.0, 2),
        liquidity_reliability_score=round(sub_scores.get("liquidity_reliability") or 0.0, 2),
        repayment_reliability_score=round(repayment_value, 2),
        fraud_risk_label=fraud_risk_label,
        nodal_score=round(nodal_score, 2),
        risk_tier=risk_tier,
        confidence={
            "identity": identity_tier,
            "cash_flow": cash_flow_tier,
            "stability": stability_tier,
            "repayment_history": repayment_tier,
        },
        recommended_liquidity_line_ghs=recommended_line,
        recommended_duration_hours=duration_hours,
        risk_adjusted_price_pct=price_pct,
        reasons=reasons,
        risk_flags=risk_flags,
        excluded_categories=excluded,
        sub_scores=sub_scores,
    )
