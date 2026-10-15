"""Entity models shared by data, tools, agents and other bank systems."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

Pit = Literal["snapshot", "event", "current_only"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Party(_Model):
    """Anything a relationship can attach to: an individual or an organisation."""

    party_id: str
    kind: Literal["individual", "organisation"]
    name: str
    country: str | None = None


class Person(_Model):
    """A natural person linked to a party (beneficial owner, director, family member)."""

    person_id: str
    name: str
    nationality: str | None = None
    pep_status: bool | None = None


class Relationship(_Model):
    """Typed, directed link between two parties, with optional validity and a source."""

    from_id: str
    to_id: str
    kind: str
    valid_from: date | None = None
    valid_to: date | None = None
    source: str


class Client(_Model):
    client_id: str
    name: str
    base_currency: str
    wealth_band: str
    risk_profile: str
    risk_tolerance_score: int
    tax_domicile: str
    country_of_residence: str
    kyc_review_due: date
    pep_status: bool
    liquidity_needs: str
    investment_horizon_years: int
    objectives: str
    source_of_wealth: str
    pit: Pit = "current_only"


class Portfolio(_Model):
    portfolio_id: str
    client_id: str
    name: str
    mandate_code: str
    service_model: str
    base_currency: str
    benchmark: str
    aum: float | None = None
    pit_attributes: Pit = "current_only"


class Position(_Model):
    portfolio_id: str
    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str | None
    region: str
    instrument_ccy: str
    quantity: int
    price_local: float
    market_value_base: float
    market_value_usd: float
    weight_pct: float
    cost_basis_base: float | None
    unrealised_pnl_base: float | None
    lending_value_base: float
    liquidity_tier: str
    valuation_date: date
    snapshot_date: date


class Instrument(_Model):
    instrument_id: str
    name: str
    asset_class: str
    sub_asset_class: str
    sector: str | None
    region: str
    currency: str
    liquidity_tier: str
    underlying_reference: str | None
    sustainability_excluded: bool
    concentration_limit_applies: bool


class Event(_Model):
    event_date: date
    event_type: str
    region: str
    description: str
    primary_transmission: str
    severity: str


