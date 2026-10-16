"""Portfolio sector exposure: direct, and looked through structured-product underlyings."""

import polars as pl

from rm_dashboard.domain import QualityFlag

from .base import Calc, insufficient, register
from .concentration import normalise_name, parse_underlyings
from .exposure import UNCLASSIFIED, exposures

UNCLASSIFIED_LOOK_THROUGH = "Unclassified (look-through)"

METHOD_SECTOR = register(
    "sector_look_through",
    "Direct: positions are grouped by the sector of their instrument, exposure_pct = group value / "
    "portfolio value x 100 (portfolio base currency). Look-through: each structured product is replaced "
    "by its referenced underlyings, each classified by the sector of the non-structured instrument whose "
    "normalised name it matches; a product referencing a basket attributes its value equally to each "
    "underlying (an assumption, not a sensitivity). An underlying that matches no instrument or has no "
    "sector, and a product whose underlyings cannot be identified, is grouped as 'Unclassified "
    "(look-through)'; a position without a sector is 'unclassified'. Sector labels that are asset types "
    "(Diversified, Corporate, Sovereign, Cash, Gold, Multi, Macro) are shown as their own groups. No "
    "sector data is added. Both views use the same denominator, which is stated.",
)


def _sector(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def sector_look_through(positions: pl.DataFrame, instruments: pl.DataFrame, *, value_col: str = "market_value_base",
                        denominator_label: str = "portfolio value in base currency") -> Calc:
    """``positions`` needs portfolio_id, instrument_id, instrument_name, asset_class, sector and ``value_col``."""
    direct = exposures(positions, dimension="sector", column="sector", value_col=value_col,
                       denominator_label=denominator_label)
    if direct.status != "ok":
        return insufficient("sector_look_through", direct.reason or "no positions supplied", METHOD_SECTOR)
    total = direct.data["denominator"]
    flags: list[QualityFlag] = [f for f in direct.flags]

    sector_by_name: dict[str, str | None] = {}
    inst = {}
    for r in instruments.iter_rows(named=True):
        inst[r["instrument_id"]] = r
        if r["asset_class"] != "Structured Products":
            sector_by_name.setdefault(normalise_name(r["instrument_name"]), _sector(r.get("sector")))

    groups: dict[str, dict] = {}

    def add(name: str, value: float, contributor: str | None) -> None:
        g = groups.setdefault(name, {"name": name, "value": 0.0, "positions": 0, "contributors": []})
        g["value"] += value
        if contributor is None:
            g["positions"] += 1
        elif contributor not in g["contributors"]:
            g["contributors"].append(contributor)

    basket = False
    for r in positions.iter_rows(named=True):
        v = r[value_col]
        pf, iid = r["portfolio_id"], r["instrument_id"]
        if r["asset_class"] == "Structured Products":
            names, ok = parse_underlyings(inst.get(iid, {}).get("underlying_reference"), r["instrument_name"])
            if not ok:
                flags.append(QualityFlag(
                    code="unresolved_underlying", subject=f"{pf}/{iid}",
                    message="underlying names not identifiable from the reference; value is unclassified in the look-through view"))
                add(UNCLASSIFIED_LOOK_THROUGH, v, iid)
                continue
            basket = basket or len(names) > 1
            for n in names:
                sector = sector_by_name.get(normalise_name(n))
                if sector is None:
                    flags.append(QualityFlag(
                        code="unclassified_underlying", subject=f"{pf}/{iid}",
                        message=f"underlying '{n}' of {iid} matches no instrument with a sector; unclassified in the look-through view"))
                    add(UNCLASSIFIED_LOOK_THROUGH, v / len(names), iid)
                else:
                    add(sector, v / len(names), iid)
            continue
        add(_sector(r.get("sector")) or UNCLASSIFIED, v, None)
    if basket:
        flags.append(QualityFlag(
            code="basket_attribution_assumption",
            message="basket products attribute value equally to each underlying; actual sensitivity differs"))

    look = sorted(groups.values(), key=lambda g: (-g["value"], g["name"]))
    for g in look:
        g["exposure_pct"] = g["value"] / total * 100
    return Calc("sector_look_through", {
        "denominator": total, "denominator_label": denominator_label,
        "direct": direct.data["groups"], "look_through": look,
    }, METHOD_SECTOR, flags=flags)
