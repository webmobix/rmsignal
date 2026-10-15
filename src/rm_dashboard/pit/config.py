"""Configuration for data-quality rules: no client ids, years or literals live in logic."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QualityConfig:
    # holding.valuation_date earlier than snapshot_date by more than this many days
    stale_mark_days: int = 0
    # asset classes whose quantity is expressed in units of 100 nominal
    bond_asset_classes: tuple[str, ...] = ("Fixed Income",)
    bond_nominal_unit: int = 100
    # transaction types that must settle in the portfolio base currency
    subscription_types: tuple[str, ...] = ("Structured Product Subscription",)
    # transaction type that explains an increase in facility drawn amount
    drawdown_types: tuple[str, ...] = ("Facility Drawdown",)
    drawdown_tolerance: float = 1.0
    # snapshot older than as_of by more than this many days is flagged
    snapshot_gap_flag_days: int = 0
