NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 1
Nodal Liquidity Passport
Product & Technical Specification
Data architecture, onboarding tiers, and developer build guide for the Individual, SME,
and Mobile Money Agent nodes.
Version 0.1 · August 2026 · Prototype / hackathon build spec
Prepared for: engineering & product build team
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 2
Contents
1. Overview
2. Progressive verification model (Tiers 0–4)
3. Node specification — Individual
4. Node specification — SME
5. Node specification — Mobile Money Agent
6. Onboarding channels
7. System architecture
8. Core data schemas
9. API specification
10. Scoring engine specification
11. Security, consent & compliance requirements
12. Non-functional requirements
13. Suggested tech stack
14. Appendix — example payloads
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 3
1. Overview
The Nodal Liquidity Passport is a continuously updated financial representation of a business or individual, built
from data the person already generates through everyday economic activity. It replaces static credit checks with a
live, portable score that answers three questions: what does this person or business need, what can they safely
support, and what financial product is appropriate right now.
The Passport is built from three onboarding nodes — Individual, SME, and Mobile Money Agent — each with its
own data requirements. All three nodes follow the same underlying principle: nobody is blocked from getting a
score for lack of a document or a smartphone. What changes with more data is score confidence and credit
ceiling, not eligibility to participate. This document specifies the data required per node, the verification-tier model
that governs manual-to-automated progression, and the technical architecture engineers need to build the system.
This is a build specification, not a pitch document. Sections 7–14 are written for developers implementing the ingestion,
scoring, and decision layers.
2. Progressive Verification Model (Tiers 0–4)
Every profile in Nodal carries a per-source verification tier. The overall Passport confidence score is a function of
the highest tier reached per data category, not a single global switch — an agent can be Tier 3 on mobile money
data and Tier 1 on utility data simultaneously. This lets the system serve someone with only a receipt number
today, while automatically upgrading their confidence the moment they connect a live API source.
Tier What's provided Confidence Effect on Passport
0 — Self-declared National ID (Ghana Card) only; self-reported
business type, location, income band
Low Small starter facility, seeds a
track record
1 — Token / receipt
verified
Utility prepaid token or postpaid bill reference
number entered via app or USSD; MoMo
transaction reference codes
Medium Confirms a real, paying
address or transaction without
a smartphone or camera
2 — Document
uploaded
Photo/PDF of utility bill, MoMo statement, bank
statement
Medium–Hig
h
OCR-extracted and
cross-matched against Tier 1
data where available
3 — API-linked Live consented connection to MNO, bank, or
payment gateway API
High,
live-updating
Score recalculates after every
new transaction event
4 — Multi-source
reconciled
Two or more Tier 3 sources cross-validated
against each other (e.g. MoMo + bank)
Highest Best available pricing and
largest limits
Design rule for developers: the scoring engine must never treat a missing data category as a negative signal.
Absence of a source simply excludes that category's weight from the confidence calculation (see Section 10) — it must
not be scored as zero or as risk.
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 4
3. Node Specification — Individual
Data point Phase 1 — manual Phase 2 — automated Low-tech / no-smartphone path
Identity Ghana Card number,
manual entry
Ghana Card API
verification (NIA)
Ghana Card number works on any phone,
incl. USSD entry
Address / stability Photo of utility bill (ECG /
Ghana Water)
Live utility provider API pull Enter prepaid meter token or postpaid bill
reference number via USSD; matched
against utility provider without a camera
Cash flow MoMo statement PDF or
screenshot upload
Consented MTN / Telecel /
AT transaction API
MoMo statement pulled via *170#/*228#
read out at an agent point, or
SMS-forwarded
Formal banking
(optional)
Bank statement upload Open banking / bank API
link
Not applicable — only if banked
Income (optional) Payslip photo Employer payroll API
(future)
Not applicable
4. Node Specification — SME
Data point Phase 1 — manual Phase 2 — automated Low-tech / no-smartphone path
Identity +
business
Owner's Ghana Card;
business registration if
formalised (not required)
Registrar General's Dept.
API check where formal
Same identity path as Individual node
Premises stability Utility bill for the shop
premises
Live utility API Token / bill reference entry, identical
mechanism to Individual node
Sales / turnover Payment gateway or
merchant MoMo statement
upload
Consented payment
gateway API
Agent-assisted entry of merchant MoMo
transaction reference codes at any agent
point
Banking (optional) Bank statement upload Bank API link Not applicable
Inventory /
supplier signal
(post-MVP)
Supplier receipt photos Not in MVP scope Supplier receipt / invoice reference
number entry
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 5
5. Node Specification — Mobile Money Agent
This is the richest node and the primary node the prototype should demonstrate end to end.
Data point Phase 1 — manual Phase 2 — automated Low-tech / no-smartphone path
Identity + agent
status
Ghana Card, MNO agent
code
MNO agent-registry API
confirms live agent status
Agent code is already MNO-assigned —
entry only, no upload required
Transaction /
commission
history
Screenshot of agent-app
dashboard or commission
statement
Direct consented API from
MTN / Telecel / AT
Agent reads own USSD
balance/commission check result, enters
reference number
Cash-in / cash-out
& float behaviour
Manually logged float
top-up receipts
Live rebalancing data
pulled from telco + Nodal
transaction history
Float top-up receipt / token ID entry
Prior financing /
repayment
Self-declared + any
existing lender statement
Automatic once the agent
has borrowed once —
pulled from Nodal's own
ledger
Not applicable after first facility
Premises Utility bill for the kiosk /
shop
Live utility API Token / receipt entry, identical mechanism
to other nodes
6. Onboarding Channels
Every node can be onboarded through three converging channels, all writing into the same underlying profile and
tier model:
● Self-serve app / web — smartphone users complete identity, document upload, and API consent directly.
● USSD — feature-phone users complete identity and token/receipt entry through a menu-driven USSD session;
no data connection required.
● Agent-assisted intake — any existing MoMo agent can onboard an individual or SME on their behalf using the
same agent-assisted screen already used for cash-in/cash-out, entering the customer's Ghana Card number,
MoMo number, and utility token/receipt ID.
All three channels write to the same Onboarding Service and produce an identical profile object (Section 8),
tagged with a channel field for analytics. There is no second-class data path — a USSD-onboarded profile and an
app-onboarded profile are structurally identical and eligible for the same tier upgrades.
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 6
7. System Architecture
Components, in request flow order:
Layer Responsibility
1. Client layer Mobile app, USSD gateway integration (Africa's Talking / MNO USSD aggregator),
agent-assisted web console
2. Identity & Consent Service Ghana Card verification, consent capture, scope management, expiry tracking (default 90
days), revocation handling
3. Data Ingestion Layer Per-partner adapters: MNO transaction API, payment gateway API, bank/open-banking API,
utility token/bill verification API. Each adapter normalises into a common event schema
before it reaches the scoring engine
4. Verification & OCR Service Document upload handling, OCR extraction (utility bills, statements), token/receipt ID
validation against provider records
5. Passport / Scoring Engine Computes Business Activity, Transaction Consistency, Liquidity Reliability, Repayment
Reliability, Fraud Risk, and the composite Nodal Score; recalculates on every qualifying
ingestion event
6. Decision & Explainability
Service
Converts a score + liquidity request into a structured decision object: recommendation,
amount, duration, price, and human-readable reasons and risk flags (see Section 8.4)
7. Marketplace / Routing
Engine
Matches an assessed liquidity requirement against eligible funding partners and returns
ranked offers
8. Ledger & Repayment
Tracking Service
Records disbursement and repayment events; feeds repayment history back into the
scoring engine (the flywheel)
9. Settlement Orchestration
Layer
Domestic rails (MoMo, bank) by default; optional routing through a regulated stablecoin
settlement rail for cross-border capital sourcing only — never on the agent-facing leg (see
callout below)
10. Audit & Compliance
Logging
Immutable log of every consent grant/revocation, data access, score recalculation, and
decision issued
Settlement routing rule: the Settlement Orchestration Layer must default to domestic rails (MoMo / bank) for every
agent-facing disbursement. A stablecoin leg, if used at all, sits only between an institutional capital provider and a
licensed on/off-ramp partner, before funds ever reach GHS. This must be enforced in code as a routing constraint, not
left as a policy note.
8. Core Data Schemas
8.1 Profile object (all nodes)
{
 "profile_id": "string (uuid)",
 "node_type": "individual | sme | momo_agent",
 "onboarding_channel": "app | ussd | agent_assisted",
 "identity": {
 "ghana_card_number": "string",
 "verification_status": "self_declared | api_verified"
 },
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 7
 "created_at": "ISO 8601 timestamp",
 "sources": [
 {
 "source_type": "utility | momo | bank | payment_gateway | nodal_ledger",
 "provider": "string (e.g. ECG, MTN, GCB)",
 "tier": 0 | 1 | 2 | 3 | 4,
 "entry_method": "token_id | receipt_id | document_upload | api_link",
 "connected_at": "ISO 8601 timestamp",
 "consent_id": "string (fk -> consent record)",
 "last_synced_at": "ISO 8601 timestamp | null"
 }
 ]
}
8.2 Consent record
{
 "consent_id": "string (uuid)",
 "profile_id": "string (uuid)",
 "source_type": "utility | momo | bank | payment_gateway",
 "scopes": ["liquidity_assessment", "eligibility_calculation", "fraud_detection"],
 "excluded_scopes": ["initiate_transactions"],
 "granted_at": "ISO 8601 timestamp",
 "expires_at": "ISO 8601 timestamp (default: granted_at + 90 days)",
 "status": "active | expired | revoked",
 "revoked_at": "ISO 8601 timestamp | null"
}
8.3 Passport object
{
 "profile_id": "string (uuid)",
 "generated_at": "ISO 8601 timestamp",
 "business_activity": "strong | moderate | weak",
 "window_days": 90,
 "transaction_volume_ghs": "number",
 "avg_daily_turnover_ghs": "number",
 "transaction_consistency_pct": "number (0-100)",
 "liquidity_reliability_score": "number (0-100)",
 "repayment_reliability_score": "number (0-100)",
 "fraud_risk": "low | medium | high",
 "nodal_score": "number (0-100)",
 "confidence_by_category": {
 "identity": "0-4 tier",
 "cash_flow": "0-4 tier",
 "stability": "0-4 tier",
 "repayment_history": "0-4 tier"
 },
 "recommended_liquidity_line_ghs": "number",
 "recommended_duration_hours": "number",
 "risk_adjusted_price_pct": "number"
}
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 8
8.4 Decision object (lender-facing, explainable)
{
 "decision_id": "string (uuid)",
 "profile_id": "string (uuid)",
 "recommendation": "approve | decline | refer",
 "amount_ghs": "number",
 "duration_hours": "number",
 "risk_tier": "low | medium | high",
 "reasons": [
 "string, e.g. 'Transaction volume +21% over 90 days'",
 "string, e.g. '93% transaction consistency'",
 "string, e.g. 'No missed Nodal repayments'"
 ],
 "risk_flags": [
 "string, e.g. 'Unusual transaction spike yesterday'",
 "string, e.g. 'One newly connected data source'"
 ],
 "issued_at": "ISO 8601 timestamp",
 "issued_to_partner_id": "string"
}
9. API Specification
Endpoint Purpose
POST /v1/onboarding/{node_type} Create a new profile (individual / sme / momo_agent) from any channel
POST /v1/consent Grant a consent record for a given source and scope set
DELETE /v1/consent/{consent_id} Revoke consent; does not retroactively affect an active facility
POST /v1/ingest/{source_type} Partner-adapter endpoint receiving normalised transaction/document events
POST /v1/verify/token Validate a utility token ID or receipt/bill reference number against the relevant
provider
GET /v1/passport/{profile_id} Return the current Passport object
POST /v1/score/recalculate Internal — triggered by a qualifying ingestion event; not called by clients directly
POST /v1/decision Generate a Decision object for a stated liquidity requirement
GET /v1/marketplace/offers?profile_id= Return ranked eligible funding offers for a profile's current requirement
POST /v1/settlement/route Resolve a disbursement to the correct rail per the routing rule in Section 7
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 9
10. Scoring Engine Specification
The Nodal Score is a weighted composite of five sub-scores. Each sub-score is computed only from data
categories the profile has reached at least Tier 1 on; categories below Tier 1 are excluded from the weighted sum
rather than scored as zero (see Section 2).
Sub-score Default weight Primary inputs
Business Activity 25% 90-day transaction volume and average daily turnover vs. node-type
baseline
Transaction Consistency 20% Coefficient of variation of transaction frequency over the trailing 90-day
window
Liquidity Reliability 20% Frequency and severity of historical liquidity shortages / rebalancing
events
Repayment Reliability 25% On-time repayment rate across any prior Nodal-financed facilities;
neutral prior for first-time borrowers
Fraud Risk (inverse weight) 10% Anomaly detection on transaction pattern, device, and newly connected
sources
Recalculation triggers (must fire an event to /v1/score/recalculate):
● A new transaction is ingested from any Tier 3+ connected source
● A new document is uploaded and successfully OCR-matched (Tier 2)
● A token/receipt ID is verified against the issuing provider (Tier 1)
● A repayment event is posted to the Nodal ledger
● A consent is revoked (triggers immediate confidence re-weighting, not data deletion of historical facility terms)
For the prototype, ship a deterministic weighted-sum implementation of the table above before attempting any
ML-based scoring — the explainability requirement in Section 8.4 depends on being able to trace every point of the
score to a named input.
11. Security, Consent & Compliance Requirements
● Encryption: TLS 1.2+ in transit; AES-256 at rest for all identity and financial data.
● Scoped access tokens: every partner data connection is scoped to named purposes only — liquidity
assessment, eligibility calculation, fraud detection — and explicitly excludes transaction-initiation rights.
● Default expiry: all consents expire 90 days after grant unless renewed; expiry is enforced server-side, not just
surfaced in UI.
● Revocation: revoking a source stops future ingestion immediately; it must not retroactively alter the terms of an
already-disbursed facility.
● Data minimisation: ingestion adapters should normalise and discard raw partner payloads beyond what the
scoring engine's inputs require; store derived features, not full statements, wherever possible.
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 10
● Audit trail: every consent grant/revocation, data access, score recalculation, and decision issued must be
immutably logged with profile_id, actor, and timestamp.
● Regulatory posture (MVP): Nodal does not custody funds or lend directly in the prototype; it assesses and
routes. Regulated partners (banks, MFIs, Forms Capital) hold the actual lending relationship, subject to their
own licensing.
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 11
12. Non-Functional Requirements
Requirement Target
Passport read latency GET /v1/passport under 500ms p95 for a cached score
Score recalculation latency Under 5s from qualifying ingestion event to updated score, for the live-updating Tier
3+ path
USSD session timeout tolerance Session steps must complete within standard MNO USSD timeout windows (typically
60–180s per screen)
Availability 99.5% for the Passport and Decision APIs during prototype/demo phase
Offline-first onboarding Token/receipt entry and agent-assisted intake must function over 2G-equivalent
connectivity
Auditability Every field in a Decision object must be traceable to a stored input event — no
opaque model outputs without a logged basis
13. Suggested Tech Stack (Prototype Scope)
Layer Suggested tooling
Client apps React Native or Flutter (single codebase for agent/SME/individual self-serve app)
USSD gateway Africa's Talking or a direct MNO USSD aggregator
Backend services Node.js/TypeScript or Python (FastAPI) microservices per Section 7 component
Scoring engine Python, deterministic weighted-sum implementation (Section 10) behind a versioned internal
API
Data store Postgres for profiles/consents/decisions; append-only event store (e.g. Kafka or a simple
event table) for ingestion events feeding the scoring engine
OCR Cloud OCR API (e.g. Google Document AI / Tesseract for offline fallback) for utility bill and
statement uploads
Auth OAuth2 / OIDC for partner API consent flows; short-lived scoped tokens
Settlement (optional, backend
only)
Existing regulated on/off-ramp infrastructure for any stablecoin leg — do not build custom
blockchain infrastructure for the prototype
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 12
14. Appendix — Example Payloads
14.1 Example: agent-assisted onboarding request (USSD/agent channel)
POST /v1/onboarding/momo_agent
{
 "onboarding_channel": "agent_assisted",
 "assisting_agent_id": "AG-04521",
 "identity": {
 "ghana_card_number": "GHA-XXXXXXXXX-X"
 },
 "sources": [
 {
 "source_type": "utility",
 "provider": "ECG",
 "entry_method": "token_id",
 "value": "1234-5678-9012-3456-7890"
 },
 {
 "source_type": "momo",
 "provider": "MTN",
 "entry_method": "receipt_id",
 "value": "MP240818.1932.A00123"
 }
 ]
}
14.2 Example: Passport API response
GET /v1/passport/8f14e2a1-...
{
 "profile_id": "8f14e2a1-...",
 "generated_at": "2026-08-18T09:12:00Z",
 "business_activity": "strong",
 "window_days": 90,
 "transaction_volume_ghs": 186400,
 "avg_daily_turnover_ghs": 2071,
 "transaction_consistency_pct": 91,
 "liquidity_reliability_score": 84,
 "repayment_reliability_score": 96,
 "fraud_risk": "low",
 "nodal_score": 87,
 "confidence_by_category": {
 "identity": 3,
 "cash_flow": 3,
 "stability": 1,
 "repayment_history": 3
 },
 "recommended_liquidity_line_ghs": 4800,
 "recommended_duration_hours": 24,
 "risk_adjusted_price_pct": 1.2
}
14.3 Example: Decision object issued to a lending partner
POST /v1/decision -> response
{
 "decision_id": "d3a9f0e2-...",
NODAL LIQUIDITY PASSPORT Product & Technical Specification
Confidential — prototype specification, v0.1 Page 13
 "profile_id": "8f14e2a1-...",
 "recommendation": "approve",
 "amount_ghs": 3200,
 "duration_hours": 20,
 "risk_tier": "low",
 "reasons": [
 "Transaction volume +21% over 90 days",
 "93% transaction consistency",
 "No missed Nodal repayments",
 "Average daily inflow covers facility 3.8x"
 ],
 "risk_flags": [
 "Unusual transaction spike yesterday",
 "One newly connected data source"
 ],
 "issued_at": "2026-08-18T09:14:02Z",
 "issued_to_partner_id": "forms-capital"
}
End of specification. This document covers data requirements and build architecture only; see the accompanying product
narrative for market context, business model, and panel positioning.