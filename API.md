# Nodal Liquidity Passport — API Integration Reference

This document is the complete contract for the Nodal backend: every endpoint, every request/response shape, every enum, every error case. It's written to be consumed directly — by a person integrating the frontend, or by an LLM/AI coding assistant generating that integration — without needing to read backend source.

## 1. Basics

| | |
|---|---|
| **Base URL (dev)** | `http://127.0.0.1:8000` |
| **API prefix** | `/v1` (every endpoint below is `{base}/v1/{path}`, except `/health`) |
| **Content-Type (JSON endpoints)** | `application/json` |
| **Content-Type (file upload endpoints)** | `multipart/form-data` — let your HTTP client set this automatically from a `FormData` body; don't set it by hand |
| **Auth** | **None implemented yet.** No `Authorization` header, no API key, no cookies. Every endpoint is open. Do not build auth-dependent UI logic against this backend yet — it isn't there. |
| **CORS** | Wide open (`allow_origins: ["*"]`) for this build stage. Fine for local dev against any port. |
| **IDs** | All `profile_id`, `consent_id`, `decision_id`, etc. are UUIDv4 strings, e.g. `"5bb7a600-9af0-4b31-925d-57a5712a9f52"`. |
| **Timestamps** | ISO 8601 with UTC offset, e.g. `"2026-08-19T00:04:19.237121Z"`. Always send/expect UTC. |
| **Money** | GHS, as JSON numbers with 2 decimal places, e.g. `557.0`. Never a string. |

### Error shape

Every non-2xx response has this exact shape:

```json
{ "detail": "human-readable message, or a validation error array" }
```

- `404` — the thing referenced (profile, decision, consent) doesn't exist.
- `403` — action blocked by a business rule (usually: no active consent).
- `409` — conflict (e.g. trying to settle an already-settled decision).
- `400` — the uploaded file/content couldn't be processed (e.g. not a real image).
- `413` — uploaded file too large (8MB cap on all file-upload endpoints).
- `422` — request body failed schema validation. `detail` is FastAPI's standard array:
  ```json
  { "detail": [{ "type": "...", "loc": ["body", "field_name"], "msg": "...", "input": "..." }] }
  ```

---

## 2. Enums & the tier model

**Canonical source:** `GET /v1/lookup/enums` returns this live, and will include anything added after this document was written. The list below is a snapshot for convenience.

| Enum | Values |
|---|---|
| `NodeType` | `individual`, `sme`, `momo_agent` |
| `OnboardingChannel` | `app`, `ussd`, `agent_assisted` |
| `IdentityVerificationStatus` | `self_declared`, `api_verified` |
| `SourceType` | `utility`, `momo`, `bank`, `payment_gateway`, `nodal_ledger`, `receipt` |
| `EntryMethod` | `token_id`, `receipt_id`, `document_upload`, `api_link` |
| `ConsentScope` | `liquidity_assessment`, `eligibility_calculation`, `fraud_detection`, `initiate_transactions` |
| `ConsentStatus` | `active`, `expired`, `revoked` |
| `EventType` | `transaction`, `balance_snapshot`, `document` |
| `Direction` | `in`, `out` |
| `BusinessActivityLabel` | `weak`, `moderate`, `strong` |
| `RiskLabel` | `low`, `medium`, `high` (used for both `fraud_risk` and `risk_tier`) |
| `RecommendationType` | `approve`, `decline`, `refer` |
| `LedgerEntryType` | `disbursement`, `repayment` |
| `SettlementRail` | `domestic`, `stablecoin` (this backend only ever produces `domestic`) |

### Tiers (0–4)

Every `Source` carries a `tier`, independent per data source — a profile can be Tier 3 on `momo` and Tier 0 on `utility` at once.

| Tier | Meaning |
|---|---|
| `0` | Self-declared — nothing verified yet. |
| `1` | Token/receipt verified — a code checked against the expected format. |
| `2` | Document uploaded — OCR-extracted, cross-matched against Tier 1 data if any exists. |
| `3` | API-linked — live consented connection; recalculates on every new event. |
| `4` | Multi-source reconciled — two+ Tier 3 sources cross-validated. |

---

## 3. Core objects, referenced throughout

### Profile

```json
{
  "profile_id": "uuid",
  "node_type": "individual | sme | momo_agent",
  "onboarding_channel": "app | ussd | agent_assisted",
  "identity": {
    "ghana_card_number": "string",
    "verification_status": "self_declared | api_verified"
  },
  "created_at": "datetime",
  "sources": [
    {
      "source_type": "utility | momo | bank | payment_gateway | nodal_ledger | receipt",
      "provider": "string",
      "tier": 0,
      "entry_method": "token_id | receipt_id | document_upload | api_link",
      "connected_at": "datetime",
      "consent_id": "uuid | null",
      "last_synced_at": "datetime | null"
    }
  ]
}
```

### Consent

```json
{
  "consent_id": "uuid",
  "profile_id": "uuid",
  "source_type": "SourceType",
  "scopes": ["liquidity_assessment", "eligibility_calculation", "fraud_detection"],
  "excluded_scopes": ["initiate_transactions"],
  "granted_at": "datetime",
  "expires_at": "datetime",
  "status": "active | expired | revoked",
  "revoked_at": "datetime | null"
}
```

### Passport

```json
{
  "profile_id": "uuid",
  "generated_at": "datetime",
  "business_activity": "weak | moderate | strong",
  "window_days": 90,
  "transaction_volume_ghs": 53692.97,
  "avg_daily_turnover_ghs": 596.59,
  "transaction_consistency_pct": 51.17,
  "liquidity_reliability_score": 100.0,
  "repayment_reliability_score": 50.0,
  "fraud_risk": "low | medium | high",
  "nodal_score": 71.38,
  "risk_tier": "low | medium | high",
  "confidence_by_category": {
    "identity": 3,
    "cash_flow": 3,
    "stability": 0,
    "repayment_history": 0
  },
  "recommended_liquidity_line_ghs": 900.0,
  "recommended_duration_hours": 16,
  "risk_adjusted_price_pct": 1.4,
  "reasons": ["string", "..."],
  "risk_flags": ["string", "..."],
  "excluded_categories": ["liquidity_reliability"],
  "sub_scores": {
    "business_activity": 74.57,
    "transaction_consistency": 51.17,
    "liquidity_reliability": 100.0,
    "repayment_reliability": 50.0,
    "fraud_safety": 100.0
  }
}
```

Notes for the frontend:
- Any value in `sub_scores` can be `null` — that means it's **excluded** from the score (not zero), and its name will appear in `excluded_categories`. Render this distinctly from a low score — it means "no data yet," not "bad."
- `reasons` and `risk_flags` are human-readable strings meant to be displayed directly — don't try to parse them, just show them.

---

## 4. Endpoints

### Onboarding & Profiles

#### `POST /v1/onboarding/{node_type}`
Creates a new profile.

**Path params:** `node_type` — `individual | sme | momo_agent`

**Request body:**
```json
{
  "onboarding_channel": "app | ussd | agent_assisted",
  "assisting_agent_id": "string | null, REQUIRED if onboarding_channel is agent_assisted",
  "identity": {
    "ghana_card_number": "string, required",
    "verification_status": "self_declared | api_verified, optional, defaults to self_declared"
  },
  "sources": [
    {
      "source_type": "SourceType, required",
      "provider": "string, required, e.g. 'ECG', 'MTN', 'Paystack'",
      "entry_method": "EntryMethod, required",
      "value": "string | null, e.g. a token/receipt id",
      "tier": "int 0-4, optional, defaults to 0"
    }
  ]
}
```

**Response `201`:** a [Profile](#profile) object.

**Errors:**
- `422` — `agent_assisted` channel without `assisting_agent_id`.

---

#### `GET /v1/onboarding/{profile_id}`
Fetch one profile.

**Response `200`:** a [Profile](#profile) object.
**Errors:** `404` — profile not found.

---

#### `GET /v1/profiles`
List profiles (for admin/debug views — not in the original spec's endpoint table, added for convenience).

**Query params:** `node_type` (optional filter), `limit` (optional, default 50, max 200)

**Response `200`:** array of [Profile](#profile) objects.

---

### Consent

#### `POST /v1/consent`
Grants a consent record. **Required before any ingestion (`/v1/ingest/*`) for that `source_type` will be accepted.**

**Request body:**
```json
{
  "profile_id": "uuid, required",
  "source_type": "SourceType, required",
  "scopes": ["ConsentScope, at least 1 required"],
  "excluded_scopes": ["ConsentScope, optional, defaults to []"]
}
```

**Response `201`:** a [Consent](#consent) object. `expires_at` is computed server-side as `granted_at + 90 days` — never send it yourself.

---

#### `DELETE /v1/consent/{consent_id}`
Revokes a consent. Stops future ingestion for that source_type immediately; does **not** retroactively alter anything already decided/disbursed.

**Response `200`:** the [Consent](#consent) object, `status: "revoked"`.
**Errors:** `404` — consent not found.

---

### Verification

#### `POST /v1/verify/token`
Validates a manually-entered token/receipt code against the expected format for that provider. On success, upgrades the matching `Source` to Tier 1.

**Request body:**
```json
{
  "profile_id": "uuid, required",
  "source_type": "SourceType, required",
  "value": "string, required — must exactly match a Source.entry_value already on this profile"
}
```

**Response `200`:**
```json
{
  "profile_id": "uuid",
  "source_type": "SourceType",
  "verified": true,
  "tier": 1,
  "verified_at": "datetime | null (null if verified: false)",
  "message": "string"
}
```
Note: a format mismatch returns `200` with `verified: false`, not an error — it's a legitimate outcome, not a client mistake.

**Errors:** `404` — no `Source` on this profile matches that `source_type` + exact `value` (onboard it first).

---

#### `POST /v1/verify/document`
Uploads a photo of a document (utility bill, statement). OCRs it, searches for a reference code shaped like that provider's format, and on success upgrades/creates a Tier 2 `Source`. **Does not extract an amount** — see `/v1/ingest/receipt` for that.

**Content-Type:** `multipart/form-data`

**Form fields:**
| Field | Type | Required |
|---|---|---|
| `profile_id` | uuid string | yes |
| `source_type` | SourceType string | yes |
| `provider` | string | yes |
| `file` | file (JPG/PNG only, ≤8MB, **no PDF**) | yes |

**Response `200`:**
```json
{
  "profile_id": "uuid",
  "source_type": "SourceType",
  "verified": true,
  "tier": 2,
  "verified_at": "datetime | null",
  "extracted_reference": "string | null",
  "cross_matched_tier1": true,
  "message": "string"
}
```
If no reference found, `verified: false`, `extracted_reference: null`, and `message` may include a "did you mean a different source_type" hint.

**Errors:**
- `404` — profile not found.
- `400` — file isn't a readable image.
- `413` — file over 8MB.

---

### Ingestion

#### `POST /v1/ingest/{source_type}`
Records a live transaction/balance event from an already-consented source. Creates the `Source` at Tier 3 if it doesn't exist yet. **Triggers an immediate score recalculation.**

**Path params:** `source_type` — any `SourceType` **except** `receipt` (that has its own endpoint below).

**Request body:**
```json
{
  "profile_id": "uuid, required",
  "provider": "string, required",
  "event_type": "EventType, required",
  "occurred_at": "datetime, required",
  "amount_ghs": "number >= 0 | null",
  "direction": "in | out | null",
  "reference": "string | null"
}
```

**Response `201`:**
```json
{
  "id": "uuid",
  "profile_id": "uuid",
  "source_id": "uuid",
  "consent_id": "uuid",
  "event_type": "EventType",
  "direction": "in | out | null",
  "amount_ghs": 150.0,
  "reference": "string | null",
  "occurred_at": "datetime",
  "ingested_at": "datetime"
}
```

**Errors:**
- `404` — profile not found.
- `403` — no active consent for this `profile_id` + `source_type`. **Grant consent first.**

---

#### `POST /v1/ingest/receipt`
Uploads a photo of any receipt (utility bill, insurance payment, school fees — anything with a printed GHS amount) for a profile with no digital financial rails at all. OCRs it, extracts the amount actually paid (disambiguating between multiple printed figures by keyword priority — "total amount paid" beats a plain "total" beats nothing), and records it as an **outflow** transaction event. Creates/upgrades a Tier 2 `receipt` `Source` (one per `provider` per profile). **Triggers an immediate score recalculation.**

**Content-Type:** `multipart/form-data`

**Form fields:**
| Field | Type | Required |
|---|---|---|
| `profile_id` | uuid string | yes |
| `provider` | string, e.g. `"ECG"`, `"ClickInsure"` | yes |
| `file` | file (JPG/PNG only, ≤8MB, no PDF) | yes |

**Response `201`:**
```json
{
  "profile_id": "uuid",
  "success": true,
  "provider": "string",
  "amount_ghs": 557.0,
  "occurred_at": "datetime",
  "date_extracted": true,
  "tier": 2,
  "message": "string"
}
```
If no GHS amount could be found on the receipt, this still returns `201`, but with `success: false`, `amount_ghs: null`, `tier: null` — **check `success`, not just the status code.** No records are created in that case.

**Important semantic note for the frontend:** receipt evidence is outflow-only (we only ever see what someone paid, never what they received). It feeds Business Activity, Consistency, and Fraud scoring, but is deliberately **excluded** from Liquidity Reliability until the profile also has a real `momo`/`bank`/`payment_gateway` source — check `passport.excluded_categories` for `"liquidity_reliability"` and explain that gap in the UI rather than showing a misleadingly low score.

**Errors:**
- `404` — profile not found.
- `403` — no active consent for `source_type: "receipt"` on this profile.
- `400` — file isn't a readable image.
- `413` — file over 8MB.

---

### Passport / Scoring

#### `GET /v1/passport/{profile_id}`
Returns the current (cached) [Passport](#passport). Computes and caches one on first read if the profile has never been scored.

**Response `200`:** a [Passport](#passport) object.
**Errors:** `404` — profile not found.

---

#### `POST /v1/score/recalculate`
Forces a fresh score computation, overwriting the cache. Internal-use endpoint per the spec (meant to be fired by ingestion/repayment events, which already do this automatically) — exposed here mainly for manual testing/debugging.

**Request body:**
```json
{ "profile_id": "uuid, required" }
```

**Response `200`:** a [Passport](#passport) object.
**Errors:** `404` — profile not found.

---

### Decision & Marketplace

#### `GET /v1/marketplace/partners`
Lists the funding partner catalog. **Use this to populate any partner picker** — don't hardcode partner IDs in the frontend.

**Response `200`:**
```json
[
  {
    "partner_id": "forms-capital",
    "name": "Forms Capital",
    "max_risk_tier": "medium",
    "capacity_multiplier": 1.0,
    "price_adjustment_pct": 0.0
  },
  {
    "partner_id": "community-mfi-trust",
    "name": "Community MFI Trust",
    "max_risk_tier": "high",
    "capacity_multiplier": 0.5,
    "price_adjustment_pct": 0.8
  }
]
```

---

#### `POST /v1/decision`
Generates and persists an explainable lending decision for a stated amount request.

**Request body:**
```json
{
  "profile_id": "uuid, required",
  "requested_amount_ghs": "number > 0, required",
  "requested_duration_hours": "int > 0 | null, optional",
  "issued_to_partner_id": "string, required — use a partner_id from /v1/marketplace/partners"
}
```

**Response `201`:**
```json
{
  "decision_id": "uuid",
  "profile_id": "uuid",
  "recommendation": "approve | decline | refer",
  "amount_ghs": 900.0,
  "duration_hours": 16,
  "risk_tier": "low | medium | high",
  "reasons": ["string", "..."],
  "risk_flags": ["string", "..."],
  "issued_at": "datetime",
  "issued_to_partner_id": "string"
}
```

**How to render each `recommendation` value:**
| Value | Meaning | Suggested UI |
|---|---|---|
| `approve` | Safe to fund, `amount_ghs` may be capped below what was requested — check `reasons` for why. | Green/positive state, show the (possibly capped) amount clearly. |
| `refer` | Not enough data yet, or risk tier too high to auto-decide. Not a rejection. | Neutral/pending state — "needs review," never "declined." |
| `decline` | Active fraud signal. Overrides everything else. | Red/blocking state. |

**Errors:** `404` — profile not found.

---

#### `GET /v1/marketplace/offers`
Ranked, eligible funding offers for a profile's current assessment (no specific requested amount — reflects the profile's overall capacity).

**Query params:** `profile_id` (required)

**Response `200`:**
```json
{
  "profile_id": "uuid",
  "generated_at": "datetime",
  "offers": [
    {
      "partner_id": "forms-capital",
      "partner_name": "Forms Capital",
      "amount_ghs": 900.0,
      "duration_hours": 16,
      "price_pct": 1.4,
      "reasons": ["string", "..."]
    }
  ]
}
```
`offers` is sorted cheapest-first. **Can be an empty array** — this means no partner will currently fund this profile (active fraud signal, or zero assessed capacity). Show a clear empty state, not a spinner or an error.

**Errors:** `404` — profile not found.

---

### Ledger & Settlement

#### `POST /v1/settlement/route`
Settles an **approved** decision — records the disbursement. Always routes to the `domestic` rail (this endpoint can never produce `stablecoin`). Auto-registers a Tier 3 `nodal_ledger` source on the profile.

**Request body:**
```json
{ "decision_id": "uuid, required" }
```

**Response `201`:**
```json
{
  "id": "uuid",
  "profile_id": "uuid",
  "decision_id": "uuid",
  "entry_type": "disbursement",
  "amount_ghs": 900.0,
  "occurred_at": "datetime",
  "rail": "domestic",
  "due_at": "datetime",
  "repaid": false,
  "on_time": null
}
```

**Errors:**
- `404` — decision not found.
- `409` — decision isn't `approve`, or has already been settled.

---

#### `POST /v1/ledger/repayment`
Records a repayment against a profile's most recent outstanding (unrepaid) facility. **Triggers an immediate score recalculation** — this is what makes Repayment Reliability real instead of a permanent neutral 50.

**Request body:**
```json
{
  "profile_id": "uuid, required",
  "amount_ghs": "number, required",
  "paid_at": "datetime | null, optional, defaults to now"
}
```

**Response `201`:**
```json
{
  "id": "uuid",
  "profile_id": "uuid",
  "decision_id": "uuid | null",
  "entry_type": "repayment",
  "amount_ghs": 900.0,
  "occurred_at": "datetime",
  "rail": null,
  "due_at": null,
  "repaid": null,
  "on_time": true
}
```

**Errors:** `404` — profile not found, or no outstanding facility to repay.

---

#### `GET /v1/ledger/{profile_id}`
Full disbursement/repayment history for a profile, oldest first.

**Response `200`:** array of [LedgerEntry](#post-v1settlementroute-shaped-objects) objects (same shape as the settlement/repayment responses above).
**Errors:** `404` — profile not found.

---

### Lookup

#### `GET /v1/lookup/enums`
Every enum in the system, plus the tier model — the live source of truth for any dropdown/picker in the frontend. Auto-derived from backend code, so it can't go stale relative to what the API actually accepts.

**Response `200`:**
```json
{
  "enums": {
    "SourceType": {
      "description": "The kind of data feed a Source represents.",
      "values": ["utility", "momo", "bank", "payment_gateway", "nodal_ledger", "receipt"]
    }
  },
  "tiers": {
    "description": "string",
    "values": { "0": "string", "1": "string", "2": "string", "3": "string", "4": "string" }
  }
}
```

---

### Health

#### `GET /health`
No `/v1` prefix. Returns `{ "status": "ok" }`. Use for a connectivity check, not for anything else.

---

## 5. The golden path — a full sequence

The order below is the only order that actually works; several endpoints will `403`/`404` if called out of sequence.

```
1.  POST /v1/onboarding/{node_type}          → get profile_id
2.  POST /v1/consent                          → grant consent for a source_type
3a. POST /v1/verify/token   (or)
3b. POST /v1/verify/document (or)
3c. POST /v1/ingest/receipt                   → build up tier + transaction history
4.  POST /v1/ingest/{source_type}             → (for live momo/bank/payment_gateway data)
5.  GET  /v1/passport/{profile_id}            → see the current score
6.  GET  /v1/marketplace/partners             → let the user pick a partner
7.  POST /v1/decision                         → get approve/decline/refer + amount
8.  POST /v1/settlement/route                 → (only if recommendation was "approve") disburse
9.  POST /v1/ledger/repayment                 → record repayment; score updates automatically
    → back to step 5, score now reflects the repayment
```

Consent (step 2) is per `source_type` — a profile using both `momo` and `receipt` needs two separate consent grants, one for each.
