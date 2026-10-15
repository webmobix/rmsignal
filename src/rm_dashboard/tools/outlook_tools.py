"""Outlook tools: read the persisted house view. They never start an outlook run."""

from rm_dashboard.domain import QualityFlag
from rm_dashboard.outlook.contracts import InstrumentOutlook, MarketOutlook
from rm_dashboard.outlook.digest import market_digest
from rm_dashboard.outlook.store import OutlookStore

from .envelope import build_result
from .spec import AsOfOnly, InstrumentParams, ToolContext, ToolSpec

PRIOR_VIEW = "prior_view"
HOUSE_VIEW = "house_view"
STALE_OUTLOOK = "stale_outlook"
NO_MARKET_OUTLOOK = "no market outlook exists on or before as_of"
NO_INSTRUMENT_OUTLOOK = "no earlier outlook exists for this instrument: this would be the first"
NO_FOLDER_FOR = "no reports folder is configured: the outlook of {id} cannot be read; run rm-dashboard-outlook"
NO_OUTLOOK_FOR = "no outlook exists for {id} on or before as_of; run rm-dashboard-outlook"
NO_FOLDER = "no reports folder is configured: previous outlooks cannot be read"
FIRST = "no earlier market outlook exists: this would be the first outlook"


def view_summary(o: MarketOutlook) -> list[dict]:
    """Views as plain statements. Evidence ids are left out on purpose: a previous view is a reference, not support."""
    return [{"segment": v.segment, "direction": v.direction, "horizon": v.horizon, "confidence": v.confidence,
             "rationale": v.rationale, "drivers": [d.claim for d in v.drivers], "risks": [r.claim for r in v.risks],
             "would_change_if": v.would_change_if} for v in o.views]


def previous_market(ctx: ToolContext, p: AsOfOnly):
    prev = OutlookStore(ctx.reports_dir).previous_market(before=p.as_of) if ctx.reports_dir else None
    if prev is None:
        return build_result(tool="outlook.previous_market", version="1", params=p, as_of=p.as_of, data=None,
                            status="no_data", reason=NO_FOLDER if not ctx.reports_dir else FIRST)
    flag = QualityFlag(code=PRIOR_VIEW, message=f"previous market outlook of {prev.as_of}: a reference view, not evidence for a driver or risk")
    data = {"previous_as_of": prev.as_of.isoformat(), "inputs": prev.inputs.model_dump(mode="json"),
            "carried_forward_from": prev.carried_forward_from.isoformat() if prev.carried_forward_from else None,
            "views": view_summary(prev)}
    return build_result(tool="outlook.previous_market", version="1", params=p, as_of=p.as_of, data=data, extra_flags=[flag])


def instrument_view_summary(o: InstrumentOutlook) -> dict | None:
    v = o.view
    return None if v is None else {"direction": v.direction, "horizon": v.horizon, "confidence": v.confidence, "rationale": v.rationale,
                                   "drivers": [d.claim for d in v.drivers], "risks": [r.claim for r in v.risks],
                                   "would_change_if": v.would_change_if}


def outlook_market(ctx: ToolContext, p: AsOfOnly):
    store = OutlookStore(ctx.reports_dir) if ctx.reports_dir else None
    o = store.latest_market(not_after=p.as_of) if store else None
    if o is None:
        return build_result(tool="outlook.market", version="1", params=p, as_of=p.as_of, data=None, status="no_data",
                            reason=NO_FOLDER if not ctx.reports_dir else NO_MARKET_OUTLOOK)
    flags = [QualityFlag(code=HOUSE_VIEW, message=f"market outlook of {o.as_of}, horizon {o.views[0].horizon if o.views else 'n/a'}: "
                                                   "a forward-looking view of the bank, not a fact")]
    if o.as_of != p.as_of:
        flags.append(QualityFlag(code=STALE_OUTLOOK, message=f"the latest market outlook is dated {o.as_of}, {(p.as_of - o.as_of).days} days before as_of"))
    if ctx.store is not None:  # the evidence behind the outlook's drivers becomes resolvable in this run
        for e in store.load_market_evidence(o.as_of):
            ctx.store.add(e)
    data = {"market_outlook_as_of": o.as_of.isoformat(), "digest": market_digest(o), "inputs": o.inputs.model_dump(mode="json"),
            "carried_forward_from": o.carried_forward_from.isoformat() if o.carried_forward_from else None, "views": view_summary(o)}
    return build_result(tool="outlook.market", version="1", params=p, as_of=p.as_of, data=data, extra_flags=flags)


def outlook_instrument(ctx: ToolContext, p: InstrumentParams):
    store = OutlookStore(ctx.reports_dir) if ctx.reports_dir else None
    o = store.latest_instrument(p.instrument_id, not_after=p.as_of) if store else None
    if o is None:
        return build_result(tool="outlook.instrument", version="1", params=p, as_of=p.as_of, data=None, status="no_data",
                            reason=NO_FOLDER_FOR.format(id=p.instrument_id) if store is None else NO_OUTLOOK_FOR.format(id=p.instrument_id))
    v = o.view
    flags = [QualityFlag(code=HOUSE_VIEW, message=f"outlook of {o.subject} dated {o.as_of}, horizon {v.horizon}, confidence {v.confidence}: "
                                                   "the bank's forward-looking view, not a fact")]
    if o.as_of != p.as_of:
        flags.append(QualityFlag(code=STALE_OUTLOOK, message=f"the latest outlook of {o.subject} is dated {o.as_of}, {(p.as_of - o.as_of).days} days before as_of"))
    if ctx.store is not None:  # the evidence behind the outlook's drivers becomes resolvable in this run
        for e in store.load_instrument_evidence(o.as_of, o.subject):
            ctx.store.add(e)
    reason = lambda r: {"claim": r.claim, "evidence_ids": r.evidence_ids, "event_refs": r.event_refs}
    data = {"instrument_id": o.subject, "instrument_name": o.instrument.instrument_name if o.instrument else None, "outlook_as_of": o.as_of.isoformat(),
            "direction": v.direction, "horizon": v.horizon, "confidence": v.confidence, "rationale": v.rationale,
            "drivers": [reason(r) for r in v.drivers], "risks": [reason(r) for r in v.risks], "would_change_if": v.would_change_if,
            "change": v.change.model_dump(mode="json"), "market_context": [c.model_dump(mode="json") for c in o.market_context],
            "market_outlook_as_of": o.market_outlook_as_of.isoformat() if o.market_outlook_as_of else None,
            "unavailable_statistics": o.unavailable_statistics, "carried_forward_from": o.carried_forward_from.isoformat() if o.carried_forward_from else None}
    return build_result(tool="outlook.instrument", version="1", params=p, as_of=p.as_of, data=data, extra_flags=flags)


def previous_instrument(ctx: ToolContext, p: InstrumentParams):
    prev = OutlookStore(ctx.reports_dir).previous_instrument(p.instrument_id, before=p.as_of) if ctx.reports_dir else None
    if prev is None:
        return build_result(tool="outlook.previous_instrument", version="1", params=p, as_of=p.as_of, data=None, status="no_data",
                            reason=NO_FOLDER if not ctx.reports_dir else NO_INSTRUMENT_OUTLOOK)
    flag = QualityFlag(code=PRIOR_VIEW, message=f"previous outlook of {prev.subject} dated {prev.as_of}: a reference view, not evidence for a driver or risk")
    data = {"previous_as_of": prev.as_of.isoformat(), "inputs": prev.inputs.model_dump(mode="json"),
            "carried_forward_from": prev.carried_forward_from.isoformat() if prev.carried_forward_from else None,
            "view": instrument_view_summary(prev)}
    return build_result(tool="outlook.previous_instrument", version="1", params=p, as_of=p.as_of, data=data, extra_flags=[flag])


OUTLOOK_TOOLS = [
    ToolSpec("outlook.previous_market", "The latest earlier market outlook, as a reference view only (never support for a driver or risk).",
             AsOfOnly, previous_market, "outlook"),
    ToolSpec("outlook.market", "The market outlook for the run's date (the latest one not after it), as the bank's view with its date.",
             AsOfOnly, outlook_market, "outlook"),
    ToolSpec("outlook.instrument", "The outlook of one instrument for the run's date (the latest one not after it), as the bank's view with its date.",
             InstrumentParams, outlook_instrument, "outlook"),
    ToolSpec("outlook.previous_instrument", "The latest earlier outlook of one instrument, as a reference view only (never support for a driver or risk).",
             InstrumentParams, previous_instrument, "outlook"),
]
