"""Scripted behaviour of the stub model: which tools to call, then findings that quote tool results.

A plan reads the conversation like a model would: it counts the steps already taken, parses earlier tool
messages, and either asks for more tools (possibly delegating with ``task``) or writes the final JSON.
"""

import json
import re

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from .stub import StubModelError, human_text, tool_results
from .tooladapter import lc_name

ID_PATTERNS = {
    "relationship_analyst": r"CL-\d{4}",
    "portfolio_analyst": r"PF-\d{4}",
    "instrument_analyst": r"SYN-[A-Z]{2}-\d{4}",
}


def _calls(messages: list[BaseMessage], calls: list[tuple[str, dict]]) -> AIMessage:
    n = len(messages)
    return AIMessage(content="", tool_calls=[
        {"name": name if name == "task" else lc_name(name), "args": args, "id": f"call_{n}_{i}", "type": "tool_call"}
        for i, (name, args) in enumerate(calls)])


def _steps_taken(messages: list[BaseMessage]) -> int:
    last_human = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1)
    return sum(1 for m in messages[last_human + 1:] if isinstance(m, AIMessage) and m.tool_calls)


def _by_tool(results: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in results:
        if "tool" in r and "evidence_id" in r:
            out.setdefault(r["tool"], []).append(r)
    return out


def _children(results: list[dict]) -> list[dict]:
    return [r for r in results if "agent" in r and "findings" in r and "evidence_id" not in r]


def _final(findings: list[dict], summary: str, mode: str, anchor: str | None) -> AIMessage:
    if mode == "uncited_number" and anchor:
        findings = [*findings, {"claim": "Equity weight is 7351.24% of the total.", "confidence": "high", "evidence_ids": [anchor]}]
    return AIMessage(content=json.dumps({"summary": summary, "findings": findings}))


def _f(claim: str, ids: list[str], confidence: str = "high") -> dict:
    return {"claim": claim, "confidence": confidence, "evidence_ids": ids}


def plan_for(role: str, mode: str, messages: list[BaseMessage]) -> AIMessage:
    if role == "note_reconciler":
        return _note_reconciler(mode, human_text(messages))
    if role == "mandate_reconciler":
        return _mandate_reconciler(mode, human_text(messages))
    if role == "rm_overview_summary":
        return _overview_summary(mode, human_text(messages))
    if role == "client_actions":
        return _client_actions(mode, human_text(messages))
    if role == "outlook_analyst":
        return _outlook(mode, messages)
    humans = human_text(messages)
    results = tool_results(messages)
    if len(humans) > 1 and results:
        return _follow_up(mode, humans[-1], results)
    subject = _subject(role, humans[0] if humans else "")
    step = _steps_taken(messages)
    by = _by_tool(results)
    plan = {"instrument_analyst": _instrument, "portfolio_analyst": _portfolio, "relationship_analyst": _relationship}[role]
    return plan(subject, step, by, results, messages, mode)


def _subject(role: str, text: str) -> str:
    m = re.search(ID_PATTERNS[role], text)
    return m.group(0) if m else ""


def _first(by, tool):
    return (by.get(tool) or [None])[0]


# ---- instrument -----------------------------------------------------------------------
def _instrument(sid, step, by, results, messages, mode):
    if step == 0:
        return _calls(messages, [("instruments.get", {"instrument_id": sid}), ("instruments.prices", {"instrument_id": sid})])
    g, p = _first(by, "instruments.get"), _first(by, "instruments.prices")
    findings = []
    if g and g["data"]:
        d = g["data"]
        findings.append(_f(f"{d['instrument_name']} is a {d['sub_asset_class']} instrument in the {d['asset_class']} asset class, "
                           f"quoted in {d['currency']} with {d['liquidity_tier']} liquidity.", [g["evidence_id"]]))
    elif g:
        findings.append(_f(f"No reference data was returned for {sid}: {g['reason']}.", [g["evidence_id"]], "high"))
    if p and p["data"]:
        rows = sorted(p["data"], key=lambda r: r["snapshot_date"])
        a, b = rows[0], rows[-1]
        findings.append(_f(f"Price moved from {a['price']:g} to {b['price']:g} between {a['snapshot_date']} and {b['snapshot_date']}.",
                           [p["evidence_id"]]))
    return _final(findings, f"Instrument analysis of {sid}.", mode, (g or p or {}).get("evidence_id"))


# ---- portfolio ------------------------------------------------------------------------
def _portfolio(sid, step, by, results, messages, mode):
    if step == 0:
        return _calls(messages, [
            ("portfolios.get", {"portfolio_id": sid}), ("positions.list", {"portfolio_id": sid}),
            ("analytics.weights", {"portfolio_id": sid}), ("analytics.exposure", {"portfolio_id": sid, "dimension": "asset_class"}),
            ("analytics.mandate_drift", {"portfolio_id": sid}), ("analytics.exclusion_breaches", {"portfolio_id": sid}),
            ("analytics.pnl", {"portfolio_id": sid})])
    w = _first(by, "analytics.weights")
    if step == 1 and w and w["data"]:
        top = sorted(w["data"]["weights"], key=lambda r: (-r["weight_pct"], r["instrument_id"]))[:2]
        return _calls(messages, [("outlook.market", {}), *[("outlook.instrument", {"instrument_id": r["instrument_id"]}) for r in top]])
    findings = []
    m, pnl = _first(by, "analytics.mandate_drift"), _first(by, "analytics.pnl")
    if m:
        d = m["data"] or {}
        if m["status"] != "ok":
            findings.append(_f(f"Mandate comparison was not possible: {m['reason']}.", [m["evidence_id"]]))
        elif d.get("applicable") is False:
            findings.append(_f(f"Portfolio {sid} is a custody account and is not measured against a mandate.", [m["evidence_id"]]))
        elif d.get("breaches"):
            for b in d["breaches"]:
                lim = b["max_pct"] if b["breach"] == "above_max" else b["min_pct"]
                word = "maximum" if b["breach"] == "above_max" else "minimum"
                findings.append(_f(f"{b['asset_class']} weight is {b['weight_pct']:.2f}% against a {word} of {lim:.2f}% "
                                   f"(gap {abs(b['gap_pp']):.2f} percentage points).", [m["evidence_id"]]))
        else:
            findings.append(_f("All asset-class weights are within the mandate bands.", [m["evidence_id"]]))
    x = _first(by, "analytics.exclusion_breaches")
    if x and x["status"] == "ok" and (x["data"] or {}).get("breaches"):
        for b in x["data"]["breaches"]:
            how = f"through {b['via_instrument_name']}" if b["held"] == "look_through" else "directly"
            findings.append(_f(f"Excluded holding {b['instrument_name']} ({b['instrument_id']}) is {b['weight_pct']:.2f}% of the portfolio, "
                               f"held {how}, against the mandate's binding exclusions.", [x["evidence_id"]]))
    if w and w["data"]:
        t = max(w["data"]["weights"], key=lambda r: (r["weight_pct"], r["instrument_id"]))
        findings.append(_f(f"The largest position, {t['instrument_id']}, is {t['weight_pct']:.2f}% of the portfolio.", [w["evidence_id"]]))
    if pnl and pnl["data"] and pnl["data"].get("unrealised_pnl_pct") is not None:
        d = pnl["data"]
        findings.append(_f(f"Unrealised P&L is {d['unrealised_pnl_pct']:.2f}% of cost basis across {d['positions_included']} positions; "
                           f"{d['positions_excluded']} without cost basis are excluded.", [pnl["evidence_id"]]))
    findings += _outlook_findings(by)
    return _final(findings, f"Portfolio analysis of {sid}.", mode, (w or m or {}).get("evidence_id"))


def _outlook_findings(by) -> list[dict]:
    """The bank's views as the client analysts state them: dated, with direction, horizon and confidence; or the fact that none exists."""
    out = []
    for r in by.get("outlook.market", []):
        if r["status"] == "ok":
            overall = next((v for v in r["data"]["views"] if v["segment"] == "overall"), None)
            if overall:
                out.append(_f(f"The bank's market view as of {r['data']['market_outlook_as_of']} is {overall['direction']} "
                              f"({overall['confidence']} confidence, {overall['horizon']} horizon).", [r["evidence_id"]], "medium"))
        else:
            out.append(_f(f"No market outlook is available: {r['reason']}.", [r["evidence_id"]], "high"))
    for r in by.get("outlook.instrument", []):
        if r["status"] == "ok":
            d = r["data"]
            out.append(_f(f"The bank's view of {d['instrument_id']} as of {d['outlook_as_of']} is {d['direction']} "
                          f"({d['confidence']} confidence, {d['horizon']} horizon).", [r["evidence_id"]], "medium"))
        else:
            out.append(_f(f"No outlook is available: {r['reason']}.", [r["evidence_id"]], "high"))
    return out


# ---- relationship ---------------------------------------------------------------------
def _relationship(cid, step, by, results, messages, mode):
    if step == 0:
        return _calls(messages, [
            ("clients.get", {"client_id": cid}), ("parties.get", {"client_id": cid}), ("relationships.list", {"client_id": cid}),
            ("persons.list", {"client_id": cid}), ("portfolios.list", {"client_id": cid}), ("credit.facilities", {"client_id": cid}),
            ("analytics.concentration", {"client_id": cid}), ("analytics.liquidity", {"client_id": cid}), ("notes.list", {"client_id": cid}),
            ("peers.kyc_status", {"client_id": cid}), ("outlook.market", {})])
    if step == 1:
        calls = []
        facs = _first(by, "credit.facilities")
        for f in ((facs or {}).get("data") or {}).get("facilities", []):
            calls.append(("analytics.credit_ltv", {"facility_id": f["facility_id"]}))
        pfs = _first(by, "portfolios.list")
        tasks = [{"name": "task", "args": {"subagent_type": "portfolio_analyst", "description": f"Analyse portfolio {p['portfolio_id']}."},
                  "id": f"call_{len(messages)}_t{i}", "type": "tool_call"} for i, p in enumerate(((pfs or {}).get("data")) or [])]
        base = _calls(messages, calls).tool_calls if calls else []
        return AIMessage(content="", tool_calls=[*base, *tasks])
    findings = []
    c, rel, per = _first(by, "clients.get"), _first(by, "relationships.list"), _first(by, "persons.list")
    conc, liq = _first(by, "analytics.concentration"), _first(by, "analytics.liquidity")
    if c and c["data"] and c["data"]["client"]:
        cl = c["data"]["client"]
        if cl["kyc_overdue"]:
            findings.append(_f(f"The KYC review is overdue by {abs(cl['days_to_kyc_due'])} days.", [c["evidence_id"]]))
        else:
            findings.append(_f(f"The KYC review is due in {cl['days_to_kyc_due']} days.", [c["evidence_id"]]))
    peer = _first(by, "peers.kyc_status")
    if peer and peer["status"] == "ok":
        findings.append(_f(f"The KYC peer agent ({peer['data']['peer']}, mock) reports: {peer['data']['kyc_status']}.", [peer["evidence_id"]], "low"))
    if rel:
        findings.append(_f("Related-party data was unavailable, so no related parties are listed and none are inferred.",
                           [rel["evidence_id"], *( [per["evidence_id"]] if per else [])], "high"))
    if conc and conc["data"] and conc["data"].get("single_names"):
        s = conc["data"]["single_names"][0]
        findings.append(_f(f"The largest single-name exposure is {s['name']} at {s['share_pct']:.2f}% of {conc['data']['denominator_label']}.",
                           [conc["evidence_id"]]))
    if liq and liq["data"] and liq["status"] == "ok":
        d = liq["data"]
        if d["shortfall_usd"] > 0:
            findings.append(_f(f"Daily-liquid assets fall short of needs within {d['horizon_days']} days by {d['shortfall_usd']:,.0f} USD.", [liq["evidence_id"]]))
        elif d["needs_total_usd"]:
            findings.append(_f(f"Daily-liquid assets cover needs within {d['horizon_days']} days {d['coverage_ratio']:.2f} times.", [liq["evidence_id"]]))
    for r in by.get("analytics.credit_ltv", []):
        d = r["data"]
        if d:
            state = "above" if d["breached"] else "below"
            findings.append(_f(f"Facility {d['facility_id']} LTV is {d['ltv_pct']:.2f}%, {state} its {d['trigger_pct']:.2f}% trigger.", [r["evidence_id"]]))
    for ch in _children(results):
        for cf in ch["findings"][:1]:
            findings.append(_f(f"Portfolio analysis of {ch['subject']}: {cf['claim']}", cf["evidence_ids"], "medium"))
    findings += _outlook_findings({"outlook.market": by.get("outlook.market", [])})
    return _final(findings, f"Relationship analysis of {cid}.", mode, (conc or c or {}).get("evidence_id"))


# ---- follow-up -------------------------------------------------------------------------
def _follow_up(mode, question, results):
    q = question.lower()
    by = _by_tool(results)
    findings = []
    if "concentration" in q and "analytics.concentration" in by:
        r = by["analytics.concentration"][0]
        s = (r["data"].get("single_names") or [None])[0]
        if s:
            findings.append(_f(f"Earlier analysis: the largest single-name exposure is {s['name']} at {s['share_pct']:.2f}%.", [r["evidence_id"]]))
    elif "liquidity" in q and "analytics.liquidity" in by:
        r = by["analytics.liquidity"][0]
        findings.append(_f(f"Earlier analysis: the liquidity shortfall is {r['data']['shortfall_usd']:,.0f} USD.", [r["evidence_id"]]))
    if not findings:
        r = next(x for x in results if "evidence_id" in x)
        findings.append(_f(f"Earlier analysis ({r['tool']}) returned status {r['status']}.", [r["evidence_id"]], "medium"))
    return _final(findings, "Follow-up answered from earlier evidence.", mode, findings[0]["evidence_ids"][0])


# ---- note reconciliation ---------------------------------------------------------------
INPUT_MARKER = "INPUT:"


def _note_reconciler(mode: str, humans: list[str]) -> AIMessage:
    """A note is `consistent` when a finding quotes it by id, otherwise `unverifiable`."""
    if mode == "unparsable":
        return AIMessage(content="I could not produce a structured answer.")
    text = humans[-1] if humans else ""
    payload = json.loads(text[text.index(INPUT_MARKER) + len(INPUT_MARKER):])
    findings = payload["findings"]
    results = []
    for n in payload["notes"]:
        refs = [f["ref"] for f in findings if n["note_id"] in f["claim"]]
        if refs:
            results.append({"note_id": n["note_id"], "verdict": "consistent",
                            "rationale": f"The report quotes note {n['note_id']}.", "finding_refs": refs[:2]})
        else:
            results.append({"note_id": n["note_id"], "verdict": "unverifiable",
                            "rationale": "No finding addresses this note.", "finding_refs": []})
    if results and mode == "uncited_number":
        results[0] = {**results[0], "verdict": "contradicted", "rationale": "Exposure is 7351.24% of the total."}
    if results and mode == "bad_ref":
        results[0] = {**results[0], "verdict": "consistent", "rationale": "Supported.", "finding_refs": ["CL-9999#f99"]}
    return AIMessage(content=json.dumps({"results": results}))


# ---- mandate reconciliation ------------------------------------------------------------------
_MANDATE_CUES = (  # (status, cues in the note); first status with a cue wins, in order of precedence
    ("contradicted", ("fully aligned", "within the limits", "within limits")),
    ("client_directed", ("waiver", "instructed", "unwilling", "will not", "not sell")),
    ("acknowledged", ("acknowledged", "aware of", "knows")),
)


def _mandate_reconciler(mode: str, humans: list[str]) -> AIMessage:
    """Reads a note as bearing on a breach when it mentions one of the breach's names, then classifies it by cue words."""
    if mode == "unparsable":
        return AIMessage(content="I could not produce a structured answer.")
    text = humans[-1] if humans else ""
    payload = json.loads(text[text.index(INPUT_MARKER) + len(INPUT_MARKER):])
    results = []
    for b in payload["breaches"]:
        best, cited = "no_note", []
        for n in payload["notes"]:
            low = n["quote"].lower()
            if not any(t in low for t in b["names"]):
                continue
            for status, cues in _MANDATE_CUES:
                if any(c in low for c in cues):
                    cited.append(n["note_id"])
                    if _PRECEDENCE.index(status) < _PRECEDENCE.index(best):
                        best = status
                    break
        if best != "no_note":
            results.append({"portfolio_id": b["portfolio_id"], "kind": b["kind"], "key": b["key"], "evidence_id": b["evidence_id"],
                            "status": best, "note_ids": cited,
                            "rationale": f"The cited note bears on this breach ({best.replace('_', ' ')})."})
    return AIMessage(content=json.dumps({"results": results, "ambiguous_notes": []}))


_PRECEDENCE = ("contradicted", "client_directed", "acknowledged", "no_note")


# ---- client actions --------------------------------------------------------------------------
_ACTION_RULES = (  # (claim pattern, category, importance, title, what, why)
    (r"KYC review is (due|overdue)", "compliance_kyc", "medium", "Prepare the KYC review",
     "Schedule and prepare the periodic KYC review with the client.", "The report shows the KYC review date."),
    (r"largest single-name exposure", "concentration_risk", "high", "Discuss the single-name concentration",
     "Review the largest single-name exposure with the client and agree on a diversification path.",
     "The report shows a concentrated single-name exposure."),
    (r"(above|below) (a|its) (maximum|minimum|trigger)|weight is .* against a", "mandate_drift", "high", "Address the mandate breach",
     "Bring the portfolio back within its mandate bands.", "The report shows a mandate band breach."),
    (r"Excluded holding .* binding exclusions", "mandate_drift", "high", "Resolve the excluded holding",
     "Review the excluded holding with the client and bring the portfolio back within its binding exclusions.",
     "The report shows a holding the mandate excludes."),
    (r"LTV is", "credit_collateral", "medium", "Review the credit facility",
     "Review the Lombard facility headroom with the client.", "The report shows the facility LTV against its trigger."),
    (r"(fall|falls) short", "liquidity_cash_needs", "high", "Plan the liquidity shortfall",
     "Arrange funding for the planned cash needs.", "The report shows daily-liquid assets short of planned needs."),
)


_MANDATE_WORDING = {  # status -> (title, what, proposed importance)
    "acknowledged": ("Follow up the plan for the acknowledged breach", "Follow up the plan agreed with the client for the breach.", "low"),
    "client_directed": ("Review the client's instruction on the breach", "Review the client's instruction that sits outside the mandate.", "low"),
    "contradicted": ("Correct the record with the client", "Correct the record with the client: the notes and the computed breach disagree.", "low"),
}


def _client_actions(mode: str, humans: list[str]) -> AIMessage:
    """One action per matching finding (first match per rule) and one per contradicted note."""
    if mode == "unparsable":
        return AIMessage(content="No structured answer.")
    text = humans[-1] if humans else ""
    payload = json.loads(text[text.index(INPUT_MARKER) + len(INPUT_MARKER):])
    actions = []
    mandate = [m for m in payload.get("mandate", [])]
    covered = {m["breach"] for m in mandate if m["status"] != "no_note"}
    for pattern, cat, imp, title, what, why in _ACTION_RULES:
        hit = next((f for f in payload["findings"] if re.search(pattern, f["claim"]) and f["claim"] not in covered), None)
        if hit:
            actions.append({"category": cat, "importance": imp, "title": title, "what": what, "why": why, "refs": [hit["ref"]]})
    for m in mandate:
        if m["status"] != "no_note":
            title, what, imp = _MANDATE_WORDING[m["status"]]
            if m["status"] == "client_directed" and m["waiver_claimed"]:
                what += " Verify that the claimed waiver is on file."
            actions.append({"category": "mandate_drift", "importance": imp, "title": title, "what": what,
                            "why": f"The mandate reconciliation shows this breach as {m['status'].replace('_', ' ')}.", "refs": [m["ref"]]})
    for n in payload["notes"]:
        if n["verdict"] == "contradicted":
            actions.append({"category": "client_contact", "importance": "low", "title": f"Follow up on note {n['note_id']}",
                            "what": "Discuss the difference between the client's stated intent and the book.",
                            "why": "The reconciliation found the note contradicted by the report.", "refs": [n["note_id"]]})
    if actions and mode == "uncited_number":
        actions[0] = {**actions[0], "why": "Equity weight is 7351.24% of the total."}
    if actions and mode == "bad_ref":
        actions[0] = {**actions[0], "refs": ["CL-9999#f99"]}
    if actions and mode == "bad_category":
        actions[0] = {**actions[0], "category": "marketing"}
    return AIMessage(content=json.dumps({"actions": actions}))


# ---- RM overview summary ---------------------------------------------------------------------
def _overview_summary(mode: str, humans: list[str]) -> AIMessage:
    """Names the first action and groups actions of the same category into themes."""
    if mode == "unparsable":
        return AIMessage(content="No structured answer.")
    text = humans[-1] if humans else ""
    payload = json.loads(text[text.index(INPUT_MARKER) + len(INPUT_MARKER):])
    actions = payload["actions"]
    summary = f"First attention: {actions[0]['title']}." if actions else ""
    by: dict[str, list[str]] = {}
    for a in actions:
        by.setdefault(a["category"], []).append(a["action_id"])
    themes = [{"title": f"{cat.replace('_', ' ').capitalize()} across clients", "action_ids": ids}
              for cat, ids in by.items() if len(ids) >= 2]
    out: dict = {"summary": summary, "themes": themes}
    if mode == "uncited_number":
        out["summary"] = "Equity weight is 7351.24% of the total."
    if mode == "bad_ids":
        out["themes"] = [*themes, {"title": "Phantom theme", "action_ids": ["CL-9999-A1", "CL-9999-A2"]}]
    if mode == "reorder":
        out["order"] = [a["action_id"] for a in reversed(actions)]
        out["actions"] = list(reversed(actions))
    return AIMessage(content=json.dumps(out))


# ---- market outlook ---------------------------------------------------------------------------
_SEGMENT_OF = {"Equity index": "equity", "Rates": "rates", "FX": "fx", "Commodity": "commodities", "Volatility": "volatility"}
_UP_IS = {"equity": "positive", "commodities": "positive", "rates": "negative", "volatility": "negative", "fx": "neutral"}
_FLIP = {"positive": "negative", "negative": "positive", "neutral": "neutral"}
_EVENT_WORDS = {"overall": (), "commodities": ("energy", "oil", "gold", "brent"), "rates": ("duration", "yield", "fixed income", "treasury")}


def _outlook(mode: str, messages: list[BaseMessage]) -> AIMessage:
    if mode == "unparsable":
        return AIMessage(content="No structured answer.")
    humans = human_text(messages)
    sid = re.search(r"SYN-[A-Z]{2}-\d{4}", humans[0] if humans else "")
    if sid:
        return _outlook_instrument(mode, messages, sid.group(0))
    step = _steps_taken(messages)
    if step == 0:
        return _calls(messages, [("analytics.market_trend", {}), ("news.list", {}), ("outlook.previous_market", {})])
    by = _by_tool(tool_results(messages))
    trend, news = _first(by, "analytics.market_trend"), _first(by, "news.list")
    m = re.search(r"Segments: ([a-z, ]+)\.", humans[0] if humans else "")
    segments = [x.strip() for x in m.group(1).split(",")] if m else ["overall"]
    series = {}
    for r in ((trend or {}).get("data") or {}).get("series", []):
        series.setdefault(_SEGMENT_OF.get(r["category"], ""), []).append(r)
    severe = [e for e in ((news or {}).get("data") or {}).get("news", []) if e["severity"] in ("High", "Severe")]
    views = []
    for seg in segments:
        rows = sorted(series.get(seg, []), key=lambda r: r["series_id"])
        moves = [r["vs_previous"]["change_pct"] for r in rows if "vs_previous" in r and r["vs_previous"]["change_pct"] is not None]
        if seg == "overall":
            direction = "neutral"
        elif not moves or sum(moves) == 0:
            direction = "neutral"
        else:
            up = sum(moves) > 0
            direction = _UP_IS[seg] if up else _FLIP[_UP_IS[seg]]
        if mode == "flip":
            direction = _FLIP[direction]
        drivers = []
        if rows and trend:
            r = rows[0]
            claim = f"{r['series_name']} stands at {r['latest']:g} {r['unit']}." if "previous" not in r else \
                f"{r['series_name']} stands at {r['latest']:g} {r['unit']} after {r['previous']:g} at the previous snapshot."
            drivers.append({"claim": claim, "evidence_ids": [trend["evidence_id"]], "event_refs": []})
        words = _EVENT_WORDS.get(seg)
        if words is not None and news:
            hits = [e for e in severe if not words or any(w in (e["primary_transmission"] + " " + e["description"]).lower() for w in words)]
            for e in hits[-2:]:
                drivers.append({"claim": e["description"], "evidence_ids": [], "event_refs": [e["event_id"]]})
        if mode == "uncited_number" and seg == "equity" and trend:
            drivers.append({"claim": "Equities will reach 98765 points.", "evidence_ids": [trend["evidence_id"]], "event_refs": []})
        if not drivers and news:
            drivers.append({"claim": "No market series moved enough to name a driver.", "evidence_ids": [news["evidence_id"]], "event_refs": []})
        change = {"why": "Market data moved since the previous outlook.", "evidence_ids": [trend["evidence_id"]] if trend else [], "event_refs": []}
        views.append({"segment": seg, "direction": direction, "horizon": "3m", "confidence": "medium",
                      "rationale": f"The {seg} view follows the latest market snapshot and the events that bear on it.",
                      "drivers": drivers, "risks": [], "would_change_if": "A new market snapshot or event points the other way.",
                      "change": change})
    return AIMessage(content=json.dumps({"summary": "House view of the market.", "views": views}))


def _n(x: float) -> str:
    """A figure as written in prose: no exponent, so the guard can read it back."""
    return f"{x:.10g}"


def _outlook_instrument(mode: str, messages: list[BaseMessage], iid: str) -> AIMessage:
    if _steps_taken(messages) == 0:
        return _calls(messages, [("instruments.context", {"instrument_id": iid}), ("events.relevant", {"instrument_id": iid}),
                                 ("outlook.market", {}), ("outlook.previous_instrument", {"instrument_id": iid})])
    by = _by_tool(tool_results(messages))
    ctx, ev, mk = _first(by, "instruments.context"), _first(by, "events.relevant"), _first(by, "outlook.market")
    data = (ctx or {}).get("data") or {}
    summary = data.get("summary") or {}
    move = summary.get("vs_previous_pct")
    direction = "neutral" if not move else ("positive" if move > 0 else "negative")
    if mode == "flip":
        direction = _FLIP[direction]
    drivers = []
    if ctx and "previous" in summary:
        drivers.append({"claim": f"The price moved from {_n(summary['previous'])} to {_n(summary['latest'])} between the last two snapshots.",
                        "evidence_ids": [ctx["evidence_id"]], "event_refs": []})
        peers = data.get("peers") or {}
        if peers.get("members") and peers.get("group_avg_vs_previous_pct") is not None:
            drivers.append({"claim": f"Peers moved {_n(peers['group_avg_vs_previous_pct'])}% against {_n(move)}% for the instrument.",
                            "evidence_ids": [ctx["evidence_id"]], "event_refs": []})
    severe = [e for e in ((ev or {}).get("data") or {}).get("events", []) if e["severity"] in ("High", "Severe")]
    for e in severe[-2:]:
        drivers.append({"claim": e["description"], "evidence_ids": [], "event_refs": [e["event_id"]]})
    views = {v["segment"]: v for v in (((mk or {}).get("data") or {}).get("views") or [])}
    if mk and "overall" in views:
        drivers.append({"claim": f"The overall market view is {views['overall']['direction']}.", "evidence_ids": [mk["evidence_id"]], "event_refs": []})
    if mode == "uncited_number" and ctx:
        drivers.append({"claim": "The price will reach 98765.", "evidence_ids": [ctx["evidence_id"]], "event_refs": []})
    if not drivers and ctx:
        drivers.append({"claim": "Too little history to name a driver.", "evidence_ids": [ctx["evidence_id"]], "event_refs": []})
    view = {"direction": direction, "horizon": "3m", "confidence": "medium",
            "rationale": "The view follows the latest price move, its peers, the events that bear on it and the market outlook.",
            "drivers": drivers, "risks": [], "would_change_if": "A new price, event or market outlook points the other way.",
            "change": {"why": "The price moved since the previous outlook.", "evidence_ids": [ctx["evidence_id"]] if ctx else [], "event_refs": []}}
    return AIMessage(content=json.dumps({"summary": "House view of the instrument.", "view": view}))
