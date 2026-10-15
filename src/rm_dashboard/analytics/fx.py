"""FX normalisation with explicit quote direction, and bond nominal handling."""

import re
from dataclasses import dataclass

from .base import register

METHOD_FX = register(
    "fx",
    "Each pair is a quote: 1 base = rate quote (USDSGD 1.352 means SGD 1.352 per USD). "
    "A currency's USD value is rate when it is the base of a pair quoted in USD, and 1/rate "
    "when it is the quote of a pair based in USD. Amounts convert as amount x usd_per(from) / usd_per(to).",
)
METHOD_BOND = register(
    "bond_nominal",
    "Bond quantity is in units of 100 nominal; nominal = quantity x 100 and market value = "
    "quantity x price, the same formula as every other asset class.",
)

_UNIT = re.compile(r"^\s*([A-Z]{3}) per ([A-Z]{3})\s*$")


class MissingRate(KeyError):
    pass


@dataclass(frozen=True, slots=True)
class FxQuote:
    """1 ``base`` = ``rate`` ``quote``."""

    base: str
    quote: str
    rate: float


def quote_from_market_row(series_id: str, unit: str, value: float) -> FxQuote | None:
    """Direction comes from the series' unit text ('SGD per USD'), never from the id alone."""
    m = _UNIT.match(unit or "")
    if not m or len(series_id) != 6:
        return None
    quote, base = m.group(1), m.group(2)
    if series_id != base + quote:
        return None
    return FxQuote(base, quote, float(value))


class FxTable:
    def __init__(self, quotes: list[FxQuote], reference: str = "USD"):
        self.reference = reference
        self._usd: dict[str, float] = {reference: 1.0}
        for q in quotes:
            if q.quote == reference:
                self._usd[q.base] = q.rate
            elif q.base == reference:
                self._usd[q.quote] = 1.0 / q.rate

    def usd_per(self, ccy: str) -> float:
        try:
            return self._usd[ccy]
        except KeyError:
            raise MissingRate(ccy) from None

    def convert(self, amount: float, from_ccy: str, to_ccy: str) -> float:
        if from_ccy == to_ccy:
            return amount
        return amount * self.usd_per(from_ccy) / self.usd_per(to_ccy)

    def base_per_local(self, local: str, base: str) -> float:
        return self.usd_per(local) / self.usd_per(base)

    @property
    def currencies(self) -> list[str]:
        return sorted(self._usd)


def bond_nominal(quantity: float, unit: int = 100) -> float:
    return quantity * unit


def market_value(quantity: float, price: float) -> float:
    """Valid for every asset class, bonds included (quantity in units of 100 nominal)."""
    return quantity * price


def fx_table(market_rows) -> FxTable:
    """Build a table from market_context rows (dicts with series_id, unit, value)."""
    quotes = [q for r in market_rows if (q := quote_from_market_row(r["series_id"], r["unit"], r["value"]))]
    return FxTable(quotes)
