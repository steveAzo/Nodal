import enum


class NodeType(str, enum.Enum):
    individual = "individual"
    sme = "sme"
    momo_agent = "momo_agent"


class OnboardingChannel(str, enum.Enum):
    app = "app"
    ussd = "ussd"
    agent_assisted = "agent_assisted"


class IdentityVerificationStatus(str, enum.Enum):
    self_declared = "self_declared"
    api_verified = "api_verified"


class SourceType(str, enum.Enum):
    utility = "utility"
    momo = "momo"
    bank = "bank"
    payment_gateway = "payment_gateway"
    nodal_ledger = "nodal_ledger"


class EntryMethod(str, enum.Enum):
    token_id = "token_id"
    receipt_id = "receipt_id"
    document_upload = "document_upload"
    api_link = "api_link"


class ConsentScope(str, enum.Enum):
    liquidity_assessment = "liquidity_assessment"
    eligibility_calculation = "eligibility_calculation"
    fraud_detection = "fraud_detection"
    initiate_transactions = "initiate_transactions"


class ConsentStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"
