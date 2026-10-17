"""The channel vocabulary of a shock vector and the rules that bring a holding to its channels.

Channels are layered so that additive moves do not count one exposure twice:

* **market** channels carry the move of an asset-class bucket (equity by region bucket, rates duration, gold, broad commodities,
  real estate);
* **overlay** channels carry an *excess* over that market move (a sector over its equity market, credit spreads over rates);
* **fx** channels carry the move of a non-USD currency against USD, applied as translation to the holdings denominated in it.

A holding reaches at most one market channel, any overlays that its sector or credit quality call for, and one fx channel. Its move
is the sum of those. The vocabulary is derived from the instruments present, not fixed in code: a channel exists when a holding
can reach it. There is no shipping sector in the data, so shipping is expressed through the industrials overlay.
"""

from dataclasses import dataclass

from .contracts import ChannelKind

CASH = "Cash and Equivalents"

REGION_BUCKETS = {
    "north america": "equity_us", "europe": "equity_europe", "japan": "equity_japan",
    "asia ex-japan": "equity_asia", "greater china": "equity_asia", "hong kong": "equity_asia", "singapore": "equity_asia",
    "southeast asia": "equity_asia", "south asia": "equity_asia", "asia pacific": "equity_asia", "indonesia": "equity_asia",
    "asia": "equity_asia", "global": "equity_global", "emerging markets": "equity_global",
}
"""Region of an equity -> its market channel. A region outside this table reaches ``equity_global``."""

SECTOR_OVERLAYS = {
    "Energy": "sector_energy", "Information Technology": "sector_technology", "Health Care": "sector_health_care",
    "Industrials": "sector_industrials", "Utilities": "sector_utilities", "Consumer Discretionary": "sector_consumer_discretionary",
    "Consumer Staples": "sector_consumer_staples", "Real Estate": "sector_real_estate",
}
"""Sector of a listed equity -> the overlay carrying the sector's excess over its equity market. ``Diversified`` has none."""

CREDIT_SECTORS = ("Corporate", "Financials", "Real Estate")
CREDIT_SUB_CLASSES = ("credit", "high yield", "emerging market debt", "subordinated")

MARKET_CHANNELS = {
    "equity_global": "Global equity market", "equity_us": "US equity market", "equity_europe": "European equity market",
    "equity_japan": "Japanese equity market", "equity_asia": "Asian equity markets (Japan excluded)",
    "rates_duration": "Government bond and interest-rate duration", "gold": "Gold price",
    "commodities_broad": "Broad commodities price", "real_estate": "Property valuations (unlisted real estate)",
}
OVERLAY_CHANNELS = {
    "credit_spreads": "Credit spreads, as an excess over the rates duration move",
    **{v: f"{k} sector, as an excess over its equity market move" for k, v in SECTOR_OVERLAYS.items()},
}
SINGLE_INSTRUMENT_PREFIX = "SYN-"
"""Instrument ids start like this: a key that does, or names an instrument, is a single-instrument move and is refused."""


@dataclass(frozen=True)
class Channel:
    channel: str
    kind: ChannelKind
    label: str


def fx_channel(currency: str | None) -> str | None:
    """The translation channel of a currency; USD has none."""
    c = (currency or "").strip().upper()
    return None if c in ("", "USD") else f"fx_{c.lower()}"


def region_bucket(region: str | None) -> str:
    return REGION_BUCKETS.get((region or "").strip().lower(), "equity_global")


@dataclass(frozen=True)
class RuleResult:
    channels: tuple[tuple[str, str], ...] = ()
    """(channel, why) pairs, market channel first."""
    ambiguous: str | None = None
    """Why code cannot map the holding; an agent may then propose a mapping."""


def _text(row: dict, key: str) -> str:
    return str(row.get(key) or "").strip()


def instrument_channels(row: dict) -> RuleResult:
    """Channels of one instrument by asset class, region, sector and sub-asset class. Structured products are not handled here:
    they are looked through by the mapping, and ``sector_channels`` is the fallback for a product whose underlyings do not resolve."""
    ac, sector, sub, region = _text(row, "asset_class"), _text(row, "sector"), _text(row, "sub_asset_class"), _text(row, "region")
    if ac == "Equity":
        market = region_bucket(region)
        out = [(market, f"equity in {region or 'an unstated region'} reaches {market}")]
        if sector in SECTOR_OVERLAYS:
            out.append((SECTOR_OVERLAYS[sector], f"{sector} sector excess over {market}"))
        return RuleResult(tuple(out))
    if ac == "Fixed Income":
        out = [("rates_duration", f"{sub or 'fixed income'} is priced off interest rates")]
        if sector in CREDIT_SECTORS or any(k in sub.lower() for k in CREDIT_SUB_CLASSES):
            out.append(("credit_spreads", f"{sub or sector} carries credit spread risk"))
        return RuleResult(tuple(out))
    if ac == "Commodities":
        if sector == "Gold":
            return RuleResult((("gold", "gold holding"),))
        if sector == "Diversified":
            return RuleResult((("commodities_broad", "diversified commodities holding"),))
        return RuleResult(ambiguous=f"commodities holding with sector {sector or 'unstated'}")
    if ac == CASH:
        return RuleResult()
    if ac == "Alternatives":
        if sector == "Real Estate":
            return RuleResult((("real_estate", f"{sub or 'real estate'} follows property valuations"),))
        return RuleResult(ambiguous=f"{sub or 'alternative'} ({sector or 'no sector'}) has no public market channel")
    if ac == "Structured Products":
        return sector_channels(row)
    return RuleResult(ambiguous=f"asset class {ac or 'unstated'} has no mapping rule")


def sector_channels(row: dict) -> RuleResult:
    """The fallback for a structured product whose underlyings do not resolve: follow the product's own sector, when it names one."""
    sector, region = _text(row, "sector"), _text(row, "region")
    if sector == "Gold":
        return RuleResult((("gold", "product is classified Gold"),))
    if sector in SECTOR_OVERLAYS:
        market = region_bucket(region)
        return RuleResult(((market, f"product's sector {sector} in {region or 'an unstated region'}"),
                           (SECTOR_OVERLAYS[sector], f"{sector} sector excess over {market}")))
    return RuleResult(ambiguous=f"structured product with sector {sector or 'unstated'} and no resolvable underlying")


def vocabulary(instruments: list[dict]) -> list[Channel]:
    """The channels a holding in these instruments can reach: the set a shock vector may speak about."""
    seen: dict[str, Channel] = {}

    def add(channel: str) -> None:
        if channel in seen:
            return
        if channel in MARKET_CHANNELS:
            seen[channel] = Channel(channel, "market", MARKET_CHANNELS[channel])
        elif channel in OVERLAY_CHANNELS:
            seen[channel] = Channel(channel, "overlay", OVERLAY_CHANNELS[channel])
        else:
            seen[channel] = Channel(channel, "fx", f"{channel[3:].upper()} against USD, as translation of holdings denominated in it")

    for r in instruments:
        for ch, _ in instrument_channels(r).channels:
            add(ch)
        if fx := fx_channel(r.get("currency")):
            add(fx)
    order = {**{c: i for i, c in enumerate(MARKET_CHANNELS)}, **{c: 100 + i for i, c in enumerate(OVERLAY_CHANNELS)}}
    return sorted(seen.values(), key=lambda c: (order.get(c.channel, 1000), c.channel))


def is_single_instrument_key(key: str, known_names: set[str] | None = None) -> bool:
    k = key.strip()
    return k.upper().startswith(SINGLE_INSTRUMENT_PREFIX) or k.lower() in (known_names or set())
