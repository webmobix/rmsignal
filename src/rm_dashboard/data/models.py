"""Typed records for the Julius Baer wealth intelligence dataset: one dataclass per file.

Field names equal the source column names, except that hyphens in date-suffixed
columns (``aum_2026-08-26``) become underscores (``aum_2026_08_26``). Dates are
``datetime.date``, yes/no flags are ``bool``; a ``| None`` annotation marks a
column whose source cells may be empty.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Client:
    """One row of ``clients.csv``."""

    client_id: str
    client_name: str
    age: int | None
    gender: str
    nationality: str
    country_of_residence: str
    tax_domicile: str
    booking_centre: str
    rm_id: str
    rm_name: str
    rm_desk: str
    base_currency: str
    wealth_band: str
    total_aum_usd: float
    life_stage: str
    source_of_wealth: str
    risk_profile: str
    risk_tolerance_score: int
    investment_horizon_years: int
    liquidity_needs: str
    objectives: str
    client_since: date
    kyc_review_due: date
    pep_status: bool
    reporting_language: str


@dataclass(frozen=True, slots=True)
class Portfolio:
    """One row of ``portfolios.csv``."""

    portfolio_id: str
    client_id: str
    portfolio_name: str
    mandate_code: str
    mandate_name: str
    service_model: str
    base_currency: str
    inception_date: date
    benchmark: str
    aum_2025_12_31: float
    aum_2026_02_27: float
    aum_2026_03_31: float
    aum_2026_06_30: float
    aum_2026_08_26: float
    aum_usd_current: float


@dataclass(frozen=True, slots=True)
class Holding:
    """One row of ``holdings.csv``."""

    snapshot_date: date
    portfolio_id: str
    client_id: str
    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str | None
    region: str
    instrument_ccy: str
    quantity: int
    price_local: float
    market_value_local: float
    portfolio_ccy: str
    market_value_base: float
    market_value_usd: float
    weight_pct: float
    avg_cost_local: float | None
    cost_basis_base: float | None
    unrealised_pnl_base: float | None
    unrealised_pnl_pct: float | None
    lending_value_base: float
    advance_rate_pct: float
    liquidity_tier: str
    valuation_date: date
    acquired_date: date


@dataclass(frozen=True, slots=True)
class Instrument:
    """One row of ``instruments.csv``."""

    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str | None
    region: str
    currency: str
    liquidity_tier: str
    underlying_reference: str | None
    sustainability_excluded: bool
    concentration_limit_applies: bool
    price_2025_12_31: float
    price_2026_02_27: float
    price_2026_03_31: float
    price_2026_06_30: float
    price_2026_08_26: float


@dataclass(frozen=True, slots=True)
class Mandate:
    """One row of ``mandates.csv``."""

    mandate_code: str
    mandate_name: str
    asset_class: str
    min_pct: float
    target_pct: float
    max_pct: float
    max_single_position_pct: float
    mandate_notes: str


@dataclass(frozen=True, slots=True)
class Transaction:
    """One row of ``transactions.csv``."""

    transaction_id: str
    trade_date: date
    settlement_date: date
    portfolio_id: str
    client_id: str
    transaction_type: str
    instrument_id: str | None
    instrument_name: str | None
    quantity: int | None
    price_local: float | None
    currency: str
    amount: float
    narrative: str


@dataclass(frozen=True, slots=True)
class CreditFacility:
    """One row of ``credit_facilities.csv``."""

    facility_id: str
    client_id: str
    collateral_portfolio_id: str
    facility_type: str
    facility_ccy: str
    credit_limit: float
    interest_rate_pct: float
    margin_call_ltv_pct: float
    drawn_2025_12_31: float
    collateral_market_value_2025_12_31: float
    lending_value_2025_12_31: float
    ltv_pct_2025_12_31: float
    headroom_2025_12_31: float
    drawn_2026_02_27: float
    collateral_market_value_2026_02_27: float
    lending_value_2026_02_27: float
    ltv_pct_2026_02_27: float
    headroom_2026_02_27: float
    drawn_2026_03_31: float
    collateral_market_value_2026_03_31: float
    lending_value_2026_03_31: float
    ltv_pct_2026_03_31: float
    headroom_2026_03_31: float
    drawn_2026_06_30: float
    collateral_market_value_2026_06_30: float
    lending_value_2026_06_30: float
    ltv_pct_2026_06_30: float
    headroom_2026_06_30: float
    drawn_2026_08_26: float
    collateral_market_value_2026_08_26: float
    lending_value_2026_08_26: float
    ltv_pct_2026_08_26: float
    headroom_2026_08_26: float
    utilisation_pct_current: float


@dataclass(frozen=True, slots=True)
class Commitment:
    """One row of ``commitments.csv``."""

    commitment_id: str
    client_id: str
    portfolio_id: str
    fund_name: str
    currency: str
    committed: float
    called_to_date: float
    uncalled: float
    expected_call_window: str


@dataclass(frozen=True, slots=True)
class PlannedCashNeed:
    """One row of ``planned_cash_needs.csv``."""

    need_id: str
    client_id: str
    description: str
    currency: str
    amount: float
    due_from: date
    due_to: date
    recurrence: str
    certainty: str


@dataclass(frozen=True, slots=True)
class MarketContext:
    """One row of ``market_context.csv``."""

    snapshot_date: date
    series_id: str
    series_name: str
    category: str
    unit: str
    value: float
    snapshot_label: str


@dataclass(frozen=True, slots=True)
class Event:
    """One row of ``event_log.csv``."""

    event_date: date
    event_type: str
    region: str
    description: str
    primary_transmission: str
    severity: str


@dataclass(frozen=True, slots=True)
class RMNote:
    """One entry of ``rm_notes.json``."""

    note_id: str
    client_id: str
    note_date: date
    rm_id: str
    rm_name: str
    channel: str
    note: str
