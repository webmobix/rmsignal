"""Client-level concentration including look-through to structured-product underlyings."""

import re

import polars as pl

from rm_dashboard.domain import QualityFlag

from .base import Calc, insufficient, register

METHOD_CONCENTRATION = register(
    "concentration",
    "Value is aggregated per exposure entity across all supplied portfolios. Structured "
    "products are looked through to their referenced underlyings; a product referencing a "
    "basket attributes its value equally to each underlying (an assumption, not a "
    "sensitivity). Single names are positions flagged concentration_limit_applies, matched "
    "by normalised issuer name. share_pct = entity value / denominator x 100; HHI = sum of "
    "squared shares in percent (0-10000) over all entities, diversified positions counted "
    "individually. The denominator is stated.",
)

NAME_SUFFIXES = frozenset({"inc", "ltd", "corp", "tbk", "pte", "ag", "ab", "kk", "adr", "plc", "co", "limited", "sa", "nv"})
NUMBER_WORDS = ("two", "three", "four", "five", "six", "several", "multiple")
_UNDERLYING = re.compile(r"(?:worst-of basket|single underlying|underlying)\s*:\s*(.+?)(?:,|$)", re.I)
_NAME_REF = re.compile(r"\bref\.\s*(.+?)(?:,|$)")


def normalise_name(name: str) -> str:
    n = re.sub(r"\s+\d+(?:\.\d+)?%.*$", "", name.strip().lower())  # coupon / perpetual tail
    n = re.sub(r"[^\w\s]", " ", n)
    toks = [t for t in n.split() if t not in NAME_SUFFIXES]
    return " ".join(toks)


def parse_underlyings(reference: str | None, instrument_name: str) -> tuple[list[str], bool]:
    """(underlying names, resolved). Unresolvable references return ([], False)."""
    if reference:
        m = _UNDERLYING.search(reference)
        if m:
            parts = [p.strip() for p in m.group(1).split(" / ") if p.strip()]
            if parts and not (len(parts) == 1 and parts[0].lower().startswith(NUMBER_WORDS)):
                return parts, True
            return [], False
    m = _NAME_REF.search(instrument_name)
    if m and not m.group(1).lower().startswith(("basket", "asia")):
        return [m.group(1).strip()], True
    return [], False


def client_concentration(positions: pl.DataFrame, instruments: pl.DataFrame, *, value_col: str,
                         include_custody: bool, top_n: int = 5) -> Calc:
    """``positions`` needs portfolio_id, instrument_id, service_model and ``value_col``."""
    df = positions if include_custody else positions.filter(pl.col("service_model") != "Custody")
    scope_text = "all portfolios, custody included" if include_custody else "managed portfolios, custody excluded"
    label = f"{'USD market value' if value_col.endswith('usd') else 'market value'} of {scope_text}"
    if df.is_empty():
        return insufficient("concentration", "no positions supplied", METHOD_CONCENTRATION)
    total = float(df[value_col].sum())
    if total <= 0:
        return insufficient("concentration", "denominator is not positive", METHOD_CONCENTRATION)
    inst = {r["instrument_id"]: r for r in instruments.iter_rows(named=True)}
    entities: dict[str, dict] = {}
    flags: list[QualityFlag] = []
    basket = False

    def add(key: str, display: str, single: bool, value: float, pf: str, iid: str, via: str):
        e = entities.setdefault(key, {"name": display, "single_name": single, "value": 0.0, "contributions": []})
        e["single_name"] = e["single_name"] or single
        e["value"] += value
        e["contributions"].append({"portfolio_id": pf, "instrument_id": iid, "value": value, "via": via})

    for r in df.iter_rows(named=True):
        i = inst.get(r["instrument_id"], {})
        v, pf, iid = r[value_col], r["portfolio_id"], r["instrument_id"]
        if r["asset_class"] == "Structured Products":
            names, ok = parse_underlyings(i.get("underlying_reference"), r["instrument_name"])
            if ok:
                if len(names) > 1:
                    basket = True
                for n in names:
                    add(normalise_name(n), n, True, v / len(names), pf, iid, "look_through")
                continue
            flags.append(QualityFlag(
                code="unresolved_underlying", subject=f"{pf}/{iid}",
                message="underlying names not identifiable from the reference; counted as the product itself",
            ))
        single = bool(i.get("concentration_limit_applies"))
        key = normalise_name(r["instrument_name"]) if single else f"{iid}"
        add(key, r["instrument_name"], single, v, pf, iid, "direct")
    if basket:
        flags.append(QualityFlag(
            code="basket_attribution_assumption",
            message="basket products attribute value equally to each underlying; actual sensitivity differs",
        ))
    ranked = sorted(entities.values(), key=lambda e: (-e["value"], e["name"]))
    for e in ranked:
        e["share_pct"] = e["value"] / total * 100
    singles = [e for e in ranked if e["single_name"]]
    return Calc("concentration", {
        "denominator": total, "denominator_label": label, "include_custody": include_custody,
        "top": ranked[:top_n], "single_names": singles,
        "hhi": sum(e["share_pct"] ** 2 for e in ranked),
        "entity_count": len(ranked),
    }, METHOD_CONCENTRATION, flags=flags)
