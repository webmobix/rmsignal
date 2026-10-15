"""Per-agent tool allow-lists. A new analyst is a prompt, an allow-list and an agent card."""

INSTRUMENT_ANALYST = (
    "instruments.get", "instruments.prices", "market.snapshot", "events.list", "news.list", "analytics.risk",
)

PORTFOLIO_ANALYST = (
    "portfolios.get", "positions.list", "instruments.get", "market.snapshot", "events.list",
    "analytics.weights", "analytics.exposure", "analytics.mandate_drift", "analytics.pnl", "analytics.change",
)

RELATIONSHIP_ANALYST = (
    "clients.get", "parties.get", "relationships.list", "persons.list", "portfolios.list", "notes.list",
    "credit.facilities", "cash_needs.list", "commitments.list", "market.snapshot", "events.list", "news.list",
    "analytics.concentration", "analytics.liquidity", "analytics.credit_ltv", "analytics.collateral_funding",
    "peers.kyc_status",
)

NOTE_RECONCILER = ("notes.list",)

ALLOWLISTS = {
    "instrument_analyst": INSTRUMENT_ANALYST,
    "portfolio_analyst": PORTFOLIO_ANALYST,
    "relationship_analyst": RELATIONSHIP_ANALYST,
    "note_reconciler": NOTE_RECONCILER,
}
