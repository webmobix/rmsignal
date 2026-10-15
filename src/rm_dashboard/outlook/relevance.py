"""Which events may bear on an instrument. Lexical and deliberately plain: it proposes candidates and says why,
the model decides which are relevant and must cite them."""

import re
from typing import Any

MATCHING = ("lexical: an event is a candidate when its region is a non-global region of the instrument, or when a word of its "
            "transmission also appears in the instrument's sector, asset class, sub-asset class, name or underlying reference. "
            "Candidates only; relevance is the analyst's judgement.")

FIELDS = ("sector", "asset_class", "sub_asset_class", "instrument_name", "underlying_reference")
STOPWORDS = frozenset(
    "and the for with from into fund funds global income assets asset exposure market markets index group holdings ltd inc corp "
    "limited note notes linked based rate sensitive long short term private ref due perpetual call usd eur sgd hkd chf jpy gbp".split())
REGION_ALIASES = {"United States": {"North America", "United States"}, "North America": {"North America", "United States"}}


def tokens(text: str | None) -> set[str]:
    """Lower-case words of at least 3 letters without stop words (currency codes included); a plural s is dropped."""
    out = set()
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        if len(w) < 3 or w in STOPWORDS:
            continue
        out.add(w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "us", "ous")) else w)
    return out


def region_matches(event_region: str | None, instrument_region: str | None) -> bool:
    if not event_region or event_region == "Global" or not instrument_region:
        return False
    return instrument_region in REGION_ALIASES.get(event_region, {event_region})


def relevant_events(instrument: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Events (with their ids) that are candidates for ``instrument``, each with ``matched_on``."""
    own = {f: tokens(instrument.get(f)) for f in FIELDS}
    out = []
    for e in events:
        matched = []
        if region_matches(e.get("region"), instrument.get("region")):
            matched.append({"field": "region", "token": e["region"]})
        for tok in sorted(tokens(e.get("primary_transmission"))):
            matched += [{"field": f, "token": tok} for f in FIELDS if tok in own[f]]
        if matched:
            out.append({**e, "matched_on": matched})
    return out
