"""From holdings to channels. Deterministic rules first; only what the rules cannot place is offered to an agent."""

from dataclasses import dataclass, field

from rm_dashboard.analytics.concentration import normalise_name, parse_underlyings

from .channels import RuleResult, fx_channel, instrument_channels, sector_channels

STRUCTURED = "Structured Products"


@dataclass
class PortfolioInputs:
    """Everything the impact of one portfolio rests on, as plain rows (see ``inputs.load_portfolio_inputs``)."""

    portfolio: dict
    holdings: list[dict]
    instruments: dict[str, dict]
    bands: list[dict] = field(default_factory=list)
    facilities: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ChannelUse:
    channel: str
    weight: float
    """Share of the holding that the channel reaches: 1 for a rule, 1/n per underlying of a basket."""
    why: str
    agent_assigned: bool = False


@dataclass(frozen=True)
class Mapped:
    holding: dict
    mapping: str
    """``rule``, ``look_through``, ``agent`` or ``untouched``."""
    reason: str
    channels: tuple[ChannelUse, ...] = ()


@dataclass(frozen=True)
class Ambiguity:
    instrument_id: str
    instrument_name: str
    asset_class: str
    sector: str | None
    reason: str


def _fx_use(holding: dict) -> list[ChannelUse]:
    ch = fx_channel(holding.get("instrument_ccy"))
    return [ChannelUse(ch, 1.0, f"{holding['instrument_ccy']} against USD translates the position")] if ch else []


def _instrument_row(inputs: PortfolioInputs, holding: dict) -> dict:
    """Reference data of the holding's instrument; the holding's own columns when the instrument table lacks it."""
    return {**holding, **inputs.instruments.get(holding["instrument_id"], {})}


def _by_name(inputs: PortfolioInputs) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in inputs.instruments.values():
        if r["asset_class"] != STRUCTURED:
            out.setdefault(normalise_name(r["instrument_name"]), r)
    return out


def _look_through(inputs: PortfolioInputs, row: dict, names: dict[str, dict]) -> tuple[list[ChannelUse] | None, str]:
    """Channels of a structured product via its underlyings, or (None, why) when they do not all resolve."""
    underlyings, resolved = parse_underlyings(row.get("underlying_reference"), row["instrument_name"])
    if not resolved:
        return None, "underlying names not identifiable from the reference"
    weights: dict[str, float] = {}
    why: dict[str, list[str]] = {}
    for n in underlyings:
        u = names.get(normalise_name(n))
        if u is None:
            return None, f"underlying '{n}' matches no instrument"
        rule = instrument_channels(u)
        if rule.ambiguous:
            return None, f"underlying '{n}' cannot be mapped ({rule.ambiguous})"
        for ch, reason in rule.channels:
            weights[ch] = weights.get(ch, 0.0) + 1 / len(underlyings)
            why.setdefault(ch, []).append(f"{u['instrument_name']}: {reason}")
    return [ChannelUse(ch, w, "look-through " + "; ".join(why[ch])) for ch, w in weights.items()], ""


def _rule(inputs: PortfolioInputs, holding: dict, names: dict[str, dict]) -> tuple[RuleResult, list[ChannelUse] | None, str]:
    """(plain rule result, look-through uses or None, reason a look-through failed)."""
    row = _instrument_row(inputs, holding)
    if row["asset_class"] != STRUCTURED:
        return instrument_channels(row), None, ""
    uses, why = _look_through(inputs, row, names)
    if uses is not None:
        return RuleResult(), uses, ""
    fallback = sector_channels(row)
    if fallback.ambiguous:
        return RuleResult(ambiguous=f"{why}; {fallback.ambiguous}"), None, why
    return fallback, None, why


def ambiguous_holdings(inputs: PortfolioInputs) -> list[Ambiguity]:
    """Holdings the rules cannot place: the only ones an agent may be asked about."""
    names = _by_name(inputs)
    out = []
    for h in inputs.holdings:
        rule, _, _ = _rule(inputs, h, names)
        if rule.ambiguous:
            out.append(Ambiguity(h["instrument_id"], h["instrument_name"], h["asset_class"], h.get("sector"), rule.ambiguous))
    return out


def map_holdings(inputs: PortfolioInputs, agent_channels: dict[str, list[tuple[str, str]]] | None = None) -> list[Mapped]:
    """Each holding's channels. ``agent_channels`` maps an ambiguous instrument to accepted (channel, reason) pairs; an ambiguous
    holding without one is untouched, and so is a holding whose channels are none (cash in USD). FX is added by code."""
    agent_channels = agent_channels or {}
    names = _by_name(inputs)
    out: list[Mapped] = []
    for h in inputs.holdings:
        rule, look, why = _rule(inputs, h, names)
        if rule.ambiguous:
            proposed = agent_channels.get(h["instrument_id"])
            if proposed:
                uses = [ChannelUse(ch, 1.0, f"agent-assigned: {reason}", True) for ch, reason in proposed] + _fx_use(h)
                out.append(Mapped(h, "agent", proposed[0][1], tuple(uses)))
            else:
                out.append(Mapped(h, "untouched", f"not mapped: {rule.ambiguous}"))
            continue
        if look is not None:
            uses = [*look, *_fx_use(h)]
            out.append(Mapped(h, "look_through", "structured product followed through its underlyings", tuple(uses)))
            continue
        uses = [ChannelUse(ch, 1.0, reason) for ch, reason in rule.channels] + _fx_use(h)
        if why and rule.channels:
            out.append(Mapped(h, "rule", f"underlyings did not resolve ({why}): followed the product's own sector", tuple(uses)))
        elif uses:
            out.append(Mapped(h, "rule", "mapped by asset class, region, sector and currency", tuple(uses)))
        else:
            out.append(Mapped(h, "untouched", "no channel reaches this holding"))
    return out
