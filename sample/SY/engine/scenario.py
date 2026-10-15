"""
Module F. Reprice a stated shock, do not forecast one.

The distinction is the entire module. Nothing here predicts anything: a scenario
is a vector of price moves somebody has *asserted*, and the engine answers the
arithmetic question that follows — if those moves happened, what would this
client be worth, what would it do to their loan, and which mandate bands would
cross. No probability is attached, none is implied, and the UI is not allowed to
imply one either.

CL-0019 asked his RM for exactly this and did not get an answer: he holds 24.3%
of his wealth in one shipping company and another sleeve in a shipping fund, and
he wanted to know what happens to him if the Strait of Hormuz reopens. The event
log records the closure on 2026-03-04. The reopening is not a forecast; it is the
question he asked, run backwards through the same channels.

The channels reuse the matcher from engine/performance.py — every discriminating
word of a channel must appear in the instrument's own name, class, sector or
region. A holding no stated channel reaches does not move, and is listed as
untouched rather than silently zeroed.

Two things this deliberately does not do. It does not net a position against a
hedge, because the dataset does not record hedges. And it does not vary the move
by duration, because the dataset carries no duration — every sovereign holding
takes the same move, which for a 2045 Treasury against a 2028 is wrong in a way
the caveat on each scenario says out loud.
"""
import performance as perf

# ── the channels a shock travels down ─────────────────────────────────────
# A channel matches a holding when every one of its words appears in that
# instrument's name, asset class, sub-class, sector or region. Narrow on purpose:
# a channel that matches everything encodes nothing.
CHANNELS = {
    "shipping":    {"shipping"},
    "energy":      {"energy"},
    "gold":        {"gold"},
    "technology":  {"technology"},
    "semis":       {"semiconductor"},
    "sovereign":   {"sovereign"},
    "credit":      {"credit"},
    "high_yield":  {"high", "yield"},
    "reit":        {"reit"},
    "property":    {"property"},
    "commodity":   {"commodity"},
    "equity_dm":   {"developed", "equity"},
    "equity_asia": {"asia", "equity"},
}

# ── the stated shocks ─────────────────────────────────────────────────────
# One visible block, as with WEIGHTS and CALIBRATION. Every move carries the
# reason it is in the vector, and every scenario names the event in
# data/event_log.csv it is drawn from. These are assumptions to argue with, which
# is the only honest form for a scenario to take.
SCENARIOS = [
    {
        "id": "hormuz_reopens",
        "name": "The Strait of Hormuz reopens",
        "asked_by": "CL-0019",
        "premise": "Transit resumes and the risk premium built up since February "
                   "comes back out of freight, crude and the safe havens.",
        "mirrors": "2026-03-04 — Strait of Hormuz effectively closed, Brent past "
                   "USD 120, QatarEnergy force majeure on all exports",
        "caveat": "Freight rates and tanker equities did not move together on the "
                  "way up and will not on the way down. One move is applied to "
                  "both because the dataset has one shipping channel, not two.",
        "moves": [
            {"channel": "shipping", "pct": -32.0,
             "why": "tanker day-rates gave the whole move; they give it back first"},
            {"channel": "energy", "pct": -18.0,
             "why": "the crude premium unwinds"},
            {"channel": "gold", "pct": -9.0,
             "why": "the safe-haven bid unwinds with it"},
            {"channel": "credit", "pct": 1.5,
             "why": "spreads tighten as the geopolitical premium comes out"},
            {"channel": "commodity", "pct": -7.0,
             "why": "broad indices carry the energy weight"},
        ],
    },
    {
        "id": "rates_up_100",
        "name": "Long rates rise another 100bp",
        "asked_by": None,
        "premise": "The move that ran from June continues: another point on the "
                   "long end, and everything priced off it reprices.",
        "mirrors": "2026-06-17 and 2026-06-19 — policy repricing and long-duration "
                   "fixed income",
        "caveat": "The dataset carries no duration, so every sovereign holding "
                  "takes the same move. A 2045 Treasury would fall far more than a "
                  "2028; this understates the long end and overstates the short.",
        "moves": [
            {"channel": "sovereign", "pct": -8.0, "why": "the discount rate moves"},
            {"channel": "credit", "pct": -4.0, "why": "duration plus a little spread"},
            {"channel": "high_yield", "pct": -3.0, "why": "shorter, but spread widens"},
            {"channel": "reit", "pct": -9.0, "why": "rate-sensitive by construction"},
            {"channel": "property", "pct": -6.0, "why": "cap rates follow, with a lag"},
            {"channel": "technology", "pct": -7.0, "why": "long-duration equity"},
        ],
    },
    {
        "id": "rates_down_100",
        "name": "The easing timeline comes back",
        "asked_by": None,
        "premise": "The cuts the market priced in June and then took out arrive after "
                   "all: a point off the long end, and everything priced against it "
                   "reprices the other way.",
        "mirrors": "2026-06-17 and 2026-07-29 — the Fed holds twice and the easing "
                   "timeline is pushed out; this is that decision reversed",
        "caveat": "The mirror image of the rate rise, with the same missing duration "
                  "and the same single move applied to every sovereign. Symmetry is "
                  "assumed and rate moves are not symmetric — a rally usually runs "
                  "smaller than the sell-off that preceded it, so this is the "
                  "optimistic end of an optimistic case.",
        "moves": [
            {"channel": "sovereign", "pct": 7.0, "why": "the discount rate moves back"},
            {"channel": "credit", "pct": 3.5, "why": "duration, and spreads tighten"},
            {"channel": "high_yield", "pct": 3.0, "why": "spread does most of the work"},
            {"channel": "reit", "pct": 8.0, "why": "rate-sensitive by construction"},
            {"channel": "property", "pct": 4.0, "why": "cap rates follow, with a lag"},
            {"channel": "technology", "pct": 6.0, "why": "long-duration equity"},
            {"channel": "equity_dm", "pct": 4.0, "why": "multiples expand on the discount rate"},
        ],
    },
    {
        "id": "tech_drawdown",
        "name": "A 25% drawdown in technology",
        "asked_by": None,
        "premise": "The concentrated-equity risk the June event flagged is realised.",
        "mirrors": "2026-06-05 — US technology, concentrated equity, "
                   "collateralised lending",
        "caveat": "Applied to holdings the technology and semiconductor channels "
                  "reach. A diversified fund with a large technology weight is not "
                  "reached, and is understated here.",
        "moves": [
            {"channel": "technology", "pct": -25.0, "why": "the stated shock"},
            {"channel": "semis", "pct": -30.0, "why": "higher beta to the same move"},
            {"channel": "equity_dm", "pct": -8.0,
             "why": "index weights carry part of it"},
            {"channel": "credit", "pct": -2.0, "why": "risk sentiment"},
        ],
    },
]


def channels_for(book, iid):
    """Every channel that reaches this instrument, and nothing else."""
    words = perf._haystack(book, iid)
    return [name for name, keys in CHANNELS.items() if keys <= words]


def reprice(book, cid, scenario):
    """What this client would be worth if the stated moves happened.

    Channels are applied additively: a shipping company caught by both `shipping`
    and `energy` takes both, and the breakdown says so. Nothing is netted."""
    by_channel = {m["channel"]: m for m in scenario["moves"]}
    positions = book.positions(cid)
    wealth = book.wealth(cid)

    moved, untouched, total_after = [], [], 0.0
    for iid, pos in positions.items():
        hits = [c for c in channels_for(book, iid) if c in by_channel]
        pct = sum(by_channel[c]["pct"] for c in hits)
        after = pos["mv"] * (1 + pct / 100.0)
        total_after += after
        row = {
            "instrument_id": iid, "instrument": book.I[iid]["instrument_name"],
            "asset_class": book.I[iid]["asset_class"],
            "before_usd": round(pos["mv"]), "after_usd": round(after),
            "delta_usd": round(after - pos["mv"]), "move_pct": round(pct, 1),
            "channels": [{"channel": c, "pct": by_channel[c]["pct"],
                          "why": by_channel[c]["why"]} for c in hits],
            "weight_pct": round(100 * pos["mv"] / wealth, 2) if wealth else 0.0,
        }
        (moved if hits else untouched).append(row)
    moved.sort(key=lambda r: r["delta_usd"])

    return {
        "id": scenario["id"], "name": scenario["name"],
        "premise": scenario["premise"], "mirrors": scenario["mirrors"],
        "caveat": scenario["caveat"], "asked_by": scenario["asked_by"],
        "moves": scenario["moves"],
        "before_usd": round(wealth), "after_usd": round(total_after),
        "delta_usd": round(total_after - wealth),
        "delta_pct": round(100 * (total_after - wealth) / wealth, 2) if wealth else 0.0,
        "reached_pct": round(100 * sum(r["before_usd"] for r in moved) / wealth, 1)
                       if wealth else 0.0,
        "positions": moved,
        "untouched_count": len(untouched),
        "collateral": _collateral(book, cid, moved),
        "bands": _bands(book, cid, moved),
    }


def _factor(moved):
    return {r["instrument_id"]: 1 + r["move_pct"] / 100.0 for r in moved}


def _collateral(book, cid, moved):
    """Lending value moves with market value at the same advance rate, so a shock
    to the collateral is a shock to the loan-to-value. This is the part a client
    never sees on a statement and the part that actually bites."""
    f = _factor(moved)
    out = []
    for fac in book.client_facilities(cid):
        pid = fac["collateral_portfolio_id"]
        rows = book.portfolio_rows(pid)
        lv_before = sum(r["_lend_base"] for r in rows)
        lv_after = sum(r["_lend_base"] * f.get(r["instrument_id"], 1.0) for r in rows)
        if lv_before <= 0:
            continue
        # scale the facility's own reported lending value by the same ratio, so
        # the currency and any haircut the facility applies are preserved
        lv = float(fac["lending_value_" + book.today])
        drawn = float(fac["drawn_" + book.today])
        new_lv = lv * (lv_after / lv_before)
        trigger = float(fac["margin_call_ltv_pct"])
        after = (100 * drawn / new_lv) if new_lv > 0 else None
        out.append({
            "facility": fac["facility_id"], "portfolio": pid,
            "currency": fac["facility_ccy"], "trigger_pct": trigger,
            "ltv_before_pct": round(100 * drawn / lv, 1) if lv else None,
            "ltv_after_pct": round(after, 1) if after else None,
            "breaches": bool(after and after >= trigger),
            "shortfall": round(max(0.0, drawn - trigger / 100 * new_lv)) if after else 0,
        })
    return out


def _bands(book, cid, moved):
    """Which mandate bands the shock would push across. A scenario that heals a
    breach is as much worth knowing as one that causes it."""
    f = _factor(moved)
    out = []
    for p in book.managed_portfolios(cid):
        code = p["mandate_code"]
        rows = book.portfolio_rows(p["portfolio_id"])
        before, after = {}, {}
        for r in rows:
            k = r["asset_class"]
            before[k] = before.get(k, 0.0) + r["_mv"]
            after[k] = after.get(k, 0.0) + r["_mv"] * f.get(r["instrument_id"], 1.0)
        tb, ta = sum(before.values()), sum(after.values())
        if not tb or not ta:
            continue
        for asset, (lo, tgt, hi) in book.bands.get(code, {}).items():
            wb = 100 * before.get(asset, 0.0) / tb
            wa = 100 * after.get(asset, 0.0) / ta
            ob = wb > hi + 0.05 or wb < lo - 0.05
            oa = wa > hi + 0.05 or wa < lo - 0.05
            if ob == oa or abs(wa - wb) < 0.05:
                continue
            out.append({
                "portfolio": p["portfolio_id"], "mandate": code, "asset_class": asset,
                "before_pct": round(wb, 1), "after_pct": round(wa, 1),
                "band": [lo, hi], "crosses": "out" if oa else "in",
            })
    return out


def build_for(book, cid):
    """Every stated shock, repriced for one client."""
    return [reprice(book, cid, s) for s in SCENARIOS]
